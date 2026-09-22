#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把省级边界 GeoJSON 烘焙成前端可直接使用的紧凑 JS 数据。"""
import json, math, os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts'))
from geoenc import encode_d

HERE = os.path.dirname(os.path.abspath(__file__))
geo = json.load(open(os.path.join(HERE, 'data', 'china_provinces_simplified.json')))

# 投影：Albers 等积圆锥（标准纬线 25°N/47°N，中央经线 105°E）——适配中国轮廓
# 投影：等距圆柱（平面投影），与中国/世界两层统一，定义在 scripts/projection.py。
# 曾用 Albers 等积圆锥（中央经线 105°E、标准纬线 25/47°N）：它对中国轮廓变形小，
# 但纬线是弧线、整体带旋转，与世界的伪圆柱投影不是同一套观感，放大后显得"像球面"。
# 结论：统一用平面投影，改投影只改 scripts/projection.py。
from scripts.projection import SCALE as WORLD_SCALE, CX as WORLD_CX, CY as WORLD_CY  # noqa: E402
WORLD_W = 2620.0
WORLD_H = 1400.0


def _perp(p, a, b):
    (x, y), (x1, y1), (x2, y2) = p, a, b
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(x - x1, y - y1)
    t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(x - (x1 + t * dx), y - (y1 + t * dy))


def rdp(pts, eps):
    """Ramer–Douglas–Peucker 简化（经纬度平面近似）"""
    if len(pts) < 3:
        return pts
    dmax, idx = 0.0, 0
    for i in range(1, len(pts) - 1):
        d = _perp(pts[i], pts[0], pts[-1])
        if d > dmax:
            dmax, idx = d, i
    if dmax > eps:
        return rdp(pts[:idx + 1], eps)[:-1] + rdp(pts[idx:], eps)
    return [pts[0], pts[-1]]


def project(lon, lat):
    """投影统一由 scripts/projection.py 提供（等距圆柱/平面投影）"""
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'scripts'))
    from projection import project as _p
    return _p(lon, lat)




# 只以 34 个省级行政区拟合范围（南海诸岛用角标另绘）
prov_feats = [f for f in geo['features'] if f['properties'].get('kind') != 'jd']
# 把海南要素中的南海诸岛碎块剥离出来（角标另绘），主图只保留海南本岛
south_islands = []
for f in prov_feats:
    if f['properties']['name'] != '海南':
        continue
    main, rest = [], []
    for poly in f['geometry']['coordinates']:
        lats = [p[1] for p in poly[0]]
        (main if max(lats) > 17.5 else rest).append(poly)
    f['geometry']['coordinates'] = main
    south_islands = rest
print('海南本岛环数:', len(main), '| 剥离出的南海诸岛碎块:', len(south_islands))

pts = []
for f in prov_feats:
    for poly in f['geometry']['coordinates']:
        for ring in poly:
            pts.extend(ring)
xs = [project(*p)[0] for p in pts]
ys = [project(*p)[1] for p in pts]
minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
# 世界统一坐标：不做“按中国拟合”，中国范围单独记录以便初始镜头
CN = (minx, miny, maxx, maxy)
W = 1000.0
scale = 1.0
H = maxy - miny
print('世界画布 %.0f x %.0f；中国范围 %.0f,%.0f — %.0f,%.0f'
      % (WORLD_W, WORLD_H, minx, miny, maxx, maxy))

def tf(p):
    return project(p[0], p[1])

def fmt(v):
    s = ('%.1f' % v).rstrip('0').rstrip('.')
    return s if s else '0'

