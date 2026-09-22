# 项目架构（Architecture）

> 目标：让这个"世界历史地图"在**数据持续增长**（史料更新与校正）的前提下仍然可维护、可验证、可换分发方式。
> 数据层的细节见 `docs/DATA_ARCHITECTURE.md`；本文覆盖整个项目。

---

## 一、现状诊断（有据）

| 维度 | 现状 | 问题 |
|---|---|---|
| 应用层 | `src/app.js` **单文件 2674 行 / 1 个 IIFE / 15 个小节** | 无模块边界；时间、渲染、抽屉、检索、图例互相直接调用；只能整体理解 |
| 数据入口 | `window.__GEO__` / `window.__DATA__` 全局注入 | 与"单文件 HTML"强绑定；换成静态站点/Dynamic 都要动核心代码 |
| 构建层 | `build.py` 747 + `build_geo.py` 686 + `build_world.py` 401 行，各自管路径与 IO | 源/产物不分；改了源忘记重跑哪个脚本会静默用旧产物（已发生） |
| 数据层 | 源数据、94 MB 抓取缓存、生成物同放 `data/` | 无法一眼分辨"能改什么"；无 manifest、无 schema |
| 身份模型 | 名称字符串即身份（`jin`、`dian`、`wuyue`、`Khmer Empire`/`Angkor`…） | 撞名、覆盖、别名不达（均已发生多次） |
| 时间模型 | 区间/步长/切片选择写在 `build.py` 的代码里 | 区间重叠 3 次、切片不可达 10 个（均已发生） |
| 测试 | 浏览器内 776 行自检 + 真实鼠标脚本 | 覆盖面不错，但纯逻辑（时间换算、编码、注册表）无法在 Node/CI 里单测 |
| 分发 | `release.py` 打 zip 单文件 + Dockerfile | **分发方式被写进了架构**：应用假设自己是一个内联 HTML |

**结论**：功能是够的，架构是"长出来的"。继续加史料只会让上述每一项更痛。

---

## 二、目标架构（四层 + 一条链路）

```
┌─ L0 数据层 ──────────────────────────────────────────────┐
│ sources/（人写，唯一真相，进 git）                          │
│   timeline.json   时间轴区间与步长（声明式）                 │
│   polities/       政权注册表：id, zh, aliases[], color,     │
│                   from/to, capital, summary, sources[]      │
│   periods/        时期：名称映射、合并、注释、来源            │
│   events/         事件（china/ world/ 分目录）                │
│   people/         人物                                       │
│   regions/        割据区、周边国家等空间语义                 │
│ cache/（抓取原样，不进 git，可重下）                          │
│ build/（生成物 + manifest.json，不进 git，可重建）            │
└──────────────────────────────────────────────────────────┘
        │  规范化 normalize → 校验 check → 构建 build
        ▼
┌─ L1 构建层 scripts/ ─────────────────────────────────────┐
│ paths.py       所有路径常量（唯一处）                       │
│ fetch_*.py     取数 → cache/                                │
│ normalize.py   拼写→规范名、别名归并 → sources/（仅人工确认后）│
│ check_data.py  校验（schema/范围/来源/去重/别名/时间轴不变量）│
│ build/         geometry.py  world.py  timeline.py  bundle.py │
│ manifest.py    输入哈希 + 计数 + 校验结论                     │
└──────────────────────────────────────────────────────────┘
        │  产出：数据包（bundle）
        ▼
┌─ L2 应用层 src/（ES 模块，纯前端，无框架依赖） ─────────────┐
│ data/loader.js  ★唯一数据入口：inline / static-files / api  │
│ core/time.js    时间刻度与步长（唯一时间基准：月序号）        │
│ core/registry.js 政权/时期/地区注册表查询（id 为唯一身份）    │
│ core/geometry.js 几何解码与缓存                              │
│ map/*.js        world / china / labels / camera / land       │
│ ui/*.js         legend / drawer / timeline / search / regions│
│ app.js          仅做装配（初始化与事件接线）                  │
└──────────────────────────────────────────────────────────┘
        │
        ▼
┌─ L3 分发层（同一份应用，多种输出） ───────────────────────┐
│ A. 静态站点（默认，目标 GitHub Pages）：index.html + /data/*.json + /assets/*.js │
│ B. 单文件离线包（保留能力）：inline 模式打包成一个 HTML       │
│ C. Docker（本地/自托管）：nginx 或 python -m http.server 提供 A │
│ D. 动态（未来）：loader 指向 API，后端按同样的 ID/时间模型出数据 │
└──────────────────────────────────────────────────────────┘
```

