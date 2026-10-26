#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""服务器项目状态采集器 -> /var/www/dashboard/status.json"""
import json, os, re, subprocess, time, urllib.request

OUT = '/var/www/dashboard/status.json'

# 项目注册表
PROJECTS = [
    {'name': '学习计划系统 · 前端', 'kind': 'nginx', 'port': 80,  'desc': '学习计划管理 Web 界面'},
    {'name': '学习计划系统 · API',  'kind': 'pm2',   'port': 3001, 'pm2': 'learning-plan-server', 'desc': '后端 Node.js API 服务'},
    {'name': 'StockShape 形态选股', 'kind': 'pm2',   'port': 3000, 'pm2': 'stockshape',  'desc': '股票形态选股工具'},
    {'name': 'Resume Coach',        'kind': 'pm2',   'port': 3200, 'pm2': 'resume-coach', 'desc': '简历教练应用'},
    {'name': 'K线之王',             'kind': 'pm2',   'port': 3100, 'pm2': 'kline-master', 'desc': 'K线行情工具'},
    {'name': '文本乱码清理 Agent',  'kind': 'pm2',   'port': 4000, 'probe_port': 4001, 'pm2': 'od-toolkit', 'desc': '文本乱码清理工具'},
    {'name': '二维码内容管理',      'kind': 'pm2',   'port': 8443, 'pm2': 'qrtool', 'desc': '创建二维码 · QR Content Manager'},
    {'name': '闭眼笔记工厂',        'kind': 'docker','port': 8300, 'container': 'notefactory', 'desc': '笔记生成工具（生产）'},
    {'name': '闭眼笔记工厂 · 测试', 'kind': 'docker','port': 8301, 'container': 'notefactory-test', 'desc': '笔记工厂测试环境'},
    {'name': '俄罗斯方块小游戏',    'kind': 'pm2',   'port': 8100, 'pm2': 'tetris-web', 'desc': '俄罗斯方块 · 小游戏时间'},
    {'name': '幸运熊猫 · 注意力训练','kind': 'pm2',   'port': 8200, 'pm2': 'lucky-panda', 'desc': '幸运熊猫 ADHD 训练版'},
    {'name': '研究站',              'kind': 'nginx', 'port': 3002, 'desc': 'Research 静态站点'},
    {'name': '本看板',              'kind': 'nginx', 'port': 5000, 'desc': '服务器运行监控看板'},
]


def sh(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=25)
        return r.stdout.strip()
    except Exception:
        return ''


def http_probe(port):
    try:
        req = urllib.request.Request('http://127.0.0.1:%d/' % port, headers={'User-Agent': 'monitor'})
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=4) as r:
            r.read(1024)
            return r.status, int((time.time() - t0) * 1000)
    except urllib.error.HTTPError as e:
        return e.code, -1
    except Exception:
        return 0, -1