paths = {}
centroids = {}
for f in prov_feats:
    name = f['properties']['name']
    d = []
    for poly in f['geometry']['coordinates']:
        for ring in poly:
            sp = [tf(p) for p in ring]
            # 去掉相邻重复点
            out = [sp[0]]
            for p in sp[1:]:
                if abs(p[0] - out[-1][0]) > .05 or abs(p[1] - out[-1][1]) > .05:
                    out.append(p)
            if len(out) < 4:
                continue
            d.append('M' + 'L'.join('%s %s' % (fmt(x), fmt(y)) for x, y in out) + 'Z')
    paths[name] = ''.join(d)
    # 用最大环的质心作为标注点
    best, bestn = None, -1
    for poly in f['geometry']['coordinates']:
        ring = poly[0]
        if len(ring) > bestn:
            best, bestn = ring, len(ring)
    cx = sum(p[0] for p in best) / len(best)
    cy = sum(p[1] for p in best) / len(best)
    centroids[name] = tuple(round(v, 1) for v in tf((cx, cy)))

# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# 周边国家底图（仅作地理参照，不含事件）：Natural Earth 110m，裁剪到邻近窗口后
# 与主图同一投影绘制，置于中国之下。
# ---------------------------------------------------------------------------
NE_PATH = os.path.join(HERE, 'data', 'ne_50m_countries.geojson')
NE_WINDOW = (62.0, 3.0, 150.0, 56.0)     # lon0, lat0, lon1, lat1
NE_WANT = {
    'Russia': '俄罗斯', 'Mongolia': '蒙古', 'Kazakhstan': '哈萨克斯坦',
    'Kyrgyzstan': '吉尔吉斯斯坦', 'Tajikistan': '塔吉克斯坦', 'Afghanistan': '阿富汗',
    'Pakistan': '巴基斯坦', 'India': '印度', 'Nepal': '尼泊尔', 'Bhutan': '不丹',
    'Bangladesh': '孟加拉国', 'Myanmar': '缅甸', 'Laos': '老挝', 'Vietnam': '越南',
    'Thailand': '泰国', 'Cambodia': '柬埔寨', 'Malaysia': '马来西亚',
    'Indonesia': '印度尼西亚', 'Philippines': '菲律宾', 'Japan': '日本',
    'North Korea': '朝鲜', 'South Korea': '韩国', 'Brunei': '文莱',
    'Sri Lanka': '斯里兰卡',
}
NE_LABEL = {
    '俄罗斯': (104, 54), '蒙古': (103, 46.5), '哈萨克斯坦': (68, 47), '吉尔吉斯斯坦': (74.5, 41.5),
    '塔吉克斯坦': (71, 38.5), '阿富汗': (66, 34), '巴基斯坦': (69, 30), '印度': (79, 23),
    '尼泊尔': (84, 28.4), '不丹': (90.4, 27.6), '孟加拉国': (90.3, 24), '缅甸': (96, 21),
    '老挝': (103, 19.5), '越南': (107.5, 16.5), '泰国': (101, 15.5), '柬埔寨': (105, 12.3),
    '马来西亚': (102, 3.6), '印度尼西亚': (116, -1.5), '菲律宾': (122, 13), '日本': (138, 37),
    '朝鲜': (127, 40.3), '韩国': (127.8, 36.3), '文莱': (114.6, 4.6), '斯里兰卡': (80.7, 7.6),
}


def clip_ring(ring, win):
    """Sutherland–Hodgman：把环裁剪到经纬度矩形窗口内"""
    x0, y0, x1, y1 = win

    def clip_edge(pts, inside, inter):
        out = []
        n = len(pts)
        for i in range(n):
            a, b = pts[i], pts[(i + 1) % n]
            ia, ib = inside(a), inside(b)
            if ia:
                out.append(a)
                if not ib:
                    out.append(inter(a, b))
            elif ib:
                out.append(inter(a, b))
        return out

    def ix(a, b, x):
        t = (x - a[0]) / (b[0] - a[0]) if b[0] != a[0] else 0
        return (x, a[1] + t * (b[1] - a[1]))

    def iy(a, b, y):
        t = (y - a[1]) / (b[1] - a[1]) if b[1] != a[1] else 0
        return (a[0] + t * (b[0] - a[0]), y)

    pts = list(ring)
    if pts and pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) < 3:
        return []
    pts = clip_edge(pts, lambda p: p[0] >= x0, lambda a, b: ix(a, b, x0))
    if len(pts) < 3: return []
    pts = clip_edge(pts, lambda p: p[0] <= x1, lambda a, b: ix(a, b, x1))
    if len(pts) < 3: return []
    pts = clip_edge(pts, lambda p: p[1] >= y0, lambda a, b: iy(a, b, y0))
    if len(pts) < 3: return []
    pts = clip_edge(pts, lambda p: p[1] <= y1, lambda a, b: iy(a, b, y1))
    return pts if len(pts) >= 3 else []


