#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
构建脚本：把 data/ 下的史料数据与几何数据注入 src/template.html，
产出**完全自包含**的单文件站点 index.html（离线可直接双击打开）。

用法：
    python3 build.py                 # 完整构建
    python3 build.py --check         # 仅校验数据、不写文件

数据来源全部为公开史料（《中国历史地图集》近现代部分、各省地方志、
中共党史公开出版物、民国史公开研究），不含任何涉密内容。
"""
import json, os, re, sys, urllib.parse, hashlib, glob, difflib

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, 'data')
SRC = os.path.join(ROOT, 'src')
CHECK_ONLY = '--check' in sys.argv

Y0, Y1 = 1893, 1976
PROV_COUNT = 34


def rd(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def die(msg):
    print('  ✗ ' + msg)
    globals()['ERRORS'].append(msg)


ERRORS, WARNS = [], []

# ---------------------------------------------------------------- 1. 读取
geo = rd(os.path.join(DATA, 'geo.json'))
fac = rd(os.path.join(DATA, 'factions.json'))
ev_raw = rd(os.path.join(DATA, 'events.json'))
events = ev_raw['events'] if isinstance(ev_raw, dict) else ev_raw


# ---------------------------------------------------------------- 3.05 事件范围：全国性 / 地方性
# 「全国性」= 不隶属单一地点的事件：条约外交、中央政府决策、全国性运动。
# 这类事件钉在某一省上会误导，界面上单独用「全国」标识呈现。
_FOREIGN = ('莫斯科', '华盛顿', '伦敦', '雅尔塔', '波茨坦', '开罗', '德黑兰', '旧金山', '日内瓦',
            '巴黎', '柏林', '东京', '马关', '朴茨茅斯', '檀香山', '西姆拉', '加尔各答', '大吉岭',
            '河内', '马尼拉', '海参崴', '朝鲜', '韩国', '印度', '缅甸', '越南', '泰国', '菲律宾',
            '印尼', '瑞士', '埃及', '俄国', '苏联', '美国', '英国', '法国', '德国', '意大利', '日本')
_DIPLO = re.compile(r'条约|协定|和约|公约|密约|续约|专条|章程|会议|外交|交涉|建交|断交|宣战|停战|'
                    r'媾和|同盟|门户开放|声明')
_CAPITAL = re.compile(r'北京|北平|南京|重庆|上海|武汉|广州|西安')
_NATION = re.compile(r'全国|中央政府|政务院|国务院|全国人大|政协|宪法|约法|币制|法币|金圆券|土地改革|'
                     r'合作化|人民公社|整风|反右|大跃进|文化大革命|文革|抗美援朝|援朝|五年计划|'
                     r'内阁|国会|议会|总统|执政|改组|颁布|颁行|维新|变法|新政|预备立宪|运动|'
                     r'号召|宣言|政策|统一|易帜|迁都|成立|开国|建国|定都|联合国|安理会|万隆|志愿军|入朝|出兵|参战|镇压反革命')


def event_scope(e):
    if e.get('scope'):
        return e['scope']                             # 数据中显式声明优先
    pl = e.get('place') or ''
    foreign = pl and not pl.startswith('内蒙古') and any(pl.startswith(f) or f in pl for f in _FOREIGN)
    title = e.get('title') or ''
    if re.search(r'全国|各地|境内', pl):
        return 'nation'                                   # 地点即「全国」
    if foreign and (_DIPLO.search(title) or _NATION.search(title)):
        return 'nation'
    if _CAPITAL.search(pl) and _NATION.search(e.get('title') or ''):
        return 'nation'
    return 'local'


# ---------------------------------------------------------------- 3.1 事件时间统一到「月」
# 运行时不再解析日期字符串：构建期给出 mi（绝对月序号）、mo、day、approx 精度标记。
_MONTH_RE = re.compile(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})?\s*日?')
_MONTH_ONLY_RE = re.compile(r'(\d{1,2})\s*月')
_HALF_RE = re.compile(r'(\d{4})\s*年\s*(上|中|下)?半年')
_IN_TEXT_RE = re.compile(r'(?<![0-9])(\d{1,2})\s*月\s*(\d{1,2})?\s*日?')


def event_time(e):
    """返回 (mo, day, approx)；approx: day 精确到日 / month 精确到月 / year 仅到年"""
    d = e.get('date') or ''
    mo = day = None
    m = _MONTH_RE.search(d)
    if m:
        mo = int(m.group(2)); day = int(m.group(3)) if m.group(3) else None
        return mo, day, ('day' if day else 'month')
    m = _MONTH_ONLY_RE.search(d)
    if m:
        return int(m.group(1)), None, 'month'
    m = _HALF_RE.search(d)
    if m:
        return ({'上': 3, '下': 10}.get(m.group(2), 7)), None, 'month'
    # 仅到年：尝试从本条事件的正文里找出月份（同一事件的自述，可核对）
    txt = (e.get('detail') or '') + ' ' + (e.get('summary') or '')
    m = _IN_TEXT_RE.search(txt)
    if m:
        mm = int(m.group(1))
        if 1 <= mm <= 12:
            e['timeFrom'] = 'detail'
            return mm, (int(m.group(2)) if m.group(2) and 1 <= int(m.group(2)) <= 31 else None), \
                   ('day' if m.group(2) else 'month')
    return 1, None, 'year'
PROVS = list(geo['paths'].keys())
if len(PROVS) != PROV_COUNT:
    die('几何数据省份数 %d，预期 %d' % (len(PROVS), PROV_COUNT))

# ---------------------------------------------------------------- 2. 校验势力数据
FACTIONS = fac['factions']
PROVSEG = fac['provinces']
OVERRIDE = fac.get('monthOverride', {})

HIST_SHAPES = set()
_hg = geo.get('hist', {}) or {}
for _g in _hg.get('geoms', []):
    HIST_SHAPES.update(_g.keys())            # 历史区划形状的键（即势力键）
for _p in _hg.get('periods', []):
    HIST_SHAPES.update((_p.get('shapeNames') or {}).keys())
ALLOWED = set(PROVS) | HIST_SHAPES

for p in PROVS:
    if p not in PROVSEG:
        die('分省归属缺少：%s' % p)
for p in PROVSEG:
    if p not in ALLOWED:
        die('分省归属多余（地图无此单元）：%s' % p)

for p, segs in PROVSEG.items():
    cov = {}
    for s in segs:
        if s['faction'] not in FACTIONS:
            die('%s 引用未定义势力 %s' % (p, s['faction']))
        if s['from'] > s['to']:
            die('%s 区间倒置 %s' % (p, s))
        for y in range(s['from'], s['to'] + 1):
            if y in cov:
                die('%s 年份 %d 区间重叠' % (p, y))
            cov[y] = 1
    if p in PROVS:                          # 现行省份须逐年覆盖；历史区划单位只在其存在期内使用
        for y in range(Y0, Y1 + 1):
            if y not in cov:
                die('%s 年份 %d 缺归属' % (p, y))

for y, items in OVERRIDE.items():
    for it in items:
        if it[0] not in ALLOWED:
            die('月级切点省份未知：%s' % it[0])
        if it[2] not in FACTIONS:
            die('月级切点势力未知：%s' % it[2])
        if not (1 <= int(it[1]) <= 12):
            die('月级切点月份非法：%s' % it)

# ---------------------------------------------------------------- 3. 校验事件数据
CATS = {'战争': '#d94f45', '政治': '#5b8fd4', '外交': '#46b3a4', '经济': '#d9ac48',
        '文化': '#a878d4', '科技': '#57c2d6', '灾害': '#a9784f', '社会': '#d9784f'}
ALIAS = {'军事': '战争', '抗战': '战争', '革命': '政治', '政权': '政治', '民族': '政治',
         '教育': '文化', '卫生': '社会', '科学': '科技', '工程': '科技', '灾难': '灾害',
         '自然': '灾害', '抗灾': '灾害'}
SUFFIX = re.compile(r'(省|市|自治区|特别行政区|壮族|回族|维吾尔|自治州)$')

seen, clean = set(), []
for i, e in enumerate(events):
    e = dict(e)
    y = e.get('year')
    if not isinstance(y, int) or not (Y0 <= y <= Y1):
        die('事件年份非法：%r %r' % (e.get('title'), y)); continue
    if not e.get('title'):
        die('事件缺标题（第 %d 条）' % i); continue
    c = (e.get('category') or '政治').strip()
    c = ALIAS.get(c, c)
    if c not in CATS:
        WARNS.append('%s 类别未识别 %r → 政治' % (e['title'], e.get('category')))
        c = '政治'
    e['category'] = c

    ps = e.get('provinces') or []
    if isinstance(ps, str):
        ps = re.split(r'[、,，/｜| ]+', ps)
    norm = []
    for p in ps:
        p = SUFFIX.sub('', str(p).strip())
        p = {'内蒙': '内蒙古', '西藏自治': '西藏'}.get(p, p)
        if p in PROVS:
            if p not in norm:
                norm.append(p)
        else:
            WARNS.append('%s 省份未识别：%r' % (e['title'], p))
    if not norm:
        WARNS.append('%s 无有效关联省份（不会出现在地图上）' % e['title'])
    e['provinces'] = norm

    e['summary'] = e.get('summary') or (e.get('detail') or '')[:90]
    e['detail'] = e.get('detail') or ''
    e['importance'] = int(e.get('importance') or 2)

    e['date'] = e.get('date') or ('%d年' % y)
    e['tags'] = e.get('tags') or []
    e['scope'] = event_scope(e)
    _mo, _day, _ap = event_time(e)
    e['mo'] = _mo
    e['day'] = _day
    e['approx'] = _ap
    e['mi'] = y * 12 + (_mo - 1)
    # 来源标注：每条必须有可点击的公开来源
    ss = e.get('sources') or []
    ss2 = []
    for x in ss:
        if isinstance(x, str):
            x = {'t': x, 'u': x}
        u = str(x.get('u') or '').strip()
        if not re.match(r'^https?://', u):
            die('%s 来源链接非法：%r' % (e['title'], u)); continue
        ss2.append({'t': str(x.get('t') or u)[:60], 'u': u})
    if not ss2:
        die('%s 缺少来源标注' % e['title'])
    e['sources'] = ss2[:3]
    e.pop('_i', None)
    k = (y, e['title'])
    if k in seen:
        WARNS.append('重复事件已去重：%d %s' % k); continue
    seen.add(k)
    clean.append(e)

clean.sort(key=lambda x: (x['year'], -x['importance'], x['title']))

# ---------------------------------------------------------------- 3.2 周边国家势力
NB = {'factions': {}, 'neighbors': {}, 'monthOverride': {}}
NB_PATH = os.path.join(DATA, 'neighbors.json')
GEO_NAMES = [n['name'] for n in geo.get('neighbors', [])]
if os.path.exists(NB_PATH):
    try:
        NB = json.load(open(NB_PATH, encoding='utf-8'))
    except Exception as ex:
        die('周边国家数据解析失败: %s' % ex)
    _nbf = NB.get('factions', {})
    for _nm, _segs in NB.get('neighbors', {}).items():
        _cov = {}
        for _s in _segs:
            if _s['faction'] not in _nbf:
                die('周边 %s 引用未定义势力 %s' % (_nm, _s['faction']))
            for _y in range(_s['from'], _s['to'] + 1):
                if _y in _cov:
                    die('周边 %s 年份 %d 区间重叠' % (_nm, _y))
                _cov[_y] = 1
        for _y in range(Y0, Y1 + 1):
            if _y not in _cov:
                die('周边 %s 年份 %d 缺归属' % (_nm, _y))
    _miss = [n for n in GEO_NAMES if n not in NB.get('neighbors', {})]
    if _miss:
        WARNS.append('以下邻国缺少势力数据（将不上色）：%s' % '、'.join(_miss))

# ---------------------------------------------------------------- 3.3 割据区 / 根据地
TERR = []
_tp = os.path.join(DATA, 'territories.json')
_geoter = [x for x in geo.get('territories', [])]
if os.path.exists(_tp):
    _td = json.load(open(_tp, encoding='utf-8'))
    _by_name = {x['name']: x for x in _geoter}
    _cnmap = json.load(open(os.path.join(DATA, 'counties.json'), encoding='utf-8'))['counties'] if os.path.exists(os.path.join(DATA, 'counties.json')) else {}
    for _t in _td.get('territories', []):
        _g = _by_name.get(_t['name'])
        if not _g:
            WARNS.append('割据区缺少几何：%s' % _t['name']); continue
        if _t['faction'] not in FACTIONS and _t['faction'] not in ('suqu', 'kangri', 'jiefangqu'):
            die('割据区 %s 引用未知势力 %s' % (_t['name'], _t['faction']))
        _fy, _fm = _t['from']; _ty, _tm = _t['to']
        if not (-1600 <= _fy <= Y1 and -1600 <= _ty <= Y1) or (_ty * 12 + _tm) < (_fy * 12 + _fm):
            die('割据区 %s 起止时间非法' % _t['name'])
        _provs = []
        if _t.get('counties') and _cnmap:
            for _c in _t['counties']:
                _p = _cnmap.get(_c, {}).get('province')
                if _p and _p not in _provs:
                    _provs.append(_p)
        TERR.append({
            'name': _t['name'], 'faction': _t['faction'], 'provs': _provs,
            'from': _t['from'], 'to': _t['to'],
            'c': _g.get('c'), 'n': _g.get('n'), 'label': _g.get('label'),
            'counties': _t.get('counties', []), 'note': _t.get('note', ''),
            'sources': _t.get('sources', []),
        })
    _cnty = json.load(open(os.path.join(DATA, 'counties.json'), encoding='utf-8'))['counties']
    _cnt = len(_cnty)
    print('  割据区         %d 个（覆盖 %d 个县级单位）' % (len(TERR), _cnt))

# ------------------------------------------------ 3.5 事件深度信息 + 人物志
def _norm(s):
    return re.sub(r'[\s·、，,。：:—\-－“”"\'’！!？?（）()《》]', '', s or '')


deep_files = sorted(glob.glob(os.path.join(DATA, 'events_deep', '*.json')))
deep_items = []
for fp in deep_files:
    try:
        d = json.load(open(fp, encoding='utf-8'))
    except Exception as ex:
        WARNS.append('深度数据 %s 解析失败: %s' % (os.path.basename(fp), ex)); continue
    deep_items.extend(d.get('items', d if isinstance(d, list) else []))

by_year = {}
for e in clean:
    by_year.setdefault(e['year'], []).append(e)
deep_hit = 0
for it in deep_items:
    y = it.get('year')
    cands = by_year.get(y, [])
    nt = _norm(it.get('title', ''))
    tgt = next((c for c in cands if _norm(c['title']) == nt), None)
    if tgt is None:
        best, bs = None, 0.0
        for c in cands:
            r = difflib.SequenceMatcher(None, nt, _norm(c['title'])).ratio()
            if r > bs: best, bs = c, r
        if bs >= 0.75: tgt = best
    if tgt is None:
        WARNS.append('深度数据未匹配到事件：%s %s' % (y, it.get('title'))); continue
    tgt['deep'] = {
        'figures': it.get('figures', [])[:8],
        'timeline': [{'d': x.get('d', ''), 't': x.get('t', '')} for x in (it.get('timeline') or [])][:8],
        'impact': it.get('impact', ''),
        'forcesAtTime': it.get('forcesAtTime', ''),
    }
    deep_hit += 1

# 人物志：合并 data/people.json 与分批产物 data/people_parts/*.json（按 id 去重）
PEOPLE, _seen_pid = [], {}
def _add_people(lst, src):
    for pr in lst:
        if not isinstance(pr, dict) or not pr.get('id') or not pr.get('name'):
            continue
        pid = pr['id']
        if pid in _seen_pid:
            # 已有条目缺少正文时，用更完整的覆盖
            if len(str(pr.get('bio') or '')) > len(str(_seen_pid[pid].get('bio') or '')):
                _seen_pid[pid].update(pr)
            continue
        _seen_pid[pid] = pr
        PEOPLE.append(pr)

for fp in [os.path.join(DATA, 'people.json')] + sorted(glob.glob(os.path.join(DATA, 'people_parts', '*.json'))):
    if not os.path.exists(fp):
        continue
    try:
        dd = json.load(open(fp, encoding='utf-8'))
        _add_people(dd.get('people', dd if isinstance(dd, list) else []), fp)
    except Exception as ex:
        WARNS.append('人物志 %s 解析失败: %s' % (os.path.basename(fp), ex))
# 未写正文者回填骨架（姓名/生卒/阵营来自名册），保证索引完整
_roster = os.path.join(DATA, 'people_roster.json')
if os.path.exists(_roster):
    try:
        rr = json.load(open(_roster, encoding='utf-8'))
        rr = rr.get('people', rr if isinstance(rr, list) else [])
        for pr in rr:
            if pr.get('id') and pr['id'] not in _seen_pid:
                _add_people([dict(pr)], _roster)
    except Exception as ex:
        WARNS.append('人物名册解析失败: %s' % ex)

# 标记"仅有名册、尚无正文"的条目（前端显示为待补，不提供点击）
for pr in PEOPLE:
    pr['stub'] = not (str(pr.get('bio') or '').strip() and str(pr.get('summary') or '').strip())
STUB_COUNT = sum(1 for pr in PEOPLE if pr['stub'])

# 人物名 -> id 索引（含别名），供事件里的人物名做页内跳转（仅收录有正文者）
person_index = {}
for pr in PEOPLE:
    if not pr.get('id') or not pr.get('name') or pr.get('stub'):
        continue
    person_index[_norm(pr['name'])] = pr['id']
    for al in re.split(r'[、,，/]', pr.get('alias') or ''):
        al = _norm(al)
        if al and al not in person_index:
            person_index[al] = pr['id']
missing_fig = set()
for e in clean:
    for fg in (e.get('deep', {}).get('figures') or []):
        if _norm(fg) not in person_index:
            missing_fig.add(fg)
if missing_fig:
    WARNS.append('以下人物暂无人物志条目（前端将不可点击）：%s' % '、'.join(sorted(missing_fig)[:20]))

# ---------------------------------------------------------------- 4. 分期带 & 年度政权
BANDS = [
    {'from': 1893, 'to': 1894, 'name': '清末', 'color': '#4a3b1f'},
    {'from': 1895, 'to': 1911, 'name': '清末·变革与革命', 'color': '#6b5320'},
    {'from': 1912, 'to': 1915, 'name': '民国初年·北洋', 'color': '#2f4a63'},
    {'from': 1916, 'to': 1927, 'name': '军阀割据', 'color': '#3d5a4a'},
    {'from': 1928, 'to': 1936, 'name': '南京国民政府', 'color': '#27476b'},
    {'from': 1937, 'to': 1945, 'name': '全面抗战', 'color': '#6e2e26'},
    {'from': 1946, 'to': 1949, 'name': '解放战争', 'color': '#7a3a1c'},
    {'from': 1950, 'to': 1957, 'name': '新中国初创', 'color': '#8c2b22'},
    {'from': 1958, 'to': 1965, 'name': '探索与曲折', 'color': '#6d3a12'},
    {'from': 1966, 'to': 1976, 'name': '“文革”十年', 'color': '#4a2a4a'},
]


def faction_at(prov, y, mo):
    """与前端完全一致：年区间 + 月级锚点，再沿时间轴正向填充。"""
    return MONTH_TABLE[SI_INDEX(y, mo)][prov]


def SI_INDEX(y, mo):
    return (y - Y0) * 12 + (mo - 1)


def build_month_table():
    """构造 1008 个月的归属表：年区间打底 -> 月级锚点覆盖 -> 全时间轴正向填充。"""
    n = (Y1 - Y0 + 1) * 12
    rows = [dict() for _ in range(n)]
    for p, segs in PROVSEG.items():
        for s in segs:
            for y in range(max(Y0, s['from']), min(Y1, s['to']) + 1):
                for mo in range(1, 13):
                    rows[SI_INDEX(y, mo)][p] = {'faction': s['faction'], 'note': s.get('note', '')}
    for y, items in OVERRIDE.items():
        for it in items:
            prov, mo, fac, note = it[0], int(it[1]), it[2], it[3]
            for m in range(mo, 13):
                rows[SI_INDEX(int(y), m)][prov] = {'faction': fac, 'note': note}
    carry = {}
    for r in rows:
        for p in PROVS:
            if p in r:
                carry[p] = r[p]
            elif p in carry:
                r[p] = carry[p]
    return rows


MONTH_TABLE = build_month_table()

# 逐月展开，用于统计与自检
month_rows = MONTH_TABLE

for idx, row in enumerate(month_rows):
    for p, v in row.items():
        if not v:
            die('%d.%02d %s 无归属' % (Y0 + idx // 12, idx % 12 + 1, p))

# 关键年份势力分布统计（供报告）
def year_tally(y):
    t = {}
    for p in PROVS:
        f = (faction_at(p, y, 1) or {}).get('faction')
        if f:
            t[f] = t.get(f, 0) + 1
    return dict(sorted(t.items(), key=lambda kv: -kv[1]))



# ---------------------------------------------------------------- 校验：前近代政权键
# 1644 年前政权键不得与近现代势力键冲突（曾发生 jin=晋系军阀 被误用为金朝）
_pre_path = os.path.join(DATA, 'china_pre1893.json')
if os.path.exists(_pre_path):
    _pre = json.load(open(_pre_path, encoding='utf-8'))
    # 允许与既有键同名但定义一致（如 qing 清王朝），只拦“同名不同义”
    _pf = _pre.get('factions') or {}
    _clash = [k for k, v in _pf.items()
              if k in FACTIONS and (FACTIONS[k].get('name') != v.get('name')
                                    or FACTIONS[k].get('color') != v.get('color'))]
    if _clash:
        die('1644 前政权键与既有势力键冲突：%s' % '、'.join(_clash))
    print('  前近代政权     %d 个，无键冲突' % len(_pre.get('factions') or {}))

# ---------------------------------------------------------------- 3.9 世界图层与统一时间轴
WORLD = None
_wp = os.path.join(DATA, 'world.json')
TIMELINE = {'steps': [], 'ranges': []}
if os.path.exists(_wp):
    WORLD = json.load(open(_wp, encoding='utf-8'))
    # 时间轴：世界切片（远古） + 中国逐月（1893—1976） + 逐年（1977—2026）
    def slice_for(yy):
        """某年使用的世界切片：1886—2019 用 CShapes 逐年，2020 起用现代切片，其余取不晚于该年的最新切片"""
        if yy >= 2020:
            for i, sl in enumerate(WORLD['slices']):
                if sl.get('modern') and sl['y'] == 2014:
                    return i
        pick = 0
        for i, sl in enumerate(WORLD['slices']):
            if sl.get('modern'):
                continue
            if sl['y'] <= yy:
                pick = i
            else:
                break
        return pick

    steps = []
    # 中国逐年步只按“有朝代数据”的年份生成，避免出现无数据的空档期（如 220—617）
    _pre_path2 = os.path.join(DATA, 'china_pre1893.json')
    _era_years = set()
    if os.path.exists(_pre_path2):
        _pd = json.load(open(_pre_path2, encoding='utf-8'))
        for _er in (_pd.get('eras') or []):
            for _yy in range(max(-1600, int(_er['from'])), min(1892, int(_er['to'])) + 1):
                _era_years.add(_yy)
    else:
        _era_years = set(range(1644, 1893))
    for yy in sorted(_era_years):
        steps.append({'t': yy, 'kind': 'cny', 'y': yy, 'slice': slice_for(yy),
                      'label': '%d年' % yy})
    for _i, sl in enumerate(WORLD['slices']):
        y = sl['y']
        if sl.get('cs'):
            if 1886 <= y <= 2019:            # CShapes 逐年步（2020 后由现代切片覆盖）
                steps.append({'t': y, 'kind': 'world', 'slice': _i, 'label': sl['label']})
            continue
        if sl.get('modern'):
            continue
        if -123000 <= y <= 1885:
            steps.append({'t': y, 'kind': 'world', 'slice': _i, 'label': sl['label']})
    for yy in range(1893, 1977):
        base = slice_for(yy)
        for mo in range(1, 13):
            steps.append({'t': yy + (mo - 1) / 12.0, 'kind': 'cn', 'y': yy, 'mo': mo,
                          'slice': base, 'label': '%d年%d月' % (yy, mo)})
    for yy in range(1977, 2027):
        steps.append({'t': yy, 'kind': 'year', 'y': yy,
                      'slice': slice_for(yy), 'label': '%d年' % yy})
    steps.sort(key=lambda z: z['t'])
    TIMELINE['steps'] = steps
    # 区间互不重叠（此前 上古 覆盖到公元500，把春秋战国/秦汉/三国的中国逐年步也圈进去了）
    rng = [('史前（前123000—前3001）', -123000, -3000.01),
           ('上古（前3000—前1601）', -3000, -1600.01),
           ('商周·逐年（前1600—前771）', -1600, -770.01),
           ('春秋战国·逐年（前770—前222）', -770, -221.01),
           ('秦汉·逐年（前221—公元219）', -221, 219.99),
           ('三国两晋南北朝·逐年（220—617）', 220, 617.99),
           ('隋唐五代·逐年（618—959）', 618, 959.99),
           ('宋辽夏金·逐年（960—1270）', 960, 1270.99),
           ('元代·逐年（1271—1367）', 1271, 1367.99),
           ('明代·逐年（1368—1643）', 1368, 1643.99),
           # 政治史分期：清代止于辛亥革命（1911），近代止于新中国成立（1949.10），当代自建国起
           ('清代（1644—1911）', 1644, 1911.99),
           ('中国近代·逐月（1912—1949.09）', 1912, 1949.74, True),
           ('当代（1949.10—2026）', 1949.75, 2030, True)]
    for _item in rng:
        name, a, b = _item[0], _item[1], _item[2]
        bands = bool(_item[3]) if len(_item) > 3 else False
        idx = [i for i, z in enumerate(steps) if a <= z['t'] <= b]
        if idx:
            TIMELINE['ranges'].append({'name': name, 'from': idx[0], 'to': idx[-1],
                                       'bands': bands})
    _np = os.path.join(DATA, 'world_names.json')
    if os.path.exists(_np):
        WORLD['names'] = json.load(open(_np, encoding='utf-8'))
    # ---- 政权注册表（S3）：单一真相，含别名索引 ----
    _POLDIR = os.path.join(DATA, 'sources', 'polities')
    _pol_reg, _pol_alias = {}, {}
    if os.path.isdir(_POLDIR):
        for _fn in sorted(os.listdir(_POLDIR)):
            if not _fn.endswith('.json'):
                continue
            _grp = json.load(open(os.path.join(_POLDIR, _fn), encoding='utf-8'))
            for _e in (_grp.get('entries') or []):
                _eid = _e.get('id')
                if not _eid:
                    continue
                if _eid in _pol_reg:
                    die('政权注册表 id 重复：%s（%s）' % (_eid, _fn))
                _pol_reg[_eid] = _e
                # 别名索引带时间范围：同一 id 的不同时段可对应不同名称（id 与年份绑定）
                _spans = _e.get('spans') or [{'from': _e.get('from'), 'to': _e.get('to'),
                                              'from': _e.get('from')}]
                def _range_for(alias):
                    for _sp in _spans:
                        if _sp.get('alias') == alias or len(_spans) == 1:
                            return _sp.get('from'), _sp.get('to')
                    return None, None
                for _a in [_eid] + list(_e.get('aliases') or []):
                    _k = str(_a).lower()
                    _f, _t = _range_for(_a)
                    _lst = _pol_alias.setdefault(_k, [])
                    # 世界拼写优先解析到世界实体；中国 id 由精确 id 直接取，不受影响
                    if _lst and not _eid.startswith('world/') and not _lst[0]['id'].startswith('world/'):
                        pass
                    _lst.append({'id': _eid, 'from': _f, 'to': _t})
        _spans_n = sum(len(e.get('spans') or []) for e in _pol_reg.values())
        print('  政权注册表     %d 条 / %d 个时段（别名索引 %d 键）'
              % (len(_pol_reg), _spans_n, len(_pol_alias)))
    else:
        print('  ⚠ 未找到 data/sources/polities/，回退旧数据文件')

    # ---- 1644 年前的控制序列：优先取 sources/periods/*.json 的 control 块（S4） ----
    _PDIR2 = os.path.join(DATA, 'sources', 'periods')
    _pre1893 = None
    if os.path.isdir(_PDIR2):
        _eras = []
        for _fn in sorted(os.listdir(_PDIR2)):
            if not _fn.endswith('.json'):
                continue
            _q = json.load(open(os.path.join(_PDIR2, _fn), encoding='utf-8'))
            _c = _q.get('control')
            if not _c:
                continue
            _eras.append({
                'name': _q['label'],
                'from': _q['from']['y'] if _q['from']['m'] == 1 else _q['from']['y'],
                'to': _q['to']['y'],
                'fromM': _q['from']['m'], 'toM': _q['to']['m'],
                'faction': _c.get('faction'),
                'timeline': _c.get('timeline') or {},
                'preFaction': _c.get('preFaction') or {},
                'preName': _c.get('preName') or {},
                'note': _q.get('note') if isinstance(_q.get('note'), dict) else {},
                'approx': _c.get('approx', ''),
            })
        _eras.sort(key=lambda e: e['from'] * 12 + e.get('fromM', 1))
        if _eras:
            _pre1893 = {'eras': _eras, 'factions': {}, 'source': 'sources/periods/*.json'}
            print('  控制序列来源    sources/periods/（%d 个时期带控制序列）' % len(_eras))
    if _pre1893 is None and os.path.exists(os.path.join(DATA, 'china_pre1893.json')):
        _pre1893 = json.load(open(os.path.join(DATA, 'china_pre1893.json'), encoding='utf-8'))
        print('  ⚠ 控制序列回退到 china_pre1893.json')

    _pp = os.path.join(DATA, 'world_polities.json')
    WORLD['polities'] = json.load(open(_pp, encoding='utf-8')) if os.path.exists(_pp) else {}
    print('  政体详解      %d 条人工撰写（未撰写者由前端按切片信息即时生成）' % len(WORLD['polities']))
    print('  世界图层      %d 个切片、%d 个几何（%s → %s）'
          % (len(WORLD['slices']), len(WORLD['geoms']),
             WORLD['slices'][0]['label'], WORLD['slices'][-1]['label']))
    print('  统一时间轴    %d 步（%d 个区间：%s）'
          % (len(steps), len(TIMELINE['ranges']), '、'.join(r['name'].split('（')[0] for r in TIMELINE['ranges'])))


# ---------------------------------------------------------------- 3.95 世界历史事件
WEV = []
_wep = os.path.join(DATA, 'world_events.json')
if os.path.exists(_wep):
    _wd = json.load(open(_wep, encoding='utf-8'))
    for _e in _wd.get('events', []):
        _ss = []
        for _x in (_e.get('sources') or []):
            _u = str(_x.get('u') if isinstance(_x, dict) else _x)
            if not re.match(r'^https?://', _u):
                die('世界事件来源非法：%s' % _e.get('title'))
            _ss.append({'t': str((_x.get('t') if isinstance(_x, dict) else _u))[:60], 'u': _u})
        if not _ss:
            die('世界事件缺少来源：%s' % _e.get('title'))
        _mo = _e.get('month')
        _mo = int(_mo) if _mo else 1
        WEV.append({
            'y': int(_e['year']), 'mo': _mo,
            't': float(_e['year']) + (_mo - 1) / 12.0,
            'mi': int(_e['year']) * 12 + (_mo - 1),
            'title': _e['title'], 'place': _e.get('place', ''),
            'lat': float(_e.get('lat', 0)), 'lon': float(_e.get('lon', 0)),
            'cat': _e.get('category', ''), 'imp': int(_e.get('importance', 2)),
            'summary': _e.get('summary', ''), 'detail': _e.get('detail', ''),
            'sources': _ss[:3],
            'approx': 'month' if _e.get('month') else 'year',
        })
    WEV.sort(key=lambda z: z['t'])
    _cat = {}
    for _e in WEV:
        _cat[_e['cat']] = _cat.get(_e['cat'], 0) + 1
    print('  世界事件      %d 条（%s）' % (len(WEV), '、'.join('%s%d' % kv for kv in sorted(_cat.items(), key=lambda z: -z[1])[:6])))

# ---------------------------------------------------------------- 4.5 口径自检：战事事件与势力表的一致性
OCCUPY_PAT = re.compile(r'陷落|沦陷|失守|侵占|占领|攻占|光复|解放|易帜|和平解放')
_cross = []
for e in clean:
    if not OCCUPY_PAT.search(e['title']):
        continue
    try:
        mo = int(re.search(r'年\s*(\d{1,2})\s*月', e.get('date') or '').group(1))
    except Exception:
        continue
    for p in e['provinces']:
        rec = faction_at(p, e['year'], mo)
        occ = rec['faction'] if rec else None
        if occ in ('japan', 'manzhou', 'mengjiang', 'linshi', 'weixin', 'wangwei', 'huabei') and \
           not OCCUPY_PAT.search(e['title'].replace('沦陷', '').replace('失守', '')):
            # 仅在“该省已由日伪控制、而事件标题并不含沦陷/失守语义”时提示
            pass
        if occ in ('japan', 'manzhou', 'mengjiang', 'linshi', 'weixin', 'wangwei', 'huabei') and \
           not re.search(r'陷落|沦陷|失守|侵占|占领|攻占|伪', e['title']):
            _cross.append('%d.%02d《%s》%s：事件标题为“%s”，但该月 %s 已由「%s」控制'
                          % (e['year'], mo, e['title'], p, e['title'], p, FACTIONS[rec['faction']]['name']))
CROSS = _cross

# ---------------------------------------------------------------- 5. 统计输出
ys = sorted(set(e['year'] for e in clean))
missing = [y for y in range(Y0, Y1 + 1) if y not in ys]
per_year = {}
for e in clean:
    per_year[e['year']] = per_year.get(e['year'], 0) + 1
catcnt = {}
for e in clean:
    catcnt[e['category']] = catcnt.get(e['category'], 0) + 1

print('=' * 74)
print('  中国历史地图 1893—1976 · 构建报告')
print('=' * 74)
print('  省级单元       %d（另有历史区划单位 %d 个）' % (len(PROVS), len(HIST_SHAPES)))
print('  势力 / 政权    %d' % len(FACTIONS))
print('  归属区间       %d 段（另含 %d 年月级切点）'
      % (sum(len(v) for v in PROVSEG.values()), sum(len(v) for v in OVERRIDE.values())))
print('  时间刻度       %d 个月（%d.%02d — %d.%02d）' % (len(month_rows), Y0, 1, Y1, 12))
print('  历史事件       %d 件，覆盖 %d—%d' % (len(clean), ys[0], ys[-1]))
print('  年份空白       %s' % (', '.join(map(str, missing)) if missing else '无'))
print('  年均事件       %.1f 件' % (len(clean) / max(1, len(ys))))
print('  事件分类       %s' % json.dumps(catcnt, ensure_ascii=False))
print('  周边国家       %d 个（%d 种政权/势力）' % (len(NB.get('neighbors', {})), len(NB.get('factions', {}))))
print('  深度事件       %d 条（含时间线/相关人物/影响）' % deep_hit)
print('  人物志         %d 位（其中已撰写正文 %d 位，待补 %d 位）'
      % (len(PEOPLE), len(PEOPLE) - STUB_COUNT, STUB_COUNT))
if PEOPLE:
    _camp = {}
    for pr in PEOPLE:
        _camp[pr.get('camp', 'other')] = _camp.get(pr.get('camp', 'other'), 0) + 1
    print('  人物阵营分布   %s' % json.dumps(_camp, ensure_ascii=False))
_src = set(x['u'] for e in clean for x in e['sources'])
_host = {}
for u in _src:
    h = re.sub(r'^https?://([^/]+).*$', r'\1', u)
    _host[h] = _host.get(h, 0) + 1
print('  来源标注       每条 %d/%d 均有 ｜ 不同链接 %d 个'
      % (sum(1 for e in clean if e['sources']), len(clean), len(_src)))
print('  来源域名       %s' % ', '.join('%s(%d)' % kv for kv in
      sorted(_host.items(), key=lambda kv: -kv[1])[:6]))
print('  精确到月       %d 件（%.0f%%）' % (
    sum(1 for e in clean if re.search(r'月', e['date'])),
    100.0 * sum(1 for e in clean if re.search(r'月', e['date'])) / max(1, len(clean))))
import collections as _c
_sc = _c.Counter(e['scope'] for e in clean)
print('  事件范围       全国性 %d ｜ 地方性 %d' % (_sc['nation'], _sc['local']))
_apc = _c.Counter(e['approx'] for e in clean)
print('  时间精度       到日 %d ｜ 到月 %d ｜ 仅到年 %d ｜ 其中由正文补月 %d'
      % (_apc['day'], _apc['month'], _apc['year'],
         sum(1 for e in clean if e.get('timeFrom') == 'detail')))
print('-' * 74)
for y in (1893, 1911, 1916, 1928, 1937, 1945, 1966, 1976):
    t = year_tally(y)
    top = ' · '.join('%s %d省' % (FACTIONS[k]['name'], v) for k, v in list(t.items())[:4])
    print('  %d 年：%s' % (y, top))
print('-' * 74)
print('  逐月抽样（体现势力范围随时间变动）：')
for (yy, mm) in ((1893, 1), (1916, 7), (1928, 6), (1931, 2), (1931, 9), (1937, 7), (1937, 9),
                 (1945, 10), (1949, 1), (1949, 4), (1949, 10), (1950, 6), (1951, 6), (1966, 5)):
    row = MONTH_TABLE[SI_INDEX(yy, mm)]
    tt = {}
    for p in PROVS:
        f = row[p]['faction']
        tt[f] = tt.get(f, 0) + 1
    top = ' · '.join('%s%d' % (FACTIONS[k]['name'], v) for k, v in
                     sorted(tt.items(), key=lambda kv: -kv[1])[:4])
    print('   %d.%02d  %s' % (yy, mm, top))
print('-' * 74)
if CROSS:
    print('  ⚠ 口径待核 %d 处（战事事件标题与当月势力表可能不一致，供人工复核）：' % len(CROSS))
    for c in CROSS[:8]:
        print('     · ' + c)
if WARNS:
    print('  ⚠ 警告 %d 条' % len(WARNS))
    for w in WARNS[:10]:
        print('     · ' + w)
if ERRORS:
    print('  ✗ 错误 %d 条' % len(ERRORS))
    for x in ERRORS[:20]:
        print('     · ' + x)
    sys.exit(1)
print('  ✓ 数据校验全部通过')
print('=' * 74)
if CHECK_ONLY:
    print('  （--check：未写入文件）')
    sys.exit(0)

# ---------------------------------------------------------------- 6. 注入产出
DATAJS = {
    'factions': FACTIONS,
    'provinces': PROVSEG,
    'monthOverride': OVERRIDE,
    'events': clean,
    'bands': BANDS,
    'cats': CATS,
    'people': PEOPLE,
    'territories': TERR,
    'world': WORLD,
    'timeline': TIMELINE,
    'worldEvents': WEV,
    'polities': _pol_reg if os.path.isdir(os.path.join(DATA, 'sources', 'polities')) else None,
    'polityAlias': _pol_alias if os.path.isdir(os.path.join(DATA, 'sources', 'polities')) else None,
    'chinaPre1893': _pre1893,
    'neighborFactions': NB.get('factions', {}),
    'neighbors': NB.get('neighbors', {}),
    'neighborMonthOverride': NB.get('monthOverride', {}),
    'personIndex': person_index,
    'meta': {
        'y0': Y0, 'y1': Y1,
        'months': len(month_rows),
        'builtAt': __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M'),
        'sources': '《中国历史地图集》近现代部分、各省地方志、中共党史公开出版物、民国史公开研究（均为公开资料）',
    },
}

tpl = open(os.path.join(SRC, 'template.html'), encoding='utf-8').read()
css = open(os.path.join(SRC, 'style.css'), encoding='utf-8').read()
app_js = open(os.path.join(SRC, 'app.js'), encoding='utf-8').read()

inline_css = '<style>\n' + css + '\n</style>'
inline_geo = '<script>\nwindow.__GEO__ = ' + json.dumps(geo, ensure_ascii=False, separators=(',', ':')) + ';\n</script>'
inline_data = '<script>\nwindow.__DATA__ = ' + json.dumps(DATAJS, ensure_ascii=False, separators=(',', ':')) + ';\n</script>'
inline_app = '<script>\n' + app_js + '\n</script>'

out = tpl.replace('<!--INLINE:style.css-->', inline_css)
out = out.replace('<!--INLINE:geo.js-->', inline_geo)
out = out.replace('<!--INLINE:data.js-->', inline_data)
out = out.replace('<!--INLINE:app.js-->', inline_app)
assert '<!--INLINE:' not in out, '仍有未替换的注入占位符'

dst = os.path.join(ROOT, 'index.html')
open(dst, 'w', encoding='utf-8').write(out)
size = os.path.getsize(dst)
print('  ✓ 已生成 index.html（%.0f KB，自包含、可离线打开）' % (size / 1024))
print('  sha256 %s' % hashlib.sha256(out.encode('utf-8')).hexdigest()[:16])
print('=' * 74)
