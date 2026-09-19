# 港华燃气用气卡片（tongwangas-shandong-card）

与 `tongwangas_shandong` 集成配套的 Lovelace 卡片，零依赖单文件（不内联任何图表库，
曲线/柱状均为手绘 SVG），数据全部来自集成实体，不发起任何网络请求。

- 文件：`tongwangas-shandong-card.js`
- 卡片类型：`custom:tongwangas-shandong-card`
- 资源类型：JavaScript 模块

## 添加到 Home Assistant

**卡片随集成自动就绪，无需手动复制文件，也无需手动在仪表盘里添加 JS 资源。**

集成加载时会自动完成两件事：

1. 把集成自带的 `www/` 目录挂载为静态路径 `/tongwangas_shandong/`；
2. 把 `/tongwangas_shandong/tongwangas-shandong-card.js?v=<集成版本>` 登记为 Lovelace 资源。

### 登记方式（按你的资源模式自动分流）

| 资源模式 | 集成行为 | 效果 |
|---|---|---|
| **storage**（默认） | 写入仪表盘资源表 | 在 **设置** → **仪表盘** → 右上角 **⋮** → **资源** 中可看到；按需加载；Cast 设备（Chromecast / Nest Hub）可显示卡片 |
| **yaml** | 退回全局注入（`add_extra_js_url`） | 与 `frontend.extra_module_url` 同款机制；所有面板都会加载该 JS；Cast 设备不加载 |

URL 上的 `?v=` 为缓存穿透参数，HACS 升级集成后版本号变化，浏览器会自动拉取新卡片。
该资源由集成自动维护，请在「资源」列表中**不要手动删除**。

### 添加卡片

仪表盘 → 右下角 **编辑** → **+ 添加卡片** → 搜索「港华燃气用气卡片」直接添加，
或在「手动」中填入：

```yaml
type: custom:tongwangas-shandong-card
gs: "1111111111"
title: 港华燃气
```

### 曾经手动添加过资源？

早期版本需要手动把 JS 复制到 `config/www/community/tongwangas-shandong/` 并手动添加资源。
若照做过一次，请到 **设置** → **仪表盘** → **⋮** → **资源** 里**删除**那条
`/local/community/tongwangas-shandong/tongwangas-shandong-card.js`。
不删也能用（卡片自身做了重复注册保护），但同一份 JS 会被加载两次。

### 常见问题

| 现象 | 原因 / 处理 |
|---|---|
| 提示 `Custom element doesn't exist: tongwangas-shandong-card` | 资源未加载。到 **设置 → 仪表盘 → ⋮ → 资源** 确认存在 `/tongwangas_shandong/tongwangas-shandong-card.js?v=...`；不存在则重启集成/HA，并开启 debug 日志查看注册失败原因 |
| 卡片显示「未找到港华燃气设备」 | 集成未添加或实体未加载；也可在卡片配置里显式填写 `gs`（户号） |
| 曲线 / 日历为空 | `gas_total_daily` 尚无每日数据（来自 HA statistics，需集成运行一段时间），日历此时会自动回退用气明细的月度值 |
| 升级集成后界面没变化 | 浏览器缓存：强制刷新（`Ctrl/Cmd + Shift + R`）；或确认资源 URL 上的 `?v=` 已随版本变化 |

> **命名说明**：卡片早期文件名为 `tongwangas-shandong-gas-card.js`、类型为
> `custom:tongwangas-shandong-gas-card`，现已统一为 `tongwangas-shandong-card`。
> 若你的仪表盘里还写着旧类型名，请把 `type:` 改为 `custom:tongwangas-shandong-card`。

## 1. 功能一览

