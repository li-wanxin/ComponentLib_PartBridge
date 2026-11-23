/* ComponentLib 物料入库台 —— 前端逻辑（对接 /api/*） */
"use strict";

const $ = id => document.getElementById(id);
let STATE = {
  tables: [], curTable: null, rows: [], cols: [],
  settings: {}, dbPath: "", libRoot: "", fieldInputs: {},
  detailRow: null, editing: false, editValues: {}, dlCache: {},
  lastDatasheet: "", pickedFile: "", lastSN: null, model3d: null, m3dPending: false,
  sn: "", libgenPending: { sch: false, pcb: false }, updChecked: false,
};

/* ================= 工具 ================= */
async function api(path, body) {
  const opt = body
    ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
    : {};
  const r = await fetch(path, opt);
  const j = await r.json();
  if (!j.ok) throw new Error(j.error || "请求失败");
  return j;
}
const esc = s => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const sqlEsc = s => "'" + String(s ?? "").replace(/'/g, "''") + "'";

let toastTimer = null;
function toast(msg, err) {
  const t = $("toast");
  t.textContent = msg;
  t.className = "toast show" + (err ? " err" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 3000);
}

const FIELD_DESC = {
  "Part Number": "内部编码", "Component Type": "器件型号", "Vendor": "生产商",
  "Value": "值", "Tolerance": "精度", "Type": "器件具体类别", "Description": "描述",
  "Suppiler": "供应商", "Suppiler Number": "供应商编码",
  "Library Ref": "器件SCH封装名称", "Library Path": "器件SCH库路径",
  "Footprint Ref": "器件PCB封装名称", "Footprint Path": "器件PCB库路径",
  "PCB3D Ref": "器件3D封装名称", "PCB3D Path": "器件3D库路径",
  "Schematic_Part": "Cadence原理图", "PCB_Footprint": "Cadence封装",
  "ComponentLink2Description": "默认DataSheet", "ComponentLink2URL": "参考文件路径",
  "LatestRevisionDate": "修改日期",
};
const GRID_SHOW_COLS = ["Type", "Part Number", "Component Type", "Vendor", "Value", "Tolerance", "Description"];
const REQUIRED_KEYS = ["Component Type"];
const MODEL_KEYS = ["Library Ref", "Library Path", "Footprint Ref", "Footprint Path", "PCB3D Ref", "PCB3D Path", "Schematic_Part", "PCB_Footprint"];
const AUTOFILL_KEYS = ["Component Type", "Vendor", "Value", "Tolerance", "Type", "Description", "Suppiler", "ComponentLink2Description", "ComponentLink2URL"];
const TABLE_GROUPS = [
  ["电阻", t => t.startsWith("Resistors")],
  ["电容", t => t.startsWith("Capacitors")],
  ["IC", t => t.startsWith("ICs")],
  ["二极管/三极管/LED", t => t.startsWith("Diodes") || t.startsWith("Transistors") || t.startsWith("LED")],
  ["连接器", t => t.startsWith("Connectors")],
  ["电源时钟", t => t.startsWith("Oscillators")],
  ["模组", t => t.startsWith("Modules")],
  ["其他", () => true],
];

/* ================= 启动 ================= */
async function boot() {
  applyThemeColor(STATE.settings.dark);
  bindEvents();
  await reloadDb();
}

async function reloadDb() {
  try {
    const j = await api("/api/bootstrap");
    STATE.tables = j.tables; STATE.dbPath = j.db_path; STATE.libRoot = j.lib_root;
    STATE.settings = j.settings;
    STATE.version = j.version || "?";
    const sl = $("updStatusLine");
    if (sl.textContent.startsWith("当前版本 v?")) {
      sl.textContent = `当前版本 v${STATE.version}　｜　尚未检查更新`;
    }
    renderDbInfo(j);
    renderTableList();
    const first = j.tables.find(t => t.count > 0) || j.tables[0];
    if (first) selectTable(first.name);
    $("dbPill").className = "pill " + (j.loaded ? "on" : "err");
    $("dbPillText").textContent = j.loaded ? shorten(j.db_path, 44) : "数据库 未连接";
  } catch (e) {
    $("dbPill").className = "pill err";
    $("dbPillText").textContent = "服务异常";
    toast(e.message, true);
  }
}

function shorten(p, n) {
  p = String(p || "");
  if (p.length <= n) return p;
  return p.slice(0, 16) + "…" + p.slice(-(n - 18));
}

function renderDbInfo(j) {
  const total = j.total;
  $("navTotal").textContent = `${j.tables.length} 张表 · ${total} 条`;
  $("sideDbPath").textContent = shorten(j.db_path, 40) || "—";
  $("sideDbCount").textContent = `${j.tables.length} 张表 · ${total} 条`;
  // 表下拉
  const sel = $("tableSelect");
  sel.innerHTML = "";
  TABLE_GROUPS.forEach(([g, fn]) => {
    const items = j.tables.filter(t => fn(t.name) && !["其他"].includes(g) || (g === "其他" && !TABLE_GROUPS.slice(0, -1).some(([_, f2]) => f2(t.name))));
    if (!items.length && g !== "其他") return;
    const og = document.createElement("optgroup"); og.label = g;
    items.forEach(t => {
      const o = document.createElement("option"); o.value = t.name; o.textContent = t.name;
      og.appendChild(o);
    });
    if (og.children.length) sel.appendChild(og);
  });
  // 设置页
  $("dbPathInput").value = j.db_path;
  $("libRootHint").textContent = "库根目录（模型路径建议用）= " + (j.lib_root || "—");
  $("autoLoadChk").checked = j.settings.auto_load !== false;
  $("backupChk").checked = j.settings.backup_write !== false;
}

function renderTableList() {
  const el = $("tableList");
  el.innerHTML = "";
  TABLE_GROUPS.forEach(([g, fn]) => {
    const items = STATE.tables.filter(t => fn(t.name));
    if (!items.length) return;
    if (g === "其他" && TABLE_GROUPS.slice(0, -1).some(([_, f2]) => STATE.tables.every(t => f2(t.name)))) return;
    const gl = document.createElement("div"); gl.className = "tgrp"; gl.textContent = g;
    el.appendChild(gl);
    items.forEach(t => {
      const it = document.createElement("div");
      it.className = "titem" + (t.name === STATE.curTable ? " sel" : "");
      it.innerHTML = `<span>▤</span><span style="flex:1;overflow:hidden;text-overflow:ellipsis">${esc(t.name)}</span>` +
        (t.count > 0 ? `<span class="cnt">${t.count}</span>` : "");
      it.onclick = () => selectTable(t.name);
      el.appendChild(it);
    });
  });
}

/* ================= 浏览 ================= */
async function selectTable(name) {
  STATE.curTable = name;
  renderTableList();
  STATE.detailRow = null; STATE.editing = false;   // 换表清空详情/退出编辑
  renderDetail();
  try {
    const j = await api("/api/table?name=" + encodeURIComponent(name) + "&q=" + encodeURIComponent($("gridSearch").value || ""));
    STATE.cols = j.columns; STATE.rows = j.rows;
    renderGrid();
  } catch (e) { toast(e.message, true); }
}

function visibleRows() {
  const q = ($("gridSearch").value || "").toLowerCase();
  let rows = STATE.rows;
  if (q) rows = rows.filter(r => Object.values(r).some(v => String(v ?? "").toLowerCase().includes(q)));
  // 按器件具体类别排前：类别 → 型号 → 内部编码，同类聚簇
  return [...rows].sort((a, b) =>
    String(a["Type"] || "").localeCompare(String(b["Type"] || ""), "zh") ||
    String(a["Component Type"] || "").localeCompare(String(b["Component Type"] || ""), "en") ||
    String(a["Part Number"] || "").localeCompare(String(b["Part Number"] || ""), "en"));
}

function renderGrid() {
  // 关键：按 GRID_SHOW_COLS 声明顺序输出（此前用 STATE.cols.filter 保留的是 DB 列序，导致调序无效）
  const cols = GRID_SHOW_COLS.filter(c => STATE.cols.includes(c));
  const rows = visibleRows();
  const thead = cols.map(c =>
    `<th>${esc(c)}<span class="zh">${esc(FIELD_DESC[c] || "")}</span></th>`).join("");
  let html = `<thead><tr>${thead}</tr></thead><tbody>`;
  if (!rows.length) {
    html += `<tr><td colspan="${cols.length}" style="text-align:center;color:var(--dim-2);padding:30px">该表暂无记录</td></tr>`;
  }
  rows.forEach(r => {
    html += `<tr data-pn="${esc(r["Part Number"] || "")}">` + cols.map(c => {
      const v = String(r[c] ?? "");
      const cls = (c === "Part Number" || c === "Component Type") ? "mono-pn" : "";
      return `<td class="${cls}" title="${esc(v)}">${esc(v)}</td>`;
    }).join("") + `</tr>`;
  });
  html += "</tbody>";
  const grid = $("grid");
  grid.innerHTML = html;
  grid.querySelectorAll("tbody tr").forEach((tr, i) => {
    tr.onclick = () => showDetail(rows[i], tr);
  });
}

function showDetail(row, tr) {
  $("grid").querySelectorAll("tr.sel").forEach(x => x.classList.remove("sel"));
  if (tr) tr.classList.add("sel");
  STATE.detailRow = { ...row };   // 旧行快照，编辑定位用
  STATE.detailTr = tr || null;
  STATE.editing = false;
  renderDetail();
  loadLibCheck(STATE.detailRow);  // 库文件核对（异步，写入 #libCheckBox）
}

/* 库文件核对：封装引用在 SchLib/PcbLib/OLB/dra+psm 中的真实存在性 */
const LIBCHECK_STATUS = {
  ok:      { cls: "ok",   mark: "✓", tail: "" },
  missing: { cls: "bad",  mark: "✗", tail: "" },
  nofile:  { cls: "warn", mark: "△", tail: "（库文件缺失）" },
  nodata:  { cls: "",     mark: "△", tail: "（字段未填）" },
};

async function loadLibCheck(row) {
  const box = $("libCheckBox");
  if (!box) return;
  try {
    const j = await api("/api/libcheck", { table: STATE.curTable, data: row });
    if (!box.isConnected) return;              // 渲染期间详情已切换
    if (!j.items || !j.items.length) {
      box.innerHTML = `<div class="comp-head"><span class="comp-label">库文件核对</span>
        <span class="comp-pct">无可核对的模型字段</span></div>`;
      return;
    }
    box.innerHTML = `<div class="comp-head"><span class="comp-label">库文件核对</span>
        <span class="comp-pct">${j.items.filter(i => i.status === "ok").length}/${j.items.length} 通过</span></div>
      <ul class="checklist">` +
      j.items.map(it => {
        const s = LIBCHECK_STATUS[it.status] || LIBCHECK_STATUS.nodata;
        const d = it.detail ? ` — ${esc(it.detail)}` : "";
        return `<li class="${s.cls}">${s.mark} ${esc(it.label)}：${d}${s.tail}</li>`;
      }).join("") + `</ul>`;
  } catch (e) {
    if (box.isConnected) box.innerHTML =
      `<div class="comp-head"><span class="comp-label">库文件核对</span>
       <span class="comp-pct">核对失败：${esc(e.message)}</span></div>`;
  }
}

/* 详情面板：只读 / 编辑 双态渲染 */
const EDIT_DATALIST_COLS = ["Type", "Vendor", "Tolerance", "Value", "Suppiler",
  "Library Ref", "Footprint Ref", "PCB3D Ref"];  // 带同表已有值下拉的参数列

/* 已有记录的检测结果（记录详情只读态下方展示）：
   信息完整度 + 分条检查（必填项 / 模型字段 / 规格书；重复检查不适用于库内记录） */
function buildRecordCheckHtml(row, cols) {
  const get = c => String(row[c] ?? "").trim();
  const statCols = (cols || []).filter(c => c !== "LatestRevisionDate");
  if (!statCols.length) return "";
  const filled = statCols.filter(c => get(c)).length;
  const pct = Math.round(filled / statCols.length * 100);
  const tone = pct >= 80 ? "hi" : pct >= 40 ? "mid" : "low";
  const items = [];
  if (statCols.includes("Component Type")) {
    items.push(get("Component Type")
      ? '<li class="ok">✓ 必填项齐全（器件型号）</li>'
      : '<li class="bad">✗ 缺少必填项：器件型号（历史遗留数据）</li>');
  }
  const modelCols = ["Library Ref", "Library Path", "Footprint Ref", "Footprint Path",
                     "PCB3D Ref", "PCB3D Path"].filter(c => statCols.includes(c));
  if (modelCols.length) {
    const missModel = modelCols.filter(c => !get(c));
    items.push(missModel.length
      ? `<li class="warn">△ 模型字段缺 ${missModel.length}/${modelCols.length} 项：${esc(missModel.join("、"))}</li>`
      : `<li class="ok">✓ 模型字段完整（SCH/PCB/3D 共 ${modelCols.length} 项）</li>`);
  }
  if (statCols.includes("ComponentLink2URL")) {
    const ds = get("ComponentLink2URL");
    items.push((ds && ds !== "无可下载规格书")
      ? '<li class="ok">✓ 规格书路径已指定</li>'
      : '<li class="warn">△ 规格书未指定</li>');
  }
  return `<div class="rec-check">
    <div class="completeness">
      <div class="comp-head">
        <span class="comp-label">信息完整度</span>
        <span class="comp-pct">${pct}%（${filled}/${statCols.length} 字段）</span>
      </div>
      <div class="comp-bar"><div class="comp-fill ${tone}" style="width:${pct}%"></div></div>
    </div>
    <ul class="checklist">${items.join("")}</ul>
  </div>`;
}

function renderDetail() {
  const el = $("detailPanel");
  // 清理上一次挂到 body 顶层的弹层（重渲染后 innerHTML 里的引用已换新）
  document.querySelectorAll("body > .dt-dd").forEach(d => d.remove());
  const row = STATE.detailRow;
  if (!row) {
    el.innerHTML = `<div class="detail-title">📋 记录详情</div>
      <div class="detail-empty">点击表格行<br>查看该物料的全部字段</div>`;
    return;
  }
  const table = esc(STATE.curTable);
  let html;
  if (STATE.editing) {
    html = `<div class="detail-title"><span>✏️ ${table} · 编辑记录</span>
      <span class="dt-btns">
        <button class="ghost tiny" onclick="cancelEdit()">✕ 取消</button>
        <button class="primary tiny" onclick="finishEdit()">✔ 完成</button>
      </span></div><table class="detail-table">`;
    html += renderFieldRows(c => {
      if (c === "LatestRevisionDate") {
        // 修改日期不手动输入：更新时后端自动写当天
        return `<span style="color:var(--dim-2)">（自动更新为当天）</span>`;
      }
      const v = String(STATE.editValues[c] ?? "");
      const idKey = c.replace(/\s/g, "_");
      if (EDIT_DATALIST_COLS.includes(c)) {
        // 自定义下拉（替代原生 datalist：原生会按输入值过滤选项，且弹层尺寸不可控）
        return `<div class="dt-combo">` +
          `<input class="dt-input" id="dt-${esc(idKey)}" value="${esc(v)}" autocomplete="off">` +
          `<button class="dt-arrow" data-col="${esc(idKey)}" title="展开该表全部已有值">▾</button>` +
          `<div class="dt-dd hidden" id="dd-${esc(idKey)}"></div></div>`;
      }
      return `<input class="dt-input" id="dt-${esc(idKey)}" value="${esc(v)}" autocomplete="off">`;
    });
    html += "</table>";
  } else {
    html = `<div class="detail-title"><span>📋 ${table} · 记录详情</span>
      <span class="dt-btns"><button class="ghost tiny" onclick="startEdit()">✎ 修改</button></span></div>
      <table class="detail-table">`;
    html += renderFieldRows(c => esc(String(row[c] ?? "")) || "—");
    html += "</table>";
    // 检测结果：与添加物料页同款（信息完整度 + 分条检查），仅只读态展示
    html += buildRecordCheckHtml(row, STATE.cols);
    // 库文件核对：封装引用是否真实存在于 SchLib/PcbLib/OLB/dra+psm
    html += `<div class="rec-check" id="libCheckBox">
      <div class="comp-head"><span class="comp-label">库文件核对</span>
      <span class="comp-pct">核对中…</span></div></div>`;
  }
  if (STATE.editing) {
    html += `<div class="hint" style="margin-top:8px">点 ▾ 展开该表全部已有值供选择；也可直接输入新值。✔ 完成后确认更新 DB，修改日期由系统自动更新为当天。</div>`;
  }
  el.innerHTML = html;
  if (STATE.editing) bindDetailCombo();
}

async function startEdit() {
  if (!STATE.detailRow) return;
  // 并行取各参数列的同表已有值（供下拉选择）
  const dl = {};
  try {
    await Promise.all(EDIT_DATALIST_COLS.map(async c => {
      try {
        const j = await api("/api/distinct?table=" + encodeURIComponent(STATE.curTable) +
          "&column=" + encodeURIComponent(c));
        dl[c] = j.values || [];
      } catch (e) { dl[c] = []; }
    }));
  } catch (e) { /* 忽略，仍可手动输入 */ }
  STATE.dlCache = dl;
  STATE.editing = true;
  STATE.editValues = { ...STATE.detailRow };
  renderDetail();
}

/* ---- 详情编辑态：自定义下拉（点 ▾ 展开全部已有值，输入时过滤） ---- */
function bindDetailCombo() {
  EDIT_DATALIST_COLS.forEach(c => {
    const idKey = c.replace(/\s/g, "_");
    const inp = $("dt-" + idKey);
    const arrow = document.querySelector(`.dt-arrow[data-col="${idKey}"]`);
    const dd = $("dd-" + idKey);
    if (!inp || !arrow || !dd) return;
    arrow.onclick = e => { e.stopPropagation(); openDd(c, dd, inp, true); };
    inp.onfocus = () => openDd(c, dd, inp, false);
    inp.oninput = () => openDd(c, dd, inp, false);
    dd.onclick = e => e.stopPropagation();   // 滚动列表时不关闭
  });
}

function openDd(col, dd, inp, showAll) {
  closeAllDd();
  // 关键：弹层挂到 body 顶层按输入框坐标 fixed 定位。
  // 若留在表格单元格内，border-collapse 表格会把下方行绘制在弹层之上（混叠的根源）。
  const r = inp.getBoundingClientRect();
  dd.style.position = "fixed";
  dd.style.top = (r.bottom + 3) + "px";
  dd.style.left = r.left + "px";
  dd.style.width = r.width + "px";
  document.body.appendChild(dd);
  const vals = (STATE.dlCache || {})[col] || [];
  const q = showAll ? "" : inp.value.trim().toLowerCase();
  const items = q ? vals.filter(v => String(v).toLowerCase().includes(q)) : vals;
  dd.innerHTML = items.length
    ? items.map(v => `<div class="dt-opt">${esc(v)}</div>`).join("")
    : `<div class="dt-none">无匹配 —— 直接输入新值即可</div>`;
  dd.querySelectorAll(".dt-opt").forEach((el, i) => {
    // 用 mousedown 而非 click：mousedown 先于焦点变化触发，
    // 规避 WebView2 下点击选项后输入框重新获得焦点导致弹层复开的时序问题
    el.onmousedown = e => {
      e.preventDefault();       // 不让焦点离开输入框
      e.stopPropagation();
      inp.value = items[i];
      closeAllDd();
    };
  });
  dd.classList.remove("hidden");
}
function closeAllDd(except) {
  document.querySelectorAll(".dt-dd").forEach(d => {
    if (d !== except) d.classList.add("hidden");
  });
}

function cancelEdit() {
  STATE.editing = false;
  renderDetail();
}

function collectEditValues() {
  const o = {};
  STATE.cols.forEach(c => {
    const inp = $("dt-" + c.replace(/\s/g, "_"));
    o[c] = inp ? inp.value.trim() : String(STATE.editValues[c] ?? "");
  });
  return o;
}

function buildDiffTable(cols, data, old) {
  /* 确认弹窗用：字段 | 原数据库值 | 修改后（变更标红） */
  const changed = cols.filter(c => String(data[c] ?? "") !== String(old[c] ?? ""));
  if (!changed.length) return `<div class="hint" style="text-align:center;padding:14px">无任何改动</div>`;
  let h = `<table class="diff-table"><thead><tr>` +
    `<th>字段</th><th>原数据库数据</th><th>修改后</th></tr></thead><tbody>`;
  changed.forEach(c => {
    h += `<tr><td class="dk2">${esc(c)}<span class="zh">${esc(FIELD_DESC[c] || "")}</span></td>` +
      `<td class="old">${esc(String(old[c] ?? "")) || "—"}</td>` +
      `<td class="new">${esc(String(data[c] ?? "")) || "—"}</td></tr>`;
  });
  return h + `</tbody></table>`;
}

async function finishEdit() {
  const table = STATE.curTable;
  const data = collectEditValues();
  if (!(data["Component Type"] || "").trim()) {
    toast("器件型号为必填项，不能清空", true);
    return;
  }
  const old = STATE.detailRow;
  // 复用确认模态：对比表格模式（原数据 vs 修改后，变更标红）
  document.querySelector("#modalMask .modal-title").textContent = "确认更新记录";
  $("modalSql").classList.add("hidden");
  $("modalDiff").classList.remove("hidden");
  $("modalDiff").innerHTML = buildDiffTable(STATE.cols, data, old);
  $("modalMask").classList.remove("hidden");
  $("modalOkBtn").onclick = async () => {
    try {
      await api("/api/update", { table, old, data });
      closeModal();
      STATE.editing = false;
      toast(`已更新 [${table}]：${data["Component Type"] || ""}`);
      // 刷新表格并重新定位到更新后的记录
      await selectTable(table);
      const rows = visibleRows();
      const hit = rows.find(r => (r["Component Type"] || "") === (data["Component Type"] || "")) ||
        rows.find(r => (r["Part Number"] || "") === (data["Part Number"] || ""));
      if (hit) showDetail(hit, null);
    } catch (e) {
      toast(e.message, true);
    }
  };
}

/* 添加页两级滚动策略：
   1) 预览列能完整放下 → 预览列固定，滚动条只滚中间表单列（内部滚动）
   2) 预览列也放不下 → 整页滚动，两列一起滚 */
function layoutAddScroll() {
  const view = $("viewAdd");
  const grid = $("addGrid"), left = $("leftScroll"), right = $("addRight");
  if (!view || view.classList.contains("hidden")) return;
  const head = view.querySelector(".view-head");
  const avail = view.clientHeight - head.offsetHeight - 10;   // 预留给 head 与间距
  const needR = right.scrollHeight;                           // 预览列自然内容高度
  const needL = left.scrollHeight;                            // 表单区自然内容高度
  if (needR <= avail + 4) {
    grid.style.minHeight = "";            // 网格填满可用高度，预览列完整可见
  } else {
    // 网格高度取两列较大者：两列盒子等高，底边始终对齐，随整页滚动
    grid.style.minHeight = Math.ceil(Math.max(needR, needL)) + "px";
  }
}

/* ================= 添加物料 ================= */
function switchView(name) {
  document.querySelectorAll(".view").forEach(v => v.classList.add("hidden"));
  $("view" + name.charAt(0).toUpperCase() + name.slice(1)).classList.remove("hidden");
  document.querySelectorAll(".dev[data-nav]").forEach(d =>
    d.classList.toggle("sel", d.dataset.nav === name));
  if (name === "add") rebuildForm();
  if (name === "settings" && !STATE.updChecked) { STATE.updChecked = true; updCheck(false); }
  requestAnimationFrame(layoutAddScroll);
}

/* 添加物料分组定义（编号卡片 2~5；卡1 物料类别在 HTML 中） */
const GROUP_DEFS = [
  { num: 2, title: "物料信息", cols: ["Component Type", "Part Number", "Vendor", "Value", "Tolerance", "Description"], oneRow: false },
  { num: 3, title: "供应商", cols: ["Suppiler", "Suppiler Number"], oneRow: true },
  { num: 4, title: "数据文档", cols: ["ComponentLink2Description", "ComponentLink2URL"], oneRow: true },
  { num: 5, title: "器件封装", oneRow: false,
    cols: ["Library Ref", "Library Path", "Footprint Ref", "Footprint Path", "PCB3D Ref", "PCB3D Path"],
    pairs: [["Library Ref", "Library Path"], ["Footprint Ref", "Footprint Path"], ["PCB3D Ref", "PCB3D Path"]] },
];

/* 写入预览 / 记录详情的统一分组顺序（与添加物料分组一致） */
const PREVIEW_GROUPS = [
  ["物料类别", ["Type"]],
  ["物料信息", ["Component Type", "Part Number", "Vendor", "Value", "Tolerance", "Description"]],
  ["供应商", ["Suppiler", "Suppiler Number"]],
  ["数据文档", ["ComponentLink2Description", "ComponentLink2URL"]],
  ["器件封装", ["Library Ref", "Library Path", "Footprint Ref", "Footprint Path", "PCB3D Ref", "PCB3D Path"]],
];

function groupRows(colsList) {
  const used = new Set();
  const out = [];
  PREVIEW_GROUPS.forEach(([g, list]) => {
    const present = list.filter(c => colsList.includes(c));
    if (!present.length) return;
    present.forEach(c => used.add(c));
    out.push({ grp: g, cols: present });
  });
  const rest = colsList.filter(c => !used.has(c) && c !== "LatestRevisionDate");
  if (rest.length) out.push({ grp: "其他字段", cols: rest });
  if (colsList.includes("LatestRevisionDate")) out.push({ grp: "修改日期", cols: ["LatestRevisionDate"] });
  return out;
}

/* 统一渲染字段行：组间插入虚线分隔，便于查看 */
function renderFieldRows(valueCellHtml) {
  const groups = groupRows(STATE.cols);
  let html = "";
  groups.forEach((g, gi) => {
    if (gi > 0) html += `<tr class="grp-sep"><td colspan="2"></td></tr>`;
    g.cols.forEach(c => {
      html += `<tr><td class="dk">${esc(c)}<span class="zh">${esc(FIELD_DESC[c] || "")}</span></td>` +
        `<td class="mono">${valueCellHtml(c)}</td></tr>`;
    });
  });
  return html;
}

function mkFieldEl(c, typeVals) {
  const desc = FIELD_DESC[c] || "";
  let badges = "";
  if (REQUIRED_KEYS.includes(c)) badges += ' <span class="req">*</span>';
  if (MODEL_KEYS.includes(c)) badges += ' <span class="tag model">模型</span>';
  else if (AUTOFILL_KEYS.includes(c)) badges += ' <span class="tag auto">带出</span>';
  const wrap = document.createElement("div");
  wrap.className = "fld" + ((c === "Description" || c === "ComponentLink2URL") ? " full" : "");
  // 三个库路径文本框统一缩短，为尾部「已存在」徽标留出恒定空间
  if (["Library Path", "Footprint Path", "PCB3D Path"].includes(c)) wrap.classList.add("path-fld");
  const lbl = document.createElement("label");
  lbl.innerHTML = `${esc(c)}<span class="desc">(${esc(desc)})</span>${badges}`;
  wrap.appendChild(lbl);
  if (c === "Type") {
    // 可编辑下拉 + 「＋新增」按钮
    const sel = document.createElement("select");
    sel.innerHTML = '<option value=""></option>' +
      (typeVals || []).map(v => `<option>${esc(v)}</option>`).join("");
    sel.onchange = updatePreview;
    const rowDiv = document.createElement("div");
    rowDiv.className = "rowflex";
    rowDiv.style.width = "100%";
    const addBtn = document.createElement("button");
    addBtn.className = "ghost tiny";
    addBtn.textContent = "＋新增";
    addBtn.title = "输入新的具体类别（入库后即成为该表已有项）";
    addBtn.onclick = () => newTypeValue(sel);
    rowDiv.appendChild(sel);
    rowDiv.appendChild(addBtn);
    wrap.appendChild(rowDiv);
    STATE.fieldInputs[c] = sel;
    return wrap;
  }
  if (c === "ComponentLink2URL") {
    // 参考文件路径 = 相对路径（DataSheet/表名前缀/器件型号.pdf，与封装路径同风格，可手动改名）
    // 「替代文件」选源 PDF：确认写入时复制更名到 C2URL 路径；「预览」浏览器打开规格书网页链接
    const rowDiv = document.createElement("div");
    rowDiv.className = "rowflex";
    rowDiv.style.width = "100%";
    const input = document.createElement("input");
    input.type = "text";
    if (AUTOFILL_KEYS.includes(c)) input.className = "tint-auto";
    input.oninput = () => { STATE.pickedFile = ""; updatePreview(); };
    input.onfocus = () => showPickedPathDd(input);
    input.title = "规格书相对路径（DataSheet/表名前缀/器件型号.pdf），可手动修改；已选替代文件时点击会提示可选路径";
    const btn = document.createElement("button");
    btn.className = "ghost tiny";
    btn.textContent = "替代文件";
    btn.title = "选择本地规格书 PDF（源文件）；确认写入后将复制并更名为 C2URL 路径";
    btn.onclick = () => pickDatasheetFile(input, btn);
    const btn2 = document.createElement("button");
    btn2.className = "ghost tiny";
    btn2.textContent = "预览";
    btn2.title = "在浏览器中打开该规格书网页链接（SN 查询带出后可用）";
    btn2.onclick = () => previewDatasheet();
    rowDiv.appendChild(input);
    rowDiv.appendChild(btn);
    rowDiv.appendChild(btn2);
    wrap.appendChild(rowDiv);
    STATE.fieldInputs[c] = input;
    return wrap;
  }
  if (c === "Library Ref" || c === "Footprint Ref" || c === "PCB3D Ref") {
    const input = document.createElement("input");
    input.type = "text";
    input.className = "tint-model";
    // Ref 变更 → 对应的库文件核对（3D/AD/CD）需刷新
    input.oninput = () => {
      updatePreview();
      if (c === "PCB3D Ref") checkModel3dExists();
      else checkFootprintRefs();
    };
    wrap.appendChild(input);
    STATE.fieldInputs[c] = input;
    return wrap;
  }
  if (["Library Path", "Footprint Path", "PCB3D Path"].includes(c)) {
    // 三个库路径行：输入框统一缩短 + 尾部恒定预留位（56px）。
    // Library Path 行：AD/CD 两行垂直标注（Altium SCH / Cadence SCH）；
    // Footprint Path 行：AD/CD（Altium PCB / Cadence PCB）；
    // PCB3D Path 行：显示「✓ 已存在」。
    const rowDiv = document.createElement("div");
    rowDiv.className = "rowflex";
    rowDiv.style.width = "100%";
    const input = document.createElement("input");
    input.type = "text";
    input.className = "tint-model";
    if (c === "PCB3D Path") {
      input.oninput = () => { updatePreview(); checkModel3dExists(); };
      input.title = "3D 模型相对路径（StepModel/封装名.STEP），可手动修改；确认写入时已存在则保留原文件，不存在才从立创官方库下载";
    } else {
      input.oninput = () => { updatePreview(); checkFootprintRefs(); };
      input.title = c === "Library Path"
        ? "SCH 库相对路径（可手动修改）；右侧标注 Altium(AD)/Cadence(CD) 符号核对结果"
        : "PCB 库相对路径（可手动修改）；右侧标注 Altium(AD)/Cadence(CD) 封装核对结果";
    }
    const reserve = document.createElement("span");
    if (c === "PCB3D Path") {
      reserve.className = "path-reserve fp-mark m3d-status";
      reserve.onclick = handleM3dClick;   // 点击查询官方库是否有可下载的 3D 模型
    } else {
      reserve.className = "path-reserve fp-check";
      reserve.dataset.kind = c === "Library Path" ? "sch" : "pcb";
      // 第一个胶囊 Altium：点击查询官方库可下载性（写入时自动追加）
      reserve.innerHTML = '<span class="fp-mark" data-cap="altium" title="点击查询官方库是否有可导出的符号数据" onclick="handleLibgenClick(\'' + (c === "Library Path" ? "sch" : "pcb") + '\')"></span>' +
        '<span class="fp-mark" data-cap="cadence" title="Cadence 库文件（OLB/dra/psm）官方格式需用官方工具导入，点击查看说明" onclick="handleCadenceNote()">Cadence</span>';
    }
    rowDiv.appendChild(input);
    rowDiv.appendChild(reserve);
    wrap.appendChild(rowDiv);
    STATE.fieldInputs[c] = input;
    return wrap;
  }
  const input = document.createElement("input");
  input.type = "text";
  if (MODEL_KEYS.includes(c)) input.className = "tint-model";
  else if (AUTOFILL_KEYS.includes(c)) input.className = "tint-auto";
  input.oninput = updatePreview;
  wrap.appendChild(input);
  STATE.fieldInputs[c] = input;
  return wrap;
}

function buildGroupCard(num, title, colsList, typeVals, oneRow, pairs) {
  const card = document.createElement("div");
  card.className = "panel card";
  const hd = document.createElement("div");
  hd.className = "card-hd";
  hd.innerHTML = `<span class="chip-num">${num}</span><b>${esc(title)}</b>`;
  const bd = document.createElement("div");
  bd.className = "card-bd";
  if (pairs) {
    // 成对行：名称 + 路径 各占一行（窄窗自动换行）
    pairs.forEach(pr => {
      const row = document.createElement("div");
      row.className = "grp-row pair-row";
      pr.filter(c => colsList.includes(c)).forEach((c, i) => {
        row.appendChild(mkFieldEl(c, typeVals));
      });
      bd.appendChild(row);
    });
  } else if (oneRow) {
    // 单行分组（供应商/数据文档）：沿用 pair-row 宽度规则，
    // 使第一列文本框与器件封装组的名称列保持一致宽度
    const row = document.createElement("div");
    row.className = "grp-row pair-row";
    colsList.forEach(c => row.appendChild(mkFieldEl(c, typeVals)));
    bd.appendChild(row);
  } else {
    const grid = document.createElement("div");
    grid.className = "form-grid";
    colsList.forEach(c => grid.appendChild(mkFieldEl(c, typeVals)));
    bd.appendChild(grid);
  }
  card.appendChild(hd);
  card.appendChild(bd);
  return card;
}

async function rebuildForm() {
  const table = $("tableSelect").value;
  const grid = $("formGrid");
  const extra = $("extraGroups");
  grid.innerHTML = "";
  extra.innerHTML = "";
  STATE.fieldInputs = {};
  STATE.pickedFile = "";   // 重建表单时清除已选源文件
  if (!table) return;
  let cols = [];
  let typeVals = [];
  try {
    cols = (await api("/api/columns?table=" + encodeURIComponent(table))).columns;
    typeVals = (await api("/api/distinct?table=" + encodeURIComponent(table) + "&column=Type")).values;
  } catch (e) { toast(e.message, true); return; }

  // 卡1 物料类别：目标数据表在 HTML 中，这里挂入器件具体类别
  const typeHolder = $("typeHolder1");
  typeHolder.innerHTML = "";
  const typeFld = mkFieldEl("Type", typeVals);
  typeFld.style.flex = "1 1 240px";
  typeFld.style.minWidth = "200px";
  typeHolder.appendChild(typeFld);

  // 卡2 物料信息：12 列网格布局（按用户手绘 v2）
  // 第1行：内部编码 | 竖线 | 器件型号 | 生产商
  // 第2行：（内部编码竖跨两行）（竖线跨两行）值 | 精度
  //   —— 值与器件型号对齐、精度与生产商对齐
  // 第3行：描述(整行)
  const used = new Set(["Type", "LatestRevisionDate"]);  // 修改日期由系统自动维护
  const g2 = GROUP_DEFS[0];
  const g2Cols = g2.cols.filter(c => cols.includes(c));
  g2Cols.forEach(c => used.add(c));
  const has = c => g2Cols.includes(c);
  const place = (el, c1, c2, r1, r2) => {
    el.style.gridColumn = c1 + " / " + c2;
    if (r2) el.style.gridRow = r1 + " / " + r2;
    return el;
  };
  if (has("Part Number")) grid.appendChild(place(mkFieldEl("Part Number", typeVals), 1, 3, 1, 3));
  if (has("Part Number") && has("Component Type")) {
    const vs = document.createElement("div");
    vs.className = "vsep";
    grid.appendChild(place(vs, 3, 4, 1, 3));
  }
  if (has("Component Type")) grid.appendChild(place(mkFieldEl("Component Type", typeVals), 4, 9, 1));
  if (has("Vendor")) grid.appendChild(place(mkFieldEl("Vendor", typeVals), 9, 13, 1));
  if (has("Value")) grid.appendChild(place(mkFieldEl("Value", typeVals), 4, 9, 2));
  if (has("Tolerance")) grid.appendChild(place(mkFieldEl("Tolerance", typeVals), 9, 13, 2));
  if (has("Description")) {
    const d = mkFieldEl("Description", typeVals);
    d.style.gridColumn = "1 / 13";
    d.style.gridRow = "3";
    grid.appendChild(d);
  }
  // 物料信息组中未参与上述布局的剩余字段（如有）兜底铺满一行
  g2Cols.filter(c => !["Part Number", "Component Type", "Vendor", "Value", "Tolerance", "Description"].includes(c))
    .forEach(c => grid.appendChild(place(mkFieldEl(c, typeVals), 1, 13)));

  // 卡3~5：供应商 / 数据文档 / 器件封装（封装组按 名称+路径 成对三行）
  GROUP_DEFS.slice(1).forEach(g => {
    const present = g.cols.filter(c => cols.includes(c));
    present.forEach(c => used.add(c));
    if (!present.length) return;
    extra.appendChild(buildGroupCard(g.num, g.title, present, typeVals, g.oneRow, g.pairs));
  });
  // 自定义表多出的字段 / Cadence 附加字段兜底分组
  const rest = cols.filter(c => !used.has(c));
  if (rest.length) extra.appendChild(buildGroupCard(6, "Cadence / 其他字段", rest, typeVals, false));
  updatePreview();
  requestAnimationFrame(layoutAddScroll);
}

function collectFields() {
  const o = {};
  for (const [k, el] of Object.entries(STATE.fieldInputs)) {
    o[k] = (el.tagName === "SELECT" ? el.value : el.value).trim();
  }
  return o;
}

function buildSql(table, cols, data) {
  const colSql = cols.map(c => `[${c}]`).join(", ");
  const valSql = cols.map(c => sqlEsc(data[c] || "")).join(",\n   ");
  return `INSERT INTO [${table}]\n  (${colSql})\nVALUES\n  (${valSql});`;
}

async function updatePreview() {
  const table = $("tableSelect").value;
  const chk = $("checklist");
  const btn = $("addBtn");
  if (!table) {
    $("fieldPreview").innerHTML =
      '<div class="detail-empty">填写下方表单后<br>这里实时展示将要写入的字段值</div>';
    chk.innerHTML = '<li class="bad">✗ 未选择目标表</li>'; btn.disabled = true; return;
  }
  const data = collectFields();
  let cols = STATE.fieldColsCache && STATE.fieldColsTable === table
    ? STATE.fieldColsCache
    : (STATE.fieldColsCache = (await api("/api/columns?table=" + encodeURIComponent(table))).columns,
       STATE.fieldColsTable = table, STATE.fieldColsCache);
  // 写入预览：与记录详情同款的两列字段值对照表（分组顺序 + 分隔线）
  const today = new Date().toISOString().slice(0, 10);
  $("fieldPreview").innerHTML =
    `<table class="detail-table">${renderFieldRows(c => {
      if (c === "LatestRevisionDate") return esc(today);   // 修改日期：直接展示当天
      return esc(data[c] || "") || "—";
    })}</table>`;
  const missing = REQUIRED_KEYS.filter(k => !data[k]);
  let dup = null;
  try { dup = (await api("/api/dup", { table, data })).dup; } catch (e) { /* ignore */ }

  // 信息完整度：已填字段数 / 参与统计字段数（排除系统维护的修改日期）
  const statCols = cols.filter(c => c !== "LatestRevisionDate");
  const filled = statCols.filter(c => String(data[c] || "").trim()).length;
  const pct = statCols.length ? Math.round(filled / statCols.length * 100) : 0;
  $("compPct").textContent = statCols.length ? `${pct}%（${filled}/${statCols.length} 字段）` : "—";
  const fillEl = $("compFill");
  fillEl.style.width = pct + "%";
  fillEl.className = "comp-fill" + (pct >= 80 ? " hi" : pct >= 40 ? " mid" : " low");

  // 分条检测结果
  const items = [];
  items.push(missing.length
    ? `<li class="bad">✗ 缺少必填项：${esc(missing.join("、"))}</li>`
    : `<li class="ok">✓ 必填项齐全（${esc(REQUIRED_KEYS.join("、"))}）</li>`);
  items.push(dup
    ? `<li class="bad">✗ 重复检查：${esc(dup)}</li>`
    : '<li class="ok">✓ 重复检查：同表无重复</li>');
  const modelCols = ["Library Ref", "Library Path", "Footprint Ref", "Footprint Path",
                     "PCB3D Ref", "PCB3D Path"].filter(c => statCols.includes(c));
  if (modelCols.length) {
    const missModel = modelCols.filter(c => !String(data[c] || "").trim());
    items.push(missModel.length
      ? `<li class="warn">△ 模型字段缺 ${missModel.length}/${modelCols.length} 项：${esc(missModel.join("、"))}</li>`
      : `<li class="ok">✓ 模型字段完整（SCH/PCB/3D 共 ${modelCols.length} 项）</li>`);
  }
  if (statCols.includes("ComponentLink2URL")) {
    const ds = String(data["ComponentLink2URL"] || "").trim();
    items.push((ds && ds !== "无可下载规格书")
      ? '<li class="ok">✓ 规格书路径已指定（写入后自动落盘或下载）</li>'
      : '<li class="warn">△ 规格书未指定（写入后无 PDF 落盘）</li>');
  }
  chk.innerHTML = items.join("");
  btn.disabled = !!(missing.length || dup);
  requestAnimationFrame(layoutAddScroll);
}

/* SN 查询 */
/* 将 SN 查询结果填充到当前表单（查询成功与换表重建后共用） */
function applySNData(sn) {
  const d = sn.data || {};
  for (const [k, v] of Object.entries(d)) {
    if (STATE.fieldInputs[k]) STATE.fieldInputs[k].value = String(v);
  }
  for (const [k, v] of Object.entries(sn.suggest_fields || {})) {
    if (STATE.fieldInputs[k] && !STATE.fieldInputs[k].value) STATE.fieldInputs[k].value = String(v);
  }
  if (sn.suggest_part_number && STATE.fieldInputs["Part Number"] &&
      !STATE.fieldInputs["Part Number"].value) {
    STATE.fieldInputs["Part Number"].value = sn.suggest_part_number;
  }
  STATE.lastDatasheet = sn.datasheet_url || "";
  STATE.model3d = sn.model3d || null;   // 3D 模型编号（跨表重填保留，封装不变）
  if (STATE.fieldInputs["ComponentLink2Description"] &&
      !STATE.fieldInputs["ComponentLink2Description"].value) {
    STATE.fieldInputs["ComponentLink2Description"].value = "DataSheet";
  }
  if (STATE.fieldInputs["ComponentLink2URL"]) {
    const mpn = String(d["Component Type"] || "");
    STATE.fieldInputs["ComponentLink2URL"].value =
      (STATE.lastDatasheet && mpn)
        ? suggestDatasheetPath($("tableSelect").value, mpn)
        : "无可下载规格书";
  }
  checkModel3dExists();   // 带出封装后立即检测 3D 模型是否已存在
  checkFootprintRefs();   // 同步核对 Altium/Cadence SCH 与 PCB 封装存在性
  updatePreview();
}

/* 规格书目标相对路径：DataSheet/表名前缀(-前段)/器件型号.pdf（与封装路径同风格） */
function suggestDatasheetPath(table, mpn) {
  if (!mpn) return "";
  const folder = String(table || "").split("-")[0] || "DataSheet";
  return `DataSheet/${folder}/${mpn}.pdf`;
}

/* C2URL 聚焦时：已选替代文件 → 弹下拉展示「原文件名 → 库参考路径」，点击采用 */
function showPickedPathDd(inp) {
  if (!STATE.pickedFile) return;
  const base = String(STATE.pickedFile).replace(/\\/g, "/").split("/").pop();
  const target = suggestDatasheetPath($("tableSelect").value, base.replace(/\.pdf$/i, ""));
  closeAllDd();
  const dd = document.createElement("div");
  dd.className = "dt-dd";
  dd.style.cssText = "position:fixed;z-index:999;";
  const r = inp.getBoundingClientRect();
  dd.style.top = (r.bottom + 3) + "px";
  dd.style.left = r.left + "px";
  dd.style.width = Math.max(r.width, 340) + "px";
  dd.innerHTML =
    `<div class="dt-opt" style="display:flex;flex-direction:column;align-items:flex-start;gap:2px">` +
    `<span>📄 ${esc(base)} <span style="color:var(--dim);font-weight:400">（替代文件）</span></span>` +
    `<span style="font-size:10.5px;color:var(--ok)">→ ${esc(target)}</span></div>` +
    `<div class="dt-none">点击上方条目采用该库参考路径</div>`;
  dd.querySelector(".dt-opt").onmousedown = e => {
    e.preventDefault();
    e.stopPropagation();
    inp.value = target;
    closeAllDd();
    updatePreview();
  };
  document.body.appendChild(dd);
  dd.classList.remove("hidden");
}

/* 选择源规格书 PDF（pywebview 原生对话框）：只记住所选文件，不改动 C2URL。
   确认写入时把所选文件复制更名到 C2URL 目标相对路径。 */
async function pickDatasheetFile(input, btn) {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.pick_datasheet_file) {
    const r = await window.pywebview.api.pick_datasheet_file();
    if (r && r.path) {
      STATE.pickedFile = r.path;
      const base = String(r.path).replace(/\\/g, "/").split("/").pop();
      btn.textContent = base.length > 14 ? "✓ " + base.slice(0, 13) + "…" : "✓ " + base;
      btn.title = "已选替代文件：" + r.path + "（确认写入后复制更名为 C2URL 相对路径）";
      updatePreview();
    }
  } else {
    toast("浏览器模式不支持文件选择，请手动把文件放到目标路径", true);
  }
}