neighbors = []
china_outline = []
if os.path.exists(NE_PATH):
    ne = json.load(open(NE_PATH, encoding='utf-8'))

    def proj_paths(g):
        """把 (Multi)Polygon 投影为 SVG path，保留多环与孔洞（配合 fill-rule=evenodd）"""
        polys = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
        segs = []
        for poly in polys:
            for ring in poly:
                pts = [tf(pt) for pt in ring]
                if len(pts) < 3:
                    continue
                # 去掉极近重复点，压缩体积（不改变形状）
                out = [pts[0]]
                for q in pts[1:]:
                    if abs(q[0] - out[-1][0]) > 0.08 or abs(q[1] - out[-1][1]) > 0.08:
                        out.append(q)
                # 面积过小的碎岛省去（对整体形状无影响）
                ar = 0.0
                for k in range(len(out)):
                    x1, y1 = out[k]
                    x2, y2 = out[(k + 1) % len(out)]
                    ar += x1 * y2 - x2 * y1
                if len(out) >= 3 and abs(ar) / 2 > 0.02:
                    segs.append('M' + 'L'.join('%s %s' % (fmt(x), fmt(y)) for x, y in out) + 'Z')
        return ''.join(segs)

    for f in ne['features']:
        nm = f['properties'].get('ADMIN') or f['properties'].get('NAME')
        g = f['geometry']
        if not g:
            continue
        if nm == 'China':
            # 用于给邻国层做蒙版：遮住中国领土范围，避免与省界不一致造成碎片填充
            china_outline.append(proj_paths(g))
            continue
        if nm not in NE_WANT:
            continue
        # 只保留邻近区域的国家（按经纬度包围盒粗筛），不做裁剪以免破坏形状
        xs = [pt[0] for poly in (g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]) for ring in poly for pt in ring]
        ys = [pt[1] for poly in (g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]) for ring in poly for pt in ring]
        if not xs or max(xs) < 55 or min(xs) > 155 or max(ys) < -12 or min(ys) > 58:
            continue
        d = proj_paths(g)
        if not d:
            continue
        cn = NE_WANT[nm]
        lab = NE_LABEL.get(cn)
        neighbors.append({
            'name': cn,
            'd': d,
            'label': [round(v, 1) for v in tf(lab)] if lab else None,
        })
    print('周边国家：%d 个（%s）' % (len(neighbors), '、'.join(n['name'] for n in neighbors)))
    print('中国轮廓（蒙版用）：%d 段，%d 字符' % (len(china_outline), sum(len(x) for x in china_outline)))

# ---------------------------------------------------------------------------
# 南海诸岛：并入主画布（同一地理关系，位于海南岛正南），采用等距圆柱投影，
# 与主图南部比例衔接。画布可拖动，用户可自行移到南海查看。
# ---------------------------------------------------------------------------
# 与主图使用同一 Albers 投影：南海诸岛与大陆、周边国家的地理关系因此严格一致
def sstf(lon, lat):
    return tuple(round(v, 1) for v in tf((lon, lat)))