| 区块 | 数据来源 | 说明 |
|---|---|---|
| 费用指标行 | `available_balance` / `fee_payable` / `gas_total` | 可用余额、应缴费用（>0 标红）、累计用气量 |
| 用气卡片 | `gas_total_daily` | 标题「本月用气」：本月每日用气量/费用**累加**（费用=日用量×单价估算），并显示**较上月的增减百分比**；右侧为本月每日用气折线，hover/点击显示当日用气量与费用。仅统计**完整日**（不含今天） |
| 用气阶梯 | `step_name` | 三档单价 + 区间，按 `gas_total_yearly`（今年累计）高亮当前所在档位 |
| 用气日历 | `gas_total_daily` + `gas_consumption_info` | 每日用气量/费用，按月统计总用气量/费用（详见第 4 节） |
| 用气曲线 | `gas_consumption_trend_info` | 今年 vs 去年 **双折线 + 双柱状** 对比，全年 12 个月 |
| 用气明细 | `gas_consumption_info` | 每月一行表格：月份 / 抄表日期 / 用气量 / 费用 / 读数 |
| 日用气曲线 | `gas_total_daily` | 逐日用气量（跳表增量平摊，**仅统计完整日、不含今天**，详见第 3 节） |

> 原济南水务卡片的「订单列表」在本卡片中**已移除**（燃气场景不需要）。

## 2. 实体依赖

所有实体 id 形如 `sensor.tongwangas_shandong_<key>_<户号>`，户号即集成配置中的 `subsCode`：

| 卡片用途 | 实体 key |
|---|---|
| 可用余额 | `available_balance` |
| 应缴费用 | `fee_payable` |
| 累计用气量 | `gas_total` |
| 今年累计用气量 | `gas_total_yearly` |
| 上次抄表日期 | `last_meter_reading_date` |
| 当前阶梯气价 | `step_name` |
| 用气明细 | `gas_consumption_info` |
| 用气趋势 | `gas_consumption_trend_info` |
| 每日用气量 | `gas_total_daily`（新增，见下） |

卡片右下角四个按钮分别展开：用气日历 / 用气曲线 / 用气明细 / 日用气。

## 3. 每日用气量实体（`gas_total_daily`）与 HA statistics

上游接口只返回**按月**用气数据（每月一条读表记录），没有「每日」接口。为了拿到逐日消耗，
集成新增了 `gas_total_daily` 传感器：

- 它读取 `gas_total`（累计用气量，状态类 `total_increasing`）实体的 **sum 统计量**
  （Home Assistant 为带 `state_class` 的实体自动生成的长期统计表 `statistics`），
  调用 `statistics_during_period(..., period="day", types={"state","sum"})` 取按天序列。
- HA 返回行的 `start` 是 **Unix 时间戳（float）**，需换算成本地日期；`sum` 是**累计值**
  （自首次统计以来单调不减），因此用**相邻跳表的差值**得到增量。
- 卡片读取该实体的 `attributes.graph`（`[{date, gasSum}]`）绘制日历与日曲线。
- 「日用气曲线」面板支持区间切换：**近一周 / 近一月（默认）/ 近一年 / 自定义**。
  - 「自定义」首次进入会预填「最近一个月」，避免空区间看起来像全部数据；
  - 起止日期颠倒时自动交换，输入越界（早于/晚于现有数据）会自动收敛到实际数据边界；
  - 面板右上角显示当前区间实际覆盖的天数与起止日期，便于确认筛选生效。

### 3.1 跳表增量平摊（重要）

家用燃气表精度为 **1 m³**，而真实日用量常在 1 m³ 以下，因此表具要「攒够 1 m³ 才跳一次表」，
表现为「某几天没有数据，某天突然 +1」。若把没有数据的天空着或记 0，都会谎报「当天零消耗」，
且会让月合计偏低。因此集成做了**平摊**：

- 每次跳表的增量，**平均分摊到距上次跳表之间的每一天**。
- 任何区间的合计仍**等于表具累计读数的实际增量**（月账单口径不受影响）。
- 跳表间隔为 1 天时无法平摊（说明当天确实用了 ≥1 m³），保持原值。
- 最后一次跳表之后直到昨天的日子记 0（确实未观测到消耗）。
- 该算法对上游行密度不敏感：统计量行「只在跳表日出现」或「每天都有」结果完全一致。

### 3.2 只统计「完整日」

`graph` **不包含今天**，`state` 表示**昨天**的用气量。原因：

- 当天尚未结束，读数不完整，取值会在一天内不断变化；
- 跳表常发生在凌晨（如 00:25 的轮询），实际对应前一晚的用量，计入当天会虚高。

下一次刷新（今天成为完整日）时，相关增量会自动正确归属。

### 3.3 界面上的精度提示

「本月用气」「用气日历」「日用气曲线」三个基于日粒度数据的面板底部，会显示统一的小字提示：

