#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抓取 aourednik/historical-basemaps 的全球政治边界时间切片（CC-BY-SA 4.0）。
52 个切片：bc123000 — 2010。缓存到 data/_world_cache/，可重复运行。
"""
import json, os, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, 'data', '_world_cache')
UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0 Safari/537.36')
BASE = 'https://cdn.jsdelivr.net/gh/aourednik/historical-basemaps@master/geojson/%s.geojson'

SLICES = ['world_bc123000', 'world_bc10000', 'world_bc8000', 'world_bc5000', 'world_bc4000',
          'world_bc3000', 'world_bc2000', 'world_bc1500', 'world_bc1000', 'world_bc700',
          'world_bc500', 'world_bc400', 'world_bc323', 'world_bc300', 'world_bc200',
          'world_bc100', 'world_bc1', 'world_100', 'world_200', 'world_300', 'world_400',
          'world_500', 'world_600', 'world_700', 'world_800', 'world_900', 'world_1000',
          'world_1100', 'world_1200', 'world_1279', 'world_1300', 'world_1400', 'world_1492',
          'world_1500', 'world_1530', 'world_1600', 'world_1650', 'world_1700', 'world_1715',
          'world_1783', 'world_1800', 'world_1815', 'world_1878', 'world_1880', 'world_1900',
          'world_1914', 'world_1920', 'world_1930', 'world_1938', 'world_1945', 'world_1960',
          'world_1994', 'world_2000', 'world_2010']


def fetch(name):
    os.makedirs(CACHE, exist_ok=True)
    fp = os.path.join(CACHE, name + '.geojson')
    if os.path.exists(fp) and os.path.getsize(fp) > 1000:
        return 'cached'
    req = urllib.request.Request(BASE % name, headers={'User-Agent': UA})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                raw = r.read()
            if len(raw) < 1000:
                raise ValueError('过小')
            json.loads(raw.decode('utf-8'))          # 校验
            open(fp, 'wb').write(raw)
            time.sleep(0.3)
            return 'ok %d KB' % (len(raw) // 1024)
        except Exception as e:
            if attempt == 4:
                return 'FAIL %s' % e
            time.sleep(2.5)
    return 'FAIL'


def main():
    print('切片总数：%d' % len(SLICES))
    for i, s in enumerate(SLICES, 1):
        r = fetch(s)
        print('  [%2d/%d] %-16s %s' % (i, len(SLICES), s, r), flush=True)
    total = sum(os.path.getsize(os.path.join(CACHE, f)) for f in os.listdir(CACHE))
    print('缓存合计 %.1f MB' % (total / 1024 / 1024))


if __name__ == '__main__':
    main()