/* 预览：浏览器打开该 SN 的规格书网页链接 */
async function previewDatasheet() {
  const url = STATE.lastDatasheet;
  if (!url) {
    toast("暂无规格书链接（请先查询 SN；官方未提供规格书时无链接）", true);
    return;
  }
  if (window.pywebview && window.pywebview.api && window.pywebview.api.open_url) {
    const r = await window.pywebview.api.open_url(url);
    if (r && r.ok === false) toast(r.error || "打开失败", true);
  } else {
    window.open(url, "_blank");
  }
}

/* 3D 模型存在性实时检测：按 Path（缺省按 Ref 推导 StepModel/<封装>.STEP）
   查询后端；已存在时在 Path 行显示「已存在」徽标，否则清空不占位 */
let m3dCheckTimer = null;
function checkModel3dExists() {
  clearTimeout(m3dCheckTimer);
  m3dCheckTimer = setTimeout(async () => {
    const st = document.querySelector(".m3d-status");
    if (!st) return;
    const path = (STATE.fieldInputs["PCB3D Path"] || {}).value || "";
    const ref = (STATE.fieldInputs["PCB3D Ref"] || {}).value || "";
    if (!path || !ref) {
      st.textContent = "";
      st.className = "path-reserve fp-mark m3d-status";
      return;
    }
    const downloadable = STATE.m3dPending && STATE.model3d &&
      (STATE.model3d.uuid || STATE.model3d.uuid_3d);
    try {
      const qs = "path=" + encodeURIComponent(path) + "&ref=" + encodeURIComponent(ref);
      const j = await api("/api/model3d_exists?" + qs);
      if (j.exists) {
        STATE.m3dPending = false;
        st.textContent = "PCB 3D已存在";
        st.className = "path-reserve fp-mark m3d-status fp-ok";
      } else if (downloadable) {
        // 用户已点击确认可下载：跨表重填后保持「待下载」状态
        st.textContent = "PCB 3D不存在，待下载";
        st.className = "path-reserve fp-mark m3d-status fp-ok";
      } else {
        st.textContent = "PCB 3D不存在";
        st.className = "path-reserve fp-mark m3d-status fp-bad";
      }
    } catch (e) {
      st.textContent = "";
      st.className = "path-reserve fp-mark m3d-status";
    }
  }, 400);
}

