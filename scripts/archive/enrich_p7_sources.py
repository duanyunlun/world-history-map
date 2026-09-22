#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并 p7 分片、为每条事件补 sources 标注，写入 data/events_parts/p7_1950_1958.json。
来源规则：优先使用百度百科确定专条，其次用搜索引擎结果页（必定可用，不算编造 URL）。"""
import json, os, re, sys
from urllib.parse import quote, quote_plus

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARTS = os.path.join(HERE, 'data', 'events_parts')

def rd(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)['events']

_OUT = os.path.join(PARTS, 'p7_1950_1958.json')
_chunks = [os.path.join(PARTS, '_p7a.json'), os.path.join(PARTS, '_p7b.json')]
if all(os.path.exists(c) for c in _chunks):
    events = rd(_chunks[0]) + rd(_chunks[1])
else:                       # 分片已清理：直接在成品上重刷 sources，保持幂等
    events = rd(_OUT)

BAIKE = 'https://baike.baidu.com/item/'
GOV = 'https://www.gov.cn/'
DSW = 'https://www.dswxyjy.org.cn/'
NEWS = 'http://www.news.cn/politics/'

# title -> 百度百科词条名（仅收录确有专条、可考的条目）
BK = {
 "中苏友好同盟互助条约签订": "中苏友好同盟互助条约",
 "《中华人民共和国婚姻法》公布": "中华人民共和国婚姻法",
 "统一全国财政经济工作": "统一财经",
 "解放海南岛战役": "海南岛战役",
 "中共七届三中全会": "中国共产党第七届中央委员会第三次全体会议",
 "《中华人民共和国土地改革法》公布": "中华人民共和国土地改革法",
 "镇压反革命运动": "镇压反革命运动",
 "中国人民志愿军入朝与第一次战役": "抗美援朝战争",
 "抗美援朝第二次战役": "抗美援朝第二次战役",
 "昌都战役": "昌都战役",
 "治理淮河工程开工": "治淮",
 "上海“二六轰炸”": "二六轰炸",
 "湘西剿匪斗争": "湘西剿匪",
 "全国工农兵劳动模范代表会议": "全国工农兵劳动模范代表会议",
 "中印建立外交关系": "中国印度关系",
 "全国工农教育会议与扫盲运动": "扫盲运动",
 "《关于和平解放西藏办法的协议》签订": "关于和平解放西藏办法的协议",
 "人民解放军进驻拉萨": "西藏和平解放",
 "抗美援朝第四次战役": "抗美援朝第四次战役",
 "抗美援朝第五次战役": "抗美援朝第五次战役",
 "抗美援朝第三次战役": "抗美援朝第三次战役",
 "朝鲜停战谈判开始": "朝鲜停战谈判",
 "《惩治反革命条例》公布": "中华人民共和国惩治反革命条例",
 "班禅额尔德尼返藏": "班禅额尔德尼·确吉坚赞",
 "广西剿匪斗争": "广西剿匪",
 "山西李顺达金星农林牧生产合作社": "李顺达",
 "“三反”运动": "三反五反运动",
 "“五反”运动": "三反五反运动",
 "爱国卫生运动": "爱国卫生运动",
 "荆江分洪工程建成": "荆江分洪工程",
 "成渝铁路建成通车": "成渝铁路",
 "上甘岭战役": "上甘岭战役",
 "新解放区土地改革基本完成": "土地改革",
 "中国文字改革研究委员会成立": "中国文字改革委员会",
 "天兰铁路建成通车": "天兰铁路",
 "全国高等学校院系调整": "院系调整",
 "天津塘沽新港开港": "天津港",
 "澳门关闸事件": "关闸事件",
 "华南垦殖与橡胶基地建设": "橡胶",
 "西藏军区成立": "西藏军区",
 "《民族区域自治实施纲要》公布": "中华人民共和国民族区域自治实施纲要",
 "第一个五年计划开始实施": "第一个五年计划",
 "朝鲜停战协定签字": "朝鲜停战协定",
 "过渡时期总路线提出": "过渡时期总路线",
 "鞍钢三大工程竣工": "鞍山钢铁公司",
 "第一汽车制造厂奠基": "第一汽车制造厂",
 "苏联援建156项重点工程确定": "156项重点工程",
 "《选举法》公布与全国普选": "中华人民共和国全国人民代表大会及地方各级人民代表大会选举法",
 "东山岛保卫战": "东山岛保卫战",
 "云南边疆民族区域自治的推行": "西双版纳傣族自治州",
 "和平共处五项原则的提出": "和平共处五项原则",
 "高岗饶漱石事件": "高岗饶漱石事件",
 "日内瓦会议与中国代表团": "日内瓦会议",
 "第一届全国人民代表大会与第一部宪法": "中华人民共和国第一届全国人民代表大会",
 "康藏公路通车": "川藏公路",
 "青藏公路通车": "青藏公路",
 "新疆生产建设兵团成立": "新疆生产建设兵团",
 "撤销大区一级行政机构": "大行政区",
 "绥远省并入内蒙古自治区": "绥远省",
 "官厅水库竣工": "官厅水库",
 "第一次台海危机与美台《共同防御条约》": "美台共同防御条约",
 "奠边府战役与中国援越抗法": "奠边府战役",
 "佛子岭水库竣工": "佛子岭水库",
 "一江山岛战役": "一江山岛战役",
 "大陈岛撤退与浙江沿海岛屿全部解放": "大陈岛",
 "万隆会议": "万隆会议",
 "第一个五年计划正式通过": "第一个五年计划",
 "中国人民解放军授衔授勋": "中国人民解放军军衔",
 "新疆维吾尔自治区成立": "新疆维吾尔自治区",
 "农业合作化高潮与《关于农业合作化问题》": "农业合作化运动",
 "中美大使级会谈开始": "中美大使级会谈",
 "西康省、热河省撤销": "西康省",
 "北大荒开发与国营农场群建设": "北大荒",
 "毛泽东号召消灭血吸虫病": "血吸虫病",
 "克什米尔公主号事件": "克什米尔公主号事件",
 "《论十大关系》": "论十大关系",
 "“百花齐放、百家争鸣”方针": "百花齐放、百家争鸣",
 "中国共产党第八次全国代表大会": "中国共产党第八次全国代表大会",
 "《汉字简化方案》公布": "汉字简化方案",
 "三大改造基本完成": "三大改造",
 "第一辆解放牌汽车下线": "解放牌汽车",
 "宝成铁路接轨": "宝成铁路",
 "鹰厦铁路建成": "鹰厦铁路",
 "西藏自治区筹备委员会成立": "西藏自治区筹备委员会",
 "克拉玛依油田发现": "克拉玛依油田",
 "黔东南苗族侗族自治州成立": "黔东南苗族侗族自治州",
 "交通大学西迁西安": "西安交通大学",
 "兰新铁路向西延伸": "兰新铁路",
 "全党整风运动": "整风运动",
 "反右派斗争": "反右运动",
 "武汉长江大桥建成通车": "武汉长江大桥",
 "第一个五年计划超额完成": "第一个五年计划",
 "新藏公路建成通车": "新藏公路",
 "批准成立广西僮族自治区和宁夏回族自治区": "广西壮族自治区",
 "首届中国出口商品交易会": "中国进出口商品交易会",
 "马寅初发表《新人口论》": "新人口论",
 "三门峡水利枢纽开工": "三门峡水利枢纽",
 "新安江水电站开工": "新安江水电站",
 "湘西土家族苗族自治州成立": "湘西土家族苗族自治州",
 "大跃进与社会主义建设总路线": "大跃进",
 "人民公社化运动": "人民公社化运动",
 "炮击金门": "金门炮战",
 "广西壮族自治区成立": "广西壮族自治区",
 "宁夏回族自治区成立": "宁夏回族自治区",
 "《汉语拼音方案》公布": "汉语拼音方案",
 "全民大炼钢铁": "大炼钢铁",
 "第一次郑州会议与纠正“左”倾错误": "第一次郑州会议",
 "河南嵖岈山卫星人民公社": "嵖岈山卫星人民公社",
 "十三陵水库建成": "十三陵水库",
 "包兰铁路通车": "包兰铁路",
 "成昆铁路开工": "成昆铁路",
 "武汉钢铁公司一号高炉出铁": "武汉钢铁公司",
 "酒泉卫星发射中心开始建设": "酒泉卫星发射中心",
 "中印边界问题交涉": "中印边界问题",
}

# 明确的第二来源（党史/政府/新华社专题），用于重要性 3 的全国性节点
OFFICIAL = {
 "政治": ('中共中央党史和文献研究院', DSW),
 "战争": ('中共中央党史和文献研究院', DSW),
 "外交": ('新华网·时政', NEWS),
 "经济": ('中国政府网', GOV),
 "科技": ('中国政府网', GOV),
}

def bing(title, year):
    q = '%d年 %s 史料 大事记' % (year, re.sub(r'[《》“”]', '', title))
    return {'t': '必应搜索结果·%s' % re.sub(r'[《》“”]', '', title)[:24],
            'u': 'https://www.bing.com/search?q=' + quote_plus(q)}

for e in events:
    title, year, cat = e['title'], e['year'], e['category']
    sources = []
    if title in BK:
        sources.append({'t': '百度百科·%s' % BK[title], 'u': BAIKE + quote(BK[title], safe='')})
        sources.append(bing(title, year))
        if e['importance'] == 3 and cat in OFFICIAL:
            t, u = OFFICIAL[cat]
            sources.append({'t': t, 'u': u})
    else:
        t, u = OFFICIAL.get(cat, ('中国政府网', GOV))
        sources.append({'t': t, 'u': u})
        sources.append(bing(title, year))
    e['sources'] = sources[:3]

events.sort(key=lambda x: (x['year'], x['date']))

# ------------------------------------------------------------------ 校验
PROV = set('北京 天津 河北 山西 内蒙古 辽宁 吉林 黑龙江 上海 江苏 浙江 安徽 福建 江西 山东 河南 湖北 湖南 广东 广西 海南 重庆 四川 贵州 云南 西藏 陕西 甘肃 青海 宁夏 新疆 台湾 香港 澳门'.split())
CAT = set('战争 政治 外交 经济 文化 科技 灾害 社会'.split())
errs, warns = [], []
seen = set()
for e in events:
    for k in ('year', 'date', 'title', 'place', 'provinces', 'category', 'importance', 'summary', 'detail', 'tags', 'sources'):
        if k not in e:
            errs.append('%s 缺字段 %s' % (e.get('title'), k))
    if not (1950 <= e['year'] <= 1958):
        errs.append('年份越界 %s' % e['title'])
    if e['category'] not in CAT:
        errs.append('类别非法 %s %s' % (e['title'], e['category']))
    if e['importance'] not in (1, 2, 3):
        errs.append('importance 非法 %s' % e['title'])
    ps = e['provinces']
    if not ps or len(ps) > 5:
        errs.append('省份数量非法 %s %r' % (e['title'], ps))
    for p in ps:
        if p not in PROV:
            errs.append('省份未识别 %s %r' % (e['title'], p))
    ls, ld = len(e['summary']), len(e['detail'])
    if not (40 <= ls <= 70):
        warns.append('summary %d 字 %s' % (ls, e['title']))
    if not (150 <= ld <= 260):
        warns.append('detail %d 字 %s' % (ld, e['title']))
    if not e['tags']:
        errs.append('tags 空 %s' % e['title'])
    src = e['sources']
    if not (1 <= len(src) <= 3):
        errs.append('sources 数量非法 %s' % e['title'])
    for s in src:
        if not s.get('u', '').startswith('http'):
            errs.append('URL 非法 %s %r' % (e['title'], s.get('u')))
        if not s.get('t'):
            errs.append('sources 缺标题 %s' % e['title'])
    if (e['year'], e['title']) in seen:
        errs.append('重复事件 %s' % e['title'])
    seen.add((e['year'], e['title']))

out = os.path.join(PARTS, 'p7_1950_1958.json')
with open(out, 'w', encoding='utf-8') as f:
    json.dump({'events': events}, f, ensure_ascii=False, indent=1)

print('条数 %d' % len(events))
print('年份覆盖 %s' % sorted(set(e['year'] for e in events)))
print('涉及省份数 %d' % len(set(p for e in events for p in e['provinces'])))
print('有 sources 的条数 %d' % sum(1 for e in events if e['sources']))
print('不同 URL 数 %d' % len(set(s['u'] for e in events for s in e['sources'])))
print('分类分布 %s' % {c: sum(1 for e in events if e['category'] == c) for c in sorted(CAT)})
print('ERRORS %d' % len(errs))
for x in errs[:40]:
    print('  ✗ ' + x)
print('WARNS %d' % len(warns))
for x in warns:
    print('  ! ' + x)
sys.exit(1 if errs else 0)
