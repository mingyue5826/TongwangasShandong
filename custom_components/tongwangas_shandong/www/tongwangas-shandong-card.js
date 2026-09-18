/**
 * 港华燃气用气卡片（tongwangas-shandong-card）
 * ============================================================================
 * 与集成 tongwangas_shandong 配套的前端卡片：展示可用余额/应缴费用/累计用气量、
 * 用气卡片（按月用气曲线 + hover/点击）、用气阶梯、用气日历、用气曲线（年对比
 * 今年 vs 去年 双折线+双柱状）、用气明细表格、日用气曲线。
 *
 * 添加到 Home Assistant
 * 1. 把本文件复制到 HA 配置目录下的 www：
 *      config/www/community/tongwangas-shandong/tongwangas-shandong-card.js
 *    （www 目录若不存在则自行创建；集成不会自动部署该文件）
 * 2. 设置 → 仪表盘 → 右上角「⋮」→ 资源 → 添加资源
 *      URL：/local/community/tongwangas-shandong/tongwangas-shandong-card.js
 *      资源类型：JavaScript 模块
 * 3. 仪表盘 → 右下角「编辑」→ 添加卡片 → 手动（YAML）填入下方配置
 *
 * 设计要点（与济南水务卡片保持同一技术路线）
 * 1. 零依赖单文件：不内联任何图表库，曲线/柱状均用手绘 SVG（Catmull-Rom 转贝塞尔）。
 * 2. 数据全部来自集成实体，不做任何接口请求。
 * 3. 实体 id 约定：sensor.tongwangas_shandong_<key>_<户号(subsCode)>
 *    - available_balance        可用余额
 *    - fee_payable             应缴费用
 *    - gas_total               累计用气量
 *    - gas_total_yearly        今年累计用气量（阶梯进度用）
 *    - last_meter_reading_date 上次抄表日期
 *    - step_name               当前阶梯气价（graph=三档 maxMount/price）
 *    - gas_consumption_info    用气明细（graph=每月一条：yrMonth/gasSum/money/readingDate）
 *    - gas_consumption_trend_info 用气趋势（graph=含去年Y+今年N的月度 gasSum）
 *    - gas_total_daily         每日用气量（基于 gas_total 的 sum 统计量，graph=每日序列）
 *
 * 配置示例（YAML）
 * ```yaml
 * type: custom:tongwangas-shandong-card
 * gs: "1111111111"       # 户号；不填则自动探测第一个 tongwangas_shandong 设备
 * title: 港华燃气
 * price: 3.5             # 单价覆盖（元/m³），用于日历/日曲线费用估算；不填读当前阶梯气价
 * default_panel: ""      # 默认展开："" | "calendar" | "yearCurve" | "table" | "daily"
 * ```
 */

const CARD_VERSION = "1.0.0";
const DOMAIN = "tongwangas_shandong";

/* ============================================================================
 * 实体 key -> 实体 id 后缀（与 sensor.py 中的 _sensor_key 一一对应）
 * 实体 id 形如 sensor.tongwangas_shandong_<后缀>_<户号>
 * ========================================================================== */
const ENTITY_SUFFIX = {
  available_balance: "available_balance",
  fee_payable: "fee_payable",
  gas_total: "gas_total",
  gas_total_yearly: "gas_total_yearly",
  last_meter_reading_date: "last_meter_reading_date",
  step_name: "step_name",
  gas_consumption_info: "gas_consumption_info",
  gas_consumption_trend_info: "gas_consumption_trend_info",
  gas_total_daily: "gas_total_daily",
};

// 配色（用气=橙，费用=紫，去年=蓝灰）
const COLOR_GAS = "#e8772e";
const COLOR_COST = "#9575cd";
const COLOR_LASTYEAR = "#7aa7c7";
const COLOR_AVG = "#9e9e9e";
const COLOR_WARN = "#f59e0b";
const COLOR_OK = "#22c55e";

/** 日粒度数据的小字提示：小数来自表具 1 m³ 精度的推算，而非实际读数。 */
const PRECISION_HINT = "带小数的日用量为表具 1 m³ 精度的推算值（按跳表间隔平摊），非实际读表值";

/* ============================================================================
 * 图标（内联 SVG path，避免依赖 ha-icon，预览页也能正常显示）
 * ========================================================================== */
const ICON_PATHS = {
  flame:
    "M12 2c1.2 3 4.2 5 4.2 9a4.2 4.2 0 0 1-8.4 0c0-1.6.6-3 1.6-4.3C9.2 8.4 12 6.2 12 2Z",
  wallet:
    "M21,18V19A2,2 0 0,1 19,21H5C3.89,21 3,20.1 3,19V5A2,2 0 0,1 5,3H19A2,2 0 0,1 21,5V6H12C10.89,6 10,6.9 10,8V16A2,2 0 0,0 12,18M12,16H22V8H12M16,13.5A1.5,1.5 0 0,1 14.5,12A1.5,1.5 0 0,1 16,10.5A1.5,1.5 0 0,1 17.5,12A1.5,1.5 0 0,1 16,13.5Z",
  alert:
    "M11,15H13V17H11V15M11,7H13V13H11V7M12,2C6.47,2 2,6.5 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M12,20A8,8 0 0,1 4,12A8,8 0 0,1 12,4A8,8 0 0,1 20,12A8,8 0 0,1 12,20Z",
  gavel: "M1,21H23L12,2L1,21M13,18H11V16H13V18M13,14H11V9H13V14Z",
  calendar:
    "M7,10H12V15H7M19,19H5V8H19M19,3H18V1H16V3H8V1H6V3H5C3.89,3 3,3.9 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V5A2,2 0 0,0 19,3Z",
  chart:
    "M16,11.78L20.24,4.45L21.97,5.45L16.74,14.5L10.23,10.75L5.46,19H22V21H2V3H4V17.54L9.5,8L16,11.78Z",
  list: "M7,5H21V7H7V5M7,13V11H21V13H7M4,4.5A1.5,1.5 0 0,1 5.5,6A1.5,1.5 0 0,1 4,7.5A1.5,1.5 0 0,1 2.5,6A1.5,1.5 0 0,1 4,4.5M4,10.5A1.5,1.5 0 0,1 5.5,12A1.5,1.5 0 0,1 4,13.5A1.5,1.5 0 0,1 2.5,12A1.5,1.5 0 0,1 4,10.5M7,19V17H21V19H7M4,16.5A1.5,1.5 0 0,1 5.5,18A1.5,1.5 0 0,1 4,19.5A1.5,1.5 0 0,1 2.5,18A1.5,1.5 0 0,1 4,16.5Z",
  bolt: "M11,15H6L13,1V9H18L11,23V15Z",
  chevronDown: "M7.41,8.58L12,13.17L16.59,8.58L18,10L12,16L6,10L7.41,8.58Z",
  chevronUp: "M7.41,15.41L12,10.83L16.59,15.41L18,14L12,8L6,14L7.41,15.41Z",
  arrowLeft: "M15.41,16.58L10.83,12L15.41,7.41L14,6L8,12L14,18L15.41,16.58Z",
  arrowRight: "M8.59,16.58L13.17,12L8.59,7.41L10,6L16,12L10,18L8.59,16.58Z",
};

/** 生成内联 SVG 图标（默认 16px，跟随文字颜色）。 */
function icon(name, size = 16) {
  const path = ICON_PATHS[name] || ICON_PATHS.flame;
  return `<svg class="ico" viewBox="0 0 24 24" width="${size}" height="${size}" aria-hidden="true"><path d="${path}" fill="currentColor"/></svg>`;
}

/* ============================================================================
 * 通用工具
 * ========================================================================== */
