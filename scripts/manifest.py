#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据清单（manifest）：给 data/ 下每个文件定性，并核对代码里的读写关系。

为什么需要：本项目曾多次出现「改了源数据却没重跑构建」「缓存/产物被当成源数据编辑」
「删了一个以为没用的文件导致构建失败」。这些都不是数据问题，而是**职责边界没有记录**。

角色定义（role）：
  source  人工维护的史料/注册表，是唯一真相，进 git，可编辑
  cache   从外部抓取的原始数据，不进 git，可重新下载，**只读**
  build   脚本生成的产物，不进 git，可重建，**禁止手改**
  legacy  历史遗留，当前链路不再使用（保留待清理）

用法：
  python3 scripts/manifest.py            # 校验（默认）
  python3 scripts/manifest.py --write    # 重新生成 data/manifest.json
  python3 scripts/manifest.py --list     # 打印清单
"""
import json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
OUT = os.path.join(DATA, 'manifest.json')

# ---------------------------------------------------------------- 角色声明
# 角色由人声明（这是本文件的核心信息），写入者/读取者由代码扫描得出并核对。
ROLES = {
    # —— 源数据（可编辑） ——
    'events.json': ('source', '中国事件 1893—1976（931 件，逐月）'),
    'events_deep': ('source', '中国事件深度资料（时间线/影响/人物）'),
    'people.json': ('source', '人物生平（230 人）'),
    'people_roster.json': ('source', '人物名录（校验用）'),
    'factions.json': ('source', '中国近现代势力：逐年区间 + 月级切点 + 省级归属'),
    'territories.json': ('source', '跨省割据区/根据地（按县）'),
    'neighbors.json': ('source', '周边国家 1893—1976 政权归属'),
    'historical_units.json': ('source', '中国历史时期省级区划（时分/名称/合并/来源）'),
    'china_pre1893.json': ('source', '1644 年前各朝代控制序列与政权'),
    'world_events.json': ('source', '世界事件（1111 件）'),
    'world_polities.json': ('source', '政权人工条目（简史/都城/来源）'),
    'world_names.json': ('source', '政体名中文译名表'),
    'nine_dash.example.json': ('source', '九段线矢量接口模板（非真实界线）'),
    # —— 政权注册表（S3，唯一真相：id + 别名 + 颜色 + 存续 + 都城 + 简史 + 来源） ——
    'sources': ('source', '源数据根目录（polities/ 政权注册表等；后续 periods/ 亦在此）'),
    # —— 源数据的分片目录（人工/半自动维护，构建时合并） ——
    'events_parts': ('source', '中国事件分片（按时期切分，构建时合并入 events.json）'),
    'people_parts': ('source', '人物生平分片（批量维护，构建时合并入 people.json）'),
    # —— 缓存（只读，可重下） ——
    '_county_cache': ('cache', '县级边界抓取缓存（412 个分片）'),
    'ne_110m_countries.geojson': ('cache', 'Natural Earth 110m 国界原始数据'),
    'ne_50m_countries.geojson': ('cache', 'Natural Earth 50m 国界原始数据'),
    '_world_cache': ('cache', 'historical-basemaps 原始切片（68 MB）'),
    '_cshapes': ('cache', 'CShapes 2.0 原始 GeoJSON（26 MB）'),
    '_county_raw_index.json': ('cache', '县级原始文件索引（由 build_geo 生成，可重建）'),
    'counties_all.json': ('cache', '全国县级边界原始抓取结果（2863 县）'),
    'china_provinces_raw.json': ('cache', '省级边界原始抓取结果'),
    # —— 产物（禁止手改） ——
    'geo.json': ('build', '中国几何包（省/县/割据区/历史形状，压缩后）', 'build_geo.py'),
    'world.json': ('build', '世界切片与几何池（180 切片 / 4846 几何）', 'build_world.py'),
    'counties.json': ('build', '割据区用县级边界', 'build_geo.py'),
    'china_provinces_simplified.json': ('build', '投影后的省级边界', 'scripts/make_provinces.py'),
    # —— 遗留 ——
    'events.subagent.json': ('legacy', '早期子代理产出的事件批次（已并入 events.json）'),
    'baike_verify.json': ('legacy', '百科校订记录（一次性核查）'),
}

CODE_GLOBS = ['build.py', 'build_geo.py', 'build_world.py', 'release.py']
CODE_DIRS = ['scripts', 'src', 'tests']

errors, warns = [], []


def code_files():
    out = []
    for f in CODE_GLOBS:
        p = os.path.join(ROOT, f)
        if os.path.exists(p):
            out.append(p)
    for d in CODE_DIRS:
        dd = os.path.join(ROOT, d)
        if not os.path.isdir(dd):
            continue
        for fn in sorted(os.listdir(dd)):
            if fn.endswith(('.py', '.js', '.html', '.sh')):
                out.append(os.path.join(dd, fn))
    return out


def scan_usage(name):
    """返回 (writers, readers)。按“行”判断，避免跨行误判（曾把只读当成写入）。"""
    writers, readers = set(), set()
    stem = name[:-5] if name.endswith('.json') else name
    for p in code_files():
        try:
            lines = open(p, encoding='utf-8', errors='ignore').read().split('\n')
        except Exception:
            continue
        rel = os.path.relpath(p, ROOT)
        hit = False
        for i, ln in enumerate(lines):
            if stem not in ln and name not in ln:
                continue
            hit = True
            win = '\n'.join(lines[max(0, i - 2):i + 3])
            if re.search(r"(json\.dump|write_text|f\.write|\.writelines)", win) and re.search(r"'w'|\"w\"", win):
                writers.add(rel)
            elif re.search(r"open\([^)]*'w'", win):
                writers.add(rel)
            else:
                readers.add(rel)
        if hit and rel in writers and rel in readers:
            readers.discard(rel)          # 同一文件里既出现在读处也出现在写处：以写为准
    return sorted(writers), sorted(readers)


def actual_files():
    """data/ 下应当出现在清单里的条目（目录按顶层目录名记录）。"""
    out = {}
    for e in sorted(os.listdir(DATA)):
        p = os.path.join(DATA, e)
        if e == 'manifest.json':
            continue
        if os.path.isdir(p):
            out[e] = sum(len(fs) for _, _, fs in os.walk(p))
        else:
            out[e] = 1
    return out


def check():
    files = actual_files()
    # 1) 磁盘 → 清单
    for name in files:
        if name not in ROLES:
            errors.append('未定性：data/%s（请在 scripts/manifest.py 的 ROLES 里声明角色）' % name)
    # 2) 清单 → 磁盘
    for name, spec in ROLES.items():
        role = spec[0]
        if name not in files:
            errors.append('清单中的 data/%s 不存在（应删除该条或恢复文件）' % name)
    # 3) 角色与代码行为一致性
    rows = []
    for name, spec in sorted(ROLES.items()):
        if name not in files:
            continue
        role, note = spec[0], spec[1]
        declared_writer = spec[2] if len(spec) > 2 else None
        writers, readers = scan_usage(name)
        if declared_writer:
            writers = sorted(set(writers) | {declared_writer})
        if role == 'source':
            bad = [w for w in writers if not w.startswith('scripts/') or 'rebuild' in w or 'fetch' in w]
            if bad:
                errors.append('源文件 data/%s 被构建脚本写入：%s（源数据只能人工维护）'
                              % (name, '、'.join(bad)))
        if role == 'build' and not writers:
            warns.append('标为产物的 data/%s 找不到写入它的脚本（可能已废弃）' % name)
        if role == 'cache' and writers:
            warns.append('标为缓存的 data/%s 会被 %s 写入（确认这是缓存重建而非源数据覆盖）'
                         % (name, '、'.join(writers)))
        rows.append((name, role, files[name], writers, readers, note))
    # 4) git 规则
    gi = os.path.join(ROOT, '.gitignore')
    gi_txt = open(gi, encoding='utf-8').read() if os.path.exists(gi) else ''
    for need in ['build/', 'cache/']:
        if need not in gi_txt:
            warns.append('.gitignore 缺少「%s」（产物与缓存不应进 git）' % need)
    return rows


def write_manifest(rows):
    d = {
        'generated_by': 'scripts/manifest.py',
        'roles': {k: {'role': v[0], 'note': v[1],
                      **({'writer': v[2]} if len(v) > 2 else {})} for k, v in ROLES.items()},
        'entries': [
            {'path': 'data/' + n, 'role': r, 'files': c, 'written_by': w, 'read_by': rd, 'note': note}
            for (n, r, c, w, rd, note) in rows
        ],
    }
    json.dump(d, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return OUT


def main():
    rows = check()
    counts = {}
    for _, role, *_ in rows:
        counts[role] = counts.get(role, 0) + 1
    print('数据清单：%d 个条目（%s）' % (len(rows), '、'.join('%s %d' % kv for kv in sorted(counts.items()))))
    if '--list' in sys.argv:
        for n, role, c, w, rd, note in rows:
            print('  %-34s %-7s %s' % ('data/' + n, role, ('写:' + (w[0] if w else '—'))[:28]))
    for m in warns:
        print('  ⚠ %s' % m)
    if errors:
        print('  ✗ 错误 %d 条：' % len(errors))
        for m in errors:
            print('    - %s' % m)
        sys.exit(1)
    if '--write' in sys.argv:
        p = write_manifest(rows)
        print('  ✓ 已写入 %s' % os.path.relpath(p, ROOT))
    else:
        print('  ✓ 角色与读写关系一致（%d 条警告）' % len(warns))


if __name__ == '__main__':
    main()
