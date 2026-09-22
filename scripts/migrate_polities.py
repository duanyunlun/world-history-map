#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S3 迁移：把散在三处的政权定义合并为「政权注册表」。

来源 → 去向：
  data/factions.json            factions{}            → sources/polities/china_modern.json
  data/neighbors.json           factions{}            → sources/polities/china_modern.json
  data/china_pre1893.json       factions{}            → sources/polities/china_ancient.json
  data/world_polities.json      人工条目               → sources/polities/world_major.json
  data/world_names.json         数据集拼写 → 中文      → sources/polities/world_alias.json

注册表条目：
  { id, zh, en?, aliases[], color?, from?, to?, capital?, summary?, sources[], scope }

  id 约定：中国势力用短 slug（对应控制数据里的键）；世界实体用 world/<slug> 命名空间，
  以免"日本占领军（中国境内）"与"日本（国家）"这类同名不同义被合并。

冲突不静默覆盖：同一 id 两处定义不同颜色/中文名、或同一别名被两个 id 占用，都会列出来。
用法：python3 scripts/migrate_polities.py [--write]
"""
import json, os, re, sys, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
OUT = os.path.join(DATA, 'sources', 'polities')
conflicts, notes = [], []

# 显式声明「同一实体」：中国势力 id ←→ 世界数据集拼写。
# 未列入者视为不同实体（如 japan=日本占领军 ≠ world/japan=日本国），各自独立。
EQUIV = {
    'qing': ['Qing Empire', 'Qing China', 'Qing'],
    'ming': ['Ming China', 'Ming Chinese Empire', 'Ming'],
    'han': ['Han', 'Han Empire'],
    'jinchao': ['Jin', 'Jin Dynasty'],
    'liao': ['Liao', 'Khitans'],
    'yuan': ['Yuan Dynasty', 'Yuan'],
    'song': ['Song Empire', 'Song'],
    'qin': ['Qin Dynasty', 'Qin Empire', 'Qin'],
    'sui': ['Sui Dynasty', 'Sui'],
    'tang': ['Tang Empire', 'Tang Dynasty'],
    'tibet': ['Tibet', 'Tibetans'],
    'xiongnu': ['Xiongnu'],
    'wei': ['Cao Wei', 'Wei'],
    'shu_han': ['Shu Han'],
    'wu_east': ['Eastern Wu', 'Wu'],
    'nanming': ['Southern Ming'],
    'zhungeer': ['Dzungar Khanate'],
    'tufan': ['Tibetan Empire'],
    'dali': ['Dali Kingdom', 'Dali'],
    'gaogouli': ['Goguryeo'],
    'bohai': ['Balhae'],
    'huihu': ['Uyghur Khaganate'],
    'nanzhao': ['Nanzhao'],
}
# 明确允许的“同名不同义”：世界别名与中国 id 同键属预期，不视为冲突
ALLOW_SAME_KEY = {'japan', 'jin'}   # 晋系军阀(jin) ≠ 金朝(jinchao)，但 id 与别名同键

# 同一国家/政权的不同时期：合并为一个实体（id），各时期作为 span。
# 这是“id 与年份绑定”的落地：id 稳定，span 携带该时段的名称/都城/简史/来源。
SPAN_GROUPS = {
    'world/germany': [
        ('German Empire', 1871, 1918, '德意志帝国'),
        ('Weimar Republic', 1919, 1933, '魏玛共和国'),
        ('Nazi Germany', 1933, 1945, '纳粹德国'),
        ('Germany (Prussia)', 1945, 1949, '德国（占领期）'),
        ('West Germany', 1949, 1990, '联邦德国（西德）'),
        ('Germany', 1990, 2026, '德国'),
    ],
    'world/russia': [
        ('Tsardom of Russia', 1547, 1721, '俄罗斯沙皇国'),
        ('Russian Empire', 1721, 1917, '俄罗斯帝国'),
        ('Soviet Union', 1922, 1991, '苏联'),
        ('Russia', 1991, 2026, '俄罗斯联邦'),
    ],
    'world/france': [
        ('France', 987, 1940, '法国'),
        ('Vichy France', 1940, 1944, '维希法国'),
        ('Free France', 1940, 1944, '自由法国'),
        ('France', 1944, 2026, '法兰西共和国'),
    ],
    'world/congo-kinshasa': [
        ('Congo Free State', 1885, 1908, '刚果自由邦'),
        ('Belgian Congo', 1908, 1960, '比属刚果'),
        ('Congo (Kinshasa)', 1960, 1971, '刚果共和国（利奥波德维尔）'),
        ('Zaire', 1971, 1997, '扎伊尔'),
        ('DR Congo', 1997, 2026, '刚果民主共和国'),
    ],
    'world/iran': [
        ('Persia (Qajar)', 1794, 1925, '波斯（卡扎尔王朝）'),
        ('Persia', 1925, 1935, '波斯'),
        ('Iran', 1935, 2026, '伊朗'),
    ],
    'world/turkey': [
        ('Ottoman Empire', 1299, 1922, '奥斯曼帝国'),
        ('Turkey', 1923, 2026, '土耳其共和国'),
    ],
    'world/ethiopia': [
        ('Abyssinia', 1270, 1941, '阿比西尼亚（埃塞俄比亚帝国）'),
        ('Ethiopia', 1941, 2026, '埃塞俄比亚'),
    ],
}


def rd(name):
    p = os.path.join(DATA, name)
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else None


def src_of(*urls):
    out = []
    for u in urls:
        if u:
            out.append(u if isinstance(u, str) else u)
    return out


def main():
    write = '--write' in sys.argv
    reg = {}          # id -> entry

    def put(eid, **kw):
        e = reg.setdefault(eid, {'id': eid, 'aliases': [], 'sources': []})
        for k, v in kw.items():
            if v in (None, '', []):
                continue
            if k == 'aliases':
                for a in v:
                    if a and a != eid and a not in e['aliases']:
                        e['aliases'].append(a)
            elif k == 'sources':
                for s in v:
                    if s and s not in e['sources']:
                        e['sources'].append(s)
            elif k == 'color':
                if e.get('color') and e['color'] != v:
                    conflicts.append('id=%s 颜色不一致：%s vs %s' % (eid, e['color'], v))
                e['color'] = v
            elif k == 'zh':
                if e.get('zh') and e['zh'] != v:
                    conflicts.append('id=%s 中文名不一致：%s vs %s' % (eid, e['zh'], v))
                e['zh'] = v
            else:
                e.setdefault(k, v)

    # ---- 1) 中国近现代（factions.json） ----
    f = rd('factions.json') or {}
    for kid, v in (f.get('factions') or {}).items():
        put(kid, zh=v.get('name'), color=v.get('color'), summary=v.get('desc'),
            scope='china-modern')
    # ---- 2) 周边国家（neighbors.json 的势力表） ----
    nb = rd('neighbors.json') or {}
    for kid, v in (nb.get('factions') or {}).items():
        if isinstance(v, dict):
            put(kid, zh=v.get('name'), color=v.get('color'), summary=v.get('desc'),
                scope='neighbor')
        else:
            put(kid, zh=str(v), scope='neighbor')
    # ---- 3) 1644 年前（china_pre1893.json） ----
    pre = rd('china_pre1893.json') or {}
    for kid, v in (pre.get('factions') or {}).items():
        put(kid, zh=v.get('name'), color=v.get('color'), scope='china-ancient')
    # ---- 4) 世界政权人工条目（world_polities.json，键为数据集拼写） ----
    wp = rd('world_polities.json') or {}
    for spelling, v in wp.items():
        eid = 'world/' + slug(spelling)          # 世界实体加命名空间，避免与中国势力同名（如 japan）
        put(eid, zh=v.get('zh'), en=spelling, aliases=[spelling],
            from_=v.get('from'), to_=v.get('to'), capital=v.get('capital'),
            summary=v.get('summary'), scope='world',
            sources=[s.get('u') if isinstance(s, dict) else s for s in (v.get('sources') or [])])
    # ---- 5) 世界译名表（world_names.json，键为数据集拼写） ----
    wn = rd('world_names.json') or {}
    alias_made = 0
    for spelling, zh in wn.items():
        eid = 'world/' + slug(spelling)
        if eid in reg:
            put(eid, aliases=[spelling])
        else:
            put(eid, zh=zh, en=spelling, aliases=[spelling], scope='world-alias')
            e = reg[eid]
            e['sources'] = ['https://cn.bing.com/search?q=' + quote(spelling)]
            alias_made += 1

    # ---- 等同合并：把世界拼写挂到中国实体上（同一实体只留一条） ----
    merged = 0
    for cid, spellings in EQUIV.items():
        for spelling in ([spellings] if isinstance(spellings, str) else spellings):
            wid = 'world/' + slug(spelling)
            if cid in reg and wid in reg:
                w = reg.pop(wid)
                put(cid, aliases=[spelling] + w.get('aliases', []),
                    en=w.get('en') or spelling, summary=w.get('summary'),
                    from_=w.get('from'), to_=w.get('to'), capital=w.get('capital'),
                    sources=w.get('sources'))
                merged += 1
    notes.append('等同合并 %d 组（中国势力与世界拼写指向同一实体）' % merged)

    # ---- 时段化：同一实体的多个 span（id 与年份绑定） ----
    span_made = 0
    for eid, spans in SPAN_GROUPS.items():
        parts = []
        for spelling, a, b, zh in spans:
            wid = 'world/' + slug(spelling)
            src = reg.pop(wid, None)
            parts.append({
                'from': a, 'to': b, 'zh': zh,
                'capital': (src or {}).get('capital') or (src or {}).get('capital', ''),
                'summary': (src or {}).get('summary', ''),
                'sources': (src or {}).get('sources', []),
                'alias': spelling,
            })
            span_made += 1
        reg[eid] = {'id': eid, 'zh': parts[-1]['zh'], 'en': spans[-1][0],
                    'aliases': [x[0] for x in spans], 'scope': 'world-spans',
                    'spans': parts,
                    'sources': [u for p2 in parts for u in (p2.get('sources') or [])][:3]}
    notes.append('时段化 %d 组、%d 个时段（同一 id 对应不同时期的名称）' % (len(SPAN_GROUPS), span_made))

    # 其余单时段条目：把顶层 from/to 规范化为一个 span
    for e in reg.values():
        if 'spans' not in e and ('from' in e or 'to' in e):
            e['spans'] = [{'from': e.get('from'), 'to': e.get('to'),
                           'zh': e.get('zh'), 'capital': e.get('capital', ''),
                           'summary': e.get('summary', ''), 'sources': e.get('sources', [])}]

    # ---- 别名唯一性 ----
    owner = {}
    for e in reg.values():
        for a in [e['id']] + e.get('aliases', []):
            key = a.lower()
            if key in owner and owner[key] != e['id']:
                if key in ALLOW_SAME_KEY:
                    notes.append('同名不同义（预期）：%r 分属 %s 与 %s'
                                 % (a, owner[key], e['id']))
                    continue
                conflicts.append('别名重复：%r 同时属于 %s 与 %s' % (a, owner[key], e['id']))
            owner[key] = e['id']

    # ---- 引用完整性：控制数据里的 id 必须在注册表里 ----
    used = set()
    for prov, seqs in (f.get('provinces') or {}).items():
        for s in seqs:
            if s.get('faction'):
                used.add(s['faction'])
    for y, arr in (f.get('monthOverride') or {}).items():
        for it in arr:
            if len(it) >= 3:
                used.add(it[2])
    for er in (pre.get('eras') or []):
        for seq in (er.get('timeline') or {}).values():
            for it in seq:
                used.add(it[1])
        used.update((er.get('preFaction') or {}).values())
        if er.get('faction'):
            used.add(er['faction'])
    used.discard(None)
    missing = sorted(x for x in used if x not in reg)

    # ---- 按 scope 分文件输出 ----
    groups = collections.defaultdict(list)
    for e in reg.values():
        groups[e['scope']].append(e)
    if write:
        os.makedirs(OUT, exist_ok=True)
        for scope, entries in groups.items():
            entries.sort(key=lambda x: x['id'])
            for e in entries:                      # from_/to_ → from/to
                if 'from_' in e: e['from'] = e.pop('from_')
                if 'to_' in e: e['to'] = e.pop('to_')
            fn = os.path.join(OUT, scope.replace('-', '_') + '.json')
            json.dump({'schema': 'polities/1', 'scope': scope, 'entries': entries},
                      open(fn, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            print('  写入 %-34s %4d 条' % (os.path.relpath(fn, ROOT), len(entries)))

    print('政权注册表：%d 条（%s）' % (len(reg), '、'.join('%s %d' % kv for kv in sorted(
        (k, len(v)) for k, v in groups.items()))))
    print('  控制数据引用的 id：%d 个，注册表缺失 %d 个%s'
          % (len(used), len(missing), ('：' + '、'.join(missing[:12])) if missing else ''))
    for m in notes:
        print('  说明：%s' % m)
    if conflicts:
        print('  ✗ 冲突 %d 条：' % len(conflicts))
        for m in conflicts[:20]:
            print('    - %s' % m)
        sys.exit(1)
    print('  ✓ 无冲突')


def slug(s):
    """数据集拼写 → 稳定 id：小写、去括号内容、非字母数字转连字符。"""
    s = re.sub(r'\([^)]*\)', '', s).strip()
    s = s.lower().replace('&', ' and ')
    s = re.sub(r"[^a-z0-9\u4e00-\u9fa5]+", '-', s).strip('-')
    return s or 'unknown'


def quote(s):
    import urllib.parse
    return urllib.parse.quote(s)


if __name__ == '__main__':
    main()