function num(value, fallback = null) {
  if (value === null || value === undefined || value === "" || value === "unknown" || value === "unavailable") {
    return fallback;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

/** 金额格式化：固定两位小数。 */
function money(value, digits = 2) {
  const parsed = num(value, null);
  if (parsed === null) return "--";
  return parsed.toFixed(digits);
}

/** 水量格式化：去掉多余的小数尾巴。 */
function volume(value, digits = 2) {
  const parsed = num(value, null);
  if (parsed === null) return "--";
  const fixed = parsed.toFixed(digits);
  return fixed.replace(/\.?0+$/, "") || "0";
}

/** 把 "202608" / "2026-08-24" 等规范化为 "YYYY-MM"。 */
function normalizeMonth(value) {
  if (!value || typeof value !== "string") return null;
  let text = value.trim();
  if (/^\d{6}$/.test(text)) return `${text.slice(0, 4)}-${text.slice(4, 6)}`;
  const m = text.match(/^(\d{4})-(\d{2})/);
  if (m) return `${m[1]}-${m[2]}`;
  return null;
}

/** 把任意日期串规范化为 "YYYY-MM-DD"。 */
function normalizeDate(value) {
  if (typeof value !== "string" || !value.trim()) return null;
  const m = value.trim().match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) return `${m[1]}-${m[2]}-${m[3]}`;
  return null;
}

/** Date -> "YYYY-MM-DD"（按本地时区，避免 toISOString 的 UTC 偏移导致差一天）。 */
function isoDate(date) {
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) return "";
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(
    date.getDate(),
  ).padStart(2, "0")}`;
}

/** 日粒度的日期加减（按天，规避夏令时/时区误差）。 */
function shiftDays(dateText, days) {
  const base = new Date(`${dateText}T00:00:00`);
  if (Number.isNaN(base.getTime())) return "";
  base.setDate(base.getDate() + days);
  return isoDate(base);
}

function escapeHtml(value) {
  return String(value === null || value === undefined ? "" : value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

/** 平滑曲线路径（Catmull-Rom 转三次贝塞尔），points 为 [{x, y}]。 */
function smoothPath(points) {
  if (!points.length) return "";
  if (points.length === 1) return `M ${points[0].x} ${points[0].y}`;
  let d = `M ${points[0].x} ${points[0].y}`;
  for (let i = 0; i < points.length - 1; i += 1) {
    const p0 = points[i - 1] || points[i];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[i + 2] || p2;
    const c1x = p1.x + (p2.x - p0.x) / 6;
    const c1y = p1.y + (p2.y - p0.y) / 6;
    const c2x = p2.x - (p3.x - p1.x) / 6;
    const c2y = p2.y - (p3.y - p1.y) / 6;
    d += ` C ${c1x.toFixed(2)} ${c1y.toFixed(2)}, ${c2x.toFixed(2)} ${c2y.toFixed(2)}, ${p2.x.toFixed(2)} ${p2.y.toFixed(2)}`;
  }
  return d;
}

/* ============================================================================
 * 卡片主体
 * ========================================================================== */
class TongwangasShandongCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = null;
    this._gs = null;
    this._panel = "";
    this._expanded = new Set();
    this._signature = null;
    this._cal = { year: new Date().getFullYear(), month: new Date().getMonth() + 1 };
    this._dailyRange = "month"; // 日用气曲线区间：week | month | custom（默认近一月）
    this._customStart = "";
    this._customEnd = "";
    this._onClick = this._onClick.bind(this);
    this._onMouseMove = this._onMouseMove.bind(this);
    this._onMouseLeave = this._onMouseLeave.bind(this);
    this._onChange = this._onChange.bind(this);
  }

  /* ---------------------------- HA 卡片接口 ---------------------------- */

  static getStubConfig() {
    return {
      gs: "",
      title: "港华燃气",
      default_panel: "",
    };
  }

  static getConfigElement() {
    return document.createElement("tongwangas-shandong-card-editor");
  }

  setConfig(config) {
    if (!config) throw new Error("配置不能为空");
    this._config = { ...config };
    this._panel = config.default_panel || "";
    this._expanded = new Set();
    this._signature = null;
    const today = new Date();
    this._cal = { year: today.getFullYear(), month: today.getMonth() + 1 };
    this._gs = config.gs ? String(config.gs) : null;
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._config) return;
    if (!this._gs) {
      this._gs = this._detectGs();
      if (!this._gs) {
        this._render();
        return;
      }
    }
    const signature = this._dataSignature();
    if (signature !== this._signature) {
      this._signature = signature;
      this._render();
    }
  }

  getCardSize() {
    let size = 9;
    if (this._panel === "calendar") size += 8;
    if (this._panel === "yearCurve") size += 6;
    if (this._panel === "table") size += 6;
    if (this._panel === "daily") size += 6;
    return size;
  }

  connectedCallback() {
    // 注意：change 事件 composed=false，不跨 shadow 边界，
    // 必须挂在 shadowRoot 上，挂到宿主元素上永远不会触发（曾导致自定义区间失效）。
    this.shadowRoot.addEventListener("click", this._onClick);
    this.shadowRoot.addEventListener("mousemove", this._onMouseMove);
    this.shadowRoot.addEventListener("change", this._onChange);
    this.addEventListener("mouseleave", this._onMouseLeave);
    if (this._config && this._hass) this._render();
  }

  disconnectedCallback() {
    this.shadowRoot.removeEventListener("click", this._onClick);
    this.shadowRoot.removeEventListener("mousemove", this._onMouseMove);
    this.shadowRoot.removeEventListener("change", this._onChange);
    this.removeEventListener("mouseleave", this._onMouseLeave);
  }

  /* ------------------------------ 数据读取 ------------------------------ */

  /** 自动探测户号：取第一个 tongwangas_shandong 用气明细实体的后缀。 */
  _detectGs() {
    if (!this._hass) return null;
    const pattern = new RegExp(`^sensor\\.${DOMAIN}_gas_consumption_info_(.+)$`);
    for (const entityId of Object.keys(this._hass.states)) {
      const matched = entityId.match(pattern);
      if (matched) return matched[1];
    }
    return null;
  }

  _entityId(key) {
    const override = this._config?.entities?.[key];
    if (override) return override;
    const suffix = ENTITY_SUFFIX[key] || key;
    return `sensor.${DOMAIN}_${suffix}_${this._gs}`;
  }

  _entity(key) {
    if (!this._hass || !this._gs) return null;
    return this._hass.states[this._entityId(key)] || null;
  }

  _num(key) {
    const entity = this._entity(key);
    return entity ? num(entity.state, null) : null;
  }

  /** 用气明细（每月一条，已按 yrMonth 升序）。 */
  _monthly() {
    const entity = this._entity("gas_consumption_info");
    const graph = entity?.attributes?.graph;
    if (!Array.isArray(graph)) return [];
    const rows = graph.map((r) => {
      const yrMonth = String(r.yrMonth || "");
      return {
        yrMonth,
        month: normalizeMonth(yrMonth) || "",
        gas: num(r.gasSum, 0),
        money: num(r.money, 0),
        readingDate: normalizeDate(r.readingDate) || "",
        lastReading: num(r.lastReading, null),
        currReading: num(r.currReading, null),
        flag: r.lastYearFlag,
      };
    });
    rows.sort((a, b) => a.yrMonth.localeCompare(b.yrMonth));
    return rows;
  }

  /** 用气趋势：拆成今年/去年 12 个月桶（按自然年对齐）。 */
  _trend() {
    const entity = this._entity("gas_consumption_trend_info");
    const graph = entity?.attributes?.graph;
    const thisYear = new Date().getFullYear();
    const lastYear = thisYear - 1;
    const curr = new Array(12).fill(0);
    const last = new Array(12).fill(0);
    if (Array.isArray(graph)) {
      for (const e of graph) {
        const ym = String(e.yrMonth || "");
        const y = parseInt(ym.slice(0, 4), 10);
        const m = parseInt(ym.slice(4, 6), 10) - 1;
        if (Number.isNaN(y) || m < 0 || m > 11) continue;
        const g = num(e.gasSum, 0);
        if (y === thisYear) curr[m] = g;
        else if (y === lastYear) last[m] = g;
      }
    }
    return {
      labels: Array.from({ length: 12 }, (_, i) => `${i + 1}月`),
      curr,
      last,
      thisYear,
      lastYear,
    };
  }

  /** 用气阶梯：来自 step_name 实体的 graph（三档 maxMount/price）。 */
  _steps() {
    const entity = this._entity("step_name");
    const graph = entity?.attributes?.graph;
    const state = entity?.state || "";
    const tiers = [];
    if (Array.isArray(graph)) {
      const sorted = graph
        .slice()
        .sort((a, b) => num(a.modelSeq, 0) - num(b.modelSeq, 0));
      let prevTo = 0;
      sorted.forEach((t, i) => {
        const maxMount = num(t.maxMount, null);
        const to = maxMount !== null && maxMount >= 0 ? maxMount : null;
        const from = prevTo;
        tiers.push({
          name: t.stepName || `第${i + 1}阶`,
          from,
          to,
          price: num(t.price, null),
          current: state && t.stepName === state,
        });
        prevTo = to ?? prevTo;
      });
    }
    const value = this._num("gas_total_yearly");
    return { tiers, value: value === null ? 0 : value };
  }

  /** 每日用气量（基于 gas_total 的 sum 统计量，已按日期升序）。 */
  _daily() {
    const entity = this._entity("gas_total_daily");
    const graph = entity?.attributes?.graph;
    if (!Array.isArray(graph)) return [];
    return graph
      .map((r) => ({ date: normalizeDate(r.date) || "", gas: num(r.gasSum, 0) }))
      .filter((r) => r.date)
      .sort((a, b) => a.date.localeCompare(b.date));
  }

  /** 当前估算单价：配置优先，其次当前阶梯气价，再次首档价格。 */
  _unitPrice() {
    const configured = num(this._config?.price, null);
    if (configured !== null && configured > 0) return configured;
    const steps = this._steps();
    const cur = steps.tiers.find((t) => t.current) || steps.tiers[0];
    return cur && cur.price ? cur.price : 0;
  }

  /** 数据签名：只有与展示相关的状态变化时才重新渲染。 */
  _dataSignature() {
    if (!this._hass) return null;
    const parts = Object.keys(ENTITY_SUFFIX).map((key) => {
      const entity = this._entity(key);
      if (!entity) return `${key}:-`;
      return `${key}:${entity.state}:${entity.last_updated || ""}`;
    });
    return `${this._gs}|${parts.join("|")}`;
  }

  /* ------------------------------ 交互事件 ------------------------------ */

  _onClick(event) {
    const target = event
      .composedPath()
      .find((node) => node instanceof HTMLElement && node.dataset && node.dataset.action);
    if (!target) return;
    event.stopPropagation();
    const action = target.dataset.action;

    switch (action) {
      case "toggle-panel": {
        const panel = target.dataset.panel;
        this._panel = this._panel === panel ? "" : panel;
        break;
      }
      case "cal-prev-month":
        this._shiftMonth(-1);
        break;
      case "cal-next-month":
        this._shiftMonth(1);
        break;
      case "cal-prev-year":
        this._shiftMonth(-12);
        break;
      case "cal-next-year":
        this._shiftMonth(12);
        break;
      case "cal-today": {
        const now = new Date();
        this._cal = { year: now.getFullYear(), month: now.getMonth() + 1 };
        break;
      }
      case "spark-click": {
        const chart = target.querySelector("[data-chart]");
        if (chart) this._showTooltipForChart(chart, event.clientX);
        return;
      }
      case "daily-range": {
        const range = target.dataset.range;
        if (range) {
          // 首次切到「自定义」时，预填一个合理区间（最近一个月），避免空区间=显示全部
          if (range === "custom" && !this._customStart && !this._customEnd) {
            const all = this._daily();
            const maxDate = all.length ? all[all.length - 1].date : "";
            if (maxDate) {
              this._customEnd = maxDate;
              this._customStart = shiftDays(maxDate, -29);
            }
          }
          this._dailyRange = range;
        }
        break;
      }
      default:
        return;
    }
    this._signature = this._dataSignature();
    this._render();
  }

  _shiftMonth(delta) {
    const total = this._cal.year * 12 + (this._cal.month - 1) + delta;
    this._cal = { year: Math.floor(total / 12), month: (total % 12) + 1 };
  }

  /** 在图表上根据 clientX 定位最近的数据点并展示 tooltip（hover 与点击共用）。 */
  _showTooltipForChart(chart, clientX) {
    const points = JSON.parse(chart.dataset.points || "[]");
    if (!points.length) return;
    const rect = chart.getBoundingClientRect();
    if (!rect.width) return;
    const container = chart.closest(".chart-wrap, .usage-spark");
    const tooltip = container ? container.querySelector(".chart-tooltip") : null;
    if (!tooltip) return;

    const viewWidth = Number(chart.dataset.viewWidth) || 640;
    const viewX = ((clientX - rect.left) / rect.width) * viewWidth;
    const plotLeft = Number(chart.dataset.plotLeft) || 0;
    const plotWidth = Number(chart.dataset.plotWidth) || 1;
    const step = points.length > 1 ? plotWidth / (points.length - 1) : 0;
    const index = clamp(Math.round(step ? (viewX - plotLeft) / step : 0), 0, points.length - 1);
    const point = points[index];
    if (!point) return;

    const rows = (point.rows || [])
      .map(
        (row) =>
          `<div class="tt-row"><span class="tt-dot" style="background:${row.c}"></span>${escapeHtml(row.t)}</div>`,
      )
      .join("");

    tooltip.innerHTML = `<div class="tt-date">${escapeHtml(point.label || "--")}</div>${rows}`;
    tooltip.hidden = false;
    const offsetX = (point.x / viewWidth) * rect.width;
    tooltip.style.left = `${clamp(offsetX - tooltip.offsetWidth / 2, 0, Math.max(rect.width - tooltip.offsetWidth, 0))}px`;
    tooltip.style.top = "4px";

    const cursor = container.querySelector(".chart-cursor");
    if (cursor) {
      cursor.setAttribute("x1", point.x);
      cursor.setAttribute("x2", point.x);
      cursor.style.opacity = "1";
    }
  }

  _onMouseMove(event) {
    const chart = event
      .composedPath()
      .find((node) => node && node.dataset && node.dataset.chart);
    if (!chart) return;
    this._showTooltipForChart(chart, event.clientX);
  }

  _onMouseLeave() {
    this.shadowRoot.querySelectorAll(".chart-tooltip").forEach((element) => {
      element.hidden = true;
    });
    this.shadowRoot.querySelectorAll(".chart-cursor").forEach((element) => {
      element.style.opacity = "0";
    });
  }

  /** 自定义区间的日期输入变化：切到 custom 并重新渲染。 */
  _onChange(event) {
    const el = event.composedPath ? event.composedPath()[0] : event.target;
    if (!el || !el.dataset || !el.dataset.custom) return;
    if (el.dataset.custom === "start") this._customStart = el.value || "";
    else if (el.dataset.custom === "end") this._customEnd = el.value || "";
    this._dailyRange = "custom";
    this._render();
  }

  /** 按当前区间筛选每日数据（rows 已按日期升序）。 */
  _filterDaily(rows) {
    if (!rows.length) return rows;
    const maxDate = rows[rows.length - 1].date;
    const minDate = rows[0].date;
    let start = null;
    let end = maxDate;
    if (this._dailyRange === "week") {
      start = shiftDays(maxDate, -6);
    } else if (this._dailyRange === "month") {
      start = shiftDays(maxDate, -29);
    } else if (this._dailyRange === "year") {
      start = shiftDays(maxDate, -364);
    } else if (this._dailyRange === "custom") {
      start = normalizeDate(this._customStart) || this._customStart || null;
      end = normalizeDate(this._customEnd) || this._customEnd || maxDate;
      // 起止颠倒时自动交换，避免出现空区间
      if (start && end && start > end) [start, end] = [end, start];
      // 用户输入的日期超出手头数据范围时，收敛到实际数据边界
      if (start && start < minDate) start = minDate;
      if (end && end > maxDate) end = maxDate;
    }
    if (!start) return rows;
    return rows.filter((r) => r.date >= start && r.date <= end);
  }

  /* ------------------------------- 渲染 ------------------------------- */

  _render() {
    const root = this.shadowRoot;
    if (!this._hass) return;

    if (!this._config) {
      root.innerHTML = `<style>${STYLES}</style><ha-card><div class="empty">请先配置卡片</div></ha-card>`;
      return;
    }
    if (!this._gs) {
      root.innerHTML = `<style>${STYLES}</style><ha-card><div class="empty">
        未找到港华燃气设备：请确认集成已添加，或在卡片配置中填写 gs（户号）。</div></ha-card>`;
      return;
    }

    root.innerHTML = `<style>${STYLES}</style>${this._renderMain()}${this._renderPanel()}`;
  }

  /* ---- 主视图（费用指标 + 用气卡片 + 阶梯 + 按钮） ---- */
  _renderMain() {
    const balance = this._num("available_balance");
    const payable = this._num("fee_payable");
    const total = this._num("gas_total");
    const title = this._config.title || "港华燃气";

    const lastMeterDate = this._entity("last_meter_reading_date")?.state || "";
    // 本月用气：由每日用气量（gas_total 统计量）累加；对比上月。
    const price = this._unitPrice();
    const dailyAll = this._daily();
    const now = new Date();
    const curYm = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
    const prevDate = new Date(now.getFullYear(), now.getMonth() - 1, 1);
    const prevYm = `${prevDate.getFullYear()}-${String(prevDate.getMonth() + 1).padStart(2, "0")}`;
    const sumGas = (rows) => rows.reduce((s, r) => s + r.gas, 0);
    const thisRows = dailyAll.filter((r) => r.date.startsWith(curYm));
    const lastRows = dailyAll.filter((r) => r.date.startsWith(prevYm));
    const thisGas = sumGas(thisRows);
    const lastGas = sumGas(lastRows);
    const thisFee = thisGas * price;
    const deltaPct = lastGas > 0 ? ((thisGas - lastGas) / lastGas) * 100 : null;

    return `
      <ha-card class="main-card">
        <div class="card-title-row">
          <span class="card-title">${icon("flame", 15)}${escapeHtml(title)}</span>
          <span class="card-meta">${lastMeterDate ? `上次抄表 ${escapeHtml(lastMeterDate)}` : ""}</span>
        </div>

        <div class="metrics">
          ${this._renderMetric("可用余额", balance, "wallet", "¥", false)}
          ${this._renderMetric("应缴费用", payable, "alert", "¥", (payable ?? 0) > 0)}
          ${this._renderMetric("累计用气量", total, "flame", "", false, " m³")}
        </div>

        <div class="usage-card">
          <div class="section-head">${icon("flame", 14)} 本月用气</div>
          <div class="usage-body">
            <div class="usage-left">
              <div class="usage-value">${thisGas > 0 ? volume(thisGas) : "--"}<small> m³</small></div>
              <div class="usage-cost">¥ ${thisFee > 0 ? money(thisFee) : "--"}${
                thisRows.length ? `<small class="usage-sub">日均 ${volume(thisGas / thisRows.length)} m³</small>` : ""
              }</div>
              ${
                deltaPct !== null
                  ? `<div class="usage-delta ${deltaPct >= 0 ? "up" : "down"}">较上月 ${deltaPct >= 0 ? "▲" : "▼"} ${Math.abs(deltaPct).toFixed(1)}%</div>`
                  : `<div class="usage-delta muted">较上月 --</div>`
              }
            </div>
            <div class="usage-spark" data-action="spark-click" title="本月每日用气曲线">
              ${this._renderUsageSpark(thisRows, price)}
            </div>
          </div>
          <div class="precision-hint">※ ${PRECISION_HINT}</div>
        </div>

        ${this._renderLadder()}

        <div class="actions">
          ${this._renderAction("calendar", "calendar", "用气日历")}
          ${this._renderAction("yearCurve", "chart", "用气曲线")}
          ${this._renderAction("table", "list", "用气明细")}
          ${this._renderAction("daily", "bolt", "日用气")}
        </div>
      </ha-card>`;
  }

  _renderMetric(label, value, iconName, prefix, warn, suffix = "") {
    const text = value === null ? "--" : money(value);
    return `
      <div class="metric${warn ? " warn" : ""}">
        <div class="metric-label">${icon(iconName, 13)}${escapeHtml(label)}</div>
        <div class="metric-value"><span class="cur">${prefix}</span>${text}${suffix ? `<small>${suffix}</small>` : ""}</div>
      </div>`;
  }

  _renderAction(panel, iconName, label) {
    const active = this._panel === panel ? " active" : "";
    return `<div class="action${active}" data-action="toggle-panel" data-panel="${panel}">
      ${icon(iconName, 16)}<span>${escapeHtml(label)}</span></div>`;
  }

  /* ---- 用气卡片 sparkline（本月每日用气量，hover/点击显示当日用气与费用） ---- */
  _renderUsageSpark(rows, price) {
    if (!rows || !rows.length) return `<div class="spark-empty">本月暂无每日数据</div>`;
    const width = 300;
    const height = 90;
    const pad = 8;
    const maxValue = Math.max(...rows.map((r) => r.gas), 0.1);
    const step = rows.length > 1 ? (width - pad * 2) / (rows.length - 1) : 0;
    const xOf = (index) => pad + index * step;
    const yOf = (value) => height - pad - (value / maxValue) * (height - pad * 2);

    const points = rows.map((row, index) => {
      const x = xOf(index);
      const y = yOf(row.gas);
      return {
        x,
        y,
        label: row.date.slice(5),
        rows: [
          { c: COLOR_GAS, t: `用气量 ${volume(row.gas)} m³` },
          { c: COLOR_COST, t: `费用 ¥${money(row.gas * price)}` },
        ],
      };
    });

    const linePoints = points.map((p) => ({ x: p.x, y: p.y }));
    const last = linePoints[linePoints.length - 1];
    const chartData = JSON.stringify(points.map((p) => ({ x: p.x, label: p.label, rows: p.rows })));

    return `
      <svg viewBox="0 0 ${width} ${height}" width="100%" height="${height}" preserveAspectRatio="none"
           data-chart="spark" data-points='${chartData.replace(/'/g, "&#39;")}'
           data-view-width="${width}" data-plot-left="${pad}" data-plot-width="${width - pad * 2}">
        <defs>
          <linearGradient id="tws-spark-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="${COLOR_GAS}" stop-opacity="0.28"/>
            <stop offset="100%" stop-color="${COLOR_GAS}" stop-opacity="0"/>
          </linearGradient>
        </defs>
        <path d="${smoothPath(linePoints)} L ${last.x} ${height - pad} L ${linePoints[0].x} ${height - pad} Z"
              fill="url(#tws-spark-fill)" stroke="none"/>
        <path d="${smoothPath(linePoints)}" fill="none" stroke="${COLOR_GAS}" stroke-width="2.4"
              stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="${last.x}" cy="${last.y}" r="3.2" fill="#fff" stroke="${COLOR_GAS}" stroke-width="2"/>
        <line class="chart-cursor" x1="0" y1="${pad}" x2="0" y2="${height - pad}"
              stroke="${COLOR_AVG}" stroke-width="1" style="opacity:0"/>
      </svg>
      <div class="chart-tooltip" hidden></div>`;
  }

  /* ---- 用气阶梯（三档单价 + 当前档高亮 + 今年累计进度） ---- */
  _renderLadder() {
    const { tiers, value } = this._steps();
    if (!tiers.length) {
      return `<div class="ladder-block"><div class="section-head">${icon("bolt", 13)} 用气阶梯
        <span class="ladder-value">暂无阶梯数据</span></div></div>`;
    }

    // 累计值所处档位与每档填充比例
    let activeIndex = 0;
    const fills = tiers.map((tier, index) => {
      const from = tier.from ?? 0;
      const to = tier.to;
      const span = to === null ? Math.max(tiers[index - 1] ? (tiers[index - 1].to ?? 100) - (tiers[index - 1].from ?? 0) : 100, 1) : Math.max(to - from, 1);
      let ratio = 0;
      if (value > from) ratio = clamp((value - from) / span, 0, 1);
      if (to !== null && value > to) ratio = 1;
      if (value > (to ?? Number.POSITIVE_INFINITY)) activeIndex = index + 1;
      return ratio;
    });
    activeIndex = clamp(activeIndex, 0, tiers.length - 1);
    const segmentWidth = 100 / tiers.length;
    const indicatorLeft = clamp(activeIndex * segmentWidth + fills[activeIndex] * segmentWidth, 2, 98);

    const tierBlocks = tiers
      .map(
        (tier, index) => `
        <div class="ladder-tier t${index + 1}${tier.current ? " active" : ""}">
          <div class="ladder-tier-fill" style="width:${(fills[index] * 100).toFixed(1)}%"></div>
          <span class="ladder-tier-name">${escapeHtml(tier.name)}</span>
        </div>`,
      )
      .join("");

    const ranges = tiers
      .map((tier, index) => {
        const from = tier.from ?? 0;
        const range = tier.to === null ? `${from}m³以上` : `${from}-${tier.to}m³`;
        const price = tier.price !== null ? `${money(tier.price, 2)} 元/m³` : "--";
        return `<div class="ladder-range t${index + 1}"><div class="lr-range">${range}</div><div class="lr-price">${price}</div></div>`;
      })
      .join("");

    return `
      <div class="ladder-block">
        <div class="section-head">${icon("bolt", 13)} 用气阶梯
          <span class="ladder-value"><b class="ladder-strong">今年累计</b> ${volume(value)} m³</span>
        </div>
        <div class="ladder-band">
          ${tierBlocks}
          <div class="ladder-bolt" style="left:${indicatorLeft.toFixed(1)}%" title="今年累计用气所处阶梯">
            ${icon("bolt", 15)}
          </div>
        </div>
        <div class="ladder-ranges">${ranges}</div>
      </div>`;
  }

  /* --------------------------- 面板（默认隐藏） --------------------------- */
  _renderPanel() {
    if (this._panel === "calendar") return this._renderCalendarPanel();
    if (this._panel === "yearCurve") return this._renderYearCurvePanel();
    if (this._panel === "table") return this._renderTablePanel();
    if (this._panel === "daily") return this._renderDailyPanel();
    return "";
  }

  /* ---- 用气日历（每日用气量来自 gas_total 每日统计；无每日数据的月份回退用气明细） ---- */
  _renderCalendarPanel() {
    const price = this._unitPrice();
    const dailyMap = new Map(this._daily().map((row) => [row.date, row]));
    const monthlyMap = new Map(this._monthly().map((row) => [row.month, row]));
    const { year, month } = this._cal;
    const ym = `${year}-${String(month).padStart(2, "0")}`;
    const daysInMonth = new Date(year, month, 0).getDate();
    const firstWeekday = new Date(year, month - 1, 1).getDay(); // 0=周日
    const leading = firstWeekday === 0 ? 6 : firstWeekday - 1; // 周一为第一列
    const todayIso = new Date().toISOString().slice(0, 10);

    let cells = "";
    for (let i = 0; i < leading; i += 1) cells += `<div class="cal-cell empty"></div>`;

    // 第一遍：收集本月各日数据，供分级着色与月统计使用
    const dayData = [];
    let monthGas = 0;
    let monthFee = 0;
    let hasDaily = false;
    for (let day = 1; day <= daysInMonth; day += 1) {
      const iso = `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
      const dRow = dailyMap.get(iso);
      const mRow = monthlyMap.get(ym);
      let gas = null;
      let fee = null;
      if (dRow) {
        gas = dRow.gas;
        fee = gas * price;
        hasDaily = true;
      } else if (mRow && mRow.readingDate === iso) {
        // 无每日统计的月份：用该月用气明细的抄表日兜底
        gas = mRow.gas;
        fee = mRow.money;
      }
      dayData.push({ day, iso, gas, fee });
      if (gas !== null) {
        monthGas += gas;
        monthFee += fee;
      }
    }

    // 第二遍：按本月均值与最高 2 天做 3 级渐变着色（lv3=本月最高2天 / lv2=超均值 / lv1=默认）
    const valued = dayData.filter((d) => d.gas !== null);
    const avg = valued.length ? valued.reduce((s, d) => s + d.gas, 0) / valued.length : 0;
    const top2 = valued.length
      ? valued.slice().sort((a, b) => b.gas - a.gas).slice(0, 2).map((d) => d.iso)
      : [];

    for (const d of dayData) {
      const classes = ["cal-cell"];
      if (d.gas !== null) {
        classes.push("has-data");
        if (top2.includes(d.iso)) classes.push("lv3");
        else if (d.gas > avg) classes.push("lv2");
      }
      if (d.iso === todayIso) classes.push("today");
      cells += `
        <div class="${classes.join(" ")}">
          <span class="cal-day">${d.day}</span>
          ${
            d.gas !== null
              ? `<span class="cal-usage">${volume(d.gas, 2)}</span>
                 <span class="cal-cost">¥${money(d.fee, 1)}</span>`
              : `<span class="cal-usage placeholder">-</span><span class="cal-cost placeholder">-</span>`
          }
        </div>`;
    }

    // 整月无每日/抄表数据：用该月用气明细总额兜底月统计
    if (monthGas === 0) {
      const mRow = monthlyMap.get(ym);
      if (mRow) {
        monthGas = mRow.gas;
        monthFee = mRow.money;
      }
    }

    return `
      <ha-card class="panel-card">
        <div class="cal-nav">
          <span class="nav-btn" data-action="cal-prev-year">${icon("arrowLeft", 14)}</span>
          <span class="cal-title">${year}年</span>
          <span class="nav-btn" data-action="cal-next-year">${icon("arrowRight", 14)}</span>
          <span class="nav-btn today-btn" data-action="cal-today">当月</span>
          <span class="nav-btn" data-action="cal-prev-month">${icon("arrowLeft", 14)}</span>
          <span class="cal-title">${month}月</span>
          <span class="nav-btn" data-action="cal-next-month">${icon("arrowRight", 14)}</span>
        </div>
        <div class="cal-week">${["一", "二", "三", "四", "五", "六", "日"]
          .map((d) => `<span>${d}</span>`)
          .join("")}</div>
        <div class="cal-grid">${cells}</div>
        <div class="cal-footer">
          本月合计 ${volume(monthGas)} m³ / ¥ ${money(monthFee)}
          <span class="cal-note">${
            hasDaily
              ? "费用 = 日用气量 × 单价（估算）"
              : "本月无每日数据，按用气明细月度值统计"
          }</span>
          <span class="cal-legend">
            <i class="lg lv1"></i>均值下
            <i class="lg lv2"></i>超均值
            <i class="lg lv3"></i>本月最高 2 天
          </span>
          <span class="precision-hint cal-hint">※ ${PRECISION_HINT}</span>
        </div>
      </ha-card>`;
  }

  /* ---- 用气曲线（年对比：今年 vs 去年，双折线 + 双柱状） ---- */
  _renderYearCurvePanel() {
    const trend = this._trend();
    const { labels, curr, last } = trend;
    const maxValue = Math.max(0.1, ...curr, ...last);
    const viewWidth = 680;
    const viewHeight = 300;
    const padLeft = 42;
    const padRight = 18;
    const padTop = 24;
    const padBottom = 36;
    const plotW = viewWidth - padLeft - padRight;
    const plotH = viewHeight - padTop - padBottom;
    const slotW = plotW / 12;
    const yOf = (v) => padTop + plotH - (v / maxValue) * plotH;
    const centerX = (i) => padLeft + i * slotW + slotW / 2;
    const baseY = padTop + plotH;

    const groupW = slotW * 0.66;
    const barW = groupW / 2 - 2;
    const bars = [];
    for (let i = 0; i < 12; i += 1) {
      const gx = centerX(i) - groupW / 2;
      const lv = last[i];
      if (lv > 0) {
        const h = (lv / maxValue) * plotH;
        bars.push(`<rect x="${gx.toFixed(1)}" y="${(baseY - h).toFixed(1)}" width="${barW.toFixed(1)}" height="${h.toFixed(1)}" rx="1.5" fill="${COLOR_LASTYEAR}" fill-opacity="0.45"/>`);
      }
      const cv = curr[i];
      if (cv > 0) {
        const h = (cv / maxValue) * plotH;
        bars.push(`<rect x="${(gx + barW + 4).toFixed(1)}" y="${(baseY - h).toFixed(1)}" width="${barW.toFixed(1)}" height="${h.toFixed(1)}" rx="1.5" fill="${COLOR_GAS}" fill-opacity="0.6"/>`);
      }
    }

    const lastPts = last.map((v, i) => ({ x: centerX(i), y: yOf(v) }));
    const currPts = curr.map((v, i) => ({ x: centerX(i), y: yOf(v) }));

    const gridLines = [0, 1, 2, 3, 4]
      .map((tick) => {
        const ratio = tick / 4;
        const y = padTop + plotH * ratio;
        return `
          <line x1="${padLeft}" y1="${y}" x2="${padLeft + plotW}" y2="${y}"
                stroke="var(--tws-border)" stroke-width="1" stroke-dasharray="3 4"/>
          <text x="${padLeft - 6}" y="${y + 3}" text-anchor="end" class="axis-text">${volume(maxValue * (1 - ratio), 0)}</text>`;
      })
      .join("");

    const xTicks = labels
      .map((label, i) => `<text x="${centerX(i)}" y="${viewHeight - 14}" text-anchor="middle" class="axis-text">${i % 2 === 0 || i === 11 ? label : ""}</text>`)
      .join("");

    const chartData = JSON.stringify(
      labels.map((label, i) => ({
        x: centerX(i),
        label: `${trend.thisYear}年 ${label}`,
        rows: [
          { c: COLOR_GAS, t: `今年 ${volume(curr[i])} m³` },
          { c: COLOR_LASTYEAR, t: `去年 ${volume(last[i])} m³` },
        ],
      })),
    );

    return `
      <ha-card class="panel-card">
        <div class="panel-head">${icon("chart", 15)} 用气曲线
          <span class="panel-sub">${trend.thisYear} 今年 vs ${trend.lastYear} 去年</span>
        </div>
        <div class="chart-wrap">
          <svg viewBox="0 0 ${viewWidth} ${viewHeight}" width="100%" height="${viewHeight}"
               data-chart="year" data-points='${chartData.replace(/'/g, "&#39;")}'
               data-view-width="${viewWidth}" data-plot-left="${padLeft}" data-plot-width="${plotW}">
            ${gridLines}
            ${xTicks}
            ${bars.join("")}
            <path d="${smoothPath(lastPts)}" fill="none" stroke="${COLOR_LASTYEAR}" stroke-width="2" stroke-dasharray="5 4" stroke-linecap="round"/>
            <path d="${smoothPath(currPts)}" fill="none" stroke="${COLOR_GAS}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
            <line class="chart-cursor" x1="0" y1="${padTop}" x2="0" y2="${baseY}"
                  stroke="${COLOR_AVG}" stroke-width="1" style="opacity:0"/>
          </svg>
          <div class="chart-tooltip" hidden></div>
        </div>
        <div class="chart-legend">
          <span><i style="background:${COLOR_GAS};opacity:.7"></i>今年用气 (柱/线)</span>
          <span><i style="background:${COLOR_LASTYEAR};opacity:.7"></i>去年用气 (柱/线)</span>
        </div>
      </ha-card>`;
  }

  /* ---- 用气明细表格（每月一行） ---- */
  _renderTablePanel() {
    const rows = this._monthly().slice().reverse();
    if (!rows.length) {
      return `<ha-card class="panel-card"><div class="empty">暂无用气明细</div></ha-card>`;
    }
    const body = rows
      .map(
        (r) => `
        <tr>
          <td>${escapeHtml(r.month)}</td>
          <td>${r.readingDate || "--"}</td>
          <td class="num">${volume(r.gas)}</td>
          <td class="num">¥${money(r.money)}</td>
          <td class="num">${r.lastReading !== null ? volume(r.lastReading) : "--"}→${r.currReading !== null ? volume(r.currReading) : "--"}</td>
        </tr>`,
      )
      .join("");

    return `
      <ha-card class="panel-card">
        <div class="panel-head">${icon("list", 15)} 用气明细
          <span class="panel-sub">共 ${rows.length} 条记录</span>
        </div>
        <table class="detail-table">
          <thead><tr><th>月份</th><th>抄表日期</th><th>用气量(m³)</th><th>费用</th><th>读数</th></tr></thead>
          <tbody>${body}</tbody>
        </table>
      </ha-card>`;
  }

  /* ---- 日用气曲线（来自 gas_total 每日统计量，真实逐日消耗） ---- */
  _renderDailyPanel() {
    const price = this._unitPrice();
    const allRows = this._daily();
    const rows = this._filterDaily(allRows);
    const maxDate = allRows.length ? allRows[allRows.length - 1].date : "";
    if (!rows.length) {
      return `<ha-card class="panel-card"><div class="empty">
        暂无每日用气数据。每日数据由累计用气量的统计量表自动生成，需集成运行一段时间（且取决于表具是否上报实时读数）后才有数据。
      </div></ha-card>`;
    }

    const rangeBtns = [
      { key: "week", label: "近一周" },
      { key: "month", label: "近一月" },
      { key: "year", label: "近一年" },
      { key: "custom", label: "自定义" },
    ]
      .map(
        (r) =>
          `<span class="range-btn${this._dailyRange === r.key ? " active" : ""}" data-action="daily-range" data-range="${r.key}">${r.label}</span>`,
      )
      .join("");
    const minDate = allRows[0].date;
    const rangePicker =
      this._dailyRange === "custom"
        ? `<span class="range-date">
            <input type="date" data-custom="start" value="${escapeHtml(this._customStart)}" min="${minDate}" max="${maxDate}" />
            <span class="range-sep">至</span>
            <input type="date" data-custom="end" value="${escapeHtml(this._customEnd)}" min="${minDate}" max="${maxDate}" />
          </span>`
        : "";

    const viewWidth = 680;
    const viewHeight = 240;
    const padLeft = 42;
    const padRight = 18;
    const padTop = 22;
    const padBottom = 34;
    const plotW = viewWidth - padLeft - padRight;
    const plotH = viewHeight - padTop - padBottom;
    const maxValue = Math.max(...rows.map((r) => r.gas), 0.1);
    const step = rows.length > 1 ? plotW / (rows.length - 1) : 0;
    const xOf = (i) => padLeft + i * step;
    const yOf = (v) => padTop + plotH - (v / maxValue) * plotH;

    const points = rows.map((r, i) => ({
      x: xOf(i),
      y: yOf(r.gas),
      label: r.date,
      rows: [
        { c: COLOR_GAS, t: `用气量 ${volume(r.gas)} m³` },
        { c: COLOR_COST, t: `费用 ¥${money(r.gas * price)}` },
      ],
    }));
    const linePts = points.map((p) => ({ x: p.x, y: p.y }));
    const last = linePts[linePts.length - 1];
    const chartData = JSON.stringify(points.map((p) => ({ x: p.x, label: p.label, rows: p.rows })));

    const gridLines = [0, 1, 2, 3, 4]
      .map((tick) => {
        const ratio = tick / 4;
        const y = padTop + plotH * ratio;
        return `
          <line x1="${padLeft}" y1="${y}" x2="${padLeft + plotW}" y2="${y}"
                stroke="var(--tws-border)" stroke-width="1" stroke-dasharray="3 4"/>
          <text x="${padLeft - 6}" y="${y + 3}" text-anchor="end" class="axis-text">${volume(maxValue * (1 - ratio), maxValue < 10 ? 1 : 0)}</text>`;
      })
      .join("");

    // 横轴刻度：按密度抽稀，且避免最后一个刻度与倒数第二个挤在一起
    const tickInterval = Math.max(1, Math.ceil((rows.length - 1) / 8));
    const xTicks = points
      .map((p, i) => {
        const isLast = i === rows.length - 1;
        if (!isLast && rows.length - 1 - i < tickInterval) return "";
        if (!isLast && rows.length > 10 && i % tickInterval !== 0) return "";
        return `<text x="${p.x}" y="${viewHeight - 12}" text-anchor="middle" class="axis-text">${p.label.slice(5)}</text>`;
      })
      .join("");

    return `
      <ha-card class="panel-card">
        <div class="panel-head">${icon("bolt", 15)} 日用气曲线
          <span class="panel-sub">共 ${rows.length} 天 · ${rows[0].date} ~ ${rows[rows.length - 1].date}</span>
        </div>
        <div class="daily-range">
          ${rangeBtns}
          ${rangePicker}
        </div>
        <div class="chart-wrap">
          <svg viewBox="0 0 ${viewWidth} ${viewHeight}" width="100%" height="${viewHeight}"
               data-chart="daily" data-points='${chartData.replace(/'/g, "&#39;")}'
               data-view-width="${viewWidth}" data-plot-left="${padLeft}" data-plot-width="${plotW}">
            <defs>
              <linearGradient id="tws-daily-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="${COLOR_GAS}" stop-opacity="0.3"/>
                <stop offset="100%" stop-color="${COLOR_GAS}" stop-opacity="0.02"/>
              </linearGradient>
            </defs>
            ${gridLines}
            ${xTicks}
            <path d="${smoothPath(linePts)} L ${last.x} ${padTop + plotH} L ${linePts[0].x} ${padTop + plotH} Z"
                  fill="url(#tws-daily-fill)" stroke="none"/>
            <path d="${smoothPath(linePts)}" fill="none" stroke="${COLOR_GAS}" stroke-width="2.2"
                  stroke-linecap="round" stroke-linejoin="round"/>
            <line class="chart-cursor" x1="0" y1="${padTop}" x2="0" y2="${padTop + plotH}"
                  stroke="${COLOR_AVG}" stroke-width="1" style="opacity:0"/>
          </svg>
          <div class="chart-tooltip" hidden></div>
        </div>
        <div class="chart-legend">
          <span><i style="background:${COLOR_GAS}"></i>每日用气量 (m³)</span>
          <span><i style="background:${COLOR_COST};opacity:.5"></i>费用估算 (元)</span>
        </div>
        <div class="precision-hint">※ ${PRECISION_HINT}</div>
      </ha-card>`;
  }
}

