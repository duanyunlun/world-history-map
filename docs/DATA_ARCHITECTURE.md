# 数据架构（Data Architecture）

> 这份文档回答三个问题：**数据存哪里、怎么更新、怎么变成地图上的像素**。
> 背景：项目从"中国近现代地图"长成"世界历史地图"后，数据层是靠一轮轮追加堆起来的。
> 下面先记录这种做法的具体代价（都是本项目真实发生过的），再给出目标架构与分阶段迁移计划。

---

## 一、现状与代价

### 1.1 当前 `data/` 的混乱

| 类别 | 文件 | 问题 |
|---|---|---|
| 手工维护的源数据 | `events.json` `people.json` `factions.json` `territories.json` `neighbors.json` `world_events.json` `world_polities.json` `world_names.json` `china_pre1893.json` `historical_units.json` | 与生成物、缓存混放；谁读谁写没有记录；无 schema |
| 抓取缓存（94 MB） | `_world_cache/` `_cshapes/` `_county_raw_index.json`(25 MB) | 与源数据同级，容易误提交、误删、误当输入编辑 |
| 构建产物 | `geo.json` `world.json` `counties.json` `counties_all.json` `china_provinces_*.json` | 与源数据同级，**无法一眼分辨"哪些能改、改完要重跑什么"** |
| 旁支/实验残留 | `events.subagent.json` `baike_verify.json` `people_roster.json` `nine_dash.example.json` | 无标注是否为流程一部分 |

### 1.2 真实付出过的代价（本项目内）

| 事故 | 根因 | 架构层面的缺什么 |
|---|---|---|
| 改了 `historical_units.json` 却没重跑 `build_geo.py`，验证的是旧产物 | 源→产物链路不可见 | 缺 manifest 与"谁依赖谁" |
| `jin` 同时表示金朝与晋系军阀；`dian` 同时表示滇国与滇系军阀 | 势力键没有命名空间/注册表 | 缺**实体注册表** |
| `wuyue` 一批数据覆盖了另一批（古代吴越 vs 五代吴越国） | 键是字符串，含义靠人记 | 同上 |
| 简史写了 46 条只命中 4 条 | 名字与数据集拼写不一致，无别名机制 | 缺**别名/规范名**模型 |
| 同一批里"苏伊士运河"写了两遍 | 批处理脚本各自实现去重 | 缺统一的写入入口与校验 |
| 180 个世界切片有 10 个从时间轴不可达 | 切片→时间步的映射是代码里的 if | 缺**声明式时间轴** |
| 时间轴区间重叠 3 次（上古 vs 商周等） | 区间定义在 `build.py` 里手写 | 同上 |
| 事件批量写入"整批静默失败" | 脚本参数/去重各自为政 | 缺写入守卫 |

### 1.3 结论

不是"数据不够多"的问题，而是**数据没有模型**：没有实体身份、没有时间基准、没有职责边界、没有契约与守门。

---

## 二、目标数据模型

### 2.1 四类实体（各自有稳定 ID）

| 实体 | 身份（ID） | 说明 |
|---|---|---|
| **地区 / 空间单元** `Region` | `cn:province/湖北`、`cn:county/420222`、`world:shape/1234` | 几何的唯一归属。中国用现行省/县代码；世界用 shape id（去重后的几何） |
| **政权 / 势力** `Polity` | `polity/qing`、`polity/ottoman-empire`、`polity/wei` | **规范名 + 别名表**（`aliases: ["Qing Empire","Qing China"]`），颜色、存续期、都城、简史挂在它上面 |
| **时期 / 区划制度** `Period` | `period/1644-qing`、`period/tang` | 某时段内的行政区划规则：名称映射、合并、注释、来源 |
| **事件** `Event` | `event/1895-05-02-公车上书`（年-月-日-标题） | 时间（可到日）、地点、类别、来源；与 Polity/Region 通过 ID 关联 |

### 2.2 时间模型（唯一的基准）

- **基准**：一个连续的**月序号** `MI = year*12 + (month-1)`（公元前为负）。所有时间量最终换算成它。
- **步长由"覆盖声明"决定**，不是散落在代码里的 if：

```jsonc
// data/sources/timeline.json
{
  "ranges": [
    { "id": "prehistoric", "name": "史前（前123000—前3001）", "from": -123000, "to": -3000,
      "step": "slice" },                       // 世界切片自带的年份
    { "id": "shang-zhou",  "name": "商周·逐年（前1600—前771）", "from": -1600, "to": -770,
      "step": "year", "china": "period/shang-zhou", "world": "slice" },
    { "id": "cn-monthly",  "name": "中国近代·逐月（1893—1976）", "from": 1893, "to": 1976,
      "step": "month", "china": "period/1893-1911", "world": "cshapes" },
    { "id": "contemporary","name": "当代（1977—2026）", "from": 1977, "to": 2026,
      "step": "year", "world": "modern" }
  ]
}
```

  **不变量（构建期强制）**：区间互不重叠、无缝覆盖、按 from 升序、每个 `china` 指定的 period 必须存在且覆盖该区间。

### 2.3 空间模型

- **几何只存一份**：所有时期共享同一份几何池（`shapes`），时期通过 `shapeId -> 名称/政权` 引用它。这是现在 `hist.geoms` 去重做法的正式化。
- **统一底图**：世界轮廓恒用现代海岸线（`land` 层），历史色块**裁剪其上**；切片的粗糙多边形不再决定海岸线。
- **政区≠政权**：`Region`（空间）与 `Polity`（控制者）分离；"某年某地谁控制"是一张 `控制表`，不是写在几何里。

