#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 historical-basemaps 的时间切片烘焙成前端可直接使用的世界政治地图数据。
- 投影：Natural Earth（伪圆柱等面积感，适合世界全图；中国部分同样用它重投）
- 简化：RDP，容差随切片密度自适应
- 去重：相同几何（同一政权在相邻切片中不变）只存一份
输出 data/world.json
"""
import json, math, os, re, sys, hashlib
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts'))
from geoenc import encode_d

ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(ROOT, 'data', '_world_cache')
OUT = os.path.join(ROOT, 'data', 'world.json')

# ---------------------------------------------------------------- 投影
def natural_earth(lon, lat):
    """Natural Earth 投影（d3-geo 同款），返回单位球面坐标（约 -2.7..2.7, -1.4..1.4）"""
    lam = math.radians(lon)
    phi = math.radians(lat)
    p2 = phi * phi
    p4 = p2 * p2
    x = lam * (0.8707 - 0.131979 * p2 + p4 * (-0.013791 + p4 * (0.003971 * p2 - 0.001529 * p4)))
    y = phi * (1.007226 + p2 * (0.015085 + p4 * (-0.044475 + 0.028874 * p2 - 0.005916 * p4)))
    return x, y


SCALE = 480.0            # 世界宽 ≈ 2π*0.87*480 ≈ 2620 单位
CX, CY = 1310.0, 700.0   # 画布中心


def tf(lon, lat):
    x, y = natural_earth(lon, lat)
    return (CX + x * SCALE, CY - y * SCALE)


def fmt(v):
    s = ('%.1f' % v).rstrip('0').rstrip('.')
    return s if s else '0'


# ---------------------------------------------------------------- 简化
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


def rings_of(geom):
    if not geom:
        return []
    t, c = geom.get('type'), geom.get('coordinates')
    if t == 'Polygon':
        return [c]
    if t == 'MultiPolygon':
        return c
    return []


EPS = float(os.environ.get('WORLD_EPS', '0.05'))     # 度；0.05°≈5.5km


def slice_polities(fc):
    """返回 [(名称, 路径d, 质心)]"""
    out = []
    for f in fc.get('features', []):
        pr = f.get('properties') or {}
        name = (pr.get('NAME') or pr.get('name') or pr.get('ABBREVN')
                or pr.get('SUBJECTO') or pr.get('SUBJECT') or '').strip()
        if not name:
            continue
        name = re.sub(r'\s+', ' ', name)
        segs, xs, ys = [], [], []
        for poly in rings_of(f.get('geometry')):
            for i, ring in enumerate(poly):
                pts = [(round(c[0], 4), round(c[1], 4)) for c in ring if len(c) >= 2]
                if pts and pts[0] == pts[-1]:
                    pts = pts[:-1]
                if len(pts) < 3:
                    continue
                q = rdp(pts, EPS) if len(pts) > 8 else pts
                if len(q) < 3:
                    continue
                pp = [tf(x, y) for x, y in q]
                segs.append('M' + 'L'.join('%s %s' % (fmt(x), fmt(y)) for x, y in pp) + 'Z')
                xs.extend(x for x, _ in pp)
                ys.extend(y for _, y in pp)
        if not segs:
            continue
        out.append((name, ''.join(segs), [round(sum(xs) / len(xs), 1), round(sum(ys) / len(ys), 1)],
                    pr.get('BORDERPRECISION')))
    return out


YEAR_RE = re.compile(r'world_(bc)?(\d+)$')


def slice_year(name):
    m = YEAR_RE.search(name)
    if not m:
        return None
    y = int(m.group(2))
    return -y if m.group(1) == 'bc' else y


def year_label(y):
    if y <= -10000:
        return '公元前 %s 年' % ('{:,}'.format(-y))
    if y < 0:
        return '公元前 %d 年' % (-y)
    return '%d 年' % y



# ---------------------------------------------------------------- 现代切片（2011—2026）
# historical-basemaps 止于 2010；2011 年后改用 Natural Earth 现行国界，并处理已知变更：
#   · 2011—2013：南苏丹并入苏丹（南苏丹 2011.7 独立）
#   · 2014 起：现行国界（克里米亚等争议地区按 Natural Earth 口径，界面另行标注）
NE_PATH = os.path.join(ROOT, 'data', 'ne_50m_countries.geojson')


CRIMEA_BOX = (32.0, 44.0, 37.0, 46.6)      # 克里米亚半岛经纬范围


def _in_crimea(ring):
    lons = [c[0] for c in ring]
    lats = [c[1] for c in ring]
    return (CRIMEA_BOX[0] <= min(lons) and max(lons) <= CRIMEA_BOX[2] and
            CRIMEA_BOX[1] <= min(lats) and max(lats) <= CRIMEA_BOX[3])


def modern_polities(merge_south_sudan=False, crimea_to_ukraine=False):
    if not os.path.exists(NE_PATH):
        return []
    ne = json.load(open(NE_PATH, encoding='utf-8'))
    out = []
    crimea_rings = []
    for f in ne['features']:
        pr = f['properties']
        name = (pr.get('ADMIN') or pr.get('NAME') or '').strip()
        if not name:
            continue
        if merge_south_sudan and name == 'South Sudan':
            name = 'Sudan'                      # 并入苏丹：同名政体在输出端合并
        # 2011—2013：克里米亚属乌克兰（从俄罗斯几何中剥离，稍后并入乌克兰）
        if crimea_to_ukraine and name == 'Russia':
            g0 = f.get('geometry')
            keep = []
            for poly in rings_of(g0):
                if _in_crimea(poly[0]):
                    crimea_rings.append(poly)
                else:
                    keep.append(poly)
            f = dict(f)
            f['geometry'] = {'type': 'MultiPolygon', 'coordinates': keep}
        segs, xs, ys = [], [], []
        for poly in rings_of(f.get('geometry')):
            for ring in poly:
                pts = [(round(c[0], 4), round(c[1], 4)) for c in ring if len(c) >= 2]
                if pts and pts[0] == pts[-1]:
                    pts = pts[:-1]
                if len(pts) < 3:
                    continue
                q = rdp(pts, EPS) if len(pts) > 8 else pts
                if len(q) < 3:
                    continue
                pp = [tf(x, y) for x, y in q]
                segs.append('M' + 'L'.join('%s %s' % (fmt(x), fmt(y)) for x, y in pp) + 'Z')
                xs.extend(x for x, _ in pp)
                ys.extend(y for _, y in pp)
        if segs:
            out.append((name, ''.join(segs), [round(sum(xs) / len(xs), 1), round(sum(ys) / len(ys), 1)], 'ne'))
    if crimea_to_ukraine and crimea_rings:
        segs, xs, ys = [], [], []
        for poly in crimea_rings:
            for ring in poly:
                pts = [(round(c[0], 4), round(c[1], 4)) for c in ring if len(c) >= 2]
                if pts and pts[0] == pts[-1]:
                    pts = pts[:-1]
                if len(pts) < 3:
                    continue
                q = rdp(pts, EPS) if len(pts) > 8 else pts
                if len(q) < 3:
                    continue
                pp = [tf(x, y) for x, y in q]
                segs.append('M' + 'L'.join('%s %s' % (fmt(x), fmt(y)) for x, y in pp) + 'Z')
                xs.extend(x for x, _ in pp)
                ys.extend(y for _, y in pp)
        if segs:
            lab = [round(sum(xs) / len(xs), 1), round(sum(ys) / len(ys), 1)]
            for i, (n2, d2, l2, b2) in enumerate(out):
                if n2 == 'Ukraine':
                    out[i] = (n2, d2 + ''.join(segs), l2, b2)
                    break
    # 同名合并（南苏丹并入苏丹后会有两块）
    merged = {}
    for name, d, lab, bp in out:
        if name in merged:
            merged[name][0] += d
        else:
            merged[name] = [d, lab]
    return [(n, v[0], v[1], 'ne') for n, v in merged.items()]



# ---------------------------------------------------------------- CShapes：1886—2019 逐年边界
CS_PATH = os.path.join(ROOT, 'data', '_cshapes', 'CShapes-2.0.geojson')


def cshapes_slices(y0=1886, y1=2019):
    """返回 [(year, [ (name, d, label) ... ])]；同一几何跨年复用时由调用方去重"""
    if not os.path.exists(CS_PATH):
        return []
    cs = json.load(open(CS_PATH, encoding='utf-8'))
    feats = []
    for f in cs['features']:
        pr = f['properties']
        nm = (pr.get('cntry_name') or '').strip()
        a, b = pr.get('gwsyear'), pr.get('gweyear')
        if not nm or a is None or b is None:
            continue
        feats.append((int(a), int(b), nm, f.get('geometry')))
    out = []
    for y in range(y0, y1 + 1):
        pol = []
        for a, b, nm, g in feats:
            if a <= y <= b:
                pol.append((nm, g))
        out.append((y, pol))
    print('  CShapes 覆盖 %d—%d，共 %d 年' % (y0, y1, len(out)))
    return out



CS_PATH = os.path.join(ROOT, 'data', '_cshapes', 'CShapes-2.0.geojson')



# ---------------------------------------------------------------- 分期正名
# CShapes 用固定名称贯穿全期（如 Turkey (Ottoman Empire)、Russia (Soviet Union)），
# 会造成 1960 年仍显示"奥斯曼"这类错误；这里按年份改成当时的国号。
ERA_NAME = {
    'Turkey (Ottoman Empire)': [(1886, 1922, 'Ottoman Empire'), (1923, 2030, 'Turkey')],
    'Russia (Soviet Union)': [(1886, 1917, 'Russian Empire'), (1918, 1991, 'Soviet Union'), (1992, 2030, 'Russia')],
    'Iran (Persia)': [(1886, 1934, 'Persia (Qajar)'), (1935, 2030, 'Iran')],
    'Thailand (Siam)': [(1886, 1938, 'Siam'), (1939, 2030, 'Thailand')],
    'Zimbabwe (Rhodesia)': [(1886, 1964, 'Southern Rhodesia'), (1965, 1979, 'Rhodesia'), (1980, 2030, 'Zimbabwe')],
    'Sri Lanka (Ceylon)': [(1886, 1947, 'Ceylon (British)'), (1948, 1971, 'Ceylon'), (1972, 2030, 'Sri Lanka')],
    'Myanmar (Burma)': [(1886, 1947, 'Burma (British)'), (1948, 1988, 'Burma'), (1989, 2030, 'Myanmar')],
    'Congo, Democratic Republic of (Zaire)': [(1886, 1907, 'Congo Free State'), (1908, 1959, 'Belgian Congo'),
                                               (1960, 1970, 'Congo (Kinshasa)'), (1971, 1996, 'Zaire'),
                                               (1997, 2030, 'DR Congo')],
    'Cambodia (Kampuchea)': [(1886, 1952, 'Cambodia (French)'), (1953, 1975, 'Cambodia'),
                             (1976, 1988, 'Kampuchea'), (1989, 2030, 'Cambodia')],
    'Burkina Faso (Upper Volta)': [(1886, 1959, 'Upper Volta (French)'), (1960, 1983, 'Upper Volta'),
                                   (1984, 2030, 'Burkina Faso')],
    'Swaziland (Eswatini)': [(1886, 1967, 'Swaziland (British)'), (1968, 2017, 'Swaziland'), (2018, 2030, 'Eswatini')],
    'Tanzania (Tanganyika)': [(1886, 1918, 'German East Africa'), (1919, 1960, 'Tanganyika'),
                              (1961, 1963, 'Tanganyika'), (1964, 2030, 'Tanzania')],
    'Madagascar (Malagasy)': [(1886, 1959, 'Madagascar (French)'), (1960, 2030, 'Madagascar')],
    'Vietnam (Annam/Cochin China/Tonkin)': [(1886, 1944, 'French Indochina (Vietnam)'), (1945, 1953, 'Vietnam (French)'),
                                            (1954, 1975, 'South Vietnam'), (1976, 2030, 'Vietnam')],
    'Yemen (Arab Republic of Yemen)': [(1886, 1966, 'Yemen (North)'), (1967, 1989, 'Yemen Arab Republic'),
                                       (1990, 2030, 'Yemen')],
    'Oman (Muscat and Oman)': [(1886, 1969, 'Muscat and Oman'), (1970, 2030, 'Oman')],
    'Dahomey': [(1886, 1899, 'Dahomey'), (1900, 1959, 'Dahomey (French)'), (1960, 1974, 'Dahomey'), (1975, 2030, 'Benin')],
    'British Somaliland (Somaliland Republic)': [(1886, 1959, 'British Somaliland'), (1960, 1990, 'Somalia'),
                                                 (1991, 2030, 'Somaliland')],
    'Italian Somaliland': [(1886, 1949, 'Italian Somaliland'), (1950, 1959, 'Trust Territory of Somaliland'),
                           (1960, 1990, 'Somalia'), (1991, 2030, 'Somalia')],
    'German Federal Republic': [(1949, 1989, 'West Germany'), (1990, 2030, 'Germany')],
    'Alaska': [(1886, 2030, 'Alaska (US)')],
    "Korea, Republic of": [(1948, 2030, 'South Korea')],
    "Korea, People's Republic of": [(1948, 2030, 'North Korea')],
}


def era_name(name, year):
    rules = ERA_NAME.get(name)
    if not rules:
        return name
    for a, b, disp in rules:
        if a <= year <= b:
            return disp
    return name


def main():
    files = [f for f in os.listdir(CACHE) if f.endswith('.geojson')]
    items = []
    for f in files:
        y = slice_year(f[:-len('.geojson')])
        if y is None:
            continue
        items.append((y, f))
    items.sort()
    print('切片 %d 个：%s … %s' % (len(items), items[0][0], items[-1][0]))

    geoms, gindex = [], {}
    slices = []
    for y, f in items:
        if 1886 <= y <= 2019 and os.path.exists(CS_PATH):
            continue            # 该区间由 CShapes 逐年边界取代（精度更高）
        fc = json.load(open(os.path.join(CACHE, f), encoding='utf-8'))
        pol = slice_polities(fc)
        plist = []
        for name, d, lab, bp in pol:
            key = hashlib.sha1(d.encode('utf-8')).hexdigest()[:16]
            if key not in gindex:
                gindex[key] = len(geoms)
                geoms.append({'d': d, 'label': lab})
            plist.append([era_name(name, y), gindex[key], bp or ''])
        slices.append({'y': y, 'label': year_label(y), 'p': plist})
        print('  %-12s 政体 %3d（去重后几何 %d）' % (year_label(y), len(plist), len(geoms)), flush=True)

    # 追加 CShapes 逐年切片（1886—2019）：逐年边界，精度高于原每 10—20 年一切片
    _cs_added = 0
    for year, pol in cshapes_slices():
        plist = []
        for name, g in pol:
            segs, xs, ys = [], [], []
            for poly in rings_of(g):
                for ring in poly:
                    pts = [(round(c[0], 4), round(c[1], 4)) for c in ring if len(c) >= 2]
                    if pts and pts[0] == pts[-1]:
                        pts = pts[:-1]
                    if len(pts) < 3:
                        continue
                    q = rdp(pts, EPS) if len(pts) > 8 else pts
                    if len(q) < 3:
                        continue
                    pp = [tf(x, y2) for x, y2 in q]
                    segs.append('M' + 'L'.join('%s %s' % (fmt(x), fmt(y2)) for x, y2 in pp) + 'Z')
                    xs.extend(x for x, _ in pp)
                    ys.extend(y for _, y in pp)
            if not segs:
                continue
            d = ''.join(segs)
            lab = [round(sum(xs) / len(xs), 1), round(sum(ys) / len(ys), 1)]
            key = hashlib.sha1(d.encode('utf-8')).hexdigest()[:16]
            if key not in gindex:
                gindex[key] = len(geoms)
                geoms.append({'d': d, 'label': lab})
            plist.append([era_name(name, year), gindex[key], 'cs'])
        slices.append({'y': year, 'label': '%d 年' % year, 'p': plist, 'cs': True})
        _cs_added += 1
        if year % 20 == 0:
            print('    CShapes %d 年：政体 %3d（几何累计 %d）' % (year, len(plist), len(geoms)), flush=True)

    # 追加现代切片
    for my, lbl, merge, crimea in ((2011, '2011—2013 年', True, True), (2014, '2014—2026 年', False, False)):
        pol = modern_polities(merge_south_sudan=merge, crimea_to_ukraine=crimea)
        plist = []
        for name, d, lab, bp in pol:
            key = hashlib.sha1(d.encode('utf-8')).hexdigest()[:16]
            if key not in gindex:
                gindex[key] = len(geoms)
                geoms.append({'d': d, 'label': lab})
            plist.append([era_name(name, my), gindex[key], bp or ''])
        slices.append({'y': my, 'label': lbl, 'p': plist, 'modern': True})
        print('  %-12s 政体 %3d（Natural Earth 现行国界）' % (lbl, len(plist)), flush=True)

    slices.sort(key=lambda z: (z['y'], 1 if z.get('modern') else 0))
    # 几何压缩：'d' -> 'c'（base64 增量编码），体积约降到 1/4
    _tot = 0
    for _g in geoms:
        _c, _n = encode_d(_g['d'])
        _g['c'] = _c
        _g['n'] = _n
        del _g['d']
        _tot += _n
    print('  几何压缩：%d 个几何、%d 点' % (len(geoms), _tot))
    data = {'slices': slices, 'geoms': geoms,
            'meta': {'source': 'aourednik/historical-basemaps (GPL-3.0) + Natural Earth 50m（2011 年后）',
                     'projection': 'Natural Earth', 'eps': EPS, 'scale': SCALE,
                     'cx': CX, 'cy': CY}}
    json.dump(data, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print('已写入 %s：%.1f MB（%d 个切片、%d 个几何）'
          % (OUT, os.path.getsize(OUT) / 1024 / 1024, len(slices), len(geoms)))


if __name__ == '__main__':
    main()