/* 点击 PCB3D 胶囊：查询官方库是否有该封装的 3D 模型可下载
   （可下载→绿底「待下载」，写入时自动下载；无→提示并维持红底） */
function handleM3dClick() {
  const st = document.querySelector(".m3d-status");
  if (!st) return;
  if (st.classList.contains("fp-ok") && st.textContent === "PCB 3D已存在") {
    toast("该 3D 模型已存在于库目录中，写入时将保留原文件");
    return;
  }
  const m = STATE.model3d;
  if (!m || (!m.uuid && !m.uuid_3d)) {
    st.textContent = "PCB 3D不存在";
    st.className = "path-reserve fp-mark m3d-status fp-bad";
    toast("无可下载的封装：官方库未关联该封装的 3D 模型", true);
    return;
  }
  st.textContent = "PCB 3D不存在，待下载";
  st.className = "path-reserve fp-mark m3d-status fp-ok";
  STATE.m3dPending = true;   // 已确认可下载：换表重填后保持待下载状态
  toast("官方库有该封装的 3D 模型，确认写入时将自动下载到 PCB3D Path");
}

/* AD/CD 双行核对：Library Path 行标 Altium SCH + Cadence SCH，
   Footprint Path 行标 Altium PCB + Cadence PCB（500ms 去抖） */
const FP_TAG = { altium_sch: "Altium", cadence_sch: "Cadence", altium_pcb: "Altium", cadence_pcb: "Cadence" };
const FP_MARK = { ok: "✓", missing: "✗", nofile: "△" };
const FP_CLS = { ok: "fp-ok", missing: "fp-bad", nofile: "fp-warn" };
const FP_KIND_LABEL = { sch: "原理图符号", pcb: "PCB 封装" };

function paintFpMark(el, key, r, pending) {
  if (!el) return;
  const status = r ? r.status : "";
  if (!status || status === "nodata") {
    el.textContent = "";
    el.className = "fp-mark";
    el.title = "";
    return;
  }
  if (status === "missing" && pending) {
    el.textContent = FP_TAG[key];
    el.className = "fp-mark fp-pend";
    el.title = `${FP_TAG[key]}：待下载（确认写入时自动追加到库文件）`;
    return;
  }
  el.textContent = FP_TAG[key];
  el.className = "fp-mark " + (FP_CLS[status] || "");
  el.title = r.detail ? `${FP_TAG[key]}：${status === "ok" ? "存在" : status === "missing" ? "不存在" : "库文件缺失"} — ${r.detail}`
                      : `${FP_TAG[key]}：${status === "ok" ? "存在" : status === "missing" ? "不存在" : "库文件缺失"}`;
}

let fpCheckTimer = null;
function checkFootprintRefs() {
  clearTimeout(fpCheckTimer);
  fpCheckTimer = setTimeout(async () => {
    const boxes = document.querySelectorAll(".fp-check");
    (window.FP_DEBUG = window.FP_DEBUG || []).push({ step: "run", boxes: boxes.length });
    if (!boxes.length) { toast("AD/CD 诊断：页面上没有 .fp-check 容器", true); return; }
    const val = c => (STATE.fieldInputs[c] || {}).value || "";
    const d = {
      library_ref: val("Library Ref"), library_path: val("Library Path"),
      footprint_ref: val("Footprint Ref"), footprint_path: val("Footprint Path"),
    };
    (window.FP_DEBUG = window.FP_DEBUG || []).push({ step: "req", d });
    try {
      const j = await api("/api/libcheck_fp", d);
      (window.FP_DEBUG = window.FP_DEBUG || []).push({ step: "res", j });
      boxes.forEach(box => {
        const marks = box.querySelectorAll(".fp-mark");
        const kind = box.dataset.kind;
        if (marks.length < 2) { toast(`AD/CD 诊断：${kind} 行标记位不足`, true); return; }
        const pend = STATE.libgenPending[kind] && STATE.sn;
        if (j["altium_" + kind] && j["altium_" + kind].status === "ok") {
          STATE.libgenPending[kind] = false;   // 文件已在库，待下载态解除
        }
        paintFpMark(marks[0], "altium_" + kind, j["altium_" + kind], pend);
        paintFpMark(marks[1], "cadence_" + kind, j["cadence_" + kind]);
      });
    } catch (e) {
      (window.FP_DEBUG = window.FP_DEBUG || []).push({ step: "err", msg: e.message });
      toast("AD/CD 核对失败: " + e.message, true);
      document.querySelectorAll(".fp-mark").forEach(el => { el.textContent = ""; });
    }
  }, 500);
}

/* 点击 Altium 胶囊：查询官方库是否有可导出的符号/封装数据（写入时自动追加） */
async function handleLibgenClick(kind) {
  const box = document.querySelector(`.fp-check[data-kind="${kind}"]`);
  const cap = box && box.querySelector('[data-cap="altium"]');
  if (!cap) return;
  if (cap.classList.contains("fp-pend")) {
    toast("已确认待下载：确认写入时将自动追加到库文件");
    return;
  }
  if (cap.classList.contains("fp-ok")) {
    toast("该引用已存在于库文件中");
    return;
  }
  if (!STATE.sn) {
    toast("请先查询立创 SN（下载来源为官方库数据）", true);
    return;
  }
  toast("查询官方库…");
  try {
    const j = await api("/api/libgen_check", { kind, sn: STATE.sn });
    if (!j.available) {
      toast(`无可下载的${FP_KIND_LABEL[kind]}：官方库未提供该数据`, true);
      return;
    }
    STATE.libgenPending[kind] = true;
    paintFpMark(cap, "altium_" + kind, { status: "missing" }, true);
    toast(`官方库有${FP_KIND_LABEL[kind]}数据（${j.name}），确认写入时将自动追加到库文件`);
  } catch (e) {
    toast(e.message, true);
  }
}

/* Cadence 胶囊说明：官方私有格式暂不支持自动写入 */
function handleCadenceNote() {
  alert("Cadence 说明\n\n官方库带符号/封装完整几何数据，但 Cadence 的 OLB / dra / psm 为官方私有格式，暂不支持自动写入库文件。\n\n可选路径：基于官方库数据生成 OrCAD XML（Capture 导入）或 Allegro SKILL 脚本（自动绘制各层），后续版本提供。");
}

/* ================= 自测模式（URL 带 ?selftest=<SN>）================= */
(function () {
  const sn = new URLSearchParams(location.search).get("selftest");
  if (!sn) return;
  setTimeout(async () => {
    const out = [];
    try {
      await boot();
      out.push("boot 完成, tables=" + (STATE.tables || []).length);
      $("snInput").value = sn;
      switchView("add");
      await fetchSN();
      out.push("fetchSN 完成");
      await new Promise(r => setTimeout(r, 1500));
      const boxes = [...document.querySelectorAll(".fp-check")];
      out.push("fp-check 容器数: " + boxes.length);
      boxes.forEach(b => {
        out.push(`  [${b.dataset.kind}] marks=${b.querySelectorAll(".fp-mark").length} ` +
          [...b.querySelectorAll(".fp-mark")].map(m => JSON.stringify(m.textContent)).join(" "));
      });
      out.push("LibraryRef=" + JSON.stringify((STATE.fieldInputs["Library Ref"] || {}).value));
      out.push("FootprintRef=" + JSON.stringify((STATE.fieldInputs["Footprint Ref"] || {}).value));
      out.push("PCB3DPath=" + JSON.stringify((STATE.fieldInputs["PCB3D Path"] || {}).value));
      out.push("FP_DEBUG=" + JSON.stringify(window.FP_DEBUG || []));
      // 自动点击 PCB3D 胶囊验证可下载性查询
      handleM3dClick();
      await new Promise(r => setTimeout(r, 100));
      const ms = document.querySelector(".m3d-status");
      out.push("点击后胶囊: " + JSON.stringify(ms ? ms.textContent : "(无)") + " cls=" + (ms ? ms.className : ""));
      // 自动点击 Altium 胶囊（SCH 行）验证符号可下载性查询
      await handleLibgenClick("sch");
      await new Promise(r => setTimeout(r, 800));
      const ac = document.querySelector('.fp-check[data-kind="sch"] [data-cap="altium"]');
      out.push("点击Altium后: " + JSON.stringify(ac ? ac.textContent : "(无)") + " cls=" + (ac ? ac.className : ""));
    } catch (e) {
      out.push("SELFTEST-ERR: " + (e.stack || e.message));
    }
    let pre = document.getElementById("selftestOut");
    if (!pre) {
      pre = document.createElement("pre");
      pre.id = "selftestOut";
      document.body.appendChild(pre);
    }
    pre.style.cssText = "position:fixed;inset:0;z-index:99999;background:#fff;color:#000;font-size:12px;padding:8px;white-space:pre-wrap;";
    pre.textContent = out.join("\n");
  }, 300);
})();

async function fetchSN() {
  const sn = $("snInput").value.trim().toUpperCase();
  if (!sn) { toast("请输入立创商城 SN"); return; }
  const btn = $("snFetchBtn");
  btn.disabled = true;
  $("snStatus").className = "sn-status";
  $("snStatus").textContent = "查询中…（lceda.cn → easyeda.com）";
  try {
    const j = await api("/api/sn", { sn });
    btn.disabled = false;
    if (j.fetched) {
      $("snStatus").className = "sn-status ok";
      $("snStatus").textContent = `✓ 已带出 ${Object.keys(j.data).length} 个字段（来源：${j.source}）` +
        (j.suggest_table ? ` ｜ 建议表：${j.suggest_table}` : "");
      $("snStatus").title = j.logs.join("\n");
      if (j.suggest_table) {
        $("aiBadge").classList.remove("hidden");
        const sel = $("tableSelect");
        const prev = sel.value;
        sel.value = j.suggest_table;
        if (sel.value === j.suggest_table) {
          $("catHint").textContent = `立创分类 → ${j.suggest_table}`;
        } else {
          // 后端已按实际库表解析过；此处兜底同大类近似（旧后端场景）
          const prefix = j.suggest_table.split("-")[0].toLowerCase();
          const alt = [...sel.options].find(o => o.value.toLowerCase().startsWith(prefix) && o.value !== prev)
            || [...sel.options].find(o => o.value.toLowerCase().startsWith(prefix))
            || (prev ? { value: prev } : null);
          if (alt) {
            sel.value = alt.value;
            $("catHint").textContent = `立创分类 → ${j.suggest_table}（库中无此表，已近似选 ${alt.value}）`;
            toast(`建议表「${j.suggest_table}」在库中不存在，已改选近似表「${alt.value}」，请确认目标表`, true);
          } else {
            $("catHint").textContent = `立创分类 → ${j.suggest_table}（库中无此表，请手动选择）`;
            toast(`建议表「${j.suggest_table}」在库中不存在，请手动选择目标表`, true);
          }
        }
      } else if ((j.suggest_candidates || []).length) {
        // 理想表名无法唯一解析（如表已合并）：列出候选，由用户确认
        $("aiBadge").classList.remove("hidden");
        $("catHint").textContent = `立创分类候选：${j.suggest_candidates.join("、")}（请手动选择目标表）`;
        toast(`该器件的推荐表无法唯一确定，候选：${j.suggest_candidates.join("、")} —— 请在「目标数据表」手动选择`, true);
      }
      await rebuildForm();
      for (const [k, v] of Object.entries(j.data)) {
        if (STATE.fieldInputs[k]) STATE.fieldInputs[k].value = String(v);
      }
      // 模型字段建议
      for (const [k, v] of Object.entries(j.suggest_fields || {})) {
        if (STATE.fieldInputs[k] && !STATE.fieldInputs[k].value) STATE.fieldInputs[k].value = String(v);
      }
      if (j.suggest_part_number && STATE.fieldInputs["Part Number"] && !STATE.fieldInputs["Part Number"].value) {
        STATE.fieldInputs["Part Number"].value = j.suggest_part_number;
      }
      // 规格书：C2D 默认 DataSheet；C2URL = DataSheet/表名前缀/器件型号.pdf；无规格书如实标注
      STATE.m3dPending = false;   // 新 SN：重置 3D 待下载状态（需重新点击胶囊确认）
      STATE.sn = sn;              // 符号/封装下载来源
      STATE.libgenPending = { sch: false, pcb: false };
      STATE.lastSN = { data: j.data, suggest_fields: j.suggest_fields,
                       suggest_part_number: j.suggest_part_number,
                       datasheet_url: j.datasheet_url,
                       model3d: j.model3d || null };
      STATE.pickedFile = "";
      applySNData(STATE.lastSN);
    } else {
      $("snStatus").className = "sn-status bad";
      $("snStatus").textContent = "✗ 未查到（官方库无此编号或网络失败），可手动填写 —— 悬停查看详情";
      $("snStatus").title = j.logs.join("\n");
      toast("SN 未查到，可手动填写入库", true);
    }
  } catch (e) {
    btn.disabled = false;
    $("snStatus").className = "sn-status bad";
    $("snStatus").textContent = "✗ " + e.message;
    $("snStatus").title = e.stack || "";
  }
}

function manualMode() {
  $("snStatus").className = "sn-status";
  $("snStatus").textContent = "手动录入模式";
  STATE.lastSN = null;          // 手动录入：清除 SN 缓存
  STATE.lastDatasheet = "";     // 避免预览误开上一次 SN 的链接
  STATE.model3d = null;         // 手动录入无 3D 模型来源
  STATE.m3dPending = false;
  STATE.sn = "";
  STATE.libgenPending = { sch: false, pcb: false };
  rebuildForm();
}

async function onTableChange() {
  $("aiBadge").classList.add("hidden");
  $("catHint").textContent = "手动选择";
  await rebuildForm();
  // 若刚查询过 SN：换表后自动重新带出（含按新表重新生成的规格书路径）
  if (STATE.lastSN) applySNData(STATE.lastSN);
}

/* 写入 */
async function confirmAdd() {
  const table = $("tableSelect").value;
  const data = collectFields();
  let cols;
  try { cols = (await api("/api/columns?table=" + encodeURIComponent(table))).columns; }
  catch (e) { toast(e.message, true); return; }
  $("modalDiff").classList.add("hidden");
  $("modalSql").classList.remove("hidden");
  // 修改日期自动带入当天（后端亦兜底），确认弹窗里如实展示
  data["LatestRevisionDate"] = new Date().toISOString().slice(0, 10);
  $("modalSql").textContent = buildSql(table, cols, data);
  $("modalMask").classList.remove("hidden");
  $("modalOkBtn").onclick = async () => {
    try {
      const j = await api("/api/insert", {
        table, data,
        datasheet_url: STATE.lastDatasheet,
        local_file: STATE.pickedFile,
        model3d: STATE.model3d,
        libgen_pending: {
          sch: STATE.libgenPending.sch ? STATE.sn : "",
          pcb: STATE.libgenPending.pcb ? STATE.sn : "",
        },
      });
      closeModal();
      STATE.pickedFile = "";
      STATE.lastDatasheet = "";
      STATE.model3d = null;
      STATE.m3dPending = false;
      STATE.libgenPending = { sch: false, pcb: false };
      STATE.lastSN = null;      // 该 SN 已入库，清除缓存
      toast(`已写入 [${table}]：${data["Component Type"] || ""}` +
        (j.warn ? ` ｜ ${j.warn}` : ""), !!j.warn && /失败|未/.test(j.warn));
      $("snInput").value = "";
      switchView("browse");
      await reloadDb();
      selectTable(table);
    } catch (e) { toast(e.message, true); }
  };
}
function closeModal() {
  $("modalMask").classList.add("hidden");
  // 还原为写入模式（标题 + SQL 预览），供下一次复用
  document.querySelector("#modalMask .modal-title").textContent = "确认写入";
  $("modalDiff").classList.add("hidden");
  $("modalSql").classList.remove("hidden");
}

/* 通用输入小模态 */
let inputModalCb = null;
function openInputModal(title, placeholder, hint, cb) {
  $("inputModalTitle").textContent = title;
  $("inputModalValue").value = "";
  $("inputModalValue").placeholder = placeholder;
  $("inputModalHint").textContent = hint || "";
  inputModalCb = cb;
  $("inputModalMask").classList.remove("hidden");
  setTimeout(() => $("inputModalValue").focus(), 50);
}
function closeInputModal() { $("inputModalMask").classList.add("hidden"); inputModalCb = null; }
function submitInputModal() {
  const v = $("inputModalValue").value.trim();
  if (!v) return;
  const cb = inputModalCb;
  closeInputModal();
  if (cb) cb(v);
}

/* 新增分类表（目标数据表） */
function newTable() {
  openInputModal("新增分类表", "例如：Connectors-HDMI / ICs-RF",
    "将在 mdb 中创建一张含 18 个标准字段的新表；创建后需在 Altium DbLib 中刷新链接表。",
    async name => {
      try {
        await api("/api/create_table", { name });
        toast(`分类表 [${name}] 已创建`);
        await reloadDb();
        $("tableSelect").value = name;
        onTableChange();
      } catch (e) { toast(e.message, true); }
    });
}

/* 新增具体类别（Type 下拉） */
function newTypeValue(selectEl) {
  const table = $("tableSelect").value;
  openInputModal(`新增具体类别（[${table}]）`, "例如：0603/E96/1% 或 LDO Regulators",
    "入库后该类别即写入 DB，下次会出现在下拉列表中。",
    value => {
      const o = document.createElement("option");
      o.value = value; o.textContent = value;
      selectEl.appendChild(o);
      selectEl.value = value;
      updatePreview();
      toast(`已选用新类别「${value}」，随本次入库写入`);
    });
}

/* 点击侧栏库路径卡片 → 文件选择器选新 mdb → 立即保存并重连 */
async function changeDbFromSidebar() {
  if (!(window.pywebview && window.pywebview.api && window.pywebview.api.pick_db_file)) {
    toast("浏览器模式无文件对话框，请到设置页粘贴路径", true);
    return;
  }
  const r = await window.pywebview.api.pick_db_file();
  if (!r || r.cancelled) return;
  if (!r.ok) { toast(r.error || "选择文件失败", true); return; }
  try {
    await api("/api/settings", { db_path: r.path });
    $("dbPathInput").value = r.path;
    toast("库路径已切换：" + r.path);
    await reloadDb();
  } catch (e) {
    toast(e.message, true);
  }
}

/* ================= 软件更新 ================= */
function paintUpdate(j) {
  const line = $("updStatusLine"), detail = $("updDetail"), btn = $("updDownloadBtn");
  const cur = (j.version || "?");
  const u = j.update || {};
  if (u.error) {
    line.textContent = `当前版本 v${cur}　｜　检查失败`;
    detail.textContent = u.error;
    btn.disabled = true;
    return;
  }
  if (u.available) {
    line.textContent = `当前版本 v${cur}　｜　发现新版本 v${u.latest} ✅`;
    detail.textContent = "升级包将下载到软件安装目录：安装版启动覆盖安装向导后本程序自动关闭；"
      + "绿色版自动就位替换，重开即为新版。安装完成后残留安装包自动清除。";
    btn.disabled = false;
  } else {
    line.textContent = `当前版本 v${cur}　｜　已是最新` + (u.latest ? `（线上 v${u.latest}）` : "");
    detail.textContent = u.note || "";
    btn.disabled = true;
  }
}

async function updCheck(manual = true) {
  const btn = $("updCheckBtn");
  btn.disabled = true;
  if (manual) $("updStatusLine").textContent = "正在检查更新…";
  try {
    const j = await api("/api/update_check", {});
    paintUpdate(j);
    if (manual && j.update && j.update.available) toast(`发现新版本 v${j.update.latest}！`);
  } catch (e) {
    $("updStatusLine").textContent = "检查更新失败：" + e.message;
  } finally {
    btn.disabled = false;
  }
}

async function updDownload() {
  const btn = $("updDownloadBtn");
  btn.disabled = true;
  btn.textContent = "下载中…";
  try {
    const j = await api("/api/update_download", {});
    toast(j.message || "更新已处理");
    $("updDetail").textContent = j.message || "";
    if (j.mode === "setup") {
      $("updStatusLine").textContent = "安装向导已启动，本程序即将自动关闭…";
    } else if (j.mode === "portable") {
      $("updStatusLine").textContent = "更新已就位，请完全关闭本程序后重新打开";
    } else {
      $("updStatusLine").textContent = "已打开发布页，请手动下载";
    }
  } catch (e) {
    toast(e.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = "下载并安装更新";
  }
}

/* ================= 设置 ================= */
async function pickDbFile() {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.pick_db_file) {
    const r = await window.pywebview.api.pick_db_file();
    if (r && r.path) $("dbPathInput").value = r.path;
  } else {
    toast("当前运行在浏览器模式，请手动粘贴数据库完整路径");
  }
}
async function saveSettings() {
  try {
    await api("/api/settings", {
      db_path: $("dbPathInput").value.trim(),
      auto_load: $("autoLoadChk").checked,
      backup_write: $("backupChk").checked,
    });
    toast("设置已保存，数据库已重新载入");
    await reloadDb();
  } catch (e) { toast(e.message, true); }
}

/* ================= 主题 ================= */
function applyThemeColor(dark) {
  document.documentElement.classList.toggle("light", !dark);
  $("themeBtn").textContent = dark ? "☀ 浅色" : "🌙 深色";
}
function toggleTheme() {
  const dark = !(STATE.settings.dark === true);
  STATE.settings.dark = dark;
  applyThemeColor(dark);
  api("/api/settings", { dark }).catch(() => {});
}

/* ================= 事件绑定 ================= */
function bindEvents() {
  document.addEventListener("click", e => {
    // 点击下拉组件以外区域时收起（组件内部的 focus/open 不受影响）
    if (!e.target.closest(".dt-combo") && !e.target.closest(".dt-dd")) closeAllDd();
  });
  $("detailPanel").addEventListener("scroll", () => closeAllDd());
  window.addEventListener("resize", () => { closeAllDd(); layoutAddScroll(); });
  $("gridSearch").oninput = renderGrid;
  $("tableSelect").onchange = onTableChange;
  $("snFetchBtn").onclick = fetchSN;
  $("snInput").addEventListener("keydown", e => { if (e.key === "Enter") fetchSN(); });
  $("snSkipBtn").onclick = manualMode;
  $("addBtn").onclick = confirmAdd;
  $("reloadBtn").onclick = reloadDb;
  $("dbCard").onclick = changeDbFromSidebar;
  $("browseDbBtn").onclick = pickDbFile;
  $("saveSettingsBtn").onclick = saveSettings;
  $("updCheckBtn").onclick = () => updCheck(true);
  $("updDownloadBtn").onclick = updDownload;
  $("themeBtn").onclick = toggleTheme;
  $("newTableBtn").onclick = newTable;
  $("inputModalOk").onclick = submitInputModal;
  $("inputModalValue").addEventListener("keydown", e => {
    if (e.key === "Enter") submitInputModal();
    if (e.key === "Escape") closeInputModal();
  });
  $("inputModalMask").onclick = e => { if (e.target === $("inputModalMask")) closeInputModal(); };
  $("modalMask").onclick = e => { if (e.target === $("modalMask")) closeModal(); };
  // 侧栏拖宽
  const split = $("colSplit");
  let dragging = false;
  split.addEventListener("mousedown", () => { dragging = true; document.body.style.cursor = "col-resize"; });
  window.addEventListener("mousemove", e => {
    if (!dragging) return;
    const w = Math.min(420, Math.max(190, e.clientX - 16));
    document.querySelector(".shell").style.gridTemplateColumns = `${w}px 6px minmax(0,1fr)`;
  });
  window.addEventListener("mouseup", () => { dragging = false; document.body.style.cursor = ""; });
}

boot();
