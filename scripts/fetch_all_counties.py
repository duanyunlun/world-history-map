#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抓取全国县级边界（用于按历史时期重组省级区划）。
省(_full) -> 地级市(_full) -> 区县；简化后写入 data/counties_all.json。
缓存复用 data/_county_cache/，可重复运行。
"""
import json, os, math, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, 'data', '_county_cache')
OUT = os.path.join(ROOT, 'data', 'counties_all.json')
BASE = 'https://geo.datav.aliyun.com/areas_v3/bound/%s_full.json'
UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0 Safari/537.36')
EPS = float(os.environ.get('COUNTY_EPS', '0.02'))


def fetch(adcode):
    os.makedirs(CACHE, exist_ok=True)
    fp = os.path.join(CACHE, '%s.json' % adcode)
    if os.path.exists(fp):
        return json.load(open(fp, encoding='utf-8'))
    if os.path.exists(fp + '.404'):
        return None
    req = urllib.request.Request(BASE % adcode, headers={'User-Agent': UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                d = json.loads(r.read().decode('utf-8'))
            json.dump(d, open(fp, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
            time.sleep(0.2)
            return d
        except Exception as e:
            if attempt == 3:
                if '404' in str(e):
                    open(fp + '.404', 'w').close()
                else:
                    print('   !! %s: %s' % (adcode, e))
                return None
            time.sleep(1.6)


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


def simp_ring(ring):
    closed = ring[0] == ring[-1]
    pts = ring[:-1] if closed else ring[:]
    if len(pts) < 3:
        return None
    s = rdp(pts, EPS)
    if len(s) < 3:
        return None
    s = [(round(x, 3), round(y, 3)) for x, y in s]
    if closed:
        s.append(s[0])
    return s


def main():
    provs = fetch(100000)['features']
    out = {}
    for i, pf in enumerate(provs, 1):
        pcode = pf['properties']['adcode']
        pname = pf['properties']['name']
        if not isinstance(pcode, int):
            continue
        pdata = fetch(pcode)
        if not pdata:
            continue
        def take(ftr, city=''):
            pr = ftr['properties']
            nm = (pr.get('name') or '').strip()
            g = ftr['geometry']
            if not nm or not g:
                return
            polys = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
            rings = []
            for poly in polys:
                for ring in poly:
                    r = simp_ring(ring)
                    if r:
                        rings.append(r)
            if rings:
                out['%s|%s' % (pname, nm)] = {'adcode': pr['adcode'], 'city': city, 'rings': rings,
                                              'centroid': pr.get('centroid') or pr.get('center')}

        # 依据 childrenNum 判定：0 为县级单位（直辖市辖区、省直辖县级市、直筒子市），否则为地级市
        for c in pdata['features']:
            pr = c['properties']
            ccode = pr.get('adcode')
            cname = (pr.get('name') or '').strip()
            if pr.get('childrenNum', 0) == 0 or not isinstance(ccode, int):
                take(c, pname)          # 直辖市辖区等：归属记为该直辖市/省本身
                continue
            cdata = fetch(ccode)
            if not cdata:
                continue
            for f in cdata['features']:
                take(f, cname)
        print('  [%2d/%d] %-8s 累计 %d 个县级单位' % (i, len(provs), pname, len(out)))
    json.dump({'counties': out}, open(OUT, 'w', encoding='utf-8'),
              ensure_ascii=False, separators=(',', ':'))
    print('已写入 %s：%d 个县级单位，%.0f KB' % (OUT, len(out), os.path.getsize(OUT) / 1024))


if __name__ == '__main__':
    main()