/* ============================================================================
 * 可视化配置编辑器
 * ========================================================================== */
const EDITOR_SCHEMA = [
  { name: "gs", label: "户号（留空自动探测）", selector: { text: {} } },
  { name: "title", label: "卡片标题", selector: { text: {} } },
  {
    name: "price",
    label: "气价单价（元/m³，留空读当前阶梯气价）",
    selector: { number: { min: 0, max: 20, step: 0.01, mode: "box" } },
  },
  {
    name: "default_panel",
    label: "默认展开面板",
    selector: {
      select: {
        mode: "dropdown",
        options: [
          { value: "", label: "都不展开" },
          { value: "calendar", label: "用气日历" },
          { value: "yearCurve", label: "用气曲线" },
          { value: "table", label: "用气明细" },
          { value: "daily", label: "日用气曲线" },
        ],
      },
    },
  },
];

class TongwangasShandongGasCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = {};
  }

  setConfig(config) {
    this._config = config || {};
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._form) {
      this._form.hass = hass;
    } else {
      this._render();
    }
  }

  _valueChanged(value) {
    const config = { ...this._config };
    config.gs = value.gs || "";
    config.title = value.title || "";
    config.default_panel = value.default_panel || "";
    if (num(value.price, null) !== null) config.price = num(value.price, null);
    else delete config.price;
    this._config = config;
    this.dispatchEvent(
      new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }),
    );
  }

  _render() {
    const data = {
      gs: this._config.gs || "",
      title: this._config.title || "",
      default_panel: this._config.default_panel || "",
      price: this._config.price ?? "",
    };
    if (customElements.get("ha-form")) {
      const form = document.createElement("ha-form");
      form.hass = this._hass;
      form.data = data;
      form.schema = EDITOR_SCHEMA;
      form.computeLabel = (schema) => schema.label || schema.name;
      form.addEventListener("value-changed", (event) => this._valueChanged(event.detail.value));
      this._form = form;
      this.shadowRoot.innerHTML = `<div class="editor"></div>`;
      this.shadowRoot.querySelector(".editor").appendChild(form);
      return;
    }

    // 无 HA 前端（如本地预览页）时的降级编辑器
    this._form = null;
    const fields = [
      ["gs", "户号", "text"],
      ["title", "卡片标题", "text"],
      ["price", "单价(元/m³)", "number"],
    ];
    const html = fields
      .map(
        ([name, label, type]) => `
        <label class="row">
          <span>${label}</span>
          <input class="${type}" data-field="${name}" value="${
            data[name] === undefined || data[name] === null ? "" : escapeHtml(data[name])
          }"/>
        </label>`,
      )
      .join("");
    this.shadowRoot.innerHTML = `
      <style>
        .editor { padding: 8px 0; font-family: var(--paper-font-body1_-_font-family, sans-serif); }
        .row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 4px 0; }
        .row span { font-size: 13px; color: var(--primary-text-color, #333); }
        input { flex: 0 0 130px; padding: 4px 6px; font-size: 13px; }
      </style>
      <div class="editor">${html}</div>`;
    this.shadowRoot.querySelectorAll("input").forEach((input) => {
      input.addEventListener("change", () => {
        const values = {};
        this.shadowRoot.querySelectorAll("input").forEach((item) => {
          values[item.dataset.field] = item.value;
        });
        this._valueChanged(values);
      });
    });
  }
}