> ※ 带小数的日用量为表具 1 m³ 精度的推算值（按跳表间隔平摊），非实际读表值

因为日粒度数据含平摊/推算成分，界面明确标注，避免被误当成真实读表值。
「用气明细」表格与「用气曲线」年对比使用的是账单月度数据（真实值），故不加此提示。

**性能影响可忽略**：统计量按小时桶预聚合，查询走 executor 线程；传感器随集成主刷新周期
（默认 6 小时）更新，每个户号每次仅一条轻量 SQL，不触碰原始状态表。

**数据可用性说明**：
- 若表具上报的是实时累计读数（即 `gas_total` 持续缓慢增长，而非仅在抄表日跳变），
  则每日统计为**真实逐日消耗**（经平摊后为估计值，总量精确）。
- 若累计读数仅在每月抄表日跳变，则每日统计在抄表日出现「尖峰」，与用气明细月度数据一致
  —— 此时日历/日曲线退化为按月展示，但依然真实。
- 统计表从实体开始报数起积累，全新安装后需要运行一段时间才会出现每日数据；在此之前
  「日用气曲线」会提示暂无数据，**日历会自动回退用气明细的月度值**统计当月。

## 4. 用气日历的取数逻辑

日历逐格展示每日用气量（m³）与费用（¥，费用 = 用气量 × 单价，单价为当前阶梯气价或卡片
`price` 配置）。优先级：

1. 若当日存在 `gas_total_daily` 每日数据 → 用该日真实/估算用气量。
2. 否则若该月用气明细的抄表日正好落在该日 → 用当月用气明细的用气量与费用兜底。
3. 整月既无每日数据也无抄表日匹配 → 该月单元格留空，月统计改用该月用气明细总额。

这种混合策略保证：有每日数据的月份展示真实逐日明细；早期无每日数据的月份仍能通过
月度记录显示当月用气总量。

**色块三级渐变**（以当月有数据的天为口径）：

1. **浅色（默认）**：用气量 ≤ 当月平均值；
2. **中色**：用气量 > 当月平均值；
3. **深色（重点突出）**：当月用气量**最高的 2 天**（超过平均值最多的两天）。

日历底部有图例说明三级色块含义。

## 5. Lovelace 配置示例

```yaml
type: custom:tongwangas-shandong-card
gs: "1111111111"        # 户号；留空则自动探测第一个 tongwangas_shandong 设备
title: 港华燃气
# price: 3.5            # 可选：气价单价(元/m³)，用于日历/日曲线费用估算；留空读当前阶梯气价
# default_panel: ""     # 可选：calendar | yearCurve | table | daily | ""（默认不展开）
```

任意实体可用 `entities:` 单独覆盖，例如：

```yaml
type: custom:tongwangas-shandong-card
gs: "1111111111"
entities:
  available_balance: sensor.tongwangas_shandong_available_balance_1111111111
```

## 6. 可视化编辑器

通过卡片「编辑」进入 GUI 编辑器，可配置：户号、卡片标题、气价单价、默认展开面板。
（编辑器在无 HA 前端环境下会降级为原生输入框，不影响卡片本身渲染。）

## 7. 与济南水务卡片的差异

- 「用水」全部改为「用气」。
- 用气阶梯改为从 `step_name` 实体自动读取三档单价（无需手动配置阶梯区间）。
- 日曲线改为「年对比用气曲线」（双折线+双柱状）。
- 订单列表已移除。
- 新增每日用气量（HA statistics）驱动的日历与日曲线。

## 8. 配色

配色与济南水务卡片保持一致（同一套色调，两张卡片并排视觉统一），主色为蓝：

| 用途 | 色值 |
| --- | --- |
| 用气量 / 主色（标题、曲线、选中态、日历最高 2 天） | `#2f9be0` |
| 主色深字（选中按钮文字、阶梯区间文字） | `#1b6fa8` |
| 浅底（选中按钮、日历超均值） | `#d7ecfb` / `#eaf5fd` |
| 费用 | `#9575cd` |
| 去年用气（对比折线/柱） | `#8f83db` |
| 阶梯一/二/三档填充 | `#5aa9e0` / `#8f83db` / `#c57fc6` |
| 日历三级渐变 | `#eaf5fd` → `#bfdffa` → `#2f9be0`（最高 2 天白字） |

