#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
架构守卫：把「每个关注点只能有一个权威实现」写成可执行检查。

背景：本项目长期存在"同一件事两套实现"——中国侧与世界侧各有标签布局、颜色/名称查询、
事件栏渲染、时间换算。结果是修一处、另一处照旧，且反复出现同类 bug。
本脚本把这些约束固化为断言，违反即让 pipeline 失败。

用法：python3 scripts/check_arch.py
"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, 'src', 'app.js')
problems, notes = [], []


def read(p):
    return open(p, encoding='utf-8', errors='ignore').read()


def count_defs(src, name):
    n = re.escape(name)
    return len(re.findall(r'(?:function\s+' + n + r'\s*\(|(?:const|let)\s+' + n + r'\s*=)', src))


def check_app():
    s = read(APP)
    # 1) 标签布局：只能有一个全局布局入口
    for dead in ['layoutChinaLabels']:
        if dead in s:
            problems.append('标签布局出现第二套实现：%s（应只保留 layoutAllLabels）' % dead)
    if count_defs(s, 'layoutAllLabels') != 1:
        problems.append('layoutAllLabels 必须且只能定义一次')
    # 标签显隐只能由布局函数写（其它地方一律写 dataset.vis）
    bad = []
    for m in re.finditer(r'\.style\.display\s*=\s*[\'"]{2}', s):
        seg = s[max(0, m.start() - 200):m.start()]
        if 'it.node.style.display' in seg or 'node.style.display' in seg:
            continue
        if re.search(r'labelNodes\[[^\]]+\]\.style\.display', seg):
            bad.append(s[:m.start()].count('\n') + 1)
    if bad:
        problems.append('标签显隐被布局之外的代码直接改写（行号 %s）——会导致压字' % bad[:5])
    # 1.5) 标签显隐协议：除布局外，不得直接写 .label.style.display / labelNodes[..].style.display
    direct = []
    for i, line in enumerate(s.split('\n')):
        if re.search(r'\b(labelNodes\[[^\]]+\]|\.label)\.style\.display\s*=', line):
            if 'it.node.style.display' in line or 'node.style.display' in line:
                continue
            direct.append(i + 1)
    if direct:
        problems.append('标签显隐被直接改写（应写 data-vis，由 layoutAllLabels 统一决定）：行 %s' % direct[:5])
    # 2) 颜色/名称权威唯一
    for fn in ['polityColor', 'polityName', 'polityEntryOf']:
        if count_defs(s, fn) != 1:
            problems.append('%s 必须且只能定义一次（颜色/名称的唯一权威）' % fn)
    outside = [i + 1 for i, line in enumerate(s.split('\n'))
               if re.search(r'FACTION\[[^\]]+\]\.color', line) and 'polityColor' not in line]
    if outside:
        problems.append('在 %s 处直接读 FACTION[..].color，应走 polityColor' % outside[:5])
    # 3) 时间换算唯一
    for fn in ['stepInfo', 'SI']:
        if count_defs(s, fn) != 1:
            problems.append('%s 必须且只能定义一次（时间换算唯一）' % fn)
    # 4) 事件栏唯一渲染器
    writers = re.findall(r"lane\.innerHTML\s*=", s)
    if len(writers) != 1:
        problems.append('事件栏 #nationLane 有 %d 处写入，应只有 renderNationLane 一处' % len(writers))
    # 5) 投影：app 侧只允许一处公式（读 world.meta）
    proj = len(re.findall(r'function wproj\(', s))
    if proj != 1:
        problems.append('前端投影公式应只有一处（wproj），当前 %d 处' % proj)
    notes.append('app.js 检查完成（%d 行）' % s.count('\n'))


def check_projection():
    for f in ['build_geo.py', 'build_world.py']:
        s = read(os.path.join(ROOT, f))
        if 'from projection import' not in s and 'from scripts.projection import' not in s:
            problems.append('%s 未使用 scripts/projection.py 的共享投影' % f)
        if re.search(r'def (_natural_earth|_albers|natural_earth)\(', s):
            problems.append('%s 里仍存在自带的投影实现（应只用共享投影）' % f)
    notes.append('投影唯一性检查完成')


def check_registry():
    d = os.path.join(ROOT, 'data', 'sources', 'polities')
    if not os.path.isdir(d):
        problems.append('缺少政权注册表目录 data/sources/polities/')
        return
    ids = {}
    for fn in sorted(os.listdir(d)):
        if not fn.endswith('.json'):
            continue
        import json
        try:
            g = json.load(open(os.path.join(d, fn), encoding='utf-8'))
        except Exception as e:
            problems.append('%s 解析失败：%s' % (fn, e))
            continue
        for e in (g.get('entries') or []):
            ids.setdefault(e.get('id'), []).append(fn)
    notes.append('政权注册表 %d 条 id（跨文件分片允许，构建期按 id 合并字段）' % len(ids))


def main():
    check_app()
    check_projection()
    check_registry()
    for n in notes:
        print('  · %s' % n)
    if problems:
        print('  ✗ 架构违规 %d 条：' % len(problems))
        for p in problems:
            print('    - %s' % p)
        sys.exit(1)
    print('  ✓ 架构守卫通过（单一标签布局 / 单一颜色名称权威 / 单一时间换算 / 单一事件栏 / 单一投影）')


if __name__ == '__main__':
    main()