# ---------------------------------------------------------------------------
# 南海诸岛界线（九段线）
# 说明：此线需要贴合邻国海岸走向，本工程可获取的 Natural Earth 110m 海岸线精度不足
# （巴拉望等狭窄岛体已被简化），自动贴边或手工摆点都会画歪，因此**默认不绘制自绘线**。
# 若提供权威线数据（如官方出版的矢量线），放入 data/nine_dash.json：
#   {"lines": [[[lon,lat],[lon,lat],...], ...]}   # 每段线一个数组
# 本脚本会按主图同一投影生成 nineDash 图层，前端自动绘制。
# ---------------------------------------------------------------------------
NINE_DASH_PATH = os.path.join(HERE, 'data', 'nine_dash.json')
nine_dash = []
if os.path.exists(NINE_DASH_PATH):
    try:
        _nd = json.load(open(NINE_DASH_PATH, encoding='utf-8'))
        for _line in _nd.get('lines', []):
            pts = [sstf(pt[0], pt[1]) for pt in _line]
            if len(pts) >= 2:
                nine_dash.append('M' + 'L'.join('%s %s' % (fmt(x), fmt(y)) for x, y in pts))
        print('九段线：已从 data/nine_dash.json 载入 %d 段' % len(nine_dash))
    except Exception as _e:
        print('九段线数据解析失败（跳过）：%s' % _e)
else:
    print('九段线：未提供权威线数据，本次不绘制（礁岛点位与岛群标注仍按真实坐标绘制）')

ss = {
    'scale': 1321.744,
    'nineDash': nine_dash,      # 有权威数据时非空
    'dots': [],
    'labels': [],
}
# 真实礁岛点位（数据中海海南诸岛碎块，保留经纬度便于聚类标注）
for poly in south_islands:
    ring = poly[0]
    lon = sum(pt[0] for pt in ring) / len(ring)
    lat = sum(pt[1] for pt in ring) / len(ring)
    if lat < 2.0:
        continue
    ss['dots'].append(list(sstf(lon, lat)) + [round(lon, 2), round(lat, 2)])
# 最南端曾母暗沙（公开资料约 3.9°N、112.3°E）
ss['dots'].append(list(sstf(112.3, 3.9)) + [112.3, 3.9])

# 岛群标注：按固定地理坐标定位（置于该群组北侧），避免聚类误差导致标注错位
for nm, lon, lat in (('东沙群岛', 116.7, 21.4), ('西沙群岛', 112.0, 17.6),
                     ('中沙群岛', 114.6, 16.6), ('南沙群岛', 114.2, 10.6),
                     ('黄岩岛', 118.6, 15.3), ('曾母暗沙', 111.6, 3.2)):
    ss['labels'].append({'name': nm, 'p': list(sstf(lon, lat))})
ss['titlePos'] = list(sstf(112.4, 19.4))

# ---------------------------------------------------------------------------
# 原始县级几何索引 + 多边形合并（dissolve）
# 相邻县共用边界顶点，故可用「边抵消」求并集外轮廓：成对反向的边是内部边，抵消；
# 剩余边串成外环。这样得到的整块轮廓没有缝隙，可正常描边，且比逐县拼接小得多。
# ---------------------------------------------------------------------------
_RAW_INDEX_PATH = os.path.join(HERE, 'data', '_county_raw_index.json')


def _load_raw_index():
    import glob as _glob
    if os.path.exists(_RAW_INDEX_PATH):
        try:
            return json.load(open(_RAW_INDEX_PATH, encoding='utf-8'))
        except Exception:
            pass
    idx = {}
    for fp in _glob.glob(os.path.join(HERE, 'data', '_county_cache', '*.json')):
        try:
            d = json.load(open(fp, encoding='utf-8'))
        except Exception:
            continue
        for f in d.get('features', []):
            code = f.get('properties', {}).get('adcode')
            g = f.get('geometry')
            if code and g and g.get('coordinates'):
                idx.setdefault(str(code), g)
    json.dump(idx, open(_RAW_INDEX_PATH, 'w', encoding='utf-8'),
              ensure_ascii=False, separators=(',', ':'))
    return idx


RAW = _load_raw_index()


