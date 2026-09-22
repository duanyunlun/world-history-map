#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据校验：世界事件 / 政体详情 / 时间切片。

用途：每次批量补录后强制运行，避免“整批写入失败但无人发现”。
用法：
    python3 scripts/check_data.py          # 只校验，有问题退出码非 0
    python3 scripts/check_data.py --stats  # 额外打印分布统计
"""
import json, os, re, sys, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EV = os.path.join(ROOT, 'data', 'world_events.json')
POL = os.path.join(ROOT, 'data', 'world_polities.json')
WORLD = os.path.join(ROOT, 'data', 'world.json')
CATS = {'政治', '军事', '经济', '文化', '科技', '社会', '外交', '航海', '自然'}

errors, warns = [], []


def err(m):
    errors.append(m)


def warn(m):
    warns.append(m)


def load(p):
    if not os.path.exists(p):
        err('缺少文件：%s' % p)
        return None
    try:
        return json.load(open(p, encoding='utf-8'))
    except Exception as e:
        err('%s 解析失败：%s' % (os.path.basename(p), e))
        return None


def check_events():
    d = load(EV)
    if not d:
        return 0
    ev = d.get('events') or []
    if not ev:
        err('世界事件为空')
        return 0
    seen = {}
    for e in ev:
        t = e.get('title') or ''
        if not t:
            err('存在无标题事件')
            continue
        y = e.get('year')
        if not isinstance(y, int) or not (-10000 <= y <= 2026):
            err('%s 年份越界或非整数：%r' % (t, y))
        mo = e.get('month')
        if mo is not None and not (isinstance(mo, int) and 1 <= mo <= 12):
            err('%s 月份非法：%r' % (t, mo))
        lat, lon = e.get('lat'), e.get('lon')
        if not (isinstance(lat, (int, float)) and -90 <= lat <= 90):
            err('%s 纬度非法：%r' % (t, lat))
        if not (isinstance(lon, (int, float)) and -180 <= lon <= 180):
            err('%s 经度非法：%r' % (t, lon))
        if e.get('category') not in CATS:
            warn('%s 分类未在已知集合内：%r' % (t, e.get('category')))
        ss = e.get('sources') or []
        if not ss:
            err('%s 缺少来源' % t)
        for s in ss:
            u = str(s.get('u') if isinstance(s, dict) else s)
            if not re.match(r'^https?://', u):
                err('%s 来源链接非法：%r' % (t, u))
        k = (y, t)
        if k in seen:
            err('重复事件：%d %s' % k)
        seen[k] = 1
    return len(ev)


def check_polities():
    d = load(POL)
    w = load(WORLD)
    if d is None or w is None:
        return 0
    names = set()
    for s in (w.get('slices') or []):
        for r in (s.get('p') or []):
            names.add(r[0])
    for k, v in d.items():
        if not v.get('summary'):
            # 人工条目必须带简史；自动条目（auto=True）可以没有
            if not v.get('auto'):
                warn('政体 %s 标为人工但无简史' % k)
        f, t = v.get('from'), v.get('to')
        if isinstance(f, int) and isinstance(t, int) and t < f:
            err('政体 %s 存续期倒置：%s—%s' % (k, f, t))
        for s in (v.get('sources') or []):
            u = str(s.get('u') if isinstance(s, dict) else s)
            if not re.match(r'^https?://', u):
                err('政体 %s 来源链接非法：%r' % (k, u))
        if k not in names:
            warn('政体 %s 不在任何时间切片中' % k)
    return len(d)


def check_slices():
    w = load(WORLD)
    if not w:
        return 0
    sl = w.get('slices') or []
    if not sl:
        err('世界切片为空')
        return 0
    ys = [s['y'] for s in sl]
    if ys != sorted(ys):
        err('世界切片未按年份排序')
    if min(ys) > -10000:
        err('最早切片晚于公元前10000年：%s' % min(ys))
    # 现代切片以「2014」为起点覆盖到 2026（label 标注区间），故只要求不早于 2014
    if max(ys) < 2014:
        err('最晚切片早于 2014 年：%s' % max(ys))
    if not any(s.get('modern') for s in sl):
        err('缺少 2011 年后的现代切片')
    ngeo = len(w.get('geoms') or [])
    for s in sl:
        for r in (s.get('p') or []):
            if not (0 <= r[1] < ngeo):
                err('切片 %s 引用了不存在的几何 %s' % (s['y'], r[1]))
    return len(sl)


def check_faction_keys():
    """扫描“同名不同义”风险：同一势力键在不同朝代使用且相隔久远时提示复核。

    背景：曾发生 `wuyue` 同时表示古代吴越与五代吴越国，后写入的一批覆盖了前者的颜色；
    另曾发生 `jin`（金朝）与 factions.json 的晋系军阀撞名。此检查把同类风险显式列出。
    """
    d = load(os.path.join(ROOT, 'data', 'china_pre1893.json'))
    if not d:
        return 0
    fac = d.get('factions') or {}
    use = {}
    for er in (d.get('eras') or []):
        keys = set()
        for seq in (er.get('timeline') or {}).values():
            for it in seq:
                keys.add(it[1])
        for k in keys:
            use.setdefault(k, []).append((er['name'], er['from'], er['to']))
    # 长期存在的族群/地域政权，跨代使用属正常（非同名不同义）
    PEOPLES = {'qiang', 'baiyue', 'xiongnu', 'donghu', 'tufan', 'fuyu', 'xiyu',
               'taiwan_native', 'xifan', 'guifang', 'qiangfang', 'dongyi', 'xirong',
               'shu', 'ba', 'jingchu', 'wuyue_anc', 'liao', 'jinchao', 'tuyuhun',
               'chagatai', 'huihu', 'nanzhao', 'dianguo', 'yelang', 'cuan'}
    suspicious = []
    for k, spans in use.items():
        if k in PEOPLES:
            continue
        if len(spans) > 1:
            lo = min(s[1] for s in spans); hi = max(s[2] for s in spans)
            if hi - lo > 500:
                suspicious.append('%s 跨 %d 年用于：%s' %
                                  (k, hi - lo, '、'.join('%s(%s—%s)' % s for s in spans)))
    for k in fac:
        if k not in use:
            warn('势力键 %s 已定义但未被任何朝代使用' % k)
    for m in suspicious:
        warn('请复核同名不同义风险：' + m)
    return len(fac)


def main():
    n_ev = check_events()
    n_pol = check_polities()
    n_sl = check_slices()
    n_fac = check_faction_keys()
    print('世界事件 %d 条 ｜ 政体详情 %d 条 ｜ 世界切片 %d 个 ｜ 前近代政权键 %d 个'
          % (n_ev, n_pol, n_sl, n_fac))
    if '--stats' in sys.argv:
        d = json.load(open(EV, encoding='utf-8'))
        ev = d['events']
        def era(y):
            return '前10000-前500' if y < -500 else '前500-500' if y < 500 else \
                   '500-1500' if y < 1500 else '1500-1800' if y < 1800 else \
                   '1800-1900' if y < 1900 else '1900-2026'
        def reg(lat, lon):
            if lon >= 110 and lat < 0: return '大洋洲'
            if 33 <= lon <= 63 and 12 <= lat <= 42: return '中东'
            if -20 <= lon <= 52 and -36 <= lat <= 35: return '非洲'
            if -12 <= lon <= 45 and 34 <= lat <= 72: return '欧洲'
            if 60 <= lon <= 95 and 5 <= lat <= 38: return '南亚'
            if 95 <= lon <= 146 and 15 <= lat <= 54: return '东亚'
            if 92 <= lon <= 142 and -11 <= lat < 25: return '东南亚'
            if -170 <= lon <= -50 and 12 <= lat <= 74: return '北美'
            if -85 <= lon <= -34 and -56 <= lat < 24: return '拉美'
            if 45 <= lon <= 95 and 35 <= lat <= 80: return '中亚·俄罗斯'
            return '其他/全球'
        ce = collections.Counter(era(e['year']) for e in ev)
        cr = collections.Counter(reg(e['lat'], e['lon']) for e in ev)
        cc = collections.Counter(e['category'] for e in ev)
        print('  时代：', dict(sorted(ce.items())))
        print('  地区：', dict(cr.most_common()))
        print('  类别：', dict(cc.most_common()))
    # 重要警告（同名不同义/未使用键）优先展示，其余折叠，避免被淹没
    prio = [m for m in warns if m.startswith('请复核') or m.startswith('势力键')]
    rest = [m for m in warns if m not in prio]
    for m in prio:
        print('  ⚠ %s' % m)
    for m in rest[:12]:
        print('  ⚠ %s' % m)
    if len(rest) > 12:
        print('  ⚠ …另有 %d 条一般警告（多为我撰写但数据集未采用的名字）' % (len(rest) - 12))
    if errors:
        print('  ✗ 错误 %d 条：' % len(errors))
        for m in errors[:20]:
            print('    - %s' % m)
        sys.exit(1)
    print('  ✓ 校验通过（%d 条警告）' % len(warns))


if __name__ == '__main__':
    main()
