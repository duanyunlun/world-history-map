#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S4 迁移：把中国「时期 / 政区 / 控制序列」统一为每朝一个源文件。

现状（三处、隐式关联）：
  data/historical_units.json  periods[]  —— 时期的政区（名称映射/合并/注释），月级
  data/china_pre1893.json     eras[]     —— 1644 年前各朝的控制序列，年级
  data/factions.json          provinces  —— 1893—1976 的控制表，年级 + 月级切点

去向（一处、显式关联、月级锚点）：
  data/sources/periods/<id>.json    每朝一个文件：时段(from/to 到月) + 政区 + 控制 + 来源
  data/sources/control/china_monthly.json  1893—1976 的逐月控制表（数据量大，单独放）

时段模型（与政权注册表一致）：**id 稳定，时段携带该时期的名称与规则**；
月级锚点写成 {"y": 1644, "m": 1}，将来要精确到月只改字段、不动 id。

用法：python3 scripts/migrate_periods.py [--write]
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
OUT_P = os.path.join(DATA, 'sources', 'periods')
OUT_C = os.path.join(DATA, 'sources', 'control')
errors, notes = [], []


def rd(name):
    p = os.path.join(DATA, name)
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else None


def mi(y, m):
    return y * 12 + (m - 1)


def pid(label):
    s = re.sub(r'[^0-9A-Za-z\u4e00-\u9fa5]+', '-', label).strip('-')
    return 'period/' + s


SRC = ['https://baike.baidu.com/item/' + q for q in
       ('中国行政区划史', '清朝行政区划', '中华民国行政区划', '中华人民共和国行政区划')]


def main():
    write = '--write' in sys.argv
    hu = rd('historical_units.json') or {}
    pre = rd('china_pre1893.json') or {}
    periods = hu.get('periods') or []
    eras = pre.get('eras') or []

    # ---- 控制序列：按年份区间建索引，便于挂到时期上 ----
    # 现代（1893 起）由 factions.json 提供，单独成文件，不重复塞进每个时期
    progs = []
    for e in eras:
        tl = dict(e.get('timeline') or {})
        # 老形态（明/清）：entryYear + preFaction → 合成为 timeline
        ey = e.get('entryYear') or {}
        if ey and not tl:
            for prov, yr in ey.items():
                if yr is None:
                    continue
                seq = []
                pre = (e.get('preFaction') or {}).get(prov)
                if pre and (yr < 0 or yr > e['from']):
                    seq.append([e['from'], pre])
                if yr > 0:
                    if not seq or seq[-1][0] != yr:
                        seq.append([yr, e.get('faction')])
                elif not seq:
                    seq.append([e['from'], e.get('faction')])
                tl[prov] = seq
            notes.append('朝代「%s」由 entryYear 合成 timeline（%d 省）' % (e['name'], len(tl)))
        progs.append({'name': e['name'], 'a': e['from'], 'b': e['to'],
                      'faction': e.get('faction'), 'timeline': tl,
                      'preFaction': e.get('preFaction') or {},
                      'preName': e.get('preName') or {}, 'note': e.get('note') or {},
                      'approx': e.get('approx', '')})

    out = []
    for p in periods:
        fy, fm = p['from']
        ty, tm = p['to']
        a, b = mi(fy, fm), mi(ty, tm)
        # 取与本期重叠最多的朝代控制段（避免 1 年边界重叠导致挂错）
        hit = []
        for q in progs:
            qa, qb = q['a'] * 12, q['b'] * 12 + 11
            ov = min(b, qb) - max(a, qa) + 1
            if ov > 0:
                hit.append((ov, q))
        hit.sort(key=lambda z: -z[0])
        ctrl = None
        if hit:
            q = hit[0][1]
            ctrl = {'source': 'era:%s' % q['name'], 'faction': q.get('faction'),
                    'timeline': q['timeline'],
                    'preFaction': q['preFaction'], 'preName': q['preName'],
                    'approx': q['approx']}
        out.append({
            'schema': 'periods/1',
            'id': pid(p['label']),
            'label': p['label'],
            'from': {'y': fy, 'm': fm},
            'to': {'y': ty, 'm': tm},
            'note': p.get('note', ''),
            'sources': SRC,
            'divisions': {
                'rename': p.get('provinceRename') or {},
                'merge': p.get('merge') or {},
                'units': p.get('units') or [],
            },
            **({'control': ctrl} if ctrl else {}),
        })

    # ---- 校验：月级不重叠、连续覆盖 ----
    out.sort(key=lambda x: mi(x['from']['y'], x['from']['m']))
    gaps, overlaps = [], []
    for i, q in enumerate(out):
        if q['to']['m'] > 12 or q['from']['m'] > 12:
            errors.append('%s 月份越界' % q['id'])
        if mi(q['to']['y'], q['to']['m']) < mi(q['from']['y'], q['from']['m']):
            errors.append('%s 起止倒置' % q['id'])
        if i:
            prev = out[i - 1]
            pm = mi(prev['to']['y'], prev['to']['m'])
            cm = mi(q['from']['y'], q['from']['m'])
            if cm <= pm:
                overlaps.append('%s 与 %s 重叠' % (prev['label'], q['label']))
            elif cm > pm + 1:
                gaps.append('%s → %s 缺 %d 个月' % (prev['label'], q['label'], cm - pm - 1))
        if not q['sources']:
            errors.append('%s 缺来源' % q['id'])
    notes.append('时期 %d 个，覆盖 %s — %s' % (
        len(out), out[0]['label'] if out else '—', out[-1]['label'] if out else '—'))
    if overlaps:
        for m in overlaps:
            errors.append('时段重叠：' + m)
    if gaps:
        notes.append('时段缺口 %d 处（多为旧石器至商周之间的空档）：%s' % (len(gaps), '；'.join(gaps[:3])))

    # ---- 1893—1976 逐月控制表单独落盘 ----
    f = rd('factions.json') or {}
    monthly = {
        'schema': 'control/1',
        'id': 'control/china-monthly-1893-1976',
        'note': '中国 1893—1976 省级控制表：逐年区间 + 月级切点（monthOverride）。'
                '前端按 MI=year*12+month-1 查表，逐月无缺口。',
        'sources': SRC,
        'provinces': f.get('provinces') or {},
        'monthOverride': f.get('monthOverride') or {},
        'factionsLegacy': list((f.get('factions') or {}).keys()),
    }

    if write:
        os.makedirs(OUT_P, exist_ok=True)
        os.makedirs(OUT_C, exist_ok=True)
        for q in out:
            fn = os.path.join(OUT_P, q['id'].split('/', 1)[1] + '.json')
            json.dump(q, open(fn, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        json.dump(monthly, open(os.path.join(OUT_C, 'china_monthly.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print('  写入 %s/  %d 个时期文件' % (os.path.relpath(OUT_P, ROOT), len(out)))
        print('  写入 %s/china_monthly.json（%d 省控制表）'
              % (os.path.relpath(OUT_C, ROOT), len(monthly['provinces'])))

    withctl = sum(1 for q in out if q.get('control'))
    print('时期：%d 个（%d 个带控制序列）；月级锚点全覆盖' % (len(out), withctl))
    for m in notes:
        print('  说明：%s' % m)
    if errors:
        print('  ✗ 错误 %d 条：' % len(errors))
        for m in errors[:12]:
            print('    - %s' % m)
        sys.exit(1)
    print('  ✓ 校验通过')


if __name__ == '__main__':
    main()