def human_uptime(ms):
    if not ms:
        return '-'
    s = int((time.time() * 1000 - ms) / 1000)
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, _ = divmod(s, 60)
    if d >= 30:
        return '%d 个月' % (d // 30)
    if d:
        return '%d 天 %d 小时' % (d, h)
    if h:
        return '%d 小时 %d 分' % (h, m)
    return '%d 分钟' % m


def mem_str(mb):
    return '%.0f MB' % mb if mb else '-'


# ---------- 系统资源 ----------
def collect_system():
    up = sh('cat /proc/uptime').split()
    up_s = float(up[0]) if up else 0
    load = sh('cat /proc/loadavg').split()[:3]
    mi = {}
    for line in sh('free -m').splitlines()[1:]:
        p = line.split()
        mi[p[0].rstrip(':')] = {'total': int(p[1]), 'used': int(p[2]), 'free': int(p[3])}
    dk = sh("df -m / | tail -1").split()
    return {
        'host': sh('hostname'),
        'os': sh('. /etc/os-release && echo "$PRETTY_NAME"'),
        'uptime_days': int(up_s // 86400),
        'uptime_text': '%d 天 %d 小时' % (up_s // 86400, (up_s % 86400) // 3600),
        'load': [float(x) for x in load] if load else [0, 0, 0],
        'cpu_idle': sh("top -bn1 | grep '%Cpu' | sed 's/.*, *\\([0-9.]*\\) id.*/\\1/'") or '0',
        'mem': mi.get('Mem', {}),
        'swap': mi.get('Swap', {}),
        'disk': {'total_mb': int(dk[1]), 'used_mb': int(dk[2]), 'free_mb': int(dk[3]),
                 'pct': int(dk[4].rstrip('%'))} if len(dk) >= 5 else {},
    }


# ---------- PM2 ----------
def collect_pm2():
    out = {}
    raw = sh('pm2 jlist')
    if not raw:
        return out
    try:
        for app in json.loads(raw):
            e = app.get('pm2_env', {})
            out[app.get('name')] = {
                'pid': app.get('pid'),
                'status': e.get('status', 'unknown'),
                'uptime': human_uptime(e.get('pm_uptime')),
                'uptime_ms': e.get('pm_uptime'),
                'restarts': e.get('restart_time', 0),
                'mem_mb': round((app.get('monit', {}).get('memory', 0) or 0) / 1048576, 1),
                'cpu': app.get('monit', {}).get('cpu', 0),
            }
    except Exception:
        pass
    return out


# ---------- Docker ----------
def collect_docker():
    out = {}
    fmt = '{{.Names}}\\t{{.Image}}\\t{{.Status}}\\t{{.Ports}}'
    for line in sh('sudo -n docker ps -a --format "%s"' % fmt).splitlines():
        p = line.split('\t')
        if len(p) < 3:
            continue
        st = p[2]
        out[p[0]] = {
            'image': p[1],
            'status': st,
            'running': st.lower().startswith('up'),
            'ports': p[3] if len(p) > 3 else '',
            'mem_mb': 0, 'cpu': '0%',
        }
    for line in sh('sudo -n docker stats --no-stream --format "{{.Name}}\\t{{.MemUsage}}\\t{{.CPUPerc}}"').splitlines():
        p = line.split('\t')
        if len(p) < 3 or p[0] not in out:
            continue
        m = re.match(r'([\d.]+)(MiB|GiB|KiB)', p[1])
        if m:
            v = float(m.group(1))
            out[p[0]]['mem_mb'] = round(v * 1024 if m.group(2) == 'GiB' else (v / 1024 if m.group(2) == 'KiB' else v), 1)
        out[p[0]]['cpu'] = p[2]
    return out


def service_state(svc):
    """返回 systemd 服务状态，并识别崩溃重启循环"""
    if not svc:
        return None, 'none'
    st = sh('systemctl is-active %s' % svc) or 'unknown'
    if st == 'active':
        en = sh('systemctl is-enabled %s' % svc)
        return 'systemd ✓ %s' % ('开机自启' if en == 'enabled' else ''), 'ok'
    if st == 'activating':
        return 'systemd ⚠ 崩溃重启中', 'loop'
    return 'systemd ⚠ %s' % st, 'bad'


# ---------- 裸进程：按监听端口反查 ----------
def proc_by_port(port):
    line = sh("sudo -n ss -tlnp 2>/dev/null | grep -E ':%d\\b'" % port)
    m = re.search(r'pid=(\d+)', line)
    if not m:
        return None
    pid = m.group(1)
    ps = sh("ps -o etimes=,rss=,args= -p %s" % pid).split(None, 2)
    if len(ps) < 2:
        return None
    return {'pid': int(pid),
            'uptime': human_uptime(time.time() * 1000 - int(ps[0]) * 1000),
            'mem_mb': round(int(ps[1]) / 1024, 1),
            'cwd': sh('readlink /proc/%s/cwd' % pid),
            'cmd': ps[2][:60] if len(ps) > 2 else ''}


STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.restart_state.json')


def load_state():
    try:
        return json.load(open(STATE_FILE, encoding='utf-8'))
    except Exception:
        return {}


def save_state(s):
    try:
        json.dump(s, open(STATE_FILE, 'w', encoding='utf-8'))
    except Exception:
        pass


def main():
    data = {'ts': int(time.time()), 'time': time.strftime('%Y-%m-%d %H:%M:%S'),
            'system': collect_system(), 'projects': [], 'containers': []}
    state = load_state()
    pm2 = collect_pm2()
    dk = collect_docker()

    for p in PROJECTS:
        probe_port = p.get('probe_port', p['port'])
        code, rt = http_probe(probe_port)
        item = dict(p)
        item['http'] = code
        item['rt_ms'] = rt
        item['status'] = 'up' if code == 200 else 'down'
        item['mem'] = '-'
        item['uptime'] = '-'
        item['restarts'] = None
        item['extra'] = ''
        if p['kind'] == 'pm2':
            a = pm2.get(p['pm2'])
            if a:
                item['status'] = 'up' if a['status'] == 'online' and code == 200 else 'down'
                item['mem'] = mem_str(a['mem_mb'])
                item['uptime'] = a['uptime']
                item['restarts'] = a['restarts']
                item['pid'] = a['pid']
                # 与上次采集比对增量：只有真正「新增重启」才告警，历史累计不算问题
                key = 'pm2:' + p['pm2']
                prev = state.get(key)
                r = a['restarts']
                if prev is not None and r > prev:
                    item['restart_note'] = ('⚠️ 检测到新增 %d 次重启（累计 %d 次），当前实例仅运行 %s，建议查看 PM2 错误日志'
                                            % (r - prev, r, a['uptime']))
                    item['restart_level'] = 'warn'
                elif prev is not None:
                    item['restart_note'] = ('历史累计 %d 次重启，上次采集以来无新增（当前实例已运行 %s）'
                                            % (r, a['uptime']))
                    item['restart_level'] = 'info' if r > 50 else None
                state[key] = r
            else:
                item['status'] = 'down'
                item['extra'] = 'PM2 中未找到该进程'
        elif p['kind'] == 'docker':
            c = dk.get(p['container'])
            if c:
                item['status'] = 'up' if c['running'] and code == 200 else 'down'
                item['mem'] = mem_str(c['mem_mb'])
                item['uptime'] = c['status']
                item['cpu'] = c['cpu']
            else:
                item['status'] = 'down'
        elif p['kind'] == 'proc':
            pr = proc_by_port(p['port'])
            svc_txt, svc_state = service_state(p.get('service'))
            item['supervisor'] = svc_txt or '无守护进程 ⚠'
            item['svc_state'] = svc_state
            if pr:
                item['mem'] = mem_str(pr['mem_mb'])
                item['uptime'] = pr['uptime']
                item['pid'] = pr['pid']
                item['cwd'] = pr.get('cwd', '')
            else:
                item['status'] = 'down'
        data['projects'].append(item)

    for name, c in dk.items():
        data['containers'].append({'name': name, 'image': c['image'], 'status': c['status'],
                                   'running': c['running'], 'mem': mem_str(c['mem_mb']),
                                   'cpu': c['cpu'], 'ports': c['ports']})

    tmp = OUT + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, OUT)
    save_state(state)


if __name__ == '__main__':
    main()