**关键设计**：`data/loader.js` 是唯一的数据入口。应用只认"数据包接口"，不关心它来自内联脚本、静态 JSON 还是 HTTP API。**换分发方式 = 换 loader 实现，不动应用逻辑。**

---

## 三、身份与契约（防止历史数据再次互相污染）

0. **id 与年份绑定（时段模型）**：id 是**跨时间的稳定身份**，`spans[]` 是这个身份在各时段的**状态**：
   ```jsonc
   { "id": "world/germany",
     "aliases": ["German Empire", "Weimar Republic", "Nazi Germany", "West Germany", "Germany"],
     "spans": [
       { "from": 1871, "to": 1918, "zh": "德意志帝国", "alias": "German Empire" },
       { "from": 1919, "to": 1933, "zh": "魏玛共和国", "alias": "Weimar Republic" },
       { "from": 1933, "to": 1945, "zh": "纳粹德国",   "alias": "Nazi Germany" },
       { "from": 1949, "to": 1990, "zh": "联邦德国（西德）", "alias": "West Germany" },
       { "from": 1990, "to": 2026, "zh": "德国",       "alias": "Germany" } ] }
   ```
   解析顺序是 **`resolve(name, year)`**：先按 id 精确匹配，再按别名取“覆盖该年份的时段”。
   → 同一个 id 在不同年代显示当时的名称与都城；史料校正可以**只改某个时段**，不影响其他年代。
   → 数据集里同一拼写若在不同年代指不同实体，则用不同 id；同一实体若换过名字，则用 spans。
1. **政权 ID 规范**：裸 slug 用于中国势力（与控制数据里的键一致，如 `qing`、`jin`）；
   `world/<slug>` 用于世界实体（避免"日本占领军"与"日本国"这类同名不同义互相污染）。
   中文名、英文名、历史拼写、分期名**全部作为别名**指向同一 ID：
   ```jsonc
   { "id": "polity/ottoman-empire", "zh": "奥斯曼帝国",
     "aliases": ["Ottoman Empire", "Sublime Porte", "Turkey (Ottoman)"],
     "color": "#c9a227", "from": 1299, "to": 1922, "capital": "伊斯坦布尔",
     "summary": "…", "sources": [ … ] }
   ```
   → 数据集里的任何拼写都能查到同一条目；图例/检索不再出现两个"同一个国家"。
2. **地区 ID 规范**：`cn:province/<名>`、`cn:county/<6位代码>`、`world:shape/<id>`。
   几何只属于 ID，名称与政权挂在时期/注册表上。
3. **时间不变量**（构建期强制）：区间不重叠、无缝覆盖、按序；每个时期声明自己覆盖的年月区间；
   中国逐月表必须 0 缺口。
4. **来源强制**：事件、政权、时期都必需 `sources[]`（http/https）；缺来源即构建失败。
5. **产物可追溯**：`build/manifest.json` 记录输入文件哈希、各实体计数、校验结论；
   任何交付物都能追到"由哪些输入、在哪次校验下产生"。

---

## 四、史料更新与校正的工作流（重点）

```bash
# 1) 新增/修订史料：只动 sources/
$EDITOR data/sources/events/world/1871-普法战争.json     # 事件：年月、地点、来源
$EDITOR data/sources/polities/europe.json                 # 政权：别名/颜色/存续/都城/简史

# 2) 校验（唯一入口，失败即停）
scripts/pipeline.sh --check          # schema / 范围 / 来源 / 去重 / 别名一致性 / 时间轴不变量

# 3) 构建 + 自检 + 本地预览
scripts/pipeline.sh --serve          # 只重建受影响部分（增量），跑 176 项断言 + 真实鼠标

# 4) 发布（静态站点）
scripts/pipeline.sh --site           # 产出 site/ 目录（含独立 data/*.json），可直接推 GitHub Pages
```

