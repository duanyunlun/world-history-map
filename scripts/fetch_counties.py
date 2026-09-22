#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抓取并简化「割据区/根据地」所用到的区县边界。

流程：省(_full) -> 地级市(_full) -> 区县；只保留 data/territories.json 中出现的县。
结果写入 data/counties.json（含投影前经纬度环，供 build_geo.py 用主图投影生成路径）。
缓存：data/_county_cache/<adcode>.json，重复运行不再联网。
"""
import json, os, math, time, urllib.request, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, 'data', '_county_cache')
OUT = os.path.join(ROOT, 'data', 'counties.json')
BASE = 'https://geo.datav.aliyun.com/areas_v3/bound/%s_full.json'
UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0 Safari/537.36')

PROVINCES = {
    '江西': 360000, '福建': 350000, '湖北': 420000, '河南': 410000, '安徽': 340000,
    '湖南': 430000, '四川': 510000, '陕西': 610000, '甘肃': 620000, '宁夏': 640000,
    '山西': 140000, '河北': 130000, '山东': 370000, '江苏': 320000, '海南': 460000,
    '广东': 440000, '广西': 450000,
}


def fetch(adcode):
    os.makedirs(CACHE, exist_ok=True)
    fp = os.path.join(CACHE, '%s.json' % adcode)
    if os.path.exists(fp):
        return json.load(open(fp, encoding='utf-8'))
    if os.path.exists(fp + '.404'):      # 负缓存：确认不存在的（省直辖县等）不再重试
        return None
    req = urllib.request.Request(BASE % adcode, headers={'User-Agent': UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                d = json.loads(r.read().decode('utf-8'))
            json.dump(d, open(fp, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
            time.sleep(0.22)          # 限速，避免被服务端拒绝
            return d
        except Exception as e:
            if attempt == 3:
                if '404' in str(e):
                    open(fp + '.404', 'w').close()
                else:
                    print('   !! %s 抓取失败：%s' % (adcode, e))
                return None
            time.sleep(1.8)


ALIAS = {
    '宁冈县': '井冈山市', '永定县': '永定区', '子长县': '子长市', '保安县': '志丹县',
    '安定县': '子长县', '葭县': '佳县', '完县': '顺平县', '辽县': '左权县',
    '恩隆县': '田东县', '奉议县': '田阳区', '果德县': '平果市', '礼山县': '大悟县',
    '沔阳县': '仙桃市', '大庸县': '张家界市', '乐会县': '琼海市', '经扶县': '新县',
    '黄安县': '红安县', '立煌县': '金寨县',
}


def match_name(raw, want, province):
    """把抓到的区县名匹配到 territories 里写的名字；支持「省|名」限定"""
    nm = raw.strip()
    if '%s|%s' % (province, nm) in want:
        return '%s|%s' % (province, nm)
    if nm in want:
        return nm
    for old, new in ALIAS.items():
        if new == nm and old in want:
            return old
    for w in want:
        base = w.split('|')[-1]
        if base.endswith('县') and nm.startswith(base[:-1]) and nm.endswith('自治县'):
            return w
    return None


def perp(p, a, b):
    (x, y), (x1, y1), (x2, y2) = p, a, b
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(x - x1, y - y1)
    t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(x - (x1 + t * dx), y - (y1 + t * dy))


def rdp(pts, eps):
    if len(pts) < 3:
        return pts
    dmax, idx = 0.0, 0
    for i in range(1, len(pts) - 1):
        d = perp(pts[i], pts[0], pts[-1])
        if d > dmax:
            dmax, idx = d, i
    if dmax > eps:
        return rdp(pts[:idx + 1], eps)[:-1] + rdp(pts[idx:], eps)
    return [pts[0], pts[-1]]


def simp_ring(ring, eps=0.012):
    closed = ring[0] == ring[-1]
    pts = ring[:-1] if closed else ring[:]
    if len(pts) < 3:
        return None
    s = rdp(pts, eps)
    if len(s) < 3:
        return None
    s = [(round(x, 3), round(y, 3)) for x, y in s]
    if closed:
        s.append(s[0])
    return s


def main():
    terr = json.load(open(os.path.join(ROOT, 'data', 'territories.json'), encoding='utf-8'))
    want = set()
    for t in terr['territories']:
        want.update(t['counties'])
    print('需要 %d 个县/县级市' % len(want))

    counties = {}
    for pname, pcode in PROVINCES.items():
        pdata = fetch(pcode)
        if not pdata:
            continue
        feats = [f for f in pdata['features']]
        hit = 0

        def take(ftr, pname, hit):
            pr = ftr['properties']
            nm = match_name(pr.get('name') or '', want, pname)
            if not nm or nm in counties:
                return hit
            g = ftr['geometry']
            polys = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
            rings = []
            for poly in polys:
                for ring in poly:
                    r = simp_ring(ring)
                    if r:
                        rings.append(r)
            if rings:
                counties[nm] = {'province': pname, 'adcode': pr['adcode'],
                                'centroid': pr.get('centroid') or pr.get('center'),
                                'rings': rings}
                hit += 1
            return hit

        # 省级文件里直接出现的（省直辖县级市、直筒子市）
        for f in feats:
            hit = take(f, pname, hit)
        cities = [f['properties'] for f in feats]
        for c in cities:
            cdata = fetch(c['adcode'])
            if not cdata:
                continue
            for f in cdata['features']:
                hit = take(f, pname, hit)
        print('  %-4s 命中 %2d 个' % (pname, hit))

    missing = sorted(want - set(counties))
    json.dump({'counties': counties}, open(OUT, 'w', encoding='utf-8'),
              ensure_ascii=False, separators=(',', ':'))
    print('已写入 %s：%d 个县，%.0f KB' % (OUT, len(counties), os.path.getsize(OUT) / 1024))
    if missing:
        print('未取到（%d）：%s' % (len(missing), '、'.join(missing)))


if __name__ == '__main__':
    main()