涨跌色：上涨 `#e05a5a`、下降 `#22c55e`。全部色值集中在卡片 JS 顶部的 `COLOR_*` 常量与 `STYLES` 中，改其一即可整体换肤。



# 已经有的实体以及信息

## 1. 当前阶梯气价 sensor.tongwangas_shandong_step_name_1111111111

```yaml
entity_id: sensor.tongwangas_shandong_step_name_1111111111
state: 一阶气价
last_changed: '2026-09-17T09:06:55.417Z'
last_updated: '2026-09-17T09:06:55.417Z'
attributes:
  graph:
    - priceModel: null
      modelSeq: '1'
      minMount: null
      maxMount: '216'
      mountTrate: null
      price: '3.5'
      discFactor: null
      effDate: null
      expDate: null
      priceCode: null
      stepName: 一阶气价
    - priceModel: null
      modelSeq: '2'
      minMount: null
      maxMount: '360'
      mountTrate: null
      price: '4.1'
      discFactor: null
      effDate: null
      expDate: null
      priceCode: null
      stepName: 二阶气价
    - priceModel: null
      modelSeq: '3'
      minMount: null
      maxMount: '-1'
      mountTrate: null
      price: '5'
      discFactor: null
      effDate: null
      expDate: null
      priceCode: null
      stepName: 三阶气价
```

## 今年累计用气量

```yaml
entity_id: sensor.tongwangas_shandong_gas_total_yearly_1111111111
state: '160.0'
last_changed: '2026-09-17T09:06:55.417Z'
last_updated: '2026-09-17T09:06:55.417Z'
attributes:
  state_class: total
  last_reset: '2026-01-01T00:00:00+08:00'
  unit_of_measurement: m³
  device_class: gas
  icon: mdi:meter-gas
  friendly_name: xx小区****3-601 今年累计用气量
```

## 可用余额 sensor.tongwangas_shandong_available_balance_1111111111

xx 元

## 累计用气量

```yaml
entity_id: sensor.tongwangas_shandong_gas_total_1111111111
state: '257.0'
last_changed: '2026-09-17T09:06:55.724Z'
last_updated: '2026-09-17T09:06:55.724Z'
attributes:
  state_class: total_increasing
  unit_of_measurement: m³
  device_class: gas
  icon: mdi:cash-multiple
  friendly_name: xx小区****3-601 累计用气量
```

## 上次抄表日期

```yaml
entity_id: sensor.tongwangas_shandong_last_meter_reading_date_1111111111
state: '2026-09-17'
last_changed: '2026-09-17T09:06:55.417Z'
last_updated: '2026-09-17T09:06:55.417Z'
attributes:
  icon: mdi:calendar-clock
  friendly_name: xx小区****3-601 上次抄表日期
```

## 应缴费用

```yaml
entity_id: sensor.tongwangas_shandong_fee_payable_1111111111
state: '0.0'
last_changed: '2026-09-17T09:06:55.416Z'
last_updated: '2026-09-17T09:06:55.416Z'
attributes:
  state_class: measurement
  unit_of_measurement: 元
  icon: mdi:currency-cny
  friendly_name: xx小区****3-601 应缴费用
```

## 用气明细