**校正友好性的三个具体保障**：
- **按实体分文件**：一个国家/朝代/事件一个文件或一个分组文件，diff 小、冲突少、review 容易；
- **别名表**：史料里出现的任何旧译名/异拼都能挂到既有实体上，不必改数据集的原始字符串；
- **溯源字段**：每条数据带 `sources[]` 与（可选）`revised`（校订日期与说明），校正历史可追。

---

## 五、分发路线（先不实现，但架构必须支持）

| 方案 | 形态 | 架构要求 | 现状 |
|---|---|---|---|
| **A 静态站点（推荐默认）** | `site/` 目录：`index.html` + `assets/*.js` + `data/*.json`，推 GitHub Pages 即上线 | loader 支持从相对路径取 JSON；构建产出分片数据 | 需 S1—S5 |
| B 单文件离线包 | 一个 `index.html`（当前形态） | loader 的 inline 模式 | 已有 |
| C Docker | 容器内提供 A 的静态目录 | 与 A 相同 | 已有（当前提供单文件） |
| D 动态 | 前端不变，`loader` 换 API 实现；后端按同一 ID/时间模型查询 | ID/时间模型稳定（本架构的核心收益） | 未来 |

> 静态站点的数据量评估：世界切片 2.2 MB（压缩后 0.55 MB）、中国几何 0.9 MB、事件/政体若干 MB。
> 静态站点可按"当前时间片"懒加载，**不必**一次加载全量——这也正是 loader 抽象存在的价值。

---

## 六、迁移计划（每阶段可独立验收，交付始终可用）

| 阶段 | 内容 | 验收标准 | 风险 |
|---|---|---|---|
| **S1** | 数据清单：`data/manifest.json` + `scripts/manifest.py`（角色：source/cache/build，写入者/读取者）+ `.gitignore` 规则 | 每个数据文件都有角色；角色错放即报错；`cache/`、`build/` 不入 git | 低 |
| **S2** | 时间轴声明化：`build.py` 内的区间/步长/切片规则 → `data/sources/timeline.json` + 校验器 | 改区间只改 JSON；区间重叠/切片不可达在构建期被抓 | 低 |
| **S3** | 政权注册表（含别名）：合并 `world_names` + `world_polities` + `china_pre1893.factions` | 多拼写归并为同一 ID；颜色/中文名只在一处；键冲突构建期报错 | 中 |
| **S4** | 时期统一：`historical_units.json` + `china_pre1893.json` → `sources/periods/*.json` | 新增朝代=加一个文件；不再需要同时改 3 处 | 中 |
| **S5** | 目录落位与路径常量集中（`scripts/paths.py`）+ 增量构建 | 删 `cache/`+`build/` 可由 pipeline 重建；改动中国数据不再触发世界重建 | 中 |
| **S6** | 应用层模块化：`app.js` 拆为 `data/core/map/ui` 模块，`loader.js` 三模式 | 逻辑单测可在 Node 跑；单文件模式仍可用 | 中高 |
| **S7** | 静态站点输出：`scripts/build_site.py` 产出 `site/`（分片 JSON + 模块 JS） | 本地静态服务器打开即用；GH Pages 可直接托管 | 中 |
| **S8** | 增量与 CI：只重建受影响实体；GitHub Actions 跑校验+自检 | 一次史料修订 < 1 分钟出结果 | 中 |

**原则**：先低风险的 S1/S2（马上消除最痛的"改了不知道要重跑什么""区间又重叠了"），
再动数据模型（S3/S4），最后才是目录搬家和应用拆分（S5/S6）——期间**单文件交付始终可用**。

---

## 七、本轮已落地

- 本文（整体架构）+ `docs/DATA_ARCHITECTURE.md`（数据层细节与事故清单）
- **S1 已实现**：`scripts/manifest.py` 生成并校验 `data/manifest.json`；
  接入 `scripts/pipeline.sh`，`cache/`、`build/` 的 git 规则写入 `.gitignore`。