def _raw_rings(code):
    g = RAW.get(str(code))
    if not g:
        return []
    polys = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
    return [(ring, i == 0) for poly in polys for i, ring in enumerate(poly)]


def concat_path(codes, eps=0.02, snap=0.001):
    """把若干县的环直接拼成一条路径（不做布尔合并）。
    先把顶点吸附到 snap 网格（默认 0.001°≈100m）：相邻县边界顶点原本存在微小差异，
    吸附后缝隙落到亚像素级，再由前端 landLook 滤镜补上，避免出现"马赛克"纹理。
    必须以 fill-rule:nonzero 渲染——环绕向不一致时只会叠加，不会互相挖空（evenodd 会挖出空洞）。"""
    segs, xs, ys = [], [], []
    for code in codes:
        for ring, _outer in _raw_rings(code):
            pts = ring[:-1] if ring and ring[0] == ring[-1] else list(ring or [])
            if len(pts) < 3:
                continue
            q = []
            for x, y in pts:
                px, py = round(x / snap) * snap, round(y / snap) * snap
                if not q or (px, py) != q[-1]:
                    q.append((px, py))
            if len(q) > 2 and q[0] == q[-1]:
                q.pop()
            if len(q) < 3:
                continue
            r = rdp(q, eps) if len(q) > 6 else q
            if len(r) < 3:
                continue
            pp = [tf(pt) for pt in r]
            segs.append('M' + 'L'.join('%s %s' % (fmt(x), fmt(y)) for x, y in pp) + 'Z')
            xs.extend(x for x, _ in pp)
            ys.extend(y for _, y in pp)
    if not segs:
        return None, None
    return ''.join(segs), [round(sum(xs) / len(xs), 1), round(sum(ys) / len(ys), 1)]


def dissolve(codes, grid=2e-4):
    """把若干县级单位合并，返回外环列表（经纬度，未简化）"""
    cnt = {}
    for code in codes:
        for ring, _outer in _raw_rings(code):
            pts = [(round(x / grid) * grid, round(y / grid) * grid) for x, y in ring]
            q = [pts[0]]
            for pt in pts[1:]:
                if pt != q[-1]:
                    q.append(pt)
            if len(q) < 4:
                continue
            if q[0] != q[-1]:
                q.append(q[0])
            for i in range(len(q) - 1):
                e = (q[i], q[i + 1])
                cnt[e] = cnt.get(e, 0) + 1
    out = []
    for e, n in cnt.items():
        rev = cnt.get((e[1], e[0]), 0)
        if n > rev:
            out.extend([e] * (n - rev))
    if not out:
        return []
    from collections import defaultdict
    adj = defaultdict(list)
    for a, b in out:
        adj[a].append(b)
    used, rings = set(), []
    for a, b in out:
        if (a, b) in used:
            continue
        ring = [a]
        used.add((a, b))
        cur = b
        while True:
            nxt = None
            for c in adj[cur]:
                if (cur, c) not in used:
                    nxt = c
                    break
            if nxt is None:
                break
            used.add((cur, nxt))
            if nxt == ring[0]:
                break
            ring.append(nxt)
            cur = nxt
        if len(ring) >= 3:
            rings.append(ring + [ring[0]])
    return rings


def outline_path(codes, eps=0.028):
    """合并 -> 简化 -> 投影，返回 (path, label)"""
    rings = dissolve(codes)
    if not rings:
        return None, None
    segs, xs, ys = [], [], []
    for r in rings:
        pts = r[:-1] if r[0] == r[-1] else r[:]
        q = rdp(pts, eps) if len(pts) > 6 else pts
        if len(q) < 3:
            continue
        pp = [tf(pt) for pt in q]
        segs.append('M' + 'L'.join('%s %s' % (fmt(x), fmt(y)) for x, y in pp) + 'Z')
        xs.extend(x for x, _ in pp)
        ys.extend(y for _, y in pp)
    if not segs:
        return None, None
    return ''.join(segs), [round(sum(xs) / len(xs), 1), round(ys and sum(ys) / len(ys), 1)]


# ---------------------------------------------------------------------------
# 割据区 / 根据地（跨省、只占部分县）：按县组合成面，用主图同一投影
# ---------------------------------------------------------------------------
TERR_PATH = os.path.join(HERE, 'data', 'territories.json')
CNTY_PATH = os.path.join(HERE, 'data', 'counties.json')
territories = []
if os.path.exists(TERR_PATH) and os.path.exists(CNTY_PATH):
    _terr = json.load(open(TERR_PATH, encoding='utf-8'))['territories']
    _cnty = json.load(open(CNTY_PATH, encoding='utf-8'))['counties']
    _miss = set()
    for t in _terr:
        codes = []
        for cn in t['counties']:
            c = _cnty.get(cn)
            if not c:
                _miss.add(cn)
                continue
            if c.get('adcode'):
                codes.append(c['adcode'])
        d, lab = concat_path(codes, eps=0.02)
        if not d:
            continue
        territories.append({
            'name': t['name'],
            'faction': t['faction'],
            'from': t['from'],
            'to': t['to'],
            'd': d,
            'label': lab,
            'counties': t['counties'],
            'note': t.get('note', ''),
            'sources': t.get('sources', []),
        })
    print('割据区：%d 个（共 %d 个县）' % (len(territories), sum(len(t['counties']) for t in territories)))
    if _miss:
        print('  !! 缺少县几何：%s' % '、'.join(sorted(_miss)))


# ---------------------------------------------------------------------------
# 历史区划底图：按时期把现行县级单位重组为当时的省级单位（先 dissolve 成整块再简化，
# 因此没有县界缝隙，可与现行省界同样式描边）。几何按“分配签名”去重，只存一份。
# ---------------------------------------------------------------------------
HU_PATH = os.path.join(HERE, 'data', 'historical_units.json')
CA_PATH = os.path.join(HERE, 'data', 'counties_all.json')
hist = {'periods': [], 'geoms': []}
if os.path.exists(HU_PATH) and os.path.exists(CA_PATH):
    # 时期数据：优先读 S4 的 sources/periods/*.json（每朝一个文件、月级锚点）；
    # 缺失时回退到旧的 historical_units.json，保证构建不中断
    _PDIR = os.path.join(HERE, 'data', 'sources', 'periods')
    if os.path.isdir(_PDIR) and sorted(f for f in os.listdir(_PDIR) if f.endswith('.json')):
        _periods = []
        for _fn in sorted(os.listdir(_PDIR)):
            if not _fn.endswith('.json'):
                continue
            _q = json.load(open(os.path.join(_PDIR, _fn), encoding='utf-8'))
            _periods.append({
                'from': [_q['from']['y'], _q['from']['m']],
                'to': [_q['to']['y'], _q['to']['m']],
                'label': _q['label'],
                'note': _q.get('note', ''),
                'provinceRename': (_q.get('divisions') or {}).get('rename') or {},
                'merge': (_q.get('divisions') or {}).get('merge') or {},
                'units': (_q.get('divisions') or {}).get('units') or [],
            })
        _periods.sort(key=lambda x: x['from'][0] * 12 + x['from'][1])
        _hu = {'periods': _periods, 'source': 'sources/periods/*.json'}
        print('  时期来源        sources/periods/（%d 个文件）' % len(_periods))
    else:
        _hu = json.load(open(HU_PATH, encoding='utf-8'))
        print('  ⚠ 时期来源回退到 historical_units.json（未找到 sources/periods/）')
    _ca = json.load(open(CA_PATH, encoding='utf-8'))['counties']
    # 全部省份都参与历史区划重组（清前期的并省涉及安徽、湖南等，不能只列少数省）
    AFFECTED = sorted({_np(k.split('|', 1)[0]) for k in _ca}) if '_np' in dir() else None
    _SUF = re.compile(r'(省|市|自治区|特别行政区|壮族|回族|维吾尔|自治州)$')

    def _np(nm):
        prev = None
        while prev != nm:
            prev = nm
            nm = _SUF.sub('', nm)
        return nm or prev

    # 全部省份都参与历史区划重组（清前期并省涉及安徽、湖南等）
    AFFECTED = sorted({_np(k.split('|', 1)[0]) for k in _ca})
    CITY, CODE_OF = {}, {}
    for _k, _v in _ca.items():
        _p = _np(_k.split('|', 1)[0])
        if _p not in AFFECTED:
            continue
        CITY.setdefault((_p, (_v.get('city') or _k.split('|', 1)[1])), []).append(_k)
        CODE_OF[_k] = _v.get('adcode')

    SIG_INDEX, PERIODS = {}, []
    SHAPES, SHAPE_INDEX = [], {}       # 形状全局去重：(unitKey, 县集合) -> 形状下标
    for per in _hu['periods']:
        fy, fm = per['from']; ty, tm = per['to']
        ren = per.get('provinceRename', {})
        merges = per.get('merge', {})
        units = per.get('units', [])
        assign = {}
        for (prov, city), keys in CITY.items():
            target = prov
            if city in merges:
                target = merges[city]
            elif prov in merges:
                target = merges[prov]
            for u in units:
                if city in u.get('cities', []) or prov in u.get('provinces', []):
                    target = u.get('key') or u['name']     # key 为数据键（规范省名），name 仅用于显示
                    break
            for k in keys:
                # 县级划转优先（merge 的键也可以是「省|县名」或县名）
                cname = k.split('|', 1)[1]
                if k in merges:
                    assign[k] = merges[k]
                elif cname in merges:
                    assign[k] = merges[cname]
                else:
                    assign[k] = target
        # 几何未变的省份不必重建（否则会与现行省界重叠、地名成对出现）
        prov_codes = {}
        for (prov, city), keys in CITY.items():
            prov_codes.setdefault(prov, set()).update(keys)
        drop = set()
        for prov, allk in prov_codes.items():
            if prov in ren or prov in merges:
                continue
            got = set(k for k, t in assign.items() if t == prov)
            if got == allk:
                drop.add(prov)
        if drop:
            assign = {k: t for k, t in assign.items()
                      if not (t in drop and k in prov_codes.get(t, ())) }
        sig = tuple(sorted((v, k) for k, v in assign.items()))
        if sig not in SIG_INDEX:
            by_unit = {}
            for k, t in assign.items():
                by_unit.setdefault(t, []).append(CODE_OF.get(k))
            g = {}
            for t, codes in by_unit.items():
                key = (t, tuple(sorted(c for c in codes if c)))
                if key not in SHAPE_INDEX:
                    d, lab = concat_path([c for c in codes if c])
                    if d:
                        SHAPE_INDEX[key] = len(SHAPES)
                        SHAPES.append({'d': d, 'label': lab})
                if key in SHAPE_INDEX:
                    g[t] = SHAPE_INDEX[key]

            SIG_INDEX[sig] = len(hist['geoms'])
            hist['geoms'].append(g)
        gidx = SIG_INDEX[sig]
        names = {t: ren.get(t, t) for t in hist['geoms'][gidx]}
        # 需要隐藏现行省界的省份：①几何被重建者 ②所辖县全部划归他处者
        shape_keys = set(hist['geoms'][gidx].keys())
        repl = []
        for prov in AFFECTED:
            if prov in shape_keys:
                repl.append(prov)          # 几何被重建 → 隐藏现行省界
            elif prov in drop:
                continue                   # 几何未变 → 保留现行省界与地名
            else:
                repl.append(prov)          # 辖县全部划归他处 → 隐藏
        fbf = {}
        for u in units:
            k = u.get('key') or u['name']
            fbf[k] = u.get('factionFrom') or k
        PERIODS.append({
            'fromM': fy * 12 + fm - 1, 'toM': ty * 12 + tm - 1,
            'label': per.get('label', ''), 'note': per.get('note', ''),
            'geom': gidx, 'shapeNames': names, 'factionFrom': fbf,
            'replace': sorted(set(repl)),
        })
    hist['periods'] = PERIODS
    hist['shapes'] = SHAPES
    # 逐月区划表：monthDiv[i] = 该月使用的几何集合下标（i 为绝对月序号 - 1893.01）
    _m0 = PERIODS[0]['fromM']
    _m1 = PERIODS[-1]['toM']
    month_div = []
    for _m in range(_m0, _m1 + 1):
        _hit = -1
        for _p in PERIODS:
            if _p['fromM'] <= _m <= _p['toM']:
                _hit = _p['geom']
                break
        month_div.append(_hit)
    hist['monthDiv'] = month_div
    hist['monthDivM0'] = _m0
    _gaps = [i for i, v in enumerate(month_div) if v < 0]
    print('逐月区划表：%d 个月（%d—%d），未覆盖 %d 个月'
          % (len(month_div), _m0, _m1, len(_gaps)))
    print('历史区划：%d 个时期，%d 套几何，去重后形状 %d 个（未去重前 %d）'
          % (len(PERIODS), len(hist['geoms']), len(SHAPES), sum(len(g) for g in hist['geoms'])))