```yaml
entity_id: sensor.tongwangas_shandong_gas_consumption_info_1111111111
state: 图表
last_changed: '2026-09-17T09:06:55.418Z'
last_updated: '2026-09-17T09:06:55.418Z'
attributes:
  graph:
    - resTypeCategory: '0'
      lastYearFlag: 'N'
      subsCode: '1111111111'
      yrMonth: '202608'
      meterCode: '152230600533'
      money: '66.5'
      gasSum: '19'
      lastReading: '223'
      currReading: '242'
      readingDate: '2026-08-24'
      rechargeDetails: null
    - resTypeCategory: '0'
      lastYearFlag: 'N'
      subsCode: '1111111111'
      yrMonth: '202607'
      meterCode: '152230600533'
      money: '91'
      gasSum: '26'
      lastReading: '197'
      currReading: '223'
      readingDate: '2026-07-24'
      rechargeDetails: null
    - resTypeCategory: '0'
      lastYearFlag: 'N'
      subsCode: '1111111111'
      yrMonth: '202606'
      meterCode: '152230600533'
      money: '147'
      gasSum: '42'
      lastReading: '155'
      currReading: '197'
      readingDate: '2026-06-24'
      rechargeDetails: null
    - resTypeCategory: '0'
      lastYearFlag: 'N'
      subsCode: '1111111111'
      yrMonth: '202605'
      meterCode: '152230600533'
      money: '59.5'
      gasSum: '17'
      lastReading: '138'
      currReading: '155'
      readingDate: '2026-05-24'
      rechargeDetails: null
    - resTypeCategory: '0'
      lastYearFlag: 'N'
      subsCode: '1111111111'
      yrMonth: '202604'
      meterCode: '152230600533'
      money: '35'
      gasSum: '10'
      lastReading: '128'
      currReading: '138'
      readingDate: '2026-04-22'
      rechargeDetails: null
    - resTypeCategory: '0'
      lastYearFlag: 'N'
      subsCode: '1111111111'
      yrMonth: '202603'
      meterCode: '152230600533'
      money: '49'
      gasSum: '14'
      lastReading: '114'
      currReading: '128'
      readingDate: '2026-03-24'
      rechargeDetails: null
    - resTypeCategory: '0'
      lastYearFlag: 'N'
      subsCode: '1111111111'
      yrMonth: '202602'
      meterCode: '152230600533'
      money: '42'
      gasSum: '12'
      lastReading: '102'
      currReading: '114'
      readingDate: '2026-02-24'
      rechargeDetails: null
    - resTypeCategory: '0'
      lastYearFlag: 'N'
      subsCode: '1111111111'
      yrMonth: '202601'
      meterCode: '152230600533'
      money: '24.5'
      gasSum: '7'
      lastReading: '95'
      currReading: '102'
      readingDate: '2026-01-24'
      rechargeDetails: null
    - resTypeCategory: '0'
      lastYearFlag: 'Y'
      subsCode: '1111111111'
      yrMonth: '202512'
      meterCode: '152230600533'
      money: '28'
      gasSum: '8'
      lastReading: '87'
      currReading: '95'
      readingDate: '2025-12-24'
      rechargeDetails: null
    - resTypeCategory: '0'
      lastYearFlag: 'Y'
      subsCode: '1111111111'
      yrMonth: '202511'
      meterCode: '152230600533'
      money: '28'
      gasSum: '8'
      lastReading: '79'
      currReading: '87'
      readingDate: '2025-11-24'
      rechargeDetails: null
    - resTypeCategory: '0'
      lastYearFlag: 'Y'
      subsCode: '1111111111'
      yrMonth: '202510'
      meterCode: '152230600533'
      money: '31.5'
      gasSum: '9'
      lastReading: '70'
      currReading: '79'
      readingDate: '2025-10-24'
      rechargeDetails: null
    - resTypeCategory: '0'
      lastYearFlag: 'Y'
      subsCode: '1111111111'
      yrMonth: '202509'
      meterCode: '152230600533'
      money: '38.5'
      gasSum: '11'
      lastReading: '59'
      currReading: '70'
      readingDate: '2025-09-21'
      rechargeDetails: null
    - resTypeCategory: '0'
      lastYearFlag: 'Y'
      subsCode: '1111111111'
      yrMonth: '202508'
      meterCode: '152230600533'
      money: '28'
      gasSum: '8'
      lastReading: '51'
      currReading: '59'
      readingDate: '2025-08-24'
      rechargeDetails: null
    - resTypeCategory: '0'
      lastYearFlag: 'Y'
      subsCode: '1111111111'
      yrMonth: '202507'
      meterCode: '152230600533'
      money: '31.5'
      gasSum: '9'
      lastReading: '42'
      currReading: '51'
      readingDate: '2025-07-18'
      rechargeDetails: null
    - resTypeCategory: '0'
      lastYearFlag: 'Y'
      subsCode: '1111111111'
      yrMonth: '202506'
      meterCode: '152230600533'
      money: '28'
      gasSum: '8'
      lastReading: '34'
      currReading: '42'
      readingDate: '2025-06-20'
      rechargeDetails: null
    - resTypeCategory: '0'
      lastYearFlag: 'Y'
      subsCode: '1111111111'
      yrMonth: '202505'
      meterCode: '152230600533'
      money: '24.5'
      gasSum: '7'
      lastReading: '27'
      currReading: '34'
      readingDate: '2025-05-24'
      rechargeDetails: null
    - resTypeCategory: '0'
      lastYearFlag: 'Y'
      subsCode: '1111111111'
      yrMonth: '202504'
      meterCode: '152230600533'
      money: '17.5'
      gasSum: '5'
      lastReading: '22'
      currReading: '27'
      readingDate: '2025-04-24'
      rechargeDetails: null
    - resTypeCategory: '0'
      lastYearFlag: 'Y'
      subsCode: '1111111111'
      yrMonth: '202503'
      meterCode: '152230600533'
      money: '31.5'
      gasSum: '9'
      lastReading: '13'
      currReading: '22'
      readingDate: '2025-03-24'
      rechargeDetails: null
    - resTypeCategory: '0'
      lastYearFlag: 'Y'
      subsCode: '1111111111'
      yrMonth: '202502'
      meterCode: '152230600533'
      money: '31.5'
      gasSum: '9'
      lastReading: '4'
      currReading: '13'
      readingDate: '2025-02-24'
      rechargeDetails: null
    - resTypeCategory: '0'
      lastYearFlag: 'Y'
      subsCode: '1111111111'
      yrMonth: '202501'
      meterCode: '152230600533'
      money: '7'
      gasSum: '2'
      lastReading: '2'
      currReading: '4'
      readingDate: '2025-01-20'
      rechargeDetails: null
  icon: mdi:chart-bar
  friendly_name: xx小区****3-601 用气明细
```