/* ============================================================================
 * 样式
 * ========================================================================== */
const STYLES = `
  :host { display: block; --tws-border: #e6e8eb; }
  * { box-sizing: border-box; }
  .ico { vertical-align: -2px; }

  ha-card {
    background: var(--ha-card-background, var(--card-background-color, #fff));
    color: var(--primary-text-color, #1c1c1e);
    border-radius: var(--ha-card-border-radius, 12px);
  }
  .main-card { padding: 12px 12px 10px; }
  .panel-card { padding: 12px; margin-top: 10px; }
  .empty { padding: 18px; text-align: center; color: var(--secondary-text-color, #8a8a8e); font-size: 13px; line-height: 1.6; }

  .card-title-row { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 10px; }
  .card-title { font-size: 14px; font-weight: 600; display: inline-flex; align-items: center; gap: 5px; color: ${COLOR_GAS}; }
  .card-meta { font-size: 11px; line-height: 1.45; color: var(--secondary-text-color, #8a8a8e); text-align: right; }

  .metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
  .metric { background: var(--secondary-background-color, rgba(0,0,0,0.04)); border-radius: 10px; padding: 9px 10px; min-width: 0; }
  .metric-label { font-size: 11.5px; color: var(--secondary-text-color, #8a8a8e); display: flex; align-items: center; gap: 4px; }
  .metric-value { font-size: 19px; font-weight: 700; margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .metric-value .cur { font-size: 11px; margin-right: 1px; font-weight: 500; }
  .metric-value small { font-size: 11px; font-weight: 500; color: var(--secondary-text-color, #8a8a8e); }
  .metric.warn .metric-value { color: ${COLOR_WARN}; }

  .usage-card { margin-top: 10px; border-radius: 12px; padding: 10px 12px; border: 1px solid var(--tws-border); background: var(--ha-card-background, #fff); }
  .section-head { font-size: 12.5px; font-weight: 600; display: flex; align-items: center; gap: 5px; color: var(--primary-text-color, #1c1c1e); }
  .usage-body { display: flex; align-items: center; gap: 10px; margin-top: 6px; }
  .usage-left { flex: 1 1 40%; min-width: 0; }
  .usage-label { font-size: 10.5px; color: var(--secondary-text-color, #8a8a8e); margin-bottom: 1px; }
  .usage-label + .usage-value, .usage-label + .usage-cost { margin-top: 0; }
  .usage-value { font-size: 24px; font-weight: 700; line-height: 1.15; margin-top: 1px; }
  .usage-value small { font-size: 12px; font-weight: 500; color: var(--secondary-text-color, #8a8a8e); }
  .usage-cost { font-size: 14px; font-weight: 600; margin-top: 2px; color: ${COLOR_COST}; }
  .usage-sub { font-size: 10.5px; font-weight: 500; color: var(--secondary-text-color, #8a8a8e); margin-left: 4px; }
  .usage-delta { font-size: 11.5px; font-weight: 700; margin-top: 4px; display: inline-flex; align-items: center; gap: 3px; }
  .usage-delta.up { color: #d9534f; }
  .usage-delta.down { color: #2e9e5b; }
  .usage-delta.muted { color: var(--secondary-text-color, #8a8a8e); font-weight: 500; }
  .section-sub { margin-left: auto; font-size: 11px; font-weight: 500; color: var(--secondary-text-color, #8a8a8e); }
  .usage-spark { flex: 1 1 60%; cursor: pointer; position: relative; }
  .spark-empty { font-size: 11px; color: var(--secondary-text-color, #8a8a8e); text-align: center; padding: 20px 0; }

  .ladder-block { margin-top: 12px; }
  .ladder-value { margin-left: auto; font-size: 11px; font-weight: 400; color: var(--secondary-text-color, #8a8a8e); white-space: nowrap; }
  .ladder-strong { font-weight: 700; color: var(--primary-text-color, #1c1c1e); }
  .ladder-band { position: relative; display: grid; grid-template-columns: repeat(3, 1fr); margin-top: 8px; }
  .ladder-tier { position: relative; height: 32px; overflow: hidden; display: flex; align-items: center; justify-content: center; }
  .ladder-tier:first-child { border-top-left-radius: 7px; border-bottom-left-radius: 7px; }
  .ladder-tier:last-child { border-top-right-radius: 7px; border-bottom-right-radius: 7px; }
  .ladder-tier.t1 { background: #fbe6d6; }
  .ladder-tier.t2 { background: #f6d9c4; }
  .ladder-tier.t3 { background: #f1cdb4; }
  .ladder-tier-fill { position: absolute; left: 0; top: 0; bottom: 0; width: 0; transition: width .35s ease; }
  .ladder-tier.t1 .ladder-tier-fill { background: #e8772e; }
  .ladder-tier.t2 .ladder-tier-fill { background: #d85f1c; }
  .ladder-tier.t3 .ladder-tier-fill { background: #b94a12; }
  .ladder-tier.active { outline: 2px solid ${COLOR_GAS}; outline-offset: -2px; }
  .ladder-tier-name { position: relative; z-index: 1; font-size: 11.5px; font-weight: 700; color: #5a2c0c; }
  .ladder-bolt { position: absolute; top: 50%; transform: translate(-50%, -50%); z-index: 2; color: #7a3308; display: flex; pointer-events: none; filter: drop-shadow(0 0 2px rgba(255,255,255,.95)); transition: left .35s ease; }
  .ladder-ranges { display: grid; grid-template-columns: repeat(3, 1fr); margin-top: 4px; }
  .ladder-range { text-align: center; font-size: 10.5px; padding: 4px 0; font-weight: 600; }
  .ladder-range.t1 { background: #fdeede; color: #b5531a; border-radius: 6px 0 0 6px; }
  .ladder-range.t2 { background: #fbe2d2; color: #a9480f; }
  .ladder-range.t3 { background: #f6d3bd; color: #93390a; border-radius: 0 6px 6px 0; }
  .lr-range { font-weight: 700; }
  .lr-price { font-weight: 500; opacity: .85; }

  .actions { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-top: 12px; }
  .action { display: flex; align-items: center; justify-content: center; gap: 4px; height: 38px; border-radius: 8px; cursor: pointer; font-size: 12px; font-weight: 500; background: var(--secondary-background-color, rgba(0,0,0,0.04)); border: 1px solid transparent; transition: all .18s ease; user-select: none; }
  .action:hover { border-color: ${COLOR_GAS}; }
  .action.active { background: #fbe6d6; border-color: ${COLOR_GAS}; color: #b5531a; font-weight: 700; }

  .panel-head { display: flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 600; margin-bottom: 8px; }
  .panel-sub { margin-left: auto; font-size: 11px; font-weight: 500; color: var(--secondary-text-color, #8a8a8e); }

  .cal-nav { display: grid; grid-template-columns: 26px 1fr 26px 54px 26px 1fr 26px; align-items: center; gap: 2px; }
  .cal-title { text-align: center; font-size: 13px; font-weight: 600; }
  .nav-btn { display: flex; align-items: center; justify-content: center; height: 26px; border-radius: 6px; cursor: pointer; color: var(--secondary-text-color, #6b7280); user-select: none; }
  .nav-btn:hover { background: var(--secondary-background-color, rgba(0,0,0,0.06)); }
  .today-btn { font-size: 11.5px; }
  .cal-week, .cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 3px; }
  .cal-week { margin: 8px 0 4px; }
  .cal-week span { text-align: center; font-size: 11px; color: var(--secondary-text-color, #8a8a8e); }
  .cal-cell { min-height: 52px; border-radius: 7px; padding: 4px 2px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 1px; background: transparent; }
  .cal-cell.empty { background: transparent; }
  .cal-cell.has-data { background: #fbeede; }
  .cal-cell.has-data.lv2 { background: #f6c79a; }
  .cal-cell.has-data.lv3 { background: ${COLOR_GAS}; }
  .cal-cell.has-data.lv3 .cal-day,
  .cal-cell.has-data.lv3 .cal-usage,
  .cal-cell.has-data.lv3 .cal-cost { color: #fff; }
  .cal-day { font-size: 13.5px; font-weight: 600; }
  .cal-usage { font-size: 10px; color: ${COLOR_GAS}; }
  .cal-cost { font-size: 10px; color: ${COLOR_COST}; }
  .cal-usage.placeholder, .cal-cost.placeholder { visibility: hidden; }
  .cal-cell.today { outline: 2px solid ${COLOR_GAS}; outline-offset: -2px; }
  .cal-footer { margin-top: 8px; font-size: 11.5px; color: var(--secondary-text-color, #6b7280); display: flex; flex-wrap: wrap; gap: 6px; }
  .cal-note { opacity: .8; }
  .cal-legend { width: 100%; display: flex; align-items: center; gap: 6px; margin-top: 4px; font-size: 11px; color: var(--secondary-text-color, #8a8a8e); }
  .cal-legend .lg { width: 11px; height: 11px; border-radius: 3px; display: inline-block; margin-left: 8px; }
  .cal-legend .lg.lv1 { background: #fbeede; border: 1px solid #f0d8c0; }
  .cal-legend .lg.lv2 { background: #f6c79a; }
  .cal-legend .lg.lv3 { background: ${COLOR_GAS}; }

  .chart-wrap { position: relative; }
  .axis-text { font-size: 10px; fill: var(--secondary-text-color, #8a8a8e); }
  .chart-tooltip { position: absolute; z-index: 5; pointer-events: none; background: rgba(255,255,255,0.97); color: #1c1c1e; border: 1px solid var(--tws-border); border-radius: 8px; padding: 6px 8px; box-shadow: 0 4px 14px rgba(0,0,0,.12); font-size: 11px; line-height: 1.5; min-width: 108px; }
  .tt-date { font-weight: 600; margin-bottom: 2px; }
  .tt-row { display: flex; align-items: center; gap: 4px; white-space: nowrap; }
  .tt-dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
  .chart-legend { display: flex; justify-content: center; gap: 12px; margin-top: 6px; font-size: 11px; color: var(--secondary-text-color, #6b7280); flex-wrap: wrap; }
  .chart-legend i { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 4px; }
  .precision-hint { margin-top: 6px; font-size: 10.5px; line-height: 1.45; color: var(--secondary-text-color, #9a9a9e); opacity: .85; }
  .precision-hint.cal-hint { width: 100%; margin-top: 2px; }

  .daily-range { display: flex; align-items: center; gap: 6px; margin-bottom: 8px; flex-wrap: wrap; }
  .range-btn { font-size: 11.5px; padding: 3px 11px; border-radius: 14px; cursor: pointer; user-select: none; background: var(--secondary-background-color, rgba(0,0,0,0.04)); color: var(--secondary-text-color, #6b7280); border: 1px solid transparent; transition: all .15s ease; }
  .range-btn:hover { border-color: ${COLOR_GAS}; color: #b5531a; }
  .range-btn.active { background: #fbe6d6; border-color: ${COLOR_GAS}; color: #b5531a; font-weight: 700; }
  .range-date { display: inline-flex; align-items: center; gap: 4px; margin-left: 2px; }
  .range-date input[type="date"] { font-size: 11.5px; padding: 2px 4px; border: 1px solid var(--tws-border); border-radius: 6px; background: var(--ha-card-background, #fff); color: var(--primary-text-color, #1c1c1e); }
  .range-sep { font-size: 11px; color: var(--secondary-text-color, #8a8a8e); }

  .detail-table { width: 100%; border-collapse: collapse; font-size: 12px; }
  .detail-table th, .detail-table td { padding: 6px 4px; text-align: left; }
  .detail-table th { color: var(--secondary-text-color, #8a8a8e); font-weight: 500; border-bottom: 1px solid var(--tws-border); }
  .detail-table th:not(:first-child), .detail-table td.num { text-align: right; }
  .detail-table tbody tr + tr td { border-top: 1px solid rgba(0,0,0,0.04); }

  @media (max-width: 420px) {
    .metric-value { font-size: 16px; }
    .usage-value { font-size: 21px; }
    .action { font-size: 11px; }
  }
`;

/* ============================================================================
 * 注册
 * ========================================================================== */
if (!customElements.get("tongwangas-shandong-card")) {
  customElements.define("tongwangas-shandong-card", TongwangasShandongCard);
}
if (!customElements.get("tongwangas-shandong-card-editor")) {
  customElements.define("tongwangas-shandong-card-editor", TongwangasShandongGasCardEditor);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "tongwangas-shandong-card")) {
  window.customCards.push({
    type: "tongwangas-shandong-card",
    name: "港华燃气用气卡片",
    description: "可用余额/应缴费用/累计用气量、用气曲线、用气阶梯、用气日历与用气明细",
    preview: true,
    documentationURL: "",
  });
}

console.info(
  `%c港华燃气%c tongwangas-shandong-card %cv${CARD_VERSION} %c已就绪`,
  "background:#e8772e;color:#fff;padding:4px 10px;border-radius:6px;font-weight:600;",
  "background:rgba(232,119,46,.15);color:#b5531a;padding:4px 8px;border-radius:6px;margin-left:6px;",
  "background:rgba(232,119,46,.15);color:#b5531a;padding:4px 8px;border-radius:6px;margin-left:6px;",
  "color:#4caf50;margin-left:6px;",
);