### 2.4 地图映射链路（从数据到像素）

```
时间轴步  step(t)                       ← data/sources/timeline.json（声明式，构建期校验）
   │
   ├─ 世界：slice_for(t) ─────────────► 切片(shapeId → polityId)
   │                                     └─ 名称：polity 规范名/别名 → 中文优先显示
   └─ 中国：period_for(t) ────────────► 时期(shapeId → 名称, 政权)
                                         └─ 控制表：polityAt(regionId, mi) → polityId
   │
渲染：shapeId → 路径（几何池，压缩存储）
      polityId → 颜色/名称/简史/来源（注册表）
      regionId → 标签位置/所属时期名称
```

**关键点**：任何一层只认 ID。名称、拼写、颜色、简史、来源都改在注册表里，不动几何、不动时间轴。

---

## 三、目录与存储规范

```
data/
├── sources/                  # 人写的、唯一的真相（进 git）
│   ├── timeline.json         #   时间轴区间与步长声明
│   ├── polities/             #   政权注册表（规范名、别名、颜色、存续、都城、简史、来源）
│   ├── periods/              #   时期定义（名称映射、合并、注释、来源）
│   ├── events/               #   事件（china/ world/ 分开）
│   ├── people/               #   人物
│   └── regions/              #   割据区、周边国家等空间覆盖语义
├── cache/                    # 抓取的原始数据（不进 git，可重新下载）
│   ├── world_basemaps/  cshapes/  counties/  natural_earth/
└── build/                    # 生成物（不进 git，可重建）
    ├── geo.json  world.json  counties.json …
    └── manifest.json         #   本次构建的输入哈希、计数、校验结论
```

规则：
1. **`sources/` 里只有人能编辑的、有意义的数据**；`cache/` 只读；`build/` 只出不进。
2. 任何"派生数据"不得手改（如 `build/geo.json`、世界切片）。
3. 每个 source 文件带 `schema` 字段声明版本；校验器按版本检查。
4. 构建产出的 `manifest.json` 记录：输入文件哈希、计数（事件/政体/切片/时期）、校验结论、构建时间——**交付物可追溯到输入**。

---

## 四、更新链路（唯一正确顺序）

```
1) 取数      scripts/fetch_*.py            → data/cache/           （仅世界边界/县界）
2) 规范化    scripts/normalize.py          → data/sources/         （拼写→规范名、别名归并）
3) 校验      scripts/check_data.py         ← data/sources/         （schema/范围/来源/去重/别名一致性）
4) 构建      scripts/build_all.py          sources+cache → build/  （几何、切片、时间轴、单文件）
5) 自检      tests/self_test.html + cdp    ← 单文件                （176 项断言 + 真实鼠标）
6) 部署打包  docker compose / release.py
```

- 第 3 步失败即停（**不产出坏产物**）。
- 第 4 步之后禁止再手改任何数据；要改就回到第 1/2 步。
- 全流程由 **`scripts/pipeline.sh`** 一条命令串起（已有），并在 `--full` 时执行 1—2 步。

---

## 五、迁移计划（每阶段都可独立验收，交付物始终可用）

| 阶段 | 内容 | 验收标准 |
|---|---|---|
| **S1（本轮）** | 建立 `manifest.json` + `check_manifest.py`：声明每个数据文件的角色（source/cache/build）、写入者、读取者、schema；`cache/` 与 `build/` 规则写入 `.gitignore` | 校验器列出全部数据文件、角色与依赖；角色错放即报错；pipeline 接入 |
| **S2** | 时间轴声明化：`build.py` 里的区间/步长/切片选择规则 → `data/sources/timeline.json`（+ 校验器：不重叠、无缝、period 存在） | 改区间只需改 JSON；三次区间重叠类 bug 不再可能 |
| **S3** | 政权注册表：`world_names/world_polities/china_pre1893.factions` → `sources/polities/`，带 `id/zh/aliases/color/from/to/capital/summary/sources` | 同一政权多拼写自动归并；颜色与中文名只在一处定义；键冲突在构建期报错 |
| **S4** | 时期统一：`historical_units.json` + `china_pre1893.json` → `sources/periods/*.json`（控制序列/名称/合并/注释/来源同一文件） | 新增朝代=加一个文件；不再需要同时改 3 处 |
| **S5** | 目录落位：`sources/` `cache/` `build/` 实际分家，脚本路径常量集中到 `scripts/paths.py` | `git status` 干净；删 `cache/`+`build/` 可由 pipeline 重建 |
| **S6** | 事件写入守卫统一（`add_events.py` 扩展到中国事件/人物/时期） | 所有批量写入走同一入口：去重、条数报告、强制校验 |

**不做什么**：不引入数据库、不引入外部服务、不改变"单文件离线 HTML"这一交付形态——
约束是明确的：**离线、单文件、可重建**。

---

## 六、当前进度

- 已具备：`scripts/check_data.py`（世界事件/政体/切片校验）、`scripts/add_events.py`（批量写入守卫）、
  `scripts/pipeline.sh`（一条命令跑完校验→构建→自检→部署→打包）、几何去重与压缩、统一底图与裁剪。
- 本文件即 S1 的设计；S1 的 `manifest.json` 与 `check_manifest.py` 见下节实现。