## 用气趋势

```yaml
entity_id: sensor.tongwangas_shandong_gas_consumption_trend_info_1111111111
state: 图表
last_changed: '2026-09-17T09:06:55.418Z'
last_updated: '2026-09-17T09:06:55.418Z'
attributes:
  graph:
    - lastYearFlag: 'Y'
      yrMonth: '202501'
      gasSum: '2'
    - lastYearFlag: 'Y'
      yrMonth: '202502'
      gasSum: '9'
    - lastYearFlag: 'Y'
      yrMonth: '202503'
      gasSum: '9'
    - lastYearFlag: 'Y'
      yrMonth: '202504'
      gasSum: '5'
    - lastYearFlag: 'Y'
      yrMonth: '202505'
      gasSum: '7'
    - lastYearFlag: 'Y'
      yrMonth: '202506'
      gasSum: '8'
    - lastYearFlag: 'Y'
      yrMonth: '202507'
      gasSum: '9'
    - lastYearFlag: 'Y'
      yrMonth: '202508'
      gasSum: '8'
    - lastYearFlag: 'Y'
      yrMonth: '202509'
      gasSum: '11'
    - lastYearFlag: 'Y'
      yrMonth: '202510'
      gasSum: '9'
    - lastYearFlag: 'Y'
      yrMonth: '202511'
      gasSum: '8'
    - lastYearFlag: 'Y'
      yrMonth: '202512'
      gasSum: '8'
    - lastYearFlag: 'N'
      yrMonth: '202601'
      gasSum: '7'
    - lastYearFlag: 'N'
      yrMonth: '202602'
      gasSum: '12'
    - lastYearFlag: 'N'
      yrMonth: '202603'
      gasSum: '14'
    - lastYearFlag: 'N'
      yrMonth: '202604'
      gasSum: '10'
    - lastYearFlag: 'N'
      yrMonth: '202605'
      gasSum: '17'
    - lastYearFlag: 'N'
      yrMonth: '202606'
      gasSum: '42'
    - lastYearFlag: 'N'
      yrMonth: '202607'
      gasSum: '26'
    - lastYearFlag: 'N'
      yrMonth: '202608'
      gasSum: '19'
    - lastYearFlag: 'N'
      yrMonth: '202609'
      gasSum: '0'
    - lastYearFlag: 'N'
      yrMonth: '202610'
      gasSum: '0'
    - lastYearFlag: 'N'
      yrMonth: '202611'
      gasSum: '0'
    - lastYearFlag: 'N'
      yrMonth: '202612'
      gasSum: '0'
  icon: mdi:chart-line
  friendly_name: xx小区****3-601 用气趋势
```