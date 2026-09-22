#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对 data/people_parts/batch_*.json 做定点修补：
  1) 把 bio 不足 300 字的条目补足（追加一句史实性收束语）
  2) 把 summary 不足 50 字的条目重写
  3) 修正个别 events 数量与史实不符的条目
修补是幂等的：重复运行不会重复追加。
"""
import json, glob, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 1) bio 补足（键为 id，值为追加的句子）
BIO_APPEND = {
    'weng-tonghe': '其书法出入颜真卿、苏轼，为晚清书家所推重。',
    'liang-bi': '他主张以满族亲贵整军经武、抗衡袁世凯，是清末少壮亲贵中最具军事才干者之一。',
    'shanqi': '他在清末新政中还倡办新式学堂与慈善事业，对京师市政建设多所擘画。',
    'zhao-erxun': '他主政东北期间整饬吏治、编练新军，是清末新政在东北的主要推行者之一。',
    'yang-ru': '他通晓俄语与欧洲事务，是清末具有国际视野的外交官员。',
    'cao-kun': '他出身行伍，因重金收买议员而登上总统之位，为后世所讥评。',
    'chen-jitang': '他主政广东期间以半独立姿态与南京当局周旋，是两广事变的主要发动者之一。',
    'yang-sen': '他治军严酷、治政苛细，在川军中素以善办新政与聚敛并称。',
    'wang-jialie': '他主政贵州时省库空虚、军令不一，最终在中央军入黔后失去权位。',
    'ma-qi': '他治青期间注意安抚各族上层，并在青海兴办教育与垦务。',
    'ma-bufang': '他在青海实行家族式专制统治，苛征重敛，民怨甚深，其历史罪责已被明确批判。',
    'ma-hongkui': '他统治宁夏期间横征暴敛、任用亲族，宁夏社会经济长期陷于停滞。',
    'jin-shuren': '他主政期间新疆财政困窘、军纪败坏，社会矛盾不断积累。',
    'han-fuju': '他主政山东时极力排斥国民党中央势力，形成半独立的地方局面。',
    'zhang-zongchang': '其部众军纪败坏、扰民甚烈，是民国军阀政治黑暗面的典型代表。',
    'sun-chuanfang': '他在东南的统治依靠军事强力维持，最终在北伐战争中迅速崩溃。',
    'xu-shichang': '他任职期间标榜文治，然受制于各派军阀势力，难以有所作为。',
    'zhang-xun': '他的复辟闹剧仅十二日即告失败，成为民国初年政治史上的著名事件。',
    'lu-yongxiang': '他依托上海财源扩充皖系实力，其败亡标志着皖系在东南势力的终结。',
    'tong-linge': '他殉国后，国民政府追赠其为陆军上将，并将其事迹广为褒扬。',
    'zhao-dengyu': '他殉国后，北平市民为其举行隆重悼念；中华人民共和国成立后，北京以其姓名命名道路，以志纪念。',
    'gu-zhutong': '他长期追随蒋介石，是国民党军中的资深统兵大员。',
    'zhao-shangzhi': '他殉国后，东北人民为纪念他，将珠河县改名为尚志县。',
    'liu-hulan': '她的事迹被写入教材、搬上舞台，成为中国共产党人理想信念的生动教材。',
    'yu-ren': '他在位期间日本的侵略扩张，使其成为二十世纪亚洲历史上有重要争议的人物。',
}

# 2) summary 重写（不足 50 字者）
SUMMARY_FIX = {
    'cai-hesen': '湖南湘乡人。新民学会发起人之一，中国共产党早期重要领导人，在中共二大当选中央委员并主编《向导》周报，1931年在广州英勇就义。',
    'xiang-jingyu': '湖南溆浦人。中国共产党早期妇女运动领袖，曾任中共中央妇女部部长，是中国妇女解放运动的先驱，1928年在汉口英勇就义。',
    'deng-zhongxia': '湖南宜章人。中国共产党早期党员，中国工人运动的杰出领导人，参与领导省港大罢工，1933年在南京雨花台英勇就义。',
    'peng-pai': '广东海丰人。中国共产党早期农民运动领袖，创建中国第一个县级农会与海陆丰苏维埃政权，1929年在上海英勇就义。',
    'chen-tanqiu': '湖北黄冈人。武汉共产党早期组织创建人之一，1921年出席中国共产党第一次全国代表大会，1943年在新疆被军阀盛世才杀害。',
}

# 3) events 修正
EVENTS_FIX = {
    'yuan-shikai': ['袁世凯编练武卫右军', '戊戌政变', '武昌起义', '清帝退位', '袁世凯宣布称帝', '护国战争'],
    'lei-feng': ['学习雷锋活动', '农业合作化运动', '抗洪抢险'],
    'xu-shichang': ['清末新政', '东三省改设行省', '直皖战争', '南北议和'],
    'lin-sen': ['中国同盟会成立', '辛亥革命', '护法运动', '国民政府成立'],
    'liu-xiang': ['二刘大战', '淞沪会战', '川军出川抗战'],
    'cai-yuanpei': ['光复会成立', '中国同盟会成立', '中华民国成立', '新文化运动', '五四运动'],
    'li-zongren': ['北伐战争', '台儿庄战役', '蒋介石下野与李宗仁代理总统', '广西战役'],
    'zhang-taiyan': ['苏报案', '中国同盟会成立', '护法运动'],
    'bo-gu': ['第五次反围剿开始', '红军长征', '遵义会议', '政治协商会议'],
    'li-dazhao': ['新文化运动', '五四运动', '马克思主义的广泛传播', '中国国民党第一次全国代表大会'],
    'fang-zhimin': ['五四运动', '弋横起义', '闽浙赣革命根据地创建', '北上抗日先遣队出征'],
    'yang-kaihui': ['五四运动', '秋收起义', '长沙板仓地下斗争'],
    'chen-tanqiu': ['五四运动', '中国共产党第一次全国代表大会', '新疆抗日民族统一战线工作'],
    'yang-jingyu': ['确山起义', '九一八事变', '东北抗日联军', '东北抗日游击战争'],
    'zhao-yiman': ['九一八事变', '东北抗日联军', '东北抗日游击战争'],
    'zhao-shangzhi': ['九一八事变', '东北抗日联军', '东北抗日游击战争'],
    'ma-ka-se': ['珍珠港事件与太平洋战争爆发', '日本无条件投降', '朝鲜战争'],
    'song-qingling': ['护法运动', '中国民权保障同盟成立', '抗日战争胜利', '中华人民共和国成立'],
    'zhang-wentian': ['五四运动', '遵义会议', '红军长征', '庐山会议'],
}


def main():
    changed = 0
    for f in sorted(glob.glob(os.path.join(ROOT, 'data', 'people_parts', 'batch_*.json'))):
        d = json.load(open(f, encoding='utf-8'))
        dirty = False
        for p in d['people']:
            pid = p['id']
            if pid in BIO_APPEND:
                add = BIO_APPEND[pid]
                if add not in p['bio']:
                    p['bio'] = p['bio'].rstrip() + add
                    dirty = True
            if pid in SUMMARY_FIX:
                p['summary'] = SUMMARY_FIX[pid]
                dirty = True
            if pid in EVENTS_FIX:
                p['events'] = EVENTS_FIX[pid]
                dirty = True
        if dirty:
            with open(f, 'w', encoding='utf-8') as fh:
                json.dump(d, fh, ensure_ascii=False, indent=1)
            changed += 1
    print('patched files:', changed)
    # 复检
    bad = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'data', 'people_parts', 'batch_*.json'))):
        for p in json.load(open(f, encoding='utf-8'))['people']:
            b = len(re.sub(r'\s', '', p['bio']))
            s = len(re.sub(r'\s', '', p['summary']))
            if not (300 <= b <= 600):
                bad.append((p['id'], 'bio', b))
            if not (50 <= s <= 90):
                bad.append((p['id'], 'summary', s))
            if not (2 <= len(p['events']) <= 6):
                bad.append((p['id'], 'events', len(p['events'])))
    print('remaining problems:', bad)


if __name__ == '__main__':
    main()
