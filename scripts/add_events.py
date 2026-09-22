#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量补录世界事件的通用入口：去重（批内 + 与既有）并强制校验。

用法：在被调用的脚本里 `from add_events import commit`，或在命令行把候选 JSON 传入：
    python3 scripts/add_events.py candidates.json
候选 JSON 格式：[{"year":…, "month":…, "title":…, "place":…, "lat":…, "lon":…,
                 "category":…, "importance":…, "summary":…, "sources":[{"t":…,"u":…}]}]
之所以集中处理：此前多次出现「批内重复」「参数写错整批未写入」等问题。
"""
import json, os, sys, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, 'data', 'world_events.json')


def commit(cands, check=True):
    d = json.load(open(P, encoding='utf-8'))
    ev = d['events']
    seen = {(e['year'], e['title']): i for i, e in enumerate(ev)}
    added = 0
    for c in cands:
        k = (c['year'], c['title'])
        if k in seen:
            i = seen[k]
            if len(c.get('summary') or '') > len(ev[i].get('summary') or ''):
                ev[i] = c
            continue
        seen[k] = len(ev)
        ev.append(c)
        added += 1
    ev.sort(key=lambda e: (e['year'], e['month'] or 1))
    d['meta']['count'] = len(ev)
    json.dump(d, open(P, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('候选 %d 条，写入 %d 条，合计 %d 条' % (len(cands), added, len(ev)))
    if check:
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', 'check_data.py')],
                           capture_output=True, text=True)
        print(r.stdout.strip().splitlines()[0] if r.stdout else '')
        if r.returncode != 0:
            print(r.stdout[-800:])
            raise SystemExit('校验未通过')
    return added


if __name__ == '__main__':
    cands = json.load(open(sys.argv[1], encoding='utf-8'))
    commit(cands)
