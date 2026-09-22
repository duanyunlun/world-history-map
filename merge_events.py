#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
合并 data/events_parts/*.json 的分组事件数据 -> data/events.json
包含：字段校验、来源校验、跨组去重、年份/地域覆盖统计、质量报表。
"""
import json, os, re, glob, sys, difflib, collections

ROOT = os.path.dirname(os.path.abspath(__file__))
PARTS = os.path.join(ROOT, 'data', 'events_parts')
OUT = os.path.join(ROOT, 'data', 'events.json')
Y0, Y1 = 1893, 1976
PROVS = ['北京', '天津', '河北', '山西', '内蒙古', '辽宁', '吉林', '黑龙江', '上海', '江苏', '浙江',
         '安徽', '福建', '江西', '山东', '河南', '湖北', '湖南', '广东', '广西', '海南', '重庆',
         '四川', '贵州', '云南', '西藏', '陕西', '甘肃', '青海', '宁夏', '新疆', '台湾', '香港', '澳门']
CATS = ['战争', '政治', '外交', '经济', '文化', '科技', '灾害', '社会']
ALIAS = {'军事': '战争', '抗战': '战争', '革命': '政治', '政权': '政治', '民族': '政治',
         '教育': '文化', '卫生': '社会', '科学': '科技', '工程': '科技', '灾难': '灾害',
         '自然': '灾害', '抗灾': '灾害', '金融': '经济', '工业': '经济', '农业': '经济'}
SUFFIX = re.compile(r'(省|市|自治区|特别行政区|壮族|回族|维吾尔|自治州)$')

GROUP_RANGE = {
    'p1_1893_1905': (1893, 1905), 'p2_1906_1919': (1906, 1919),
    'p3_1920_1929': (1920, 1929), 'p4_1930_1936': (1930, 1936),
    'p5_1937_1945': (1937, 1945), 'p6_1946_1949': (1946, 1949),
    'p7_1950_1958': (1950, 1958), 'p8_1959_1976': (1959, 1976),
}

ERRS, WARNS = [], []


def norm_title(t):
    t = re.sub(r'[（(【\[].*?[）)】\]]', '', t or '')
    return re.sub(r'[\s·、，,。：:—\-－·"“”\'’。！!？?]', '', t)


def sim(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()


def norm_prov(p):
    p = SUFFIX.sub('', str(p).strip())
    return {'内蒙': '内蒙古', '西藏自治': '西藏', '广西壮族': '广西'}.get(p, p)


files = sorted(glob.glob(os.path.join(PARTS, '*.json')))
if not files:
    print('!! data/events_parts/ 下没有任何分组文件'); sys.exit(1)

# 载入现有 events.json 作为底稿：仅用于保留 deep 等非分片字段
_baseline = {}
if os.path.exists(OUT):
    try:
        _b = json.load(open(OUT, encoding='utf-8'))
        for _e in (_b.get('events') if isinstance(_b, dict) else _b):
            _baseline[( _e.get('year'), norm_title(_e.get('title', '')) )] = _e
    except Exception as ex:
        print('  （底稿读取失败，忽略：%s）' % ex)

groups, all_ev = {}, []
for fp in files:
    name = os.path.splitext(os.path.basename(fp))[0]
    try:
        raw = json.load(open(fp, encoding='utf-8'))
    except Exception as e:
        ERRS.append('%s JSON 解析失败: %s' % (name, e)); continue
    evs = raw['events'] if isinstance(raw, dict) else raw
    lo, hi = GROUP_RANGE.get(name, (Y0, Y1))
    good = []
    for e in evs:
        t = e.get('title')
        y = e.get('year')
        if not isinstance(y, int) or not (Y0 <= y <= Y1):
            ERRS.append('%s 年份非法 %r (%r)' % (name, y, t)); continue
        if not (lo <= y <= hi):
            WARNS.append('%s 事件 %d《%s》越出本组区间 %d-%d' % (name, y, t, lo, hi))
        if not t:
            ERRS.append('%s 缺标题' % name); continue
        c = ALIAS.get((e.get('category') or '').strip(), (e.get('category') or '').strip())
        if c not in CATS:
            WARNS.append('%s《%s》类别 %r -> 政治' % (name, t, e.get('category'))); c = '政治'
        e['category'] = c
        ps = e.get('provinces') or []
        if isinstance(ps, str):
            ps = re.split(r'[、,，/｜| ]+', ps)
        ps = [q for q in dict.fromkeys(norm_prov(x) for x in ps)]
        bad = [q for q in ps if q not in PROVS]
        if bad:
            WARNS.append('%s《%s》省份未识别 %s' % (name, t, bad))
        ps = [q for q in ps if q in PROVS]
        if not ps:
            ERRS.append('%s《%s》无有效省份' % (name, t))
        e['provinces'] = ps
        ss = e.get('sources') or []
        if isinstance(ss, dict):
            ss = [ss]
        ss2 = []
        for s in ss:
            if isinstance(s, str):
                s = {'t': s, 'u': s}
            u = str(s.get('u') or '').strip()
            tt = str(s.get('t') or '').strip() or u
            if not re.match(r'^https?://', u):
                ERRS.append('%s《%s》来源链接非法: %r' % (name, t, u)); continue
            if ' ' in u or 'example.com' in u:
                ERRS.append('%s《%s》来源链接可疑: %r' % (name, t, u)); continue
            ss2.append({'t': tt[:60], 'u': u})
        if not ss2:
            ERRS.append('%s《%s》缺少来源' % (name, t))
        e['sources'] = ss2[:3]
        e['importance'] = int(e.get('importance') or 2)
        e['summary'] = e.get('summary') or ''
        e['detail'] = e.get('detail') or ''
        e['date'] = e.get('date') or ('%d年' % y)
        e['tags'] = e.get('tags') or []
        if len(e['detail']) < 60:
            WARNS.append('%s《%s》detail 过短(%d字)' % (name, t, len(e['detail'])))
        _old = _baseline.get((e['year'], norm_title(e['title'])))
        if _old and _old.get('deep'):
            e['deep'] = _old['deep']
        good.append(e)
    groups[name] = good
    all_ev.extend(good)
    print('  %-18s %3d 条' % (name, len(good)))

all_ev.sort(key=lambda x: (x['year'], x.get('date', ''), -x.get('importance', 2)))
kept, dropped = [], 0
for e in all_ev:
    ne = norm_title(e['title'])
    dup = None
    for k in kept:
        if abs(k['year'] - e['year']) > 1:
            continue
        nk = norm_title(k['title'])
        if nk == ne or (len(ne) > 3 and (ne in nk or nk in ne)) or sim(ne, nk) >= 0.86:
            dup = k; break
    if dup:
        dropped += 1
        if len(e['detail']) > len(dup['detail']): dup['detail'] = e['detail']
        if len(e['summary']) > len(dup['summary']): dup['summary'] = e['summary']
        for p in e['provinces']:
            if p not in dup['provinces']: dup['provinces'].append(p)
        for s in e['sources']:
            if s['u'] not in [x['u'] for x in dup['sources']] and len(dup['sources']) < 3:
                dup['sources'].append(s)
        for t in e['tags']:
            if t not in dup['tags']: dup['tags'].append(t)
        dup['importance'] = max(dup['importance'], e['importance'])
    else:
        kept.append(e)

ys = collections.Counter(e['year'] for e in kept)
missing = [y for y in range(Y0, Y1 + 1) if not ys[y]]
thin = [y for y in range(Y0, Y1 + 1) if 0 < ys[y] <= 1]
pset = collections.Counter(p for e in kept for p in e['provinces'])
cat = collections.Counter(e['category'] for e in kept)
srcs = collections.Counter(s['u'] for e in kept for s in e['sources'])
src_host = collections.Counter(re.sub(r'^https?://([^/]+).*$', r'\1', u) for u in srcs)
with_src = sum(1 for e in kept if e['sources'])
avg_len = sum(len(e['detail']) for e in kept) / max(1, len(kept))

print('-' * 74)
print('  合并结果：%d 条（原始 %d，去重 %d）' % (len(kept), len(all_ev), dropped))
print('  年份覆盖：%d—%d ｜ 空白 %d 年 ｜ 仅 1 条的年份 %d 个' % (Y0, Y1, len(missing), len(thin)))
if missing:
    print('    空白年份: %s' % ','.join(map(str, missing)))
if thin:
    print('    偏薄年份: %s' % ','.join(map(str, thin)))
print('  分类分布：%s' % json.dumps(dict(cat), ensure_ascii=False))
print('  有来源标注：%d/%d ｜ 不同来源链接 %d 个 ｜ detail 平均 %d 字'
      % (with_src, len(kept), len(srcs), avg_len))
print('  来源域名 Top: %s' % ', '.join('%s(%d)' % kv for kv in src_host.most_common(6)))
uncovered = [p for p in PROVS if pset[p] == 0]
print('  省份覆盖：%d/%d ｜ 未覆盖 %s' % (len(PROVS) - len(uncovered), len(PROVS), uncovered or '无'))
print('  覆盖最少 8 省：%s' % ' '.join('%s%d' % (p, pset[p]) for p in sorted(PROVS, key=lambda x: pset[x])[:8]))
if WARNS:
    print('  ⚠ 警告 %d 条（前 10）' % len(WARNS))
    for w in WARNS[:10]: print('     · ' + w)
if ERRS:
    print('  ✗ 错误 %d 条（前 20）' % len(ERRS))
    for x in ERRS[:20]: print('     · ' + x)
    print('  ** 存在错误，未写出 **'); sys.exit(1)
json.dump({'events': kept}, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('  ✓ 已写出 data/events.json（%d 条，%.0f KB）' % (len(kept), os.path.getsize(OUT) / 1024))
print('-' * 74)
