#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
由省级原始边界（DataV 全国省级 GeoJSON）生成高精度、可直接投影的省级几何。
要点：**共享边界必须保持完全一致**，因此简化容差取极小值（默认 0.002°），
并对每个环单独处理但在同一容差下进行；外环统一为逆时针（d3/spherical 约定）。

用法：
    python3 scripts/make_provinces.py [容差]
输出：
    data/china_provinces_simplified.json
"""
import json, math, os, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'data', 'china_provinces_raw.json')
OUT = os.path.join(ROOT, 'data', 'china_provinces_simplified.json')
SRC_URL = 'https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json'
TOL = float(sys.argv[1]) if len(sys.argv) > 1 else 0.002

NAME_MAP = {
    '北京市': '北京', '天津市': '天津', '河北省': '河北', '山西省': '山西', '内蒙古自治区': '内蒙古',
    '辽宁省': '辽宁', '吉林省': '吉林', '黑龙江省': '黑龙江', '上海市': '上海', '江苏省': '江苏',
    '浙江省': '浙江', '安徽省': '安徽', '福建省': '福建', '江西省': '江西', '山东省': '山东',
    '河南省': '河南', '湖北省': '湖北', '湖南省': '湖南', '广东省': '广东', '广西壮族自治区': '广西',
    '海南省': '海南', '重庆市': '重庆', '四川省': '四川', '贵州省': '贵州', '云南省': '云南',
    '西藏自治区': '西藏', '陕西省': '陕西', '甘肃省': '甘肃', '青海省': '青海',
    '宁夏回族自治区': '宁夏', '新疆维吾尔自治区': '新疆', '台湾省': '台湾',
    '香港特别行政区': '香港', '澳门特别行政区': '澳门',
}


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


def signed_area(ring):
    a = 0.0
    for i in range(len(ring) - 1):
        x1, y1 = ring[i]
        x2, y2 = ring[i + 1]
        a += x1 * y2 - x2 * y1
    return a / 2


def main():
    if not os.path.exists(RAW):
        print('下载原始省级边界 …')
        urllib.request.urlretrieve(SRC_URL, RAW)
    d = json.load(open(RAW, encoding='utf-8'))
    feats, pin, pout = [], 0, 0
    for f in d['features']:
        nm = f['properties'].get('name', '')
        if nm == '':
            # 南海诸岛要素（JD）：保留原始坐标，供南海点位使用
            feats.append({'type': 'Feature', 'properties': {'name': '南海诸岛', 'kind': 'jd'},
                          'geometry': f['geometry']})
            continue
        key = NAME_MAP[nm]
        g = f['geometry']
        polys = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
        new_polys = []
        for poly in polys:
            rings = []
            for i, ring in enumerate(poly):
                pin += len(ring)
                closed = ring[0] == ring[-1]
                pts = ring[:-1] if closed else ring[:]
                simp = rdp(pts, TOL) if len(pts) > 3 else pts
                if len(simp) < 3:
                    continue
                simp = [(round(x, 4), round(y, 4)) for x, y in simp]
                if closed:
                    simp.append(simp[0])
                # 外环逆时针，内环顺时针
                ccw = signed_area(simp) < 0
                if (i == 0) != ccw:
                    simp = simp[::-1]
                rings.append(simp)
                pout += len(simp)
            if rings:
                new_polys.append(rings)
        feats.append({'type': 'Feature',
                      'properties': {'name': key, 'full': nm, 'adcode': f['properties']['adcode'],
                                     'centroid': f['properties'].get('centroid') or f['properties'].get('center'),
                                     'center': f['properties'].get('center')},
                      'geometry': {'type': 'MultiPolygon', 'coordinates': new_polys}})
    json.dump({'type': 'FeatureCollection', 'features': feats},
              open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print('容差 %.3f°：点数 %d → %d，输出 %.0f KB' % (TOL, pin, pout, os.path.getsize(OUT) / 1024))


if __name__ == '__main__':
    main()