VB_W = max(1000 + 60, max(p[0] for p in ss['dots']) + 32) if ss['dots'] else 1000
VB_H = max(H, max(p[1] for p in ss['dots']) + 34) if ss['dots'] else H

out = {
    'viewBox': [0, 0, WORLD_W, WORLD_H],                 # 世界画布
    'core': [round(CN[0], 1), round(CN[1], 1),
             round(CN[2] - CN[0], 1), round(CN[3] - CN[1], 1)],   # 中国范围（初始镜头）
    'world': [0, 0, WORLD_W, WORLD_H],
    'paths': paths,
    'centroids': {k: list(v) for k, v in centroids.items()},
    'southSea': ss,
    'neighbors': neighbors,
    'territories': territories,
    'hist': hist,
    'chinaOutline': ''.join(china_outline),
    'lonlat': {},
}
# 供定位事件点用：把省会/中心经纬度投影好
for f in prov_feats:
    c = f['properties'].get('centroid') or f['properties'].get('center')
    if c:
        out['lonlat'][f['properties']['name']] = [round(v, 1) for v in tf(c)]

# ---- 几何压缩：把 'd' 路径改写为 'c'（base64 增量编码），前端一次性还原 ----
def _compress_all(o):
    if isinstance(o, dict):
        if isinstance(o.get('d'), str) and o['d']:
            _c, _n = encode_d(o['d'])
            o['c'] = _c
            o['n'] = _n
            del o['d']
        for _v in o.values():
            _compress_all(_v)
    elif isinstance(o, list):
        for _v in o:
            _compress_all(_v)


_compress_all(out)
# paths 是 名称->字符串，单独处理
out['paths'] = {k: _enc for k, _enc in ((k, encode_d(v)) for k, v in out['paths'].items())}
out['paths'] = {k: {'c': c, 'n': n} for k, (c, n) in out['paths'].items()}
if isinstance(out.get('chinaOutline'), str) and out['chinaOutline']:
    _c, _n = encode_d(out['chinaOutline'])
    out['chinaOutline'] = {'c': _c, 'n': _n}

dst = os.path.join(HERE, 'data', 'geo.json')
with open(dst, 'w', encoding='utf-8') as fh:
    json.dump(out, fh, ensure_ascii=False, separators=(',', ':'))
print('provinces:', len(paths), '| data/geo.json bytes:', os.path.getsize(dst))
print('sample 北京 path head:', paths['北京'][:60])
print('centroid 四川:', centroids['四川'], 'lonlat 四川:', out['lonlat'].get('四川'))
