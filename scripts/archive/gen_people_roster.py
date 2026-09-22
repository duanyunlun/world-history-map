#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成「人物志」花名册骨架 data/people_roster.json。

骨架字段（确定性、由本脚本保证准确）：
  id / name / camp / life / baike（百科词条名，默认与 name 相同）
派生子字段（由生成批次补全）：alias / role / summary / bio / events
sources 由 build_people.py 依据 baike 字段确定性生成。

camp 归类原则：
  qing    清廷帝后、宗室、部院督抚、清末新政与维新/立宪派
  beiyang 袁世凯及北洋政府、各系地方军阀
  gmd     同盟会—国民党—国民政府系统（含辛亥民主革命派）
  cpc     中国共产党、人民军队、新中国党政与英模人物
  japan   日本方面及伪满、汪伪等汉奸政权人物
  other   文化教育科技实业界、宗教社会人士、外国（非日本）人物
"""
import json, os

ROSTER = """
cixi|慈禧太后|qing|1835—1908|慈禧
guangxu|光绪帝|qing|1871—1908|光绪
li-hongzhang|李鸿章|qing|1823—1901|
zhang-zhidong|张之洞|qing|1837—1909|
lin-zexu|林则徐|qing|1785—1850|
kang-youwei|康有为|qing|1858—1927|
liang-qichao|梁启超|qing|1873—1929|
tan-sitong|谭嗣同|qing|1865—1898|
liu-guangdi|刘光第|qing|1859—1898|
yang-rui|杨锐|qing|1857—1898|
lin-xu|林旭|qing|1875—1898|
yang-shenxiu|杨深秀|qing|1849—1898|
kang-guangren|康广仁|qing|1867—1898|
zai-feng|载沣|qing|1883—1951|爱新觉罗·载沣
rong-lu|荣禄|qing|1836—1903|
zhang-jian|张謇|qing|1853—1926|
sheng-xuanhuai|盛宣怀|qing|1844—1916|
weng-tonghe|翁同龢|qing|1830—1904|
yikuang|奕劻|qing|1838—1917|爱新觉罗·奕劻
duan-fang|端方|qing|1861—1911|托忒克·端方
tie-liang|铁良|qing|1863—1938|
liang-bi|良弼|qing|1877—1912|爱新觉罗·良弼
shanqi|善耆|qing|1866—1922|爱新觉罗·善耆
zhao-erxun|赵尔巽|qing|1844—1927|
cen-chunxuan|岑春煊|qing|1861—1933|
liu-kunyi|刘坤一|qing|1830—1902|
yang-ru|杨儒|qing|1840—1902|
liu-yongfu|刘永福|qing|1837—1917|
ding-richang|丁汝昌|qing|1836—1895|
deng-shichang|邓世昌|qing|1849—1894|
zuo-baogui|左宝贵|qing|1837—1894|
qiu-fengjia|丘逢甲|qing|1864—1912|
tang-caichang|唐才常|qing|1867—1900|
zaitao|载涛|qing|1887—1970|爱新觉罗·载涛
nie-shicheng|聂士成|qing|1836—1900|
dong-fuxiang|董福祥|qing|1839—1908|
lin-yongsheng|林永升|qing|1853—1894|
sa-zhenbing|萨镇冰|qing|1859—1952|
yuan-shikai|袁世凯|beiyang|1859—1916|
duan-qirui|段祺瑞|beiyang|1865—1936|
feng-guozhang|冯国璋|beiyang|1859—1919|
cao-kun|曹锟|beiyang|1862—1938|
wu-peifu|吴佩孚|beiyang|1874—1939|
zhang-zuolin|张作霖|beiyang|1875—1928|
yan-xishan|阎锡山|beiyang|1883—1960|
tang-jiyao|唐继尧|beiyang|1883—1927|
cai-e|蔡锷|beiyang|1882—1916|
lu-rongting|陆荣廷|beiyang|1859—1928|
chen-jitang|陈济棠|beiyang|1890—1954|
chen-jiongming|陈炯明|beiyang|1878—1933|
tang-shengzhi|唐生智|beiyang|1889—1970|
zhao-hengtie|赵恒惕|beiyang|1880—1971|
liu-xiang|刘湘|beiyang|1888—1938|
liu-wenhui|刘文辉|beiyang|1895—1976|
yang-sen|杨森|beiyang|1884—1977|
wang-jialie|王家烈|beiyang|1893—1966|
long-yun|龙云|beiyang|1884—1962|
lu-han|卢汉|beiyang|1895—1974|
ma-qi|马麒|beiyang|1869—1931|
ma-bufang|马步芳|beiyang|1903—1975|
ma-hongkui|马鸿逵|beiyang|1892—1970|
ma-fuxiang|马福祥|beiyang|1876—1932|
yang-zengxin|杨增新|beiyang|1864—1928|
jin-shuren|金树仁|beiyang|1879—1941|
sheng-shicai|盛世才|beiyang|1896—1970|
han-fuju|韩复榘|beiyang|1890—1938|
zhang-zongchang|张宗昌|beiyang|1881—1932|
sun-chuanfang|孙传芳|beiyang|1885—1935|
li-yuanhong|黎元洪|beiyang|1864—1928|
xu-shichang|徐世昌|beiyang|1855—1939|
feng-yuxiang|冯玉祥|beiyang|1882—1948|
zhang-xun|张勋|beiyang|1854—1923|
xu-shuzheng|徐树铮|beiyang|1880—1925|
lu-yongxiang|卢永祥|beiyang|1867—1933|
qi-xieyuan|齐燮元|beiyang|1879—1946|
guo-songling|郭松龄|beiyang|1883—1925|
zhang-zuoxiang|张作相|beiyang|1881—1949|
tang-yulin|汤玉麟|beiyang|1871—1937|
liu-zhenhua|刘镇华|beiyang|1883—1956|
shi-yousan|石友三|beiyang|1891—1940|
sun-dianying|孙殿英|beiyang|1889—1947|
ma-zhanshan|马占山|beiyang|1885—1950|
wang-zhanyuan|王占元|beiyang|1861—1934|
zhang-jingyao|张敬尧|beiyang|1881—1933|
wu-junsheng|吴俊升|beiyang|1863—1928|
yang-yuting|杨宇霆|beiyang|1885—1929|
cao-rulin|曹汝霖|beiyang|1877—1966|
lu-zongyu|陆宗舆|beiyang|1876—1941|
zhang-zongxiang|章宗祥|beiyang|1879—1962|
tang-shaoyi|唐绍仪|beiyang|1862—1938|
lu-zhengxiang|陆征祥|beiyang|1871—1949|
sun-zhongshan|孙中山|gmd|1866—1925|
jiang-jieshi|蒋介石|gmd|1887—1975|
hu-hanmin|胡汉民|gmd|1879—1936|
liao-zhongkai|廖仲恺|gmd|1877—1925|
song-ziwen|宋子文|gmd|1894—1971|
kong-xiangxi|孔祥熙|gmd|1880—1967|
chen-guofu|陈果夫|gmd|1892—1951|
chen-lifu|陈立夫|gmd|1900—2001|
he-yingqin|何应钦|gmd|1890—1987|
zhang-zizhong|张自忠|gmd|1891—1940|
tong-linge|佟麟阁|gmd|1892—1937|
zhao-dengyu|赵登禹|gmd|1898—1937|
dai-anlan|戴安澜|gmd|1904—1942|
xue-yue|薛岳|gmd|1896—1998|
wei-lihuang|卫立煌|gmd|1897—1960|
du-yuming|杜聿明|gmd|1904—1981|
sun-liren|孙立人|gmd|1900—1990|
jiang-guangnai|蒋光鼐|gmd|1888—1967|
cai-tingkai|蔡廷锴|gmd|1892—1968|
xie-jinyuan|谢晋元|gmd|1905—1941|
zhang-zhizhong|张治中|gmd|1890—1969|
song-meiling|宋美龄|gmd|1898—2003|
song-qingling|宋庆龄|gmd|1893—1981|
li-zongren|李宗仁|gmd|1891—1969|
bai-chongxi|白崇禧|gmd|1893—1966|
fu-zuoyi|傅作义|gmd|1895—1974|
zhang-xueliang|张学良|gmd|1901—2001|
yang-hucheng|杨虎城|gmd|1893—1949|
huang-xing|黄兴|gmd|1874—1916|
song-jiaoren|宋教仁|gmd|1882—1913|
cai-yuanpei|蔡元培|gmd|1868—1940|
qiu-jin|秋瑾|gmd|1875—1907|
xu-xilin|徐锡麟|gmd|1873—1907|
zou-rong|邹容|gmd|1885—1905|
chen-tianhua|陈天华|gmd|1875—1905|
zhang-taiyan|章太炎|gmd|1869—1936|
chen-qimei|陈其美|gmd|1878—1916|
tao-chengzhang|陶成章|gmd|1878—1912|
dai-jitao|戴季陶|gmd|1891—1949|
yu-youren|于右任|gmd|1879—1964|
ju-zheng|居正|gmd|1876—1951|
lin-sen|林森|gmd|1868—1943|
tan-yankai|谭延闿|gmd|1880—1930|
sun-ke|孙科|gmd|1891—1973|
zhang-qun|张群|gmd|1889—1990|
dai-li|戴笠|gmd|1897—1946|
chen-cheng|陈诚|gmd|1898—1965|
gu-zhutong|顾祝同|gmd|1893—1987|
tang-enbo|汤恩伯|gmd|1898—1954|
hu-zongnan|胡宗南|gmd|1896—1962|
wang-yaowu|王耀武|gmd|1904—1968|
zhang-lingfu|张灵甫|gmd|1903—1947|
liao-yaoxiang|廖耀湘|gmd|1906—1968|
qiu-qingquan|邱清泉|gmd|1902—1949|
huang-baitao|黄百韬|gmd|1900—1948|
fang-xianjue|方先觉|gmd|1903—1983|
li-jiaoyu|李家钰|gmd|1892—1944|
hao-mengling|郝梦龄|gmd|1898—1937|
wang-mingzhang|王铭章|gmd|1893—1938|
gao-zhihang|高志航|gmd|1908—1937|
chen-mingren|陈明仁|gmd|1903—1974|
cheng-qian|程潜|gmd|1882—1968|
guan-linzheng|关麟征|gmd|1905—1980|
zheng-dongguo|郑洞国|gmd|1903—1991|
luo-zhuoying|罗卓英|gmd|1896—1961|
chen-bulei|陈布雷|gmd|1890—1948|
jiang-jingguo|蒋经国|gmd|1910—1988|
weng-wenhao|翁文灏|gmd|1889—1971|
zhu-zhixin|朱执信|gmd|1885—1920|
li-liejun|李烈钧|gmd|1882—1946|
bai-wenwei|柏文蔚|gmd|1876—1947|
jiang-yiwu|蒋翊武|gmd|1884—1913|
xiong-bingkun|熊秉坤|gmd|1885—1969|
wu-zhihui|吴稚晖|gmd|1865—1953|
mao-zedong|毛泽东|cpc|1893—1976|
zhou-enlai|周恩来|cpc|1898—1976|
zhu-de|朱德|cpc|1886—1976|
liu-shaoqi|刘少奇|cpc|1898—1969|
deng-xiaoping|邓小平|cpc|1904—1997|
chen-yun|陈云|cpc|1905—1995|
ren-bishi|任弼时|cpc|1904—1950|
peng-dehuai|彭德怀|cpc|1898—1974|
liu-bocheng|刘伯承|cpc|1892—1986|
he-long|贺龙|cpc|1896—1969|
chen-yi|陈毅|cpc|1901—1972|
luo-ronghuan|罗荣桓|cpc|1902—1963|
xu-xiangqian|徐向前|cpc|1901—1990|
nie-rongzhen|聂荣臻|cpc|1899—1992|
ye-jianying|叶剑英|cpc|1897—1986|
lin-biao|林彪|cpc|1907—1971|
li-dazhao|李大钊|cpc|1889—1927|
chen-duxiu|陈独秀|cpc|1879—1942|
qu-qiubai|瞿秋白|cpc|1899—1935|
cai-hesen|蔡和森|cpc|1895—1931|
xiang-jingyu|向警予|cpc|1895—1928|
fang-zhimin|方志敏|cpc|1899—1935|
liu-zhidan|刘志丹|cpc|1903—1936|
zuo-quan|左权|cpc|1905—1942|
ye-ting|叶挺|cpc|1896—1946|
xiang-ying|项英|cpc|1898—1941|
yang-jingyu|杨靖宇|cpc|1905—1940|
zhao-yiman|赵一曼|cpc|1905—1936|
zhao-shangzhi|赵尚志|cpc|1908—1942|
dong-cunrui|董存瑞|cpc|1929—1948|
huang-jiguang|黄继光|cpc|1931—1952|
qiu-shaoyun|邱少云|cpc|1926—1952|
lei-feng|雷锋|cpc|1940—1962|
jiao-yulu|焦裕禄|cpc|1922—1964|
wang-jinxi|王进喜|cpc|1923—1970|
zhang-wentian|张闻天|cpc|1900—1976|
wang-jiaxiang|王稼祥|cpc|1906—1974|
bo-gu|博古|cpc|1907—1946|秦邦宪
li-lisan|李立三|cpc|1899—1967|
deng-zhongxia|邓中夏|cpc|1894—1933|
yun-daiying|恽代英|cpc|1895—1931|
peng-pai|彭湃|cpc|1896—1929|
zhang-tailei|张太雷|cpc|1898—1927|
su-zhaozheng|苏兆征|cpc|1885—1929|
chen-tanqiu|陈潭秋|cpc|1896—1943|
he-shuheng|何叔衡|cpc|1876—1935|
wang-jinmei|王尽美|cpc|1898—1925|
deng-enming|邓恩铭|cpc|1901—1931|
mao-zemin|毛泽民|cpc|1896—1943|
mao-zetan|毛泽覃|cpc|1905—1935|
liu-hulan|刘胡兰|cpc|1932—1947|
jiang-zujun|江竹筠|cpc|1920—1949|
yang-kaihui|杨开慧|cpc|1901—1930|
deng-yingchao|邓颖超|cpc|1904—1992|
cai-chang|蔡畅|cpc|1900—1990|
li-fuchun|李富春|cpc|1900—1975|
su-yu|粟裕|cpc|1907—1984|
chen-geng|陈赓|cpc|1903—1961|
tan-zheng|谭政|cpc|1906—1988|
huang-kecheng|黄克诚|cpc|1902—1986|
zhang-yunyi|张云逸|cpc|1892—1974|
luo-ruiqing|罗瑞卿|cpc|1906—1978|
wang-shusheng|王树声|cpc|1905—1974|
xu-guangda|许光达|cpc|1908—1969|
xu-haidong|徐海东|cpc|1900—1970|
wang-zhen|王震|cpc|1908—1993|
yang-chengwu|杨成武|cpc|1914—2004|
li-kenong|李克农|cpc|1899—1962|
xi-zhongxun|习仲勋|cpc|1913—2002|
peng-zhen|彭真|cpc|1902—1997|
bo-yibo|薄一波|cpc|1908—2007|
li-xiannian|李先念|cpc|1909—1992|
hu-yaobang|胡耀邦|cpc|1915—1989|
wang-jingwei|汪精卫|japan|1883—1944|
puyi|溥仪|japan|1906—1967|爱新觉罗·溥仪
chen-gongbo|陈公博|japan|1892—1946|
zhou-fohai|周佛海|japan|1897—1948|
liang-hongzhi|梁鸿志|japan|1882—1946|
wang-kemin|王克敏|japan|1873—1945|
zhang-jinghui|张景惠|japan|1871—1949|
xi-qia|熙洽|japan|1884—1950|
dewang|德穆楚克栋鲁普|japan|1902—1966|
zheng-xiaoxu|郑孝胥|japan|1860—1938|
chuan-dao-fangzi|川岛芳子|japan|1907—1948|
gang-cun-ningci|冈村宁次|japan|1884—1966|
dong-tiao-yingji|东条英机|japan|1884—1948|
song-jing-shigen|松井石根|japan|1878—1948|
ban-yuan-zheng-si-lang|板垣征四郎|japan|1885—1948|
tu-fei-yuan-xian-er|土肥原贤二|japan|1883—1948|
mei-jin-mei-zhi-lang|梅津美治郎|japan|1882—1949|
jin-wei-wen-mi|近卫文麿|japan|1891—1945|
guang-tian-hong-yi|广田弘毅|japan|1878—1948|
zhong-guang-kui|重光葵|japan|1887—1957|
yu-ren|裕仁|japan|1901—1989|裕仁
yi-teng-bo-wen|伊藤博文|japan|1841—1909|
shan-xian-you-peng|山县有朋|japan|1838—1922|
shan-ben-wu-shi-liu|山本五十六|japan|1884—1943|
dong-xiang-ping-ba-lang|东乡平八郎|japan|1848—1934|
yan-fu|严复|other|1854—1921|
zhan-tianyou|詹天佑|other|1861—1919|
lu-xun|鲁迅|other|1881—1936|
hu-shi|胡适|other|1891—1962|
chen-yinke|陈寅恪|other|1890—1969|
wang-guowei|王国维|other|1877—1927|
tao-xingzhi|陶行知|other|1891—1946|
lu-zuofu|卢作孚|other|1893—1952|
fan-changjiang|范长江|other|1909—1970|
zou-taofen|邹韬奋|other|1895—1944|
nie-er|聂耳|other|1912—1935|
xian-xinghai|冼星海|other|1905—1945|
xu-beihong|徐悲鸿|other|1895—1953|
qi-baishi|齐白石|other|1864—1957|
mei-lanfang|梅兰芳|other|1894—1961|
ba-jin|巴金|other|1904—2005|
lao-she|老舍|other|1899—1966|
mao-dun|茅盾|other|1896—1981|
guo-moruo|郭沫若|other|1892—1978|
qian-zhongshu|钱钟书|other|1910—1998|
hou-debang|侯德榜|other|1890—1974|
hua-luogeng|华罗庚|other|1910—1985|
li-siguang|李四光|other|1889—1971|
mao-yisheng|茅以升|other|1896—1989|
zhu-kezhen|竺可桢|other|1890—1974|
qian-xuesen|钱学森|other|1911—2009|
deng-jiaxian|邓稼先|other|1924—1986|
tian-han|田汉|other|1898—1968|
gu-hongming|辜鸿铭|other|1857—1928|
feng-youlan|冯友兰|other|1895—1990|
liang-shuming|梁漱溟|other|1893—1988|
gu-jiegang|顾颉刚|other|1893—1980|
qian-mu|钱穆|other|1895—1990|
fu-sinian|傅斯年|other|1896—1950|
shen-congwen|沈从文|other|1902—1988|
cao-yu|曹禺|other|1910—1996|
ding-ling|丁玲|other|1904—1986|
bing-xin|冰心|other|1900—1999|
zhu-ziqing|朱自清|other|1898—1948|
wen-yiduo|闻一多|other|1899—1946|
yu-dafu|郁达夫|other|1896—1945|
xu-zhimo|徐志摩|other|1897—1931|
lin-yutang|林语堂|other|1895—1976|
feng-zikai|丰子恺|other|1898—1975|
zhang-daqian|张大千|other|1899—1983|
liu-haisu|刘海粟|other|1896—1994|
qian-sanqiang|钱三强|other|1913—1992|
tong-dizhou|童第周|other|1902—1979|
chen-shengshen|陈省身|other|1911—2004|
liang-sicheng|梁思成|other|1901—1972|
zhao-yuanren|赵元任|other|1892—1982|
zhang-jiashu|张恨水|other|1895—1967|
wang-luobin|王洛宾|other|1913—1996|
ma-ka-se|麦克阿瑟|other|1880—1964|
ni-ke-song|尼克松|other|1913—1994|
tian-zhong-jiao-rong|田中角荣|other|1918—1993|
ji-xin-ge|基辛格|other|1923—2023|
si-da-lin|斯大林|other|1878—1953|
luo-si-fu|罗斯福|other|1882—1945|
qiu-ji-er|丘吉尔|other|1874—1965|
he-lu-xiao-fu|赫鲁晓夫|other|1894—1971|
du-lu-men|杜鲁门|other|1884—1972|
ma-xie-er|马歇尔|other|1880—1959|
shi-di-wei|史迪威|other|1883—1946|
chen-na-de|陈纳德|other|1890—1958|
bai-qiu-en|白求恩|other|1890—1939|
si-nuo|斯诺|other|1905—1972|
jin-ri-cheng|金日成|other|1912—1994|
hu-zhi-ming|胡志明|other|1890—1969|
"""


# 为控制条目规模，剔除非核心人物（仍保证总数远超 200 且各类别覆盖完整）
DROP = set("""
zaitao nie-shicheng dong-fuxiang lin-yongsheng sa-zhenbing
zhang-zuoxiang tang-yulin liu-zhenhua shi-yousan sun-dianying wang-zhanyuan
zhang-jingyao wu-junsheng yang-yuting lu-zongyu zhang-zongxiang qi-xieyuan
wu-zhihui jiang-yiwu xiong-bingkun zhu-zhixin bai-wenwei weng-wenhao
chen-bulei luo-zhuoying guan-linzheng zheng-dongguo chen-mingren gao-zhihang
wang-mingzhang fang-xianjue huang-baitao qiu-qingquan liao-yaoxiang
tang-enbo zhang-qun sun-ke ju-zheng tan-yankai tao-chengzhang li-liejun
jiang-jingguo hu-zongnan wang-yaowu zhang-lingfu cheng-qian
wang-jiaxiang li-lisan zhang-tailei su-zhaozheng he-shuheng wang-jinmei
deng-enming mao-zemin mao-zetan cai-chang li-fuchun tan-zheng huang-kecheng
zhang-yunyi wang-shusheng xu-guangda xu-haidong wang-zhen yang-chengwu
li-kenong bo-yibo hu-yaobang peng-zhen li-xiannian xi-zhongxun luo-ruiqing
mei-jin-mei-zhi-lang zhong-guang-kui shan-xian-you-peng dong-xiang-ping-ba-lang
liang-hongzhi wang-kemin
cao-yu bing-xin yu-dafu xu-zhimo feng-zikai zhang-daqian liu-haisu
qian-sanqiang tong-dizhou chen-shengshen liang-sicheng zhao-yuanren
zhang-jiashu wang-luobin feng-youlan gu-jiegang du-lu-men ma-xie-er
shi-di-wei chen-na-de bai-qiu-en si-nuo jin-ri-cheng hu-zhi-ming
""".split())


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(root, 'data', 'people_roster.json')
    people, ids = [], set()
    for raw in ROSTER.strip().splitlines():
        raw = raw.strip()
        if not raw:
            continue
        parts = raw.split('|')
        pid, name, camp, life = parts[0], parts[1], parts[2], parts[3]
        baike = parts[4] if len(parts) > 4 and parts[4] else name
        assert pid not in ids, 'duplicate id: ' + pid
        assert camp in ('qing', 'beiyang', 'gmd', 'cpc', 'japan', 'other'), pid
        ids.add(pid)
        if pid in DROP:
            continue
        people.append({'id': pid, 'name': name, 'camp': camp,
                       'life': life, 'baike': baike})
    missing = DROP - ids
    assert not missing, 'DROP ids not in roster: %s' % sorted(missing)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({'people': people}, f, ensure_ascii=False, indent=1)
    print('wrote', out, 'count =', len(people))
    from collections import Counter
    print(Counter(p['camp'] for p in people))


if __name__ == '__main__':
    main()
