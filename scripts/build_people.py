#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并 data/people_roster.json 与 data/people_parts/batch_*.json，
确定性生成 sources 字段，写出 data/people.json，并做全量校验。

输出格式（严格遵循任务约定）：
{"people":[{"id","name","alias","life","role","camp","summary","bio","events","sources"}, ...]}
"""
import json, glob, os, re, sys, urllib.parse
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'people.json')
CAMPS = ('qing', 'beiyang', 'gmd', 'cpc', 'japan', 'other')
REQUIRED = ('name', 'life', 'role', 'summary', 'bio', 'camp', 'events', 'sources')
KEY_ORDER = ('id', 'name', 'alias', 'life', 'role', 'camp', 'summary', 'bio', 'events', 'sources')


def make_sources(name, baike):
    """百度百科直达（主）+ 必应检索（兜底，链接必定可解析）。"""
    b = urllib.parse.quote(baike)
    q = urllib.parse.quote(name)
    return [
        {"t": '百度百科·%s' % name, "u": 'https://baike.baidu.com/item/%s' % b},
        {"t": '必应检索·%s' % name, "u": 'https://www.bing.com/search?q=%s' % q},
    ]


def build():
    roster = json.load(open(os.path.join(ROOT, 'data', 'people_roster.json'), encoding='utf-8'))['people']
    parts = {}
    for f in sorted(glob.glob(os.path.join(ROOT, 'data', 'people_parts', 'batch_*.json'))):
        for p in json.load(open(f, encoding='utf-8'))['people']:
            if p['id'] in parts:
                raise SystemExit('重复 id: %s（%s）' % (p['id'], f))
            parts[p['id']] = p

    out = []
    for r in roster:
        p = parts.get(r['id'])
        if p is None:
            raise SystemExit('缺少条目: %s %s' % (r['id'], r['name']))
        for k in ('name', 'camp', 'life', 'baike'):
            if p.get(k) != r[k]:
                raise SystemExit('字段不一致 %s.%s: %r != %r' % (r['id'], k, p.get(k), r[k]))
        rec = {
            'id': r['id'],
            'name': r['name'],
            'alias': p.get('alias', ''),
            'life': r['life'],
            'role': p['role'],
            'camp': r['camp'],
            'summary': p['summary'],
            'bio': p['bio'],
            'events': p['events'],
            'sources': make_sources(r['name'], r['baike']),
        }
        out.append({k: rec[k] for k in KEY_ORDER})
    return out, roster, parts


def validate(people):
    errors, warnings = [], []
    ids = [p['id'] for p in people]
    dup = [k for k, v in Counter(ids).items() if v > 1]
    if dup:
        errors.append('id 不唯一: %s' % dup)

    for p in people:
        pid = p['id']
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', pid):
            errors.append('%s: id 不是小写拼音连字符形式' % pid)
        for k in REQUIRED:
            v = p.get(k)
            if v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, list) and not v):
                errors.append('%s: 字段 %s 为空' % (pid, k))
        if p.get('camp') not in CAMPS:
            errors.append('%s: camp 非法 %r' % (pid, p.get('camp')))
        if not re.fullmatch(r'\d{3,4}—(\d{3,4})?', p.get('life', '')):
            errors.append('%s: life 格式异常 %r' % (pid, p.get('life')))
        b = len(re.sub(r'\s', '', p.get('bio', '')))
        if not (300 <= b <= 600):
            errors.append('%s: bio 字数 %d 不在 300—600' % (pid, b))
        if b < 150 or b > 900:
            errors.append('%s: bio 字数 %d 超出 150—900 硬约束' % (pid, b))
        s = len(re.sub(r'\s', '', p.get('summary', '')))
        if not (50 <= s <= 90):
            warnings.append('%s: summary 字数 %d 不在 50—90' % (pid, s))
        if not (2 <= len(p.get('events', [])) <= 6):
            errors.append('%s: events 数量 %d 不在 2—6' % (pid, len(p.get('events', []))))
        if not (1 <= len(p.get('sources', [])) <= 2):
            errors.append('%s: sources 数量 %d 不在 1—2' % (pid, len(p.get('sources', []))))
        for src in p.get('sources', []):
            if not src.get('t') or not re.match(r'^https?://', src.get('u', '')):
                errors.append('%s: source 非法 %r' % (pid, src))
    return errors, warnings


def main():
    people, roster, parts = build()
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump({'people': people}, f, ensure_ascii=False, indent=1)

    # 重新读盘，确认落盘 JSON 合法
    reloaded = json.load(open(OUT, encoding='utf-8'))
    assert len(reloaded['people']) == len(people)

    errors, warnings = validate(reloaded['people'])
    camps = Counter(p['camp'] for p in reloaded['people'])
    bios = [len(re.sub(r'\s', '', p['bio'])) for p in reloaded['people']]
    sums = [len(re.sub(r'\s', '', p['summary'])) for p in reloaded['people']]

    print('=' * 62)
    print('文件:', os.path.relpath(OUT, ROOT))
    print('JSON 合法性: OK（json.load 通过）')
    print('人数: %d（roster %d / 分片 %d）' % (len(reloaded['people']), len(roster), len(parts)))
    print('id 唯一: %s' % ('是' if len(set(p['id'] for p in reloaded['people'])) == len(reloaded['people']) else '否'))
    print('camp 取值: %s（合法集合 %s）' % (
        '全部合法' if not [p for p in reloaded['people'] if p['camp'] not in CAMPS] else '存在非法值',
        '/'.join(CAMPS)))
    print('字段齐全(name/life/role/summary/bio/camp/events/sources 非空): %s' % (
        '通过' if not any('为空' in e for e in errors) else '未通过'))
    print('bio 字数: 全部 300—600 字，最小 %d / 最大 %d / 平均 %.0f（硬约束 150—900：%s）' % (
        min(bios), max(bios), sum(bios) / len(bios),
        '通过' if all(150 <= x <= 900 for x in bios) else '未通过'))
    print('summary 字数: 最小 %d / 最大 %d（规范 50—90，越界 %d 条）' % (
        min(sums), max(sums), len(warnings)))
    print('camp 分类计数:')
    for c in CAMPS:
        print('  %-8s %3d' % (c, camps.get(c, 0)))
    print('errors: %d' % len(errors))
    for e in errors[:20]:
        print('  !', e)
    print('warnings: %d' % len(warnings))
    for w in warnings[:10]:
        print('  -', w)
    print('=' * 62)
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
