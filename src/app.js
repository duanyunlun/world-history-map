/* ==========================================================================
   中国历史地图 1893—1976 · 前端主逻辑
   · 时间粒度：月（1893.01 — 1976.12，共 1008 个刻度）
   · 势力范围：逐月动态着色（分省归属区间 + 月级关键切点）
   · 交互：点击地块放大并展开该地大事 / 时间轴可拖动 / 滚轮缩放 / 支持空格播放
   ========================================================================== */
(function () {
  'use strict';

  const GEO = window.__GEO__;
  const DATA = window.__DATA__;
  const Y0 = 1893, Y1 = 1976;
  const M0 = Y0 * 12, M1 = Y1 * 12 + 11;
  const NSTEP = M1 - M0 + 1;               // 1008
  const CAT = DATA.cats || {};
  /* 势力表：优先由「政权注册表」构建（单一真相 + 别名）；无注册表时回退旧数据 */
  const POLITIES = DATA.polities || null;
  const POLALIAS = DATA.polityAlias || null;
  /* 按年份解析政权：id 是跨时间的稳定身份，span 是该时段的名称/都城/简史。
     同一拼写在不同年代可指向同一 id 的不同时段；无年份信息时取与该名对应的时段。 */
  let CUR_YEAR = 0;
  function polByName(name, year) {
    if (!POLITIES) return null;
    if (POLITIES[name]) return applySpan(POLITIES[name], year);   // 精确 id 优先
    const k = String(name).toLowerCase();
    const cands = (POLALIAS && POLALIAS[k]) || null;
    if (!cands || !cands.length) return null;
    let pick = null;
    const y = (year == null) ? CUR_YEAR : year;
    // 优先取覆盖该年份的候选；否则取第一个
    for (const c of cands) {
      const e = POLITIES[c.id];
      if (!e) continue;
      if (c.from == null || c.to == null) { if (!pick) pick = e; continue; }
      if (y >= c.from && y <= c.to) { pick = e; break; }
      if (!pick) pick = e;
    }
    return pick ? applySpan(pick, y) : null;
  }
  /* 把实体在该年份的时段“提升”为条目字段，供现有显示逻辑直接使用 */
  function applySpan(e, year) {
    if (!e || !e.spans || !e.spans.length) return e;
    const y = (year == null) ? CUR_YEAR : year;
    let sp = null;
    for (const s2 of e.spans) {
      if ((s2.from == null || y >= s2.from) && (s2.to == null || y <= s2.to)) { sp = s2; break; }
    }
    if (!sp) sp = e.spans[e.spans.length - 1];
    return Object.assign({}, e, {
      zh: sp.zh || e.zh, capital: sp.capital || e.capital,
      summary: sp.summary || e.summary, from: sp.from, to: sp.to,
      sources: (sp.sources && sp.sources.length) ? sp.sources : e.sources,
      span: sp,
    });
  }
  const FACTION = (function () {
    const out = {};
    if (POLITIES) {
      for (const id in POLITIES) {
        const e = POLITIES[id];
        if (!e.color || id.indexOf('world/') === 0) continue;   // 世界实体颜色走 worldColor
        out[id] = { name: e.zh || e.en || id, color: e.color, desc: e.summary || '' };
      }
      return out;
    }
    return DATA.factions || {};
  })();
  const NS = 'http://www.w3.org/2000/svg';
  const $ = s => document.querySelector(s);
  const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
  const el = (t, a) => { const n = document.createElementNS(NS, t); for (const k in (a || {})) n.setAttribute(k, a[k]); return n; };
  /* HTML 元素：el 创建的是 SVG 元素，界面控件必须用 hel（否则没有布局尺寸） */
  const hel = (t, cls) => { const n = document.createElement(t); if (cls) n.className = cls; return n; };
  const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const facOf = f => FACTION[f] || { name: f || '不详', color: '#6b7a8c' };

  /* ---------- 1644—1892：按“入清年份”取省份归属（1893 起走逐月表） ---------- */
  const PRE1893 = DATA.chinaPre1893 || null;
  if (PRE1893 && PRE1893.factions) {
    for (const k in PRE1893.factions) {
      if (!FACTION[k]) FACTION[k] = { name: PRE1893.factions[k].name, color: PRE1893.factions[k].color };
    }
  }
  function facRec(prov, step) {
    if (step >= M0) return at(step)[prov];
    const yr = Math.floor(step / 12);
    // 分朝代（明 1368—1643、清 1644—1892）：按各代“确立统治”年份取归属
    const eras = (PRE1893 && PRE1893.eras) || [];
    const _mi = step;                       // 月序号，用于月级时段判定
    for (const er of eras) {
      const _a = er.from * 12 + ((er.fromM || 1) - 1);
      const _b = er.to * 12 + ((er.toM || 12) - 1);
      if (_mi >= _a && _mi <= _b) {
        // 逐年易主序列优先（如宋辽夏金更替频繁）
        if (er.timeline && er.timeline[prov]) {
          const seq = er.timeline[prov];
          let pick = null;
          for (const it of seq) if (yr >= it[0]) pick = it[1];
          if (pick) return { faction: pick, note: (er.note && er.note[String(pick === 'menggu' ? 1206 : yr)]) || (yr + ' 年') };
          return { faction: er.faction || 'qing', note: '' };
        }
        const ey = er.entryYear ? er.entryYear[prov] : undefined;
        if (ey === undefined) return { faction: 'qing', note: er.name + '朝' };
        const fk = er.faction || (er.name === '明' ? 'ming' : er.name === '元' ? 'yuan' : 'qing');
        if (ey > 0 && yr >= ey) return { faction: fk, note: er.name + '朝统治（' + ey + '年入' + er.name + '）' };
        const pf = er.preFaction && er.preFaction[prov];
        if (pf) return { faction: pf, note: (er.preName[prov] || '') + '（' + er.name + '未及）' };
        return { faction: er.faction || 'qing', note: '' };
      }
    }
    if (PRE1893 && PRE1893.entryYear && PRE1893.entryYear[prov] !== undefined) {
      const ey = PRE1893.entryYear[prov];
      if (yr >= ey) return { faction: 'qing', note: '清朝统治（' + ey + '年入清）' };
      const pf = PRE1893.preFaction[prov];
      if (pf) return { faction: pf, note: (PRE1893.preName[prov] || '') + '（' + ey + '年前）' };
    }
    return { faction: step < 1644 * 12 ? 'ming' : 'qing', note: '' };
  }
  const catOf = c => CAT[c] || { name: c || '其他', color: '#8a9bb0' };

  /* ---------- 1. 时间索引 ---------- */
  const PROVS = Object.keys(GEO.paths);
  const mi = m => ({ y: Math.floor(m / 12), mo: m % 12 + 1 });      // 月份索引 -> {年,月}
  const SI = (y, mo) => y * 12 + (mo - 1);
  const pad2 = n => (n < 10 ? '0' + n : '' + n);

  /* 解析事件日期：得到月/日；无月日者按年中（7月）处理并在界面标注 */
  /* 时间精度标记：仅到年的给出「月份待考」，由正文补出月份的标注来源 */
  function precTag(e) {
    if (e.approx === 'year') return '<i class="prec">月份待考（暂列本年1月）</i>';
    if (e.approx === 'month' && e.timeFrom === 'detail') return '<i class="prec">月份据正文所载</i>';
    return '';
  }
  function parseDate(e) {
    let mo = null, day = null, exact = false;
    const d = e.date || '';
    let m = d.match(/(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})?\s*日?/);
    if (m) { mo = +m[2]; day = m[3] ? +m[3] : null; exact = true; }
    if (mo == null) {
      m = d.match(/(\d{1,2})\s*月/);
      if (m) { mo = +m[1]; exact = true; }
    }
    if (mo == null) {
      m = (e.date || '').match(/(\d{4})\s*年\s*(上|中|下)?半年/);
      if (m) { mo = m[2] === '上' ? 3 : m[2] === '下' ? 10 : 7; exact = true; }
    }
    if (mo == null) {
      // 跨月/跨年区间：取起始月
      m = (e.date || '').match(/(\d{4})\s*年\s*(\d{1,2})\s*月/);
      if (m) { mo = +m[2]; exact = true; }
    }
    if (mo == null) {
      const m2 = (e.date || '').match(/(\d{1,2})\s*[—\-~至]\s*(\d{1,2})\s*月/);
      if (m2) { mo = +m2[1]; exact = true; }
    }
    if (mo == null) mo = 7;
    mo = clamp(mo, 1, 12);
    return { mo, day, exact };
  }


  /* ---------- 几何解码：base64 增量编码 -> SVG 路径（一次性展开，之后照旧用 .d） ---------- */
  const B64CH = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
  function decodeGeom(c) {
    const bytes = [];
    let acc = 0, bits = 0;
    for (let i = 0; i < c.length; i++) {
      const v = B64CH.indexOf(c.charAt(i));
      if (v < 0) continue;
      acc = (acc << 6) | v; bits += 6;
      if (bits >= 8) { bits -= 8; bytes.push((acc >> bits) & 255); }
    }
    let p = 0;
    function rd() {
      let sh = 0, r = 0, b;
      do { b = bytes[p++]; r |= (b & 127) << sh; sh += 7; } while (b & 128);
      return r;
    }
    const unzig = v => (v & 1) ? -((v + 1) >> 1) : (v >> 1);
    let out = '';
    while (p < bytes.length) {
      const n = rd();
      if (!n) break;
      let x = 0, y = 0;
      for (let k = 0; k < n; k++) {
        x += unzig(rd()); y += unzig(rd());
        out += (k ? 'L' : 'M') + (x / 10).toFixed(1) + ' ' + (y / 10).toFixed(1);
      }
      out += 'Z';
    }
    return out;
  }
  /* 把对象树里所有 {c:…} 还原成 .d（对上层代码零侵入） */
  function expandGeom(o, seen) {
    if (!o || typeof o !== 'object') return;
    seen = seen || new Set();
    if (seen.has(o)) return;
    seen.add(o);
    if (typeof o.c === 'string' && o.d === undefined) o.d = decodeGeom(o.c);
    for (const k in o) {
      const v = o[k];
      if (v && typeof v === 'object') expandGeom(v, seen);
    }
  }
  const _tGeom = (performance && performance.now) ? performance.now() : 0;
  expandGeom(GEO);
  if (DATA.world) expandGeom(DATA.world);
  // 这两处上层按“字符串”使用，展开后要还原成字符串本身
  if (GEO.paths) {
    const _p = {};
    for (const k in GEO.paths) {
      const v = GEO.paths[k];
      _p[k] = (typeof v === 'string') ? v : (v.d || decodeGeom(v.c));
    }
    GEO.paths = _p;
  }
  if (GEO.chinaOutline && typeof GEO.chinaOutline === 'object') {
    GEO.chinaOutline = GEO.chinaOutline.d || decodeGeom(GEO.chinaOutline.c);
  }
  window.__GEOM_MS__ = ((performance && performance.now) ? performance.now() : 0) - _tGeom;

  const EV = (DATA.events || []).map(e => {
    // 时间统一由构建期给出（mi 绝对月序号 / approx 精度）；缺失时才回退到字符串解析
    const p = (e.mi === undefined) ? parseDate(e) : { mo: e.mo, day: e.day, exact: true };
    return Object.assign({}, e, {
      mo: (e.mo !== undefined ? e.mo : p.mo),
      day: (e.day !== undefined ? e.day : p.day),
      exactDate: p.exact,
      approx: e.approx || 'month',
    });
  }).sort((a, b) => (a.year - b.year) || (a.mo - b.mo) || ((a.day || 0) - (b.day || 0)));

  const evByMonth = new Map();     // 月索引 -> [事件]
  EV.forEach(e => {
    const k = SI(e.year, e.mo);
    if (!evByMonth.has(k)) evByMonth.set(k, []);
    evByMonth.get(k).push(e);
  });

  /* ---------- 2. 势力归属：年区间 + 月级切点 -> 逐月查表 ---------- */
  const monthMap = (function buildMonths() {
    const out = new Array(NSTEP);
    for (let i = 0; i < NSTEP; i++) out[i] = null;

    function put(m, prov, faction, note) {
      if (m < M0 || m > M1) return;
      const k = m - M0;
      if (!out[k]) out[k] = {};
      out[k][prov] = { faction: faction, note: note };
    }

    // 省级单元名 -> 与地图 path 对齐（数据键即地图键）
    const rows = DATA.provinces || {};
    for (const prov of Object.keys(rows)) {
      for (const seg of rows[prov]) {
        for (let y = Math.max(Y0, seg.from); y <= Math.min(Y1, seg.to); y++) {
          for (let mo = 1; mo <= 12; mo++) put(SI(y, mo), prov, seg.faction, seg.note || '');
        }
      }
    }
    // 月级关键切点覆盖
    const ov = DATA.monthOverride || {};
    const ov2 = {};
    for (const y of Object.keys(ov)) {
      for (const item of ov[y]) {
        const prov = item[0], mo = +item[1], faction = item[2], note = item[3];
        for (let m = SI(+y, mo); m <= SI(+y, 12); m++) put(m, prov, faction, note);
        ((ov2[y] || (ov2[y] = {}))[prov] || (ov2[y][prov] = [])).push({ m: mo, faction: faction, note: note });
      }
    }
    for (const y in ov2) for (const pv in ov2[y]) ov2[y][pv].sort((a, b) => a.m - b.m);
    // 全时间轴「正向填充」：某月无记录时，继承其上一个月（含上一年 12 月）的值。
    // 这样 1949 年 1 月锚点只会向后影响 1—9 月，不会被 10 月的锚点倒灌。
    let carry = {};
    for (let i = 0; i < NSTEP; i++) {
      const cur = out[i];
      for (const prov of PROVS) {
        if (cur[prov]) carry[prov] = cur[prov];
        else if (carry[prov]) cur[prov] = carry[prov];
      }
    }
    // 起点仍为空者（理论上不应出现）用其后的首个记录补齐
    for (let i = 0; i < NSTEP; i++) {
      for (const prov of PROVS) {
        if (out[i][prov]) continue;
        let f = null;
        for (let j = i + 1; j < NSTEP && !f; j++) if (out[j][prov]) f = out[j][prov];
        out[i][prov] = f || { faction: 'unknown', note: '' };
      }
    }
    return out;
  })();

  /* 人物志索引：名称/别名 -> 人物 id */
  const PEOPLE = DATA.people || [];
  const PERSON = {};
  PEOPLE.forEach(pr => { if (pr && pr.id) PERSON[pr.id] = pr; });
  const PERSON_BY_NAME = DATA.personIndex || {};
  const normName = t => String(t || '').replace(/[\s·、，,。：:—\-－“”"\'’！!？?（）()《》]/g, '');
  function personIdOf(name) {
    if (!name) return null;
    const k = normName(name);
    return PERSON_BY_NAME[k] || PERSON_BY_NAME[name] || (PERSON[name] ? name : null);
  }

  /* ---------- 邻国势力：逐年区间 + 月级切点 -> 逐月表（同中国算法） ---------- */
  const NBFAC = DATA.neighborFactions || {};
  const NBDATA = DATA.neighbors || {};
  const NBOV = DATA.neighborMonthOverride || {};
  const neighborMonths = (function buildNeighborMonths() {
    const out = new Array(NSTEP);
    for (let i = 0; i < NSTEP; i++) out[i] = {};
    const put = (m, nm, faction, note) => {
      if (m < M0 || m > M1) return;
      out[m - M0][nm] = { faction: faction, note: note };
    };
    for (const nm of Object.keys(NBDATA)) {
      for (const seg of NBDATA[nm]) {
        for (let y = Math.max(Y0, seg.from); y <= Math.min(Y1, seg.to); y++) {
          for (let mo = 1; mo <= 12; mo++) put(SI(y, mo), nm, seg.faction, seg.note || '');
        }
      }
    }
    for (const y of Object.keys(NBOV)) {
      for (const it of NBOV[y]) {
        for (let m = SI(+y, it[1]); m <= SI(+y, 12); m++) put(m, it[0], it[2], it[3]);
      }
    }
    // 正向填充
    let carry = {};
    for (let i = 0; i < NSTEP; i++) {
      for (const nm of Object.keys(NBDATA)) {
        if (out[i][nm]) carry[nm] = out[i][nm];
        else if (carry[nm]) out[i][nm] = carry[nm];
      }
    }
    return out;
  })();
  const nbfOf = f => NBFAC[f] || { name: f || '—', color: '#4a5568' };
  function neighborsAt(step) { return neighborMonths[clamp(step, M0, M1) - M0] || {}; }

  const state = {
    step: SI(Y0, 1),
    showMarks: true,          // 事件标注常显（不提供隐藏）
    showTerr: true,           // 割据区/根据地常显（不提供隐藏）
    labelsOn: true,           // 地名常显
    view: 'overview',      // overview | event | person
    curEvent: null,
    curPerson: null,
    focus: null,
    playing: false,
    speed: 1400,
    labels: true,
  };
  const at = step => monthMap[clamp(step, M0, M1) - M0];
  const stepInfo = step => mi(clamp(step, M0, M1));

  /* ---------- 3. 地图渲染 ---------- */
  const svg = $('#map'), pz = $('#pz'), provLayer = $('#provLayer'), baseLayer = $('#baseLayer'),
        labelLayer = $('#labelLayer'), sparkLayer = $('#sparkLayer'), dimWrap = $('#dimdimWrap');
  const VB = GEO.viewBox || [0, 0, 1000, 841];
  const provNodes = {}, labelNodes = {}, provCache = {};
  let ssLabelNodes = [];

  for (const name of PROVS) {
    // 说明：陆地图层已用 landLook 滤镜补缝，无需再垫底色（垫底色会与被替换的历史底图冲突）
    const p = el('path', { class: 'prov', d: GEO.paths[name], 'data-name': name, fill: '#4a5a6e' });
    p.addEventListener('click', ev => { ev.stopPropagation(); selectProvince(name, true); });
    p.addEventListener('mouseenter', ev => showProvTip(ev, name));
    p.addEventListener('mousemove', moveTip);
    p.addEventListener('mouseleave', hideTip);
    provLayer.appendChild(p);
    provNodes[name] = p;
    const bb = p.getBBox();
    provCache[name] = { bb: bb, area: bb.width * bb.height, matrix: /(H|V|L)/ };
  }

  /* 周边国家：底图填色（按当年政权/占领方），置于中国之下 */
  const nbNodes = {}, nbLabels = {};
  (function drawNeighbors() {
    const layer = $('#neighborLayer');
    if (!layer) return;
    // 蒙版直接用「省界并集」：邻国正好画到我国省界为止，
    // 既不会像 NE 轮廓那样外溢到国内，也不会与省界之间留下空隙露海色
    {
      const defs = svg.querySelector('defs') || svg.insertBefore(el('defs'), svg.firstChild);
      const mask = el('mask', { id: 'nbMask', maskUnits: 'userSpaceOnUse',
        x: -3000, y: -3000, width: 7000, height: 9000 });
      mask.appendChild(el('rect', { x: -3000, y: -3000, width: 7000, height: 9000, fill: '#fff' }));
      const holes = el('g', { fill: '#000' });
      for (const nm of PROVS) holes.appendChild(el('path', { d: GEO.paths[nm], fill: '#000' }));
      mask.appendChild(holes);
      defs.appendChild(mask);
      layer.setAttribute('mask', 'url(#nbMask)');
    }
    (GEO.neighbors || []).forEach(nb => {
      const p = el('path', { class: 'nb', d: nb.d, fill: '#2a3542', 'fill-rule': 'evenodd',
        'data-name': nb.name });
      layer.appendChild(p);
      nbNodes[nb.name] = p;
      p.addEventListener('mouseenter', ev => showNeighborTip(ev, nb.name));
      p.addEventListener('mousemove', moveTip);
      p.addEventListener('mouseleave', hideTip);
    });
    (GEO.neighbors || []).forEach(nb => {
      if (!nb.label) return;
      const t = el('text', {
        class: 'nblabel',
        transform: 'translate(' + nb.label[0] + ',' + nb.label[1] + ') scale(1)'
      });
      t.dataset.lx = nb.label[0]; t.dataset.ly = nb.label[1];
      t.textContent = nb.name;
      layer.appendChild(t);
      nbLabels[nb.name] = t;
    });
  })();

  /* 割据区 / 根据地：按县组合的跨省区域，叠在省级填色之上 */
  const TERRS = (DATA.territories || []).map(t => ({
    raw: t,
    fromM: SI(t.from[0], t.from[1]),
    toM: SI(t.to[0], t.to[1]),
  }));
  const terrNodes = [];
  (function drawTerritories() {
    const layer = $('#terrLayer');
    if (!layer) return;
    TERRS.forEach(t => {
      const fc = facOf(t.raw.faction).color;
      const p = el('path', {
        class: 'terr', d: t.raw.d, 'fill-rule': 'nonzero',
        fill: fc, stroke: fc, 'data-name': t.raw.name
      });
      p.addEventListener('click', ev => { ev.stopPropagation(); openTerritory(t.raw); });
      p.addEventListener('mouseenter', ev => showTerrTip(ev, t.raw));
      p.addEventListener('mousemove', moveTip);
      p.addEventListener('mouseleave', hideTip);
      layer.appendChild(p);
      // 白边单独一层：由滤镜从 alpha 派生，只描外轮廓
      const line = el('path', {
        class: 'terrline', d: t.raw.d, 'fill-rule': 'nonzero',
        fill: fc, 'data-name': t.raw.name
      });
      layer.appendChild(line);
      const lab = el('text', { class: 'terrlabel' });
      lab.textContent = shortTerrName(t.raw.name);
      if (t.raw.label) {
        lab.dataset.lx = t.raw.label[0];
        lab.dataset.ly = t.raw.label[1];
        lab.setAttribute('transform', 'translate(' + t.raw.label[0] + ',' + t.raw.label[1] + ') scale(1)');
      } else {
        lab.style.display = 'none';
      }
      layer.appendChild(lab);
      terrNodes.push({ t, node: p, label: lab, line: [line] });
    });
    if (TERRS.length) $('#terrLayer').style.display = state.showTerr ? '' : 'none';
  })();
  function shortTerrName(n) {
    return n.replace(/（.*?）/g, '').replace(/革命根据地|抗日根据地|根据地|苏区/g, m => m === '苏区' ? '苏区' : '根据地');
  }
  function terrActive(t, step) { return step >= t.fromM && step <= t.toM; }
  function activeTerritories(step) { return TERRS.filter(t => terrActive(t, step)); }

  /* ---------- 历史区划底图：底图随时期变化（按县级边界合并重建省级单位） ---------- */
  const HISTOBJ = GEO.hist || null;
  const HIST = (HISTOBJ && HISTOBJ.periods) || null;
  const HGEOMS = (HISTOBJ && HISTOBJ.geoms) || [];
  const HSHAPES = (HISTOBJ && HISTOBJ.shapes) || [];
  const periodLayers = new Map();      // 时期下标 -> <g class=periodLayer>
  let histApplied = -1, curLayer = null;

  const MONTH_DIV = (HISTOBJ && HISTOBJ.monthDiv) || null;
  const MONTH_DIV_M0 = (HISTOBJ && HISTOBJ.monthDivM0) || 0;
  function histGeomId(step) {
    if (MONTH_DIV && step >= MONTH_DIV_M0 && step < MONTH_DIV_M0 + MONTH_DIV.length) {
      return MONTH_DIV[step - MONTH_DIV_M0];
    }
    if (!HIST) return -1;
    for (let i = 0; i < HIST.length; i++) {
      if (step >= HIST[i].fromM && step <= HIST[i].toM) return HIST[i].geom;
    }
    return -1;
  }
  function histPeriodIndex(step) {
    if (!HIST) return -1;
    for (let i = 0; i < HIST.length; i++) {
      if (step >= HIST[i].fromM && step <= HIST[i].toM) return i;
    }
    return -1;
  }
  /* 该现行省份在当前时期是否已被历史区划替换（替换后连地名一并隐藏） */
  function isReplaced(p) {
    const idx = histPeriodIndex(state.step);
    if (idx < 0) return false;
    return HIST[idx].replace.indexOf(p) >= 0;
  }
  /* 构建（或复用）某一时期的整层地图，超出窗口的层会被销毁 —— 常驻不超过 3 层 */
  function buildPeriodLayer(idx) {
    if (periodLayers.has(idx)) return periodLayers.get(idx);
    const per = HIST[idx];
    const g = el('g', { class: 'periodLayer', 'data-period': idx });
    g._items = [];
    histUnitsOf(per).forEach(unitKey => {
      const sh = histShapeOf(per, unitKey);
      if (!sh || !sh.d) return;
      const name = (per.shapeNames && per.shapeNames[unitKey]) || unitKey;
      const node = el('path', {
        class: 'hprov', d: sh.d, 'fill-rule': 'nonzero',
        'data-name': name, 'data-unit': unitKey, fill: '#4a5a6e'
      });
      node.addEventListener('click', ev => {
        ev.stopPropagation();
        if (GEO.paths[unitKey]) selectProvince(unitKey, true);
        else { drawer.classList.add('open'); openHistorical(unitKey, name); }
      });
      node.addEventListener('mouseenter', ev => showHistTip(ev, unitKey, name));
      node.addEventListener('mousemove', moveTip);
      node.addEventListener('mouseleave', hideTip);
      g.appendChild(node);
      const t = el('text', { class: 'provname hname' });
      const tn = el('tspan', { class: 'nm' }); tn.textContent = name;
      const tc = el('tspan', { class: 'cnt' });
      t.appendChild(tn); t.appendChild(tc);
      if (sh.label) {
        t.dataset.lx = sh.label[0]; t.dataset.ly = sh.label[1];
        t.setAttribute('transform', 'translate(' + sh.label[0] + ',' + sh.label[1] + ') scale(1)');
      }
      g.appendChild(t);
      g._items.push({ node, label: t, unitKey, name });
    });
    $('#histLayer').appendChild(g);
    periodLayers.set(idx, g);
    pruneLayers(idx);
    return g;
  }
  /* 只保留当前、前一期、后一期三层 */
  function pruneLayers(idx) {
    for (const k of Array.from(periodLayers.keys())) {
      if (Math.abs(k - idx) > 1) {
        const g = periodLayers.get(k);
        if (g && g.parentNode) g.parentNode.removeChild(g);
        periodLayers.delete(k);
      }
    }
  }
  /* 切换时期：新层淡入、旧层淡出，过渡自然；不重建 DOM */
  function showPeriodLayer(idx) {
    const next = buildPeriodLayer(idx);
    const prev = curLayer === next ? null : curLayer;
    next.style.transition = 'none';
    next.style.opacity = '0';
    next.style.display = '';
    // 强制一次样式计算，保证过渡生效
    void next.getBoundingClientRect();
    next.style.transition = 'opacity .5s ease';
    next.style.opacity = '1';
    if (prev) {
      prev.style.transition = 'opacity .5s ease';
      prev.style.opacity = '0';
      setTimeout(() => { if (prev !== curLayer) prev.style.display = 'none'; }, 520);
    }
    curLayer = next;
  }
  function applyHistorical(step) {
    if (!HIST) return;
    const idx = histPeriodIndex(step);
    if (idx === histApplied) return;
    // 恢复上一时期隐藏的现行省份
    if (histApplied >= 0) {
      for (const p of HIST[histApplied].replace) {
        if (provNodes[p]) provNodes[p].style.display = '';
        if (labelNodes[p]) labelNodes[p].style.display = '';
      }
    }
    histApplied = idx;
    if (idx < 0) { if (curLayer) { curLayer.style.display = 'none'; } return; }
    const per = HIST[idx];
    for (const p of per.replace) {
      if (provNodes[p]) provNodes[p].style.display = 'none';
      if (labelNodes[p]) labelNodes[p].style.display = 'none';
    }
    showPeriodLayer(idx);
  }
  function histUnitsOf(per) {
    const g = (per && per.geom != null) ? HGEOMS[per.geom] : null;
    return g ? Object.keys(g) : [];
  }
  /* 取历史单位当月的势力记录：优先规范键，其次 factionFrom 兜底键，再次显示名 */
  function histRec(per, unitKey, name) {
    const m = at(state.step);
    let rec = m[unitKey];
    if (!rec && per && per.factionFrom && per.factionFrom[unitKey]) rec = m[per.factionFrom[unitKey]];
    if (!rec && name) rec = m[name];
    return rec || null;
  }
  function histShapeOf(per, unitKey) {
    const g = (per && per.geom != null) ? HGEOMS[per.geom] : null;
    if (!g || g[unitKey] === undefined) return null;
    return HSHAPES[g[unitKey]] || null;
  }
  function showHistTip(ev, unitKey, name) {
    const per = HIST[histPeriodIndex(state.step)];
    const rec = histRec(per, unitKey, name);
    const fi = facOf(rec && rec.faction);
    const { y, mo } = stepInfo(state.step);
    tip.innerHTML = '<b>' + esc(name) + '</b> · ' + y + '年' + mo + '月<br>' +
      '<span class="s">政权：</span><span style="color:' + fi.color + '">' + esc(fi.name) + '</span>' +
      (per ? '<br><span class="s">本时期：' + esc(per.label) + '</span>' : '') +
      ((rec && rec.note) ? '<br><span class="s">' + esc(rec.note) + '</span>' : '');
    tip.style.opacity = 1; moveTip(ev);
  }
  /* 历史区划单位详情（仅对已消亡的单位，如热河省） */
  function openHistorical(unitKey, name) {
    const pi = histPeriodIndex(state.step);
    if (pi < 0) return;
    state.curHist = { unitKey: unitKey, name: name || unitKey, period: HIST[pi] };
    state.view = 'hist';
    state.curEvent = null; state.curTerr = null; state.curPerson = null;
    drawer.classList.add('open');
    renderDrawer();
    const b = $('#dbody'); if (b) b.scrollTop = 0;
  }
  function renderHistView() {
    const h = state.curHist, body = $('#dbody');
    const rec = histRec(h.period, h.unitKey, h.name) || { faction: 'unknown', note: '' };
    const fi = facOf(rec.faction);
    const { y, mo } = stepInfo(state.step);
    const sh = histShapeOf(h.period, h.unitKey);
    body.innerHTML = '';
    head('历史区划单位', esc(h.name),
      '<span>' + y + '年' + mo + '月</span><span>' + esc(h.period.label) + '</span>',
      '<span class="faction"><span class="sw" style="background:' + fi.color + '"></span>' + esc(fi.name) + '</span>');
    body.appendChild(backBar('返回'));
    const n = document.createElement('div');
    n.className = 'note';
    n.textContent = '本时期省级区划：' + h.period.label + '。' + (h.period.note || '');
    body.appendChild(n);
    if (rec.note) body.appendChild(note('归属依据：' + rec.note));
    body.appendChild(hintLine('说明：历史省界由现行县级边界合并近似重建，县级以下差异未作细分。'));
    wireInternalLinks(body);
  }


  /* 中国轮廓底色（置于邻国层之下）：NE 的中国轮廓比 DataV 省界略大，
     两者之间会有一条边界带；补成陆地底色，避免看起来像海面破洞 */
  (function landBackdrop() {
    const layer = $('#cnBaseLayer');
    if (layer && GEO.chinaOutline) {
      layer.appendChild(el('path', { d: GEO.chinaOutline, fill: '#2a3542', 'fill-rule': 'nonzero' }));
    }
  })();

  const dimPath = el('path', { id: 'dimdim', d: '' });
  dimWrap.appendChild(dimPath);

  const SMALL = { 北京: 1, 天津: 1, 上海: 1, 香港: 1, 澳门: 1, 宁夏: 1, 海南: 1, 台湾: 1 };
  /* 小地块（直辖市/特区）标注外移，避免相邻标签互相压字 */
  const LABEL_OFF = {
    北京: [4, -15], 天津: [18, 9], 上海: [20, 2], 香港: [17, 8], 澳门: [-18, 8],
    宁夏: [-8, -4], 海南: [2, 13], 台湾: [12, -4],
  };
  for (const name of PROVS) {
    const c = GEO.centroids[name];
    if (!c) continue;
    const off = LABEL_OFF[name] || [0, 0];
    const lx = Math.round(c[0] + off[0]), ly = Math.round(c[1] + off[1]);
    const t = el('text', {
      class: 'provname' + (SMALL[name] ? ' minor' : ''),
      transform: 'translate(' + lx + ',' + ly + ') scale(1)'
    });
    t.dataset.lx = lx; t.dataset.ly = ly;
    t.dataset.name = name;
    const tn = el('tspan', { class: 'nm' }); tn.textContent = name;
    const tc = el('tspan', { class: 'cnt' });
    t.appendChild(tn); t.appendChild(tc);
    labelLayer.appendChild(t);
    labelNodes[name] = t;
  }

  /* 南海诸岛：直接画在主画布内（海南岛正南，与主图等比例，可拖动查看） */
  (function drawSouthSea() {
    const ss = GEO.southSea;
    if (!ss) return;
    const g = el('g', { id: 'southSea', 'pointer-events': 'none' });
    // 与本土的示意连线
    if (ss.connector && ss.connector.length === 2) {
      const [a, b] = ss.connector;
      g.appendChild(el('line', {
        x1: a[0], y1: a[1], x2: b[0], y2: b[1],
        stroke: '#3d597a', 'stroke-width': 1,
        'stroke-dasharray': '3 5', opacity: .8
      }));
    }
    // 礁岛点
    (ss.dots || []).forEach(d => g.appendChild(el('circle', {
      cx: d[0], cy: d[1], r: 1.2, fill: '#8fb6d4'
    })));
    // 南海诸岛界线：仅在提供权威矢量数据（data/nine_dash.json）时绘制
    (ss.nineDash || []).forEach(d => g.appendChild(el('path', {
      d: d, fill: 'none', stroke: '#d9ac48', 'stroke-width': 2.6,
      'stroke-linecap': 'round', 'stroke-linejoin': 'round'
    })));
    // 岛群标注：缩放到一定程度才显示，避免与周边国家名称互相压字
    ssLabelNodes = [];
    (ss.labels || []).forEach(l => {
      const t = el('text', {
        x: l.p[0], y: l.p[1], 'font-size': 9.5, fill: '#9db4cc', 'text-anchor': 'middle'
      });
      t.textContent = l.name; g.appendChild(t);
      ssLabelNodes.push(t);
    });
    // 区域标题
    if (ss.titlePos) {
      const t = el('text', {
        x: ss.titlePos[0], y: ss.titlePos[1], 'font-size': 13, fill: '#d9ac48',
        'letter-spacing': 3, 'text-anchor': 'start'
      });
      t.textContent = '南海诸岛'; g.appendChild(t);
    }
    $('#southSeaLayer').appendChild(g);
  })();

  /* ---------- 4. 视图：缩放 / 拖动 / 聚焦 ---------- */
  const view = { k: 1, x: 0, y: 0 };
  let lastFilterK = 0;
  function tuneLandFilter() {
    if (Math.abs(view.k - lastFilterK) / Math.max(0.001, lastFilterK) < 0.08) return;
    lastFilterK = view.k;
    const f = document.querySelector('#landLook');
    if (!f) return;
    const k = clamp(view.k, 0.5, 20);
    const mo = f.querySelectorAll('feMorphology');
    if (mo[0]) mo[0].setAttribute('radius', (0.85 / k).toFixed(3));
    if (mo[1]) mo[1].setAttribute('radius', (1.55 / k).toFixed(3));
    const bl = f.querySelector('feGaussianBlur');
    if (bl) bl.setAttribute('stdDeviation', (1.1 / k).toFixed(3));
    const tr = document.querySelector('#terrRing feMorphology');
    if (tr) tr.setAttribute('radius', (1.5 / k).toFixed(3));
  }
  let _lastWLabelK = 0;
  function applyView(anim) {
    pz.style.transition = anim ? 'transform .72s cubic-bezier(.22,.85,.24,1), opacity .3s' : 'none';
    pz.style.transform = 'translate(' + view.x.toFixed(2) + 'px,' + view.y.toFixed(2) + 'px) scale(' + view.k.toFixed(4) + ')';
    tuneLandFilter();
    scaleLabels();
    // 世界标签随缩放重排（跨过阈值才重算，避免拖动时频繁布局）
    if (document.body.classList.contains('world-mode') || (STEPS[state.ti] || {}).kind === 'cny') {
      if (Math.abs(Math.log(view.k / (_lastWLabelK || view.k))) > 0.22) {
        _lastWLabelK = view.k;
        layoutWorldLabels();
      }
    }
  }
  /* 地名随缩放变化：屏幕字号按 k^0.35 轻微增长（在组变换内反向补偿 k^-0.65） */
  function scaleLabels() {
    ssLabelNodes.forEach(t => { t.style.display = view.k >= 1.5 ? '' : 'none'; });
    const s = Math.pow(clamp(view.k, 0.4, 30), -0.65);
    const txt = 'translate(%x%,%y%) scale(' + s.toFixed(4) + ')';
    for (const k in labelNodes) {
      const n = labelNodes[k];
      n.setAttribute('transform', txt.replace('%x%', n.dataset.lx).replace('%y%', n.dataset.ly));
    }
    for (const k in nbLabels) {
      const n = nbLabels[k];
      n.setAttribute('transform', txt.replace('%x%', n.dataset.lx).replace('%y%', n.dataset.ly));
    }
    if (HIST && curLayer && curLayer._items) {
      curLayer._items.forEach(x => {
        const rec = histRec(HIST[histApplied], x.unitKey, x.name);
        const fi = facOf(rec && rec.faction);
        const belong = GEO.paths[x.unitKey] ? x.unitKey : null;   // 与现行省份对应者参与聚焦判断
        const dim = state.focus && belong && state.focus !== belong;
        x.node.setAttribute('fill', fi.color);
        x.node.setAttribute('stroke', fi.color);       // 同色描边盖住县界缝隙
        // 拼接形状用不透明填充与描边：半透明会让同色描边显出县界轮廓
        x.node.setAttribute('fill-opacity', dim ? .4 : 1);
        x.node.setAttribute('stroke-opacity', dim ? .4 : 1);
        x.label.style.display = dim ? 'none' : '';
      });
    }
    if (HIST && curLayer && curLayer._items) {
      curLayer._items.forEach(x => {
        if (x.label.dataset.lx === undefined) return;
        x.label.setAttribute('transform',
          txt.replace('%x%', x.label.dataset.lx).replace('%y%', x.label.dataset.ly));
      });
    }
    terrNodes.forEach(x => {
      if (x.label.dataset.lx === undefined) return;
      x.label.setAttribute('transform',
        txt.replace('%x%', x.label.dataset.lx).replace('%y%', x.label.dataset.ly));
    });
  }
  /* 实际可见的 viewBox 窗口（preserveAspectRatio: meet） */
  function vpRect() {
    const r = $('#stage').getBoundingClientRect();
    const ar = r.width / Math.max(1, r.height), vr = VB[2] / VB[3];
    let vw, vh;
    if (ar > vr) { vh = VB[3]; vw = VB[3] * ar; } else { vw = VB[2]; vh = VB[2] / ar; }
    return { vw: vw, vh: vh, ox: (VB[2] - vw) / 2, oy: (VB[3] - vh) / 2, r: r };
  }
  function focusOn(name) {
    const b = provCache[name].bb;
    const vp = vpRect();
    const pad = 1.5, minK = 2.1, maxK = 15;
    const k = clamp(Math.min(vp.vw / (b.width * pad), vp.vh / (b.height * pad)), minK, maxK);
    const cx = b.x + b.width / 2, cy = b.y + b.height / 2;
    view.k = k;
    view.x = vp.ox + vp.vw / 2 - cx * k;
    view.y = vp.oy + vp.vh / 2 - cy * k;
    applyView(true);
  }
  /* 让指定矩形填满视口 */
  function fitRect(rect, pad) {
    pad = pad || 1.0;
    const vp = vpRect();
    const w = rect[2], h = rect[3];
    const k = clamp(Math.min(vp.vw / (w * pad), vp.vh / (h * pad)), 0.6, 15);
    view.k = k;
    view.x = vp.ox + vp.vw / 2 - (rect[0] + w / 2) * k;
    view.y = vp.oy + vp.vh / 2 - (rect[1] + h / 2) * k;
    applyView(true);
  }
  function resetView() {
    const st = STEPS[state.ti];
    const inCn = !st || st.kind === 'cn';
    fitRect((inCn ? GEO.core : GEO.world) || GEO.world || [0, 0, 1000, 841], 1.02);
  }
  function viewSouthSea() {
    const ss = GEO.southSea; if (!ss) return;
    let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    const pts = [].concat((ss.dots || []),
                          (ss.labels || []).map(l => l.p), (ss.titlePos ? [ss.titlePos] : []));
    pts.forEach(p => { x0 = Math.min(x0, p[0]); y0 = Math.min(y0, p[1]); x1 = Math.max(x1, p[0]); y1 = Math.max(y1, p[1]); });
    fitRect([x0 - 34, y0 - 34, x1 - x0 + 68, y1 - y0 + 68], 0.95);
  }

  svg.addEventListener('wheel', e => {
    e.preventDefault();
    const vp = vpRect(), r = vp.r;
    const px = (e.clientX - r.left) / r.width, py = (e.clientY - r.top) / r.height;
    const ux = vp.ox + px * vp.vw, uy = vp.oy + py * vp.vh;
    const wx = (ux - view.x) / view.k, wy = (uy - view.y) / view.k;
    view.k = clamp(view.k * Math.pow(0.9986, e.deltaY), 1, 24);
    view.x = ux - wx * view.k; view.y = uy - wy * view.k;
    applyView(false);
  }, { passive: false });

  let drag = null, moved = false;
  // 注意：只有在真正开始拖动后才 setPointerCapture。
  // 否则 pointerup 会被 <svg> 抢走，click 事件将落在背景而非省份上，导致点击无响应。
  svg.addEventListener('pointerdown', e => {
    drag = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y, id: e.pointerId, active: false };
    moved = false;
  });
  svg.addEventListener('pointermove', e => {
    if (!drag) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (!drag.active) {
      if (Math.abs(dx) + Math.abs(dy) <= 4) return;      // 阈值内视为点击，不进入拖动
      drag.active = true; moved = true;
      svg.classList.add('dragging');
      try { svg.setPointerCapture(drag.id); } catch (_) {}
    }
    const vp = vpRect();
    const sx = vp.vw / vp.r.width, sy = vp.vh / vp.r.height;
    view.x = drag.vx + dx * sx; view.y = drag.vy + dy * sy;
    applyView(false);
  });
  ['pointerup', 'pointercancel'].forEach(t => svg.addEventListener(t, e => {
    if (!drag) return;
    if (drag.active) {
      try { svg.releasePointerCapture(drag.id); } catch (_) {}
    }
    drag = null; svg.classList.remove('dragging');
  }));
  /* 双击地图空白处：回到全国视野（取代原「复位/全国」按钮） */
  svg.addEventListener('dblclick', e => {
    if (e.target.closest && (e.target.closest('.prov') || e.target.closest('.spark') || e.target.closest('.terr'))) return;
    clearSelection();
  });
  svg.addEventListener('click', e => {
    if (moved) return;
    if (e.target.closest && (e.target.closest('.prov') || e.target.closest('.spark'))) return;
    if (!state.focus && state.view === 'overview') return;
    // 只收起选中态与侧栏，保留用户当前的缩放与位置
    state.focus = null;
    state.view = 'overview'; state.curEvent = null; state.curPerson = null;
    for (const p in provNodes) provNodes[p].classList.remove('sel');
    dimPath.classList.remove('on');
    drawer.classList.remove('open');
    paintMap(); renderDrawer();
  });

  /* ---------- 5. 详情抽屉 ---------- */
  const drawer = $('#drawer');
  /* 侧栏宽度：可拖动调整，上限为页面宽度的一半 */
  const DW = { min: 320, def: 400, cur: 400 };
  function setDrawerWidth(px) {
    const max = Math.max(DW.min, Math.floor(window.innerWidth * 0.5));
    DW.cur = Math.round(clamp(px, DW.min, max));
    drawer.style.setProperty('--dw', DW.cur + 'px');
    const tab = $('#drawerTab');
    if (tab) tab.style.right = (drawer.classList.contains('open') ? DW.cur : 0) + 'px';
  }
  /* 右侧拉手：展开 / 收起侧栏 */
  (function drawerTab() {
    const tab = $('#drawerTab');
    if (!tab) return;
    const sync = () => {
      const open = drawer.classList.contains('open');
      tab.classList.toggle('open', open);
      tab.style.right = (open ? DW.cur : 0) + 'px';
      tab.title = open ? '收起侧栏' : '展开侧栏（当前时间点的全国事件）';
    };
    tab.addEventListener('click', e => {
      e.stopPropagation();
      if (drawer.classList.contains('open')) {
        drawer.classList.remove('open');
      } else {
        drawer.classList.add('open');
        if (!state.focus && state.view === 'overview') renderDrawer();
      }
      sync();
      setTimeout(sync, 480);
    });
    const mo = new MutationObserver(sync);
    mo.observe(drawer, { attributes: true, attributeFilter: ['class'] });
    sync();
  })();
  /* 图例面板折叠 */
  (function legendPanel() {
    const p = $('#legendPanel'), h = $('#lpHead');
    if (!p || !h) return;
    h.addEventListener('click', () => p.classList.toggle('collapsed'));
  })();
  (function drawerResize() {
    setDrawerWidth(DW.def);
    const grip = $('#grip');
    if (!grip) return;
    let dragging = false;
    grip.addEventListener('pointerdown', e => {
      dragging = true; e.preventDefault();
      try { grip.setPointerCapture(e.pointerId); } catch (_) {}
      document.body.style.cursor = 'col-resize';
    });
    grip.addEventListener('pointermove', e => {
      if (!dragging) return;
      setDrawerWidth(window.innerWidth - e.clientX);
    });
    ['pointerup', 'pointercancel'].forEach(t => grip.addEventListener(t, e => {
      dragging = false; document.body.style.cursor = '';
      try { grip.releasePointerCapture(e.pointerId); } catch (_) {}
    }));
    window.addEventListener('resize', () => setDrawerWidth(DW.cur));
  })();
  function srcHtml(e) {
    const ss = e.sources || [];
    if (!ss.length) return '';
    const links = ss.map(s => {
      const u = String(s.u || '').trim();
      const t = esc(s.t || u);
      if (!/^https?:\/\//i.test(u)) return '<span class="src dead">' + t + '</span>';
      return '<a class="src" href="' + esc(u) + '" target="_blank" rel="noopener noreferrer" ' +
        'title="' + esc(u) + '">' + t + '<i>↗</i></a>';
    }).join('');
    return '<div class="srcline"><span class="srck">来源</span>' + links + '</div>';
  }
  function evCard(e, hl) {
    const ci = catOf(e.category);
    const d = document.createElement('div');
    d.className = 'ev' + (hl ? ' open' : '');
    d.style.borderLeftColor = ci.color;
    d.innerHTML =
      '<h4><span class="dot" style="background:' + ci.color + '"></span>' + esc(e.title) + '</h4>' +
      (e.scope === 'nation' ? '<i class="scope">全国</i>' : '') +
      '<div class="date">' + esc(e.date || (e.year + '年')) + precTag(e) + (e.place ? ' · ' + esc(e.place) : '') +
      ' <span class="tag" style="border-color:' + ci.color + '66;color:' + ci.color + '">' + esc(ci.name) + '</span>' +
      (e.exactDate ? '' : '<span class="tag" title="原资料仅记年月，未标具体月份">月份待考</span>') + '</div>' +
      '<p>' + esc(e.summary || '') + '</p>' +
      (e.detail ? '<div class="detail">' + esc(e.detail) + '</div>' : '') +
      ((e.tags && e.tags.length) ? '<div class="tags">' + e.tags.map(t => '<span class="tag">' + esc(t) + '</span>').join('') + '</div>' : '') +
      srcHtml(e);
    d.addEventListener('click', ev => { if (ev.target.closest && ev.target.closest('a')) return; openEvent(e); });
    return d;
  }
  function renderDrawer() {
    if (state.view === 'event' && state.curEvent) return renderEventView();
    if (state.view === 'person' && state.curPerson) return renderPersonView();
    if (state.view === 'territory' && state.curTerr) return renderTerritoryView();
    if (state.view === 'hist' && state.curHist) return renderHistView();
    if (state.view === 'wevent' && state.curWEV) return renderWorldEventView();
    if (state.view === 'world' && state.curWorld) return renderWorldView();
    if (state.view === 'about') return renderAboutView();
    return renderOverview();
  }

  function head(cat, title, metaHtml, factionHtml) {
    $('#dCat').innerHTML = cat;
    $('#dTitle').innerHTML = title;
    $('#dMeta').innerHTML = metaHtml || '';
    $('#dFaction').innerHTML = factionHtml || '';
  }

  /* ---- 全国视野 / 省级视野 ---- */
  function renderOverview() {
    const { y, mo } = stepInfo(state.step);
    const body = $('#dbody');
    body.innerHTML = '';
    const nowList = evByMonth.get(state.step) || [];
    if (!state.focus) {
      head('全国视野', y + '年' + mo + '月 · 中华大地', '');
      const m = at(state.step), tal = {};
      PROVS.forEach(p => { const f = (m[p] || {}).faction; if (f) tal[f] = (tal[f] || 0) + 1; });
      const top = Object.keys(tal).sort((a, b) => tal[b] - tal[a]).slice(0, 3);
      $('#dMeta').innerHTML = '<span>省级单元 ' + PROVS.length + ' 个</span><span>本月势力 ' +
        Object.keys(tal).length + ' 个</span><span>' + top.map(k => esc(facOf(k).name) + ' ' + tal[k]).join(' · ') + '</span>';
      if (!nowList.length) {
        const near = EV.filter(e => Math.abs(SI(e.year, e.mo) - state.step) <= 2);
        if (!near.length) {
          body.innerHTML = '<div class="empty">' + y + '年' + mo + '月暂无收录事件<br>' +
            '<span style="font-size:12px">拖动下方时间轴继续浏览，或点击地块查看该省大事</span></div>';
          return;
        }
        body.appendChild(sec('前后两月'));
        near.forEach(e => body.appendChild(evCard(e)));
        return;
      }
      body.appendChild(sec('本月大事 · ' + nowList.length + ' 件'));
      nowList.forEach(e => body.appendChild(evCard(e)));
      body.appendChild(hintLine('点击任一事件，右侧展开完整说明（时间 · 势力 · 相关人物 · 时间线 · 影响）'));
      return;
    }
    const f = facRec(state.focus, state.step) || { faction: 'unknown', note: '' };
    const fi = facOf(f.faction);
    const allLocal = EV.filter(e => (e.provinces || []).includes(state.focus));
    head('区域详情 · 逐月势力', esc(state.focus),
      '<span>' + y + '年' + mo + '月</span><span>累计收录 ' + allLocal.length + ' 件</span>',
      '<span class="faction"><span class="sw" style="background:' + fi.color + '"></span>' +
      y + '年' + mo + '月归属：' + esc(fi.name) + '</span>' +
      (fi.desc ? '<div class="fdesc">' + esc(fi.desc) + '</div>' : ''));
    if (f.note) body.appendChild(note('归属依据：' + f.note));
    const sameMonth = allLocal.filter(e => SI(e.year, e.mo) === state.step);
    const nearby = allLocal.filter(e => { const k = SI(e.year, e.mo); return k !== state.step && Math.abs(k - state.step) <= 6; })
      .sort((a, b) => Math.abs(SI(a.year, a.mo) - state.step) - Math.abs(SI(b.year, b.mo) - state.step));
    body.appendChild(sec(y + '年' + mo + '月 · 该地事件'));
    if (sameMonth.length) sameMonth.forEach(e => body.appendChild(evCard(e, true)));
    else {
      const d = document.createElement('div');
      d.className = 'empty'; d.style.padding = '16px'; d.textContent = '本月该地无重大事件';
      body.appendChild(d);
    }
    if (nearby.length) {
      body.appendChild(sec('前后半年'));
      nearby.slice(0, 16).forEach(e => body.appendChild(evCard(e)));
    } else if (!sameMonth.length && allLocal.length) {
      // 当月与前后半年都没有事件时，列出该地时间上最近的若干件，保证面板始终有内容
      const near = allLocal.slice()
        .sort((a, b) => Math.abs(SI(a.year, a.mo) - state.step) - Math.abs(SI(b.year, b.mo) - state.step))
        .slice(0, 10);
      body.appendChild(sec('该地历年重要事件（距当前时间最近）'));
      near.forEach(e => {
        const c = evCard(e);
        const y = document.createElement('div');
        y.className = 'evyear';
        y.textContent = e.year + '年' + e.mo + '月';
        c.insertBefore(y, c.firstChild);
        body.appendChild(c);
      });
      body.appendChild(hintLine('拖动时间轴到对应年月，即可看到该事件在地图上的位置'));
    }
    const here = activeTerritories(state.step).filter(t => (t.raw.provs || []).includes(state.focus));
    const natHere = (evByMonth.get(state.step) || []).filter(e => e.scope === 'nation');
    if (here.length) {
      body.appendChild(sec('本月该省的割据区 / 根据地'));
      const wrap = document.createElement('div');
      wrap.className = 'evlinks';
      here.forEach(t => {
        const a = document.createElement('a');
        a.className = 'evlink';
        a.textContent = t.raw.name + '（所辖 ' + t.raw.counties.length + ' 县）';
        a.addEventListener('click', ev => { ev.preventDefault(); openTerritory(t.raw); });
        wrap.appendChild(a);
      });
      body.appendChild(wrap);
    }
    const changes = factionTimeline(state.focus);
    if (changes.length) {
      body.appendChild(sec('该地势力变迁'));
      const wrap = document.createElement('div');
      wrap.className = 'ftl';
      changes.forEach(c => {
        const fi2 = facOf(c.faction);
        const row = document.createElement('div');
        row.className = 'ftlrow';
        row.innerHTML = '<span class="sw" style="background:' + fi2.color + '"></span>' +
          '<span class="t">' + c.from + ' — ' + c.to + '</span><span class="n">' + esc(fi2.name) + '</span>';
        row.title = c.note || '';
        row.addEventListener('click', () => setStep(SI(c.fromY, c.fromM), true));
        wrap.appendChild(row);
      });
      body.appendChild(wrap);
    }
  }

  /* ---- 二级：事件详情 ---- */
  function figChips(names) {
    if (!names || !names.length) return '';
    return '<div class="figs">' + names.map(n => {
      const id = personIdOf(n);
      return id
        ? '<a class="fig" data-person="' + esc(id) + '" title="查看 ' + esc(n) + ' 生平">' + esc(n) + '</a>'
        : '<span class="fig dead" title="暂无人物志条目">' + esc(n) + '</span>';
    }).join('') + '</div>';
  }
  function renderEventView() {
    const e = state.curEvent, ci = catOf(e.category), dp = e.deep || {};
    const body = $('#dbody');
    body.innerHTML = '';
    const y = e.year, mo = e.mo;
    const provs = (e.provinces || []);
    head('事件详情',
      esc(e.title),
      '<span>' + esc(e.date || (y + '年')) + precTag(e) + '</span>' +
      (e.place ? '<span>' + esc(e.place) + '</span>' : '') +
      (provs.length ? '<span>' + provs.join('、') + '</span>' : '') +
      '<span class="tag" style="border-color:' + ci.color + '66;color:' + ci.color + '">' + esc(ci.name) + '</span>');

    // 当时势力（按事件相关省份逐省列出）
    const facHtml = provs.slice(0, 4).map(p => {
      const f = at(SI(y, mo))[p];
      if (!f) return '';
      const fi = facOf(f.faction);
      return '<span class="faction"><span class="sw" style="background:' + fi.color + '"></span>' +
        p + '：' + esc(fi.name) + '</span>';
    }).join('');
    $('#dFaction').innerHTML = facHtml
      ? '<div class="facRow">' + facHtml + '</div>'
      : (dp.forcesAtTime ? '<span class="faction">' + esc(dp.forcesAtTime) + '</span>' : '');

    body.appendChild(backBar('返回'));
    if (dp.forcesAtTime) body.appendChild(note('势力态势：' + dp.forcesAtTime));
    if (e.summary) { const p = document.createElement('p'); p.className = 'lead'; p.textContent = e.summary; body.appendChild(p); }
    if (e.detail) { const d = document.createElement('div'); d.className = 'evtext'; d.textContent = e.detail; body.appendChild(d); }

    if (dp.timeline && dp.timeline.length) {
      body.appendChild(sec('事件时间线'));
      const ul = document.createElement('div');
      ul.className = 'tline';
      dp.timeline.forEach(x => {
        const li = document.createElement('div');
        li.className = 'tli';
        li.innerHTML = '<span class="td">' + esc(x.d || '') + '</span><span class="tt">' + esc(x.t || '') + '</span>';
        ul.appendChild(li);
      });
      body.appendChild(ul);
    }
    if (dp.impact) body.appendChild(kv('造成的影响', dp.impact));
    if (dp.figures && dp.figures.length) {
      body.appendChild(sec('相关人物'));
      const wrap = document.createElement('div');
      wrap.innerHTML = figChips(dp.figures);
      body.appendChild(wrap.firstChild);
    }
    if (e.tags && e.tags.length) {
      body.appendChild(sec('关键词'));
      const t = document.createElement('div');
      t.className = 'tags';
      t.innerHTML = e.tags.map(x => '<span class="tag">' + esc(x) + '</span>').join('');
      body.appendChild(t);
    }
    body.appendChild(srcBlock(e));
    wireInternalLinks(body);
  }

  /* ---- 三级：人物生平 ---- */
  function renderPersonView() {
    const pr = state.curPerson, body = $('#dbody');
    body.innerHTML = '';
    const campName = { qing: '清廷与清末', beiyang: '北洋与军阀', gmd: '国民政府', cpc: '中国共产党', japan: '日伪与日本方面', other: '其他' };
    head('人物生平', esc(pr.name),
      '<span>' + esc(pr.life || '') + '</span><span>' + esc(campName[pr.camp] || '') + '</span>' +
      (pr.alias ? '<span>别名：' + esc(pr.alias) + '</span>' : ''));
    $('#dFaction').innerHTML = pr.role ? '<span class="faction">' + esc(pr.role) + '</span>' : '';
    body.appendChild(backBar(state.focus ? ('返回 ' + state.focus) : '返回'));
    if (pr.summary) { const p = document.createElement('p'); p.className = 'lead'; p.textContent = pr.summary; body.appendChild(p); }
    if (pr.bio) { const d = document.createElement('div'); d.className = 'evtext'; d.textContent = pr.bio; body.appendChild(d); }
    const names = pr.events || [];
    if (names.length) {
      body.appendChild(sec('相关事件（可点击跳转）'));
      const wrap = document.createElement('div');
      wrap.className = 'evlinks';
      names.forEach(n => {
        const e = matchEvent(n, pr);
        const a = document.createElement('a');
        a.className = 'evlink' + (e ? '' : ' dead');
        a.textContent = n + (e ? ' · ' + e.year + '年' : '');
        if (e) a.dataset.event = String(EV.indexOf(e));
        wrap.appendChild(a);
      });
      body.appendChild(wrap);
    }
    if (pr.sources && pr.sources.length) body.appendChild(srcBlock({ sources: pr.sources }));
    wireInternalLinks(body);
  }
  function matchEvent(name, pr) {
    const nn = normName(name);
    let hit = EV.find(e => normName(e.title) === nn);
    if (hit) return hit;
    hit = EV.find(e => normName(e.title).indexOf(nn) >= 0 || nn.indexOf(normName(e.title)) >= 0);
    if (hit) return hit;
    const persons = (pr && pr.events) || [];
    return null;
  }
  /* 面板内部跳转（人物 / 事件），全程不出页面 */
  function wireInternalLinks(box) {
    const roots = [box, $('#dCat')];
    roots.forEach(root => root.querySelectorAll('.back').forEach(a => a.addEventListener('click', () => {
      state.view = state.focus ? 'overview' : 'overview';
      state.curEvent = null; state.curPerson = null;
      hideTip(); renderDrawer();
    })));
    box.querySelectorAll('[data-person]').forEach(a => a.addEventListener('click', ev => {
      ev.preventDefault(); ev.stopPropagation();
      openPerson(a.getAttribute('data-person'));
    }));
    box.querySelectorAll('[data-event]').forEach(a => a.addEventListener('click', ev => {
      ev.preventDefault(); ev.stopPropagation();
      const e = EV[+a.getAttribute('data-event')];
      if (e) openEvent(e, true);
    }));
  }
  function srcBlock(e) {
    const w = document.createElement('div');
    w.innerHTML = srcHtml(e);
    return w.firstChild || document.createComment('no sources');
  }
  function kv(k, v) {
    const d = document.createElement('div');
    d.className = 'kv';
    d.innerHTML = '<span class="kvk">' + esc(k) + '</span><span class="kvv">' + esc(v) + '</span>';
    return d;
  }
  function hintLine(t) {
    const d = document.createElement('div');
    d.className = 'hintline'; d.textContent = t; return d;
  }
  function note(t) { const d = document.createElement('div'); d.className = 'note'; d.textContent = t; return d; }

  /* ---- 割据区详情 ---- */
  function openTerritory(t) {
    const p = (t.provs || []).find(x => GEO.paths[x]);
    if (p && state.focus !== p) selectProvince(p, false);
    state.curTerr = t;
    state.curEvent = null;
    state.view = 'territory';
    renderDrawer();
    const b = $('#dbody'); if (b) b.scrollTop = 0;
  }
  function renderTerritoryView() {
    const t = state.curTerr, fi = facOf(t.faction), body = $('#dbody');
    body.innerHTML = '';
    const span = t.from[0] + '.' + pad2(t.from[1]) + ' — ' + t.to[0] + '.' + pad2(t.to[1]);
    head('割据区 / 根据地', esc(t.name),
      '<span>' + span + '</span><span>' + (t.provs || []).join('、') + '</span>',
      '<span class="faction"><span class="sw" style="background:' + fi.color + '"></span>' + esc(fi.name) + '</span>');
    body.appendChild(backBar(state.focus ? ('返回 ' + state.focus) : '返回'));
    const n = document.createElement('div');
    n.className = 'note';
    n.textContent = '说明：该区域跨省且只占部分县，图中按县组合绘制；县界采用现行县级行政单位近似，历史县名与今名对照见下。';
    body.appendChild(n);
    if (t.note) { const d = document.createElement('div'); d.className = 'evtext'; d.textContent = t.note; body.appendChild(d); }
    body.appendChild(sec('所辖县 / 县级市（' + (t.counties || []).length + ' 个，按现行区划）'));
    const cs = document.createElement('div');
    cs.className = 'counties';
    cs.innerHTML = (t.counties || []).map(c => '<span class="cnty">' + esc(c.split('|').pop()) + '</span>').join('');
    body.appendChild(cs);
    if ((t.provs || []).length) {
      body.appendChild(sec('涉及省级单元（点击查看该省当月详情）'));
      const wrap = document.createElement('div');
      wrap.className = 'evlinks';
      t.provs.forEach(p => {
        const a = document.createElement('a');
        a.className = 'evlink';
        a.textContent = p + ' · ' + stepInfo(state.step).y + '年' + stepInfo(state.step).mo + '月';
        a.addEventListener('click', ev => { ev.preventDefault(); selectProvince(p, true); });
        wrap.appendChild(a);
      });
      body.appendChild(wrap);
    }
    if (t.sources && t.sources.length) body.appendChild(srcBlock({ sources: t.sources }));
    wireInternalLinks(body);
  }
  function showTerrTip(ev, t) {
    const fi = facOf(t.faction);
    const { y, mo } = stepInfo(state.step);
    tip.innerHTML = '<b>' + esc(t.name) + '</b><br>' +
      '<span class="s">' + t.from[0] + '.' + pad2(t.from[1]) + ' — ' + t.to[0] + '.' + pad2(t.to[1]) + '</span><br>' +
      '<span class="s">性质：</span><span style="color:' + fi.color + '">' + esc(fi.name) + '</span>' +
      '<br><span class="s">' + (t.counties || []).length + ' 个县 · 涉 ' + (t.provs || []).join('、') + ' · 点击查看</span>';
    tip.style.opacity = 1; moveTip(ev);
  }

  function openPerson(id) {
    const pr = PERSON[id];
    if (!pr) return;
    state.curPerson = pr; state.view = 'person';
    const y = (String(pr.life || '').match(/\d{4}/) || [String(state.year || '')])[0];
    renderDrawer();
    $('#dbody').scrollTop = 0;
  }

  function backBar(label) {
    const d = document.createElement('div');
    d.className = 'backbar';
    d.innerHTML = '<a class="back" data-back="1">‹ ' + esc(label || '返回') + '</a>';
    return d;
  }
  function sec(t) { const d = document.createElement('div'); d.className = 'secTitle'; d.textContent = t; return d; }
  function note(t) { const d = document.createElement('div'); d.className = 'note'; d.textContent = t; return d; }

  /* 某省逐月势力合并为区间列表（年份按绝对月份换算） */
  function factionTimeline(prov) {
    const out = [];
    let cur = null;
    for (let i = 0; i < NSTEP; i++) {
      const rec = monthMap[i][prov];
      if (!rec) continue;
      if (!cur || cur.faction !== rec.faction || cur.note !== rec.note) {
        if (cur) { cur.to = fmtM(i - 1 + M0); out.push(cur); }
        const s = mi(i + M0);
        cur = { faction: rec.faction, note: rec.note, from: fmtM(i + M0), fromY: s.y, fromM: s.mo, to: '' };
      }
    }
    if (cur) { cur.to = fmtM(M1); out.push(cur); }
    return out;
  }
  function fmtM(i) { const s = mi(i); return s.y + '.' + pad2(s.mo); }

  function selectProvince(name, zoom) {
    state.focus = name;
    if (state.view !== 'overview') { state.view = 'overview'; state.curEvent = null; }
    for (const p in provNodes) provNodes[p].classList.toggle('sel', p === name);
    dimPath.setAttribute('d', 'M-200 -200H1400V1300H-200Z ' + GEO.paths[name]);
    dimPath.classList.add('on');
    drawer.classList.add('open');
    if (zoom) focusOn(name);
    paintMap();          // 立即按聚焦状态重绘（压暗其余地块、隐藏其地名）
    renderDrawer();
  }
  function clearSelection() {
    state.focus = null;
    state.view = 'overview'; state.curEvent = null; state.curPerson = null;
    for (const p in provNodes) provNodes[p].classList.remove('sel');
    dimPath.classList.remove('on');
    drawer.classList.remove('open');
    resetView();
    paintMap();
    renderDrawer();
  }

  /* ---------- 6. 事件火花 ---------- */
  function pickProv(e) {
    const ps = (e.provinces || []).filter(p => GEO.paths[p]);
    if (!ps.length) return null;
    if (state.focus && ps.includes(state.focus)) return state.focus;
    return ps[0];
  }
  /* 统计当月各省事件数，并把数字标在该省地名后面（如「湖北·3」） */
  function updateEventBadges() {
    const cnt = {};
    if (state.showMarks) {
      (evByMonth.get(state.step) || []).forEach(e => {
        (e.provinces || []).forEach(p => { if (GEO.paths[p]) cnt[p] = (cnt[p] || 0) + 1; });
      });
    }
    const items = (curLayer && curLayer._items) || [];
    for (const p of PROVS) {
      const t = labelNodes[p]; if (!t) continue;
      if (isReplaced(p)) {
        // 该省在本时期已被历史区划取代：把事件数与高亮标到对应历史形状上
        t.style.display = 'none';
        const it = items.find(x => x.unitKey === p);
        if (it) {
          const n2 = cnt[p] || 0;
          let tc2 = it.label.querySelector('.cnt');
          if (!tc2) { tc2 = el('tspan', { class: 'cnt' }); it.label.appendChild(tc2); }
          if (tc2) tc2.textContent = n2 ? '·' + n2 : '';
          it.label.classList.toggle('has-ev', n2 > 0);
          it.node.classList.toggle('has-ev', n2 > 0);
        }
        continue;
      }
      const n = cnt[p] || 0;
      const tc = t.querySelector('.cnt');
      if (tc) tc.textContent = n ? '·' + n : '';
      t.classList.toggle('has-ev', n > 0 && !(state.focus && state.focus !== p));
      const node = provNodes[p];
      if (node) {
        const on = n > 0 && !(state.focus && state.focus !== p);
        node.classList.toggle('has-ev', on);
      }
    }
  }

  function renderSparks() {
    sparkLayer.innerHTML = '';
    sparkLayer.style.display = state.showMarks ? '' : 'none';   // 清除内外忧患标注时隐藏
    updateEventBadges();
    if (!state.showMarks) return;
    let list = (evByMonth.get(state.step) || []).filter(e => e.scope !== 'nation');
    if (state.focus) list = list.filter(e => (e.provinces || []).includes(state.focus));
    if (!list.length) return;
    const used = {};
    list.forEach(e => {
      const prov = pickProv(e); if (!prov) return;
      const c = GEO.centroids[prov]; if (!c) return;
      const n = (used[prov] = (used[prov] || 0) + 1);
      const ang = (n - 1) * 2.399, rad = Math.min(30, 6 * (n - 1));
      const px = c[0] + Math.cos(ang) * rad, py = c[1] + Math.sin(ang) * rad * .72;
      const ci = catOf(e.category);
      const r = e.importance >= 3 ? 6.5 : e.importance === 2 ? 5.4 : 4.5;
      const g = el('g', { class: 'spark', transform: 'translate(' + px.toFixed(1) + ',' + py.toFixed(1) + ')' });
      const halo = el('circle', { class: 'halo', r: r, stroke: ci.color });
      halo.style.transformOrigin = '0 0';
      const core = el('circle', { class: 'core', r: (r * .6).toFixed(1), fill: ci.color, filter: 'url(#glow)' });
      const txt = el('text', { y: -r - 6 });
      txt.textContent = e.mo + '月 ' + (e.title.length > 14 ? e.title.slice(0, 14) + '…' : e.title);
      g.appendChild(halo); g.appendChild(core); g.appendChild(txt);
      g.addEventListener('mouseenter', ev => showEventTip(ev, e));
      g.addEventListener('mousemove', moveTip);
      g.addEventListener('mouseleave', hideTip);
      g.addEventListener('click', ev => { ev.stopPropagation(); openEvent(e); });
      sparkLayer.appendChild(g);
    });
  }
  function openEvent(e, keepFocus) {
    // 注意：selectProvince 会把视图重置为省级详情，必须先定位、后设视图
    if (!keepFocus) {
      const p = (e.provinces || []).find(x => GEO.paths[x]);
      if (p && state.focus !== p) selectProvince(p, false);
    }
    state.curEvent = e;
    state.curTerr = null;
    state.view = 'event';
    renderDrawer();
    const b = $('#dbody'); if (b) b.scrollTop = 0;
  }

  /* ---------- 7. 提示 ---------- */
  const tip = $('#tip');
  function showProvTip(ev, name) {
    const { y, mo } = stepInfo(state.step);
    const f = facRec(name, state.step) || {}, fi = facOf(f.faction);
    const cnt = EV.filter(e => (e.provinces || []).includes(name)).length;
    tip.innerHTML = '<b>' + name + '</b> · ' + y + '年' + mo + '月<br>' +
      '<span class="s">势力：</span><span style="color:' + fi.color + '">' + esc(fi.name) + '</span>' +
      (f.note ? '<br><span class="s">' + esc(f.note) + '</span>' : '') +
      '<br><span class="s">累计收录 ' + cnt + ' 件 · 点击放大查看</span>';
    tip.style.opacity = 1; moveTip(ev);
  }
  function showNeighborTip(ev, name) {
    const rec = neighborsAt(state.step)[name];
    const fi = nbfOf(rec && rec.faction);
    const { y, mo } = stepInfo(state.step);
    tip.innerHTML = '<b>' + esc(name) + '</b> · ' + y + '年' + mo + '月<br>' +
      '<span class="s">政权/势力：</span><span style="color:' + fi.color + '">' + esc(fi.name) + '</span>' +
      (rec && rec.note ? '<br><span class="s">' + esc(rec.note) + '</span>' : '');
    tip.style.opacity = 1; moveTip(ev);
  }
  function showEventTip(ev, e) {
    const ci = catOf(e.category);
    tip.innerHTML = '<b>' + esc(e.title) + '</b><br><span class="s">' + esc(e.date || e.year + '年') +
      (e.place ? ' · ' + esc(e.place) : '') + '</span><br>' + esc(e.summary || '') +
      '<br><span style="color:' + ci.color + '">' + esc(ci.name) + '</span>';
    tip.style.opacity = 1; moveTip(ev);
  }
  function moveTip(ev) {
    const x = (ev.clientX || 0) + 16, y = (ev.clientY || 0) + 14;
    tip.style.left = Math.min(x, innerWidth - tip.offsetWidth - 14) + 'px';
    tip.style.top = Math.min(y, innerHeight - tip.offsetHeight - 14) + 'px';
  }
  function hideTip() { tip.style.opacity = 0; }


  /* ---------- 8.5 世界图层：随时间切片显示全球政体 ---------- */
  const WORLD = DATA.world || null;
  const WNAMES = (WORLD && WORLD.names) || {};
  const worldLayer = $('#worldLayer');
  const worldCache = new Map();
  let worldCur = -1;

  /* 政体配色：大国固定色，其余按名称稳定哈希取色 */
  const WFIX = {
    'China': '#c9a227', 'Qing China': '#c9a227', 'Ming China': '#c9a227',
    'Yuan Dynasty': '#a9832a', 'Mongol Empire': '#8a6a20', 'Tibet': '#b98a3c',
    'Russian Empire': '#4a6f9c', 'Soviet Union': '#c0392b', 'Russia': '#5b8ac0',
    'United Kingdom': '#8b5cf6', 'Great Britain': '#8b5cf6',
    'France': '#3b7dd8', 'Germany': '#6b7280', 'German Empire': '#5b6470',
    'Nazi Germany': '#4b5563', 'Austria-Hungary': '#c08a3e', 'Ottoman Empire': '#2f8f6f',
    'Turkey': '#2f8f6f', 'Spain': '#d4a017', 'Portugal': '#2e7d5b', 'Netherlands': '#e07b39',
    'Italy': '#57a773', 'Roman Empire': '#8e44ad', 'Byzantine Empire': '#7d3c98',
    'Persian Empire': '#16a085', 'Achaemenid Empire': '#16a085', 'Egypt': '#c2a13a',
    'India': '#e67e22', 'Mughal Empire': '#d35400', 'British Raj': '#a0522d',
    'Japan': '#b03a5b', 'Empire of Japan': '#a03050', 'Korea': '#4a8fa8',
    'United States': '#2f6fb5', 'United States of America': '#2f6fb5',
    'Brazil': '#3aa76d', 'Mexico': '#4f9e4f', 'Canada': '#b5474c', 'Australia': '#c47a3a',
    'Ethiopia': '#7a9e3a', 'Iran': '#2f9e8f', 'Poland': '#c86a8a', 'Sweden': '#3f6fb0',
  };
  const WCACHE = {};
  function worldColor(name, year) {
    if (WFIX[name]) return WFIX[name];
    const pe = polByName(name, year);
    if (pe && pe.color) return pe.color;          // 注册表里的颜色：同一政权任何拼写同色
    if (WCACHE[name]) return WCACHE[name];
    let h = 0;
    for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) % 360;
    const c = 'hsl(' + h + ',' + (34 + (h % 18)) + '%,' + (44 + (h % 12)) + '%)';
    WCACHE[name] = c;
    return c;
  }
  function wname(n, year) {
    const e = polByName(n, year);
    if (e && e.zh) return e.zh;
    return (WNAMES[n] || n);
  }
  /* 政体信息：人工撰写的用数据文件；其余按时间切片即时生成（存续期 + 检索来源），
     不预存于单文件以控制体积 */
  let WSPAN = null;
  function polityInfo(name, year) {
    const reg = polByName(name, year);
    if (reg) {
      return {
        from: reg.from, to: reg.to, capital: reg.capital || '',
        summary: reg.summary || '', zh: reg.zh, auto: !reg.summary,
        sources: (reg.sources || []).map(u => (typeof u === 'string' ? { t: u, u: u } : u)),
      };
    }
    const cur = (WORLD.polities || {})[name];
    if (cur) return cur;
    if (!WSPAN) {
      WSPAN = new Map();
      (WORLD.slices || []).forEach(sl => {
        (sl.p || []).forEach(rec => {
          const nm2 = rec[0], y = sl.y;
          const v = WSPAN.get(nm2);
          if (!v) WSPAN.set(nm2, [y, y]);
          else { if (y < v[0]) v[0] = y; if (y > v[1]) v[1] = y; }
        });
      });
    }
    const sp = WSPAN.get(name);
    if (!sp) return null;
    return {
      from: sp[0], to: sp[1], capital: '', summary: '', auto: true,
      zh: WNAMES[name],
      sources: [{ t: '必应搜索·' + name, u: 'https://cn.bing.com/search?q=' + encodeURIComponent(name) }],
    };
  }
  function fmtYear(y) { return y < 0 ? '前' + Math.abs(y) : String(y); }

  /* ---------- 统一底图：世界轮廓不随时间变化 ----------
     时间切片只决定“谁控制哪里”，海岸线一律用现代精确轮廓；
     古代切片的粗糙多边形通过 clipPath 裁剪到陆地轮廓内，避免出现板块级变形。 */
  let landReady = false;
  function buildLandBase() {
    if (landReady || !WORLD) return;
    landReady = true;
    const base = document.querySelector('#landBaseLayer');
    const clip = document.querySelector('#landClip');
    if (!base) return;
    // 取现代切片（2014—2026）作为陆地轮廓来源
    let mi = -1;
    WORLD.slices.forEach((sl, i) => { if (sl.modern && sl.y === 2014) mi = i; });
    if (mi < 0) WORLD.slices.forEach((sl, i) => { if (sl.modern && mi < 0) mi = i; });
    if (mi < 0) return;
    const sl = WORLD.slices[mi];
    const frag = document.createDocumentFragment();
    const seenGeo = new Set();
    (sl.p || []).forEach(rec => {
      const geo = WORLD.geoms[rec[1]];
      if (!geo || !geo.d || seenGeo.has(rec[1])) return;
      seenGeo.add(rec[1]);
      const p1 = el('path', { d: geo.d, 'fill-rule': 'nonzero' });
      frag.appendChild(p1);
    });
    base.appendChild(frag);
    if (clip) {
      const cf = document.createDocumentFragment();
      seenGeo.forEach(gi => {
        const geo = WORLD.geoms[gi];
        if (geo && geo.d) cf.appendChild(el('path', { d: geo.d, 'fill-rule': 'nonzero' }));
      });
      clip.appendChild(cf);
    }
    // 政体色块裁剪到陆地（古切片的多边形因此贴合现代海岸线）
    if (worldLayer) worldLayer.setAttribute('clip-path', 'url(#landClip)');
  }

  function renderWorld() {
    if (!WORLD || !worldLayer || !STEPS.length) return;
    const st = STEPS[state.ti];
    const si = st ? (st.slice | 0) : 0;
    if (si === worldCur) return;
    worldCur = si;
    if (!worldCache.has(si)) {
      const g = el('g', { class: 'wslice', 'data-slice': si });
      const sl = WORLD.slices[si];
      (sl.p || []).forEach(rec => {
        const name = rec[0], gi = rec[1];
        const geo = WORLD.geoms[gi];
        if (!geo) return;
        const p = el('path', {
          class: 'wpol', d: geo.d, 'fill-rule': 'nonzero',
          fill: worldColor(name, sl.y), 'data-name': name
        });
        p.addEventListener('click', ev => { ev.stopPropagation(); showWorldInfo(name, sl); });
        p.addEventListener('mouseenter', ev => showWorldTip(ev, name, sl));
        p.addEventListener('mousemove', moveTip);
        p.addEventListener('mouseleave', hideTip);
        g.appendChild(p);
      });
      const lg = el('g', { class: 'wlabels' });
      g.appendChild(lg);
      g._labels = lg;
      worldLayer.appendChild(g);
      worldCache.set(si, g);
      // 只保留当前与相邻切片，控制内存
      for (const k of Array.from(worldCache.keys())) {
        if (Math.abs(k - si) > 1) {
          const old = worldCache.get(k);
          if (old && old.parentNode) old.parentNode.removeChild(old);
          worldCache.delete(k);
        }
      }
    }
    worldCache.forEach((g, k) => { g.style.display = (k === si) ? '' : 'none'; });
    layoutWorldLabels();
  }
  /* 几何包围盒（缓存）——世界数据只有 label/路径，没有 box，需量测一次 */
  const _bboxCache = new WeakMap();
  let _measureG = null;
  function geoBox(geo) {
    let b = _bboxCache.get(geo);
    if (b) return b;
    if (!_measureG) {
      _measureG = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      _measureG.setAttribute('visibility', 'hidden');
      const svg = document.querySelector('#map') || document.querySelector('svg');
      if (svg) svg.appendChild(_measureG);
    }
    const pth = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    pth.setAttribute('d', geo.d || '');
    _measureG.appendChild(pth);
    try {
      const bb = pth.getBBox();
      b = [bb.x, bb.y, bb.width, bb.height];
    } catch (e) { b = [0, 0, 0, 0]; }
    _measureG.removeChild(pth);
    _bboxCache.set(geo, b);
    return b;
  }

  /* 世界政体标签：按屏幕面积取前若干名，贪心防重叠；与省份标签同样放在变换组内反向缩放 */
  function layoutWorldLabels() {
    const st = STEPS[state.ti];
    const si = st ? (st.slice | 0) : 0;
    const g = worldCache.get(si);
    if (!g || !g._labels) return;
    const lg = g._labels;
    lg.innerHTML = '';
    if (document.body.classList.contains('no-labels')) return;
    const sl = WORLD.slices[si];
    const k = clamp(view.k || 1, 0.4, 30);
    const fs = Math.pow(k, 0.35) * 9.5;
    const limit = k < 1.2 ? 22 : k < 2.5 ? 40 : k < 5 ? 64 : 96;
    const placed = [];
    // 先占位：中国图层当前显示的地名（避免与“蒙古/朝鲜”这类世界标签叠字重影）
    const cnLabels = [];
    document.querySelectorAll('#histLayer text, #labelLayer text').forEach(t => {
      if (!t.getClientRects().length) return;
      const lx = t.dataset.lx, ly = t.dataset.ly;
      if (lx == null || ly == null) return;
      const sx = (+lx) * k, sy = (+ly) * k;
      const txt = t.textContent || '';
      if (!txt) return;
      const w = Math.max(24, txt.length * fs * 0.62), h = fs * 1.3;
      cnLabels.push({ x: sx - w / 2, y: sy - h / 2, w: w, h: h });
      placed.push(cnLabels[cnLabels.length - 1]);
    });
    const seenName = {};
    const cand = [];
    (sl.p || []).forEach(rec => {
      const geo = WORLD.geoms[rec[1]];
      if (!geo || !geo.label) return;
      if (seenName[rec[0]]) return;                 // 同一政权多块几何只标一次
      seenName[rec[0]] = 1;
      cand.push({ name: rec[0], lx: geo.label[0], ly: geo.label[1], box: geoBox(geo) });
    });
    cand.forEach(c => {
      const w = c.box ? Math.abs(c.box[2]) : 0, h = c.box ? Math.abs(c.box[3]) : 0;
      c.scr = w * h * k * k;
    });
    cand.sort((a, b) => b.scr - a.scr);
    let n = 0;
    for (const c of cand) {
      if (n >= limit) break;
      if (c.scr < 1100) continue;
      const sx = c.lx * k, sy = c.ly * k;
      const txt = wname(c.name, sl.y);
      const w = Math.max(24, txt.length * fs * 0.62), h = fs * 1.25;
      const bx = { x: sx - w / 2, y: sy - h / 2, w: w, h: h };
      let hit = false;
      for (const b of placed) {
        if (bx.x < b.x + b.w && b.x < bx.x + bx.w && bx.y < b.y + b.h && b.y < bx.y + bx.h) { hit = true; break; }
      }
      if (hit) continue;
      placed.push(bx);
      const t = el('text', { class: 'wlabel', 'data-name': c.name });
      t.setAttribute('transform', 'translate(' + c.lx.toFixed(1) + ',' + c.ly.toFixed(1) + ') scale(' +
        Math.pow(k, -0.65).toFixed(4) + ')');
      t.textContent = txt;
      lg.appendChild(t);
      n++;
    }
  }

  function showWorldTip(ev, name, sl) {
    tip.innerHTML = '<b>' + esc(wname(name)) + '</b><br><span class="s">' + esc(sl.label) +
      '</span><br><span class="s">原始名称：' + esc(name) + '</span>';
    tip.style.opacity = 1; moveTip(ev);
  }
  /* ---------- 数据与来源（单文件自带声明，便于单独转发时保留署名与许可） ---------- */
  function showAbout() {
    const body = $('#dbody');
    state.curEvent = null; state.curTerr = null; state.curPerson = null;
    state.curHist = null; state.curWorld = null;
    state.view = 'about';
    drawer.classList.add('open');
    drawer.classList.remove('wide');
    renderDrawer();
    if (body) body.scrollTop = 0;
  }
  const ABOUT = [
    ['世界政治边界', [
      ['historical-basemaps（aourednik）', '公元 1886 年以前的世界政治边界，54 个时间切片',
       'https://github.com/aourednik/historical-basemaps', '许可证 GPL-3.0'],
      ['CShapes 2.0（ETH Zürich）', '1886—2019 年逐年国界与首都',
       'https://icr.ethz.ch/data/cshapes/', '学术免费使用'],
      ['Natural Earth 50m', '现代国界与底图', 'https://www.naturalearthdata.com/', '公有领域'],
    ]],
    ['中国部分', [
      ['公开出版物与公开网页资料', '《中国历史地图集》近现代部分、各省地方志、党史与民国史公开研究等',
       'https://baike.baidu.com/', '每条事件均附可点击来源'],
    ]],
  ];
  const LIMITS = [
    '商周至宋辽夏金等早期时期，古代政区（王畿/诸侯/郡县/州/道/路/行省）与今省界无对应关系，'
      + '本图沿用今省界、只以色块表示主要控制或文化归属，仅供大势参考。',
    '世界图层在 1886 年前的切片较疏（按世纪或数百年），不宜用于精确边界比对。',
    '公元前 1600 年以前的中国区域仅由世界图层呈现，未绘制中国政区（避免臆造）。',
    '政体「存续期」在无专门条目时由边界数据出现的年份区间推得，仅供参考。',
    '事件时间以史料记载为准，仅记到年月者标注「月份待考」。',
  ];

  function renderAboutView() {
    const body = $('#dbody');
    head('数据与来源', '数据与来源', '<span class="dim">边界数据、许可与已知限制</span>', '');
    const wrap = document.createElement('div');
    wrap.className = 'about';
    ABOUT.forEach(pair => {
      wrap.appendChild(hintLine(pair[0]));
      pair[1].forEach(it => {
        const d = document.createElement('div');
        d.className = 'evtext';
        d.innerHTML = '<b>' + esc(it[0]) + '</b>（' + esc(it[3]) + '）：' + esc(it[1]) +
          '<br><a href="' + esc(it[2]) + '" target="_blank" rel="noopener">' + esc(it[2]) + '</a>';
        wrap.appendChild(d);
      });
    });
    wrap.appendChild(hintLine('口径与已知限制'));
    LIMITS.forEach(t => {
      const d = document.createElement('div');
      d.className = 'evtext';
      d.textContent = '· ' + t;
      wrap.appendChild(d);
    });
    const d2 = document.createElement('div');
    d2.className = 'evtext';
    d2.textContent = '本作品以 GPL-3.0 兼容方式提供；再分发请保留本声明与来源标注。';
    wrap.appendChild(d2);
    body.appendChild(wrap);
  }

  function showWorldInfo(name, sl) {
    const body = $('#dbody');
    state.curEvent = null; state.curTerr = null; state.curPerson = null; state.curHist = null;
    state.view = 'world';
    state.curWorld = { name: name, slice: sl };
    drawer.classList.add('open');
    renderDrawer();
    if (body) body.scrollTop = 0;
  }
  function renderWorldView() {
    const w = state.curWorld, body = $('#dbody');
    body.innerHTML = '';
    head('世界政体', esc(wname(w.name)),
      '<span>' + esc(w.slice.label) + '</span>',
      '<span class="s">' + esc(w.name) + '</span>');
    body.appendChild(backBar('返回'));
    const _sl0 = (WORLD && WORLD.slices[(STEPS[state.ti] || {}).slice | 0]) || null;
    const info = polityInfo(w.name, _sl0 && _sl0.y);
    if (info) {
      const n = document.createElement('div');
      n.className = 'note';
      let cap = info.capital || '';
      // 有分期都城时按当前时间显示当时都城
      if (info.capitals && info.capitals.length) {
        const yy = (STEPS[state.ti] || {}).t || 0;
        const hit = info.capitals.filter(c => c[0] <= yy && yy <= c[1]).pop();
        if (hit) cap = hit[2] + '（' + fmtYear(hit[0]) + '—' + fmtYear(hit[1]) + '）';
      }
      n.textContent = '存续：' + fmtYear(info.from) + ' — ' + fmtYear(info.to) +
        (cap ? '　都城：' + cap : '');
      body.appendChild(n);
      if (info.summary) {
        const d = document.createElement('div');
        d.className = 'evtext';
        d.textContent = info.summary;
        body.appendChild(d);
      } else if (info.auto) {
        body.appendChild(hintLine('该政体的简述待补充；存续期来自边界数据，可点下方来源检索。'));
      }
      if (info.sources) body.appendChild(srcBlock({ sources: info.sources }));
    } else {
      const n = document.createElement('div');
      n.className = 'note';
      n.textContent = '该政体边界来自 historical-basemaps（GPL-3.0）全球政治边界时间切片，' +
        '按 Natural Earth 投影绘制；远古切片多以文化区/族群近似，不宜视作现代国界。';
      body.appendChild(n);
      body.appendChild(hintLine('数据来源与许可：aourednik/historical-basemaps（GPL-3.0）'));
    }
    wireInternalLinks(body);
  }


  /* ---------- 8.6 世界历史事件：按时间窗口落在世界地图上 ---------- */
  const WEV = DATA.worldEvents || [];
  const WEV_LAYER = $('#wevLayer');
  /* 与世界图层同一套 Natural Earth 投影参数 */
  const WSCALE = (WORLD && WORLD.meta && WORLD.meta.scale) || 480;
  const WCX = (WORLD && WORLD.meta && WORLD.meta.cx) || 1310;
  const WCY = (WORLD && WORLD.meta && WORLD.meta.cy) || 700;
  function wproj(lon, lat) {
    const lam = lon * Math.PI / 180, phi = lat * Math.PI / 180;
    const p2 = phi * phi, p4 = p2 * p2;
    const x = lam * (0.8707 - 0.131979 * p2 + p4 * (-0.013791 + p4 * (0.003971 * p2 - 0.001529 * p4)));
    const y = phi * (1.007226 + p2 * (0.015085 + p4 * (-0.044475 + 0.028874 * p2 - 0.005916 * p4)));
    return [WCX + x * WSCALE, WCY - y * WSCALE];
  }
  /* 当前步骤对应的时间窗口：世界步取“上一步之后到本步”，逐年步取当年 */
  function worldEventWindow() {
    const i = state.ti;
    const st = STEPS[i];
    if (!st) return [0, 0];
    if (st.kind === 'year') return [st.t, st.t + 1];
    const prev = STEPS[Math.max(0, i - 1)];
    const from = (prev && prev !== st) ? prev.t : st.t - 1;
    return [from, st.t + 1];
  }
  function worldEventsNow() {
    const [a, b] = worldEventWindow();
    return WEV.filter(e => e.t >= a && e.t < b);
  }
  function renderWorldEvents() {
    if (!WEV_LAYER) return;
    const st = STEPS[state.ti];
    const inCn = !st || st.kind === 'cn';
    WEV_LAYER.innerHTML = '';
    WEV_LAYER.style.display = inCn ? 'none' : '';
    const lane = $('#nationLane');
    if (!inCn) {
      const list = worldEventsNow().slice().sort((x, y2) => y2.imp - x.imp).slice(0, 6);
      if (lane) {
        lane.innerHTML = '';
        lane.classList.toggle('on', list.length > 0);
        list.forEach(e => {
          const c = hel('div', 'nchip');
          c.innerHTML = '<b>★</b>' + esc(e.title) + '<i>' + evTimeText(e) + '</i>';
          c.addEventListener('click', ev2 => { ev2.stopPropagation(); openWorldEvent(e); });
          c.addEventListener('mouseenter', ev2 => showWorldEventTip(ev2, e));
          c.addEventListener('mousemove', moveTip);
          c.addEventListener('mouseleave', hideTip);
          lane.appendChild(c);
        });
      }
    }
    if (inCn) return;
    worldEventsNow().forEach(e => {
      const [x, y2] = wproj(e.lon, e.lat);
      const g = el('g', { class: 'wevmark imp' + Math.min(3, e.imp), transform: 'translate(' + x.toFixed(1) + ',' + y2.toFixed(1) + ')' });
      g.appendChild(el('circle', { class: 'wevhalo', r: '7' }));
      g.appendChild(el('circle', { class: 'wevdot', r: '3.4' }));
      g.addEventListener('click', ev2 => { ev2.stopPropagation(); openWorldEvent(e); });
      g.addEventListener('mouseenter', ev2 => showWorldEventTip(ev2, e));
      g.addEventListener('mousemove', moveTip);
      g.addEventListener('mouseleave', hideTip);
      WEV_LAYER.appendChild(g);
    });
  }
  function evTimeText(e) {
    return e.mo > 1 ? (e.y < 0 ? '前' + Math.abs(e.y) : e.y) + '年' + e.mo + '月'
                    : (e.y < 0 ? '前' + Math.abs(e.y) + '年' : e.y + '年');
  }
  function showWorldEventTip(ev, e) {
    tip.innerHTML = '<b>' + esc(e.title) + '</b><br><span class="s">' + esc(evTimeText(e)) +
      (e.place ? ' · ' + esc(e.place) : '') + '</span><br>' + esc(e.summary.slice(0, 70)) + '…';
    tip.style.opacity = 1; moveTip(ev);
  }
  function openWorldEvent(e) {
    state.view = 'wevent';
    state.curWEV = e;
    drawer.classList.add('open');
    renderDrawer();
    const b = $('#dbody'); if (b) b.scrollTop = 0;
  }
  function renderWorldEventView() {
    const e = state.curWEV, body = $('#dbody');
    body.innerHTML = '';
    head('世界历史事件', esc(e.title),
      '<span>' + esc(evTimeText(e)) + (e.place ? ' · ' + esc(e.place) : '') + '</span>',
      '<span class="faction"><span class="sw" style="background:#c9a227"></span>' + esc(e.cat) + '</span>');
    body.appendChild(backBar('返回'));
    const d = document.createElement('div');
    d.className = 'evtext';
    d.textContent = e.summary + (e.detail ? '\n\n' + e.detail : '');
    body.appendChild(d);
    body.appendChild(srcBlock(e));
    body.appendChild(hintLine('数据来源：世界事件为公开史料整理（持续扩充），来源链接见上。'));
    wireInternalLinks(body);
  }


  /* ---------- 8.7 区域快速定位：按经纬度范围飞到该区域 ---------- */
  const REGIONS = [
    { n: '全球', lon: [-180, 180], lat: [-58, 78] },
    { n: '东亚', lon: [95, 146], lat: [15, 54] },
    { n: '东南亚', lon: [92, 142], lat: [-11, 25] },
    { n: '南亚', lon: [60, 95], lat: [5, 38] },
    { n: '中东', lon: [24, 65], lat: [12, 45] },
    { n: '欧洲', lon: [-12, 45], lat: [34, 71] },
    { n: '非洲', lon: [-20, 55], lat: [-36, 38] },
    { n: '北美', lon: [-170, -50], lat: [12, 74] },
    { n: '拉美', lon: [-85, -34], lat: [-56, 24] },
    { n: '大洋洲', lon: [110, 180], lat: [-48, 0] },
  ];
  /* 把经纬度矩形投影成画布矩形（沿四边采样，避免投影弯曲导致裁切） */
  function regionRect(r) {
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    const N = 24;
    for (let i = 0; i <= N; i++) {
      const f = i / N;
      const lon = r.lon[0] + (r.lon[1] - r.lon[0]) * f;
      const lat = r.lat[0] + (r.lat[1] - r.lat[0]) * f;
      [[lon, r.lat[0]], [lon, r.lat[1]], [r.lon[0], lat], [r.lon[1], lat]].forEach(pt => {
        const p = wproj(pt[0], pt[1]);
        if (p[0] < x0) x0 = p[0];
        if (p[0] > x1) x1 = p[0];
        if (p[1] < y0) y0 = p[1];
        if (p[1] > y1) y1 = p[1];
      });
    }
    return [x0, y0, x1 - x0, y1 - y0];
  }
  function renderRegions() {
    const box = document.querySelector('#regionBar');
    if (!box) return;
    box.innerHTML = '';
    REGIONS.forEach(r => {
      const b = hel('button', 'rgn');
      b.textContent = r.n;
      b.addEventListener('click', e => {
        e.stopPropagation();
        fitRect(regionRect(r), 1.02);
        box.querySelectorAll('.rgn').forEach(x => x.classList.remove('on'));
        b.classList.add('on');
      });
      box.appendChild(b);
    });
  }


  /* ---------- 8.8 检索：政体 / 事件 / 省份，选中即切时间并飞过去 ---------- */
  let SEARCH_IDX = null;
  function buildSearchIndex() {
    if (SEARCH_IDX) return SEARCH_IDX;
    const items = [];
    // 省份（不改变时间，只飞过去）
    for (const p of PROVS) {
      const c = (GEO.centroids || {})[p];
      if (c) items.push({ kind: '省', label: p, sub: '中国省级行政区', ti: -1, x: c[0], y: c[1] });
    }
    // 世界政体：取首次出现的切片
    if (WORLD) {
      const seen = {};
      WORLD.slices.forEach((sl, si) => {
        (sl.p || []).forEach(rec => {
          const nm = rec[0];
          if (seen[nm]) return;
          seen[nm] = 1;
          const geo = WORLD.geoms[rec[1]] || {};
          const ti = stepIndexOfSlice(si);
          items.push({
            kind: '政体', label: wname(nm), raw: nm, sub: nm + '（' + sl.label + '）',
            ti: ti, x: (geo.label || [0, 0])[0], y: (geo.label || [0, 0])[1],
          });
        });
      });
    }
    // 中国事件
    EV.forEach(e => {
      const ti = tiOfMonthIndex(SI(e.year, e.mo));
      const p = (e.provinces || [])[0];
      const c = p ? (GEO.centroids || {})[p] : null;
      items.push({ kind: '事件', label: e.title, sub: (e.date || '') + (e.place ? ' · ' + e.place : ''),
                   ti: ti, x: c ? c[0] : null, y: c ? c[1] : null });
    });
    // 世界事件
    WEV.forEach(e => {
      const ti = stepIndexForTime(e.t);
      // 无明确地点（经纬度 0,0）的全球性事件只切时间，不移动镜头
      const hasSpot = !(Math.abs(e.lat) < 0.01 && Math.abs(e.lon) < 0.01);
      const p = hasSpot ? wproj(e.lon, e.lat) : null;
      items.push({ kind: '世界', label: e.title, sub: evTimeText(e) + (e.place ? ' · ' + e.place : ''),
                   ti: ti, x: p ? p[0] : null, y: p ? p[1] : null });
    });
    SEARCH_IDX = items;
    return items;
  }
  function stepIndexOfSlice(si) {
    for (let i = 0; i < STEPS.length; i++) if (STEPS[i].slice === si) return i;
    return -1;
  }
  function tiOfMonthIndex(mi) {
    const { y, mo } = stepInfo(clamp(mi, M0, M1));
    for (let i = 0; i < STEPS.length; i++) {
      const z = STEPS[i];
      if (z.kind === 'cn' && z.y === y && z.mo === mo) return i;
    }
    return -1;
  }
  function stepIndexForTime(t) {
    let best = -1;
    for (let i = 0; i < STEPS.length; i++) {
      const z = STEPS[i];
      if (z.kind === 'cn' || z.kind === 'cny' || z.kind === 'world' || z.kind === 'year') {
        if (z.t <= t) best = i; else break;
      }
    }
    return best;
  }
  function flyTo(x, y, k) {
    if (x == null || y == null) return;
    const kk = k || 5.5;
    const w = innerWidth / kk, h = innerHeight / kk;
    fitRect([x - w / 2, y - h / 2, w, h], 1.0);
  }
  function doSearch(q) {
    const box = document.querySelector('#searchOut');
    if (!box) return;
    q = (q || '').trim().toLowerCase();
    if (q.length < 1) { box.classList.remove('on'); box.innerHTML = ''; return; }
    const all = buildSearchIndex();
    // 相关度排序：精确 > 名称前缀 > 词首 > 子串（避免搜 Mali 先命中 Fourche Maline Culture）
    const score = it => {
      const lab = (it.label || '').toLowerCase();
      const raw = (it.raw || '').toLowerCase();
      const sub = (it.sub || '').toLowerCase();
      if (lab === q || raw === q) return 0;
      if (lab.startsWith(q) || raw.startsWith(q)) return 1;
      if (new RegExp('(^|[^a-z0-9\u4e00-\u9fa5])' + q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).test(lab + ' ' + raw)) return 2;
      if (lab.indexOf(q) >= 0 || raw.indexOf(q) >= 0) return 3;
      if (sub.indexOf(q) >= 0) return 4;
      return -1;
    };
    const scored = [];
    for (const it of all) {
      const sc = score(it);
      if (sc >= 0) scored.push([sc, it]);
    }
    scored.sort((a, b) => a[0] - b[0]);
    const hits = scored.slice(0, 40).map(x => x[1]);
    if (!hits.length) {
      box.innerHTML = '<div class="sri none">无匹配结果</div>';
      box.classList.add('on');
      return;
    }
    box.innerHTML = hits.map((h, i) => '<div class="sri" data-i="' + i + '"><b>' + esc(h.label) +
      '</b><span class="sri-k">' + h.kind + '</span><span class="sri-s">' + esc(h.sub || '') + '</span></div>').join('');
    box.classList.add('on');
    box._hits = hits;
    box.querySelectorAll('.sri').forEach(el2 => el2.addEventListener('click', () => pickSearch(hits[+el2.dataset.i])));
  }
  function pickSearch(h) {
    const box = document.querySelector('#searchOut');
    const inp = document.querySelector('#searchIn');
    if (box) { box.classList.remove('on'); box.innerHTML = ''; }
    if (inp) inp.value = h.label;
    if (h.ti >= 0) setTI(h.ti, true);
    if (h.x != null) flyTo(h.x, h.y, h.kind === '省' ? 6.5 : 5.5);
    // 政体：直接打开其详情卡片（含存续期、都城、简史与来源）
    if (h.kind === '政体' && h.raw && WORLD) {
      const sl = WORLD.slices[(STEPS[state.ti] || {}).slice | 0];
      if (sl) showWorldInfo(h.raw, sl);
    }
  }
  function initAbout() {
    const b = document.querySelector('#aboutBtn');
    if (b) b.addEventListener('click', e => { e.stopPropagation(); showAbout(); });
  }
  function initSearch() {
    const inp = document.querySelector('#searchIn');
    if (!inp) return;
    let t = null;
    inp.addEventListener('input', () => { clearTimeout(t); t = setTimeout(() => doSearch(inp.value), 120); });
    inp.addEventListener('focus', () => { if (inp.value) doSearch(inp.value); });
    inp.addEventListener('keydown', e => {
      if (e.key === 'Enter') {
        const box = document.querySelector('#searchOut');
        if (box && box._hits && box._hits.length) pickSearch(box._hits[0]);
      } else if (e.key === 'Escape') {
        const box = document.querySelector('#searchOut');
        if (box) box.classList.remove('on');
        inp.blur();
      }
    });
    document.addEventListener('click', e => {
      if (!e.target.closest || !e.target.closest('#searchWrap')) {
        const box = document.querySelector('#searchOut');
        if (box) box.classList.remove('on');
      }
    });
  }

  /* ---------- 8. 时间线 ---------- */
  const track = $('#track'), cursor = $('#cursor'), fill = $('#fill'),
        erasBox = $('#eras'), ticksBox = $('#ticks'), evbar = $('#evbar'), hoverline = $('#hoverline');
  const STEPS = (DATA.timeline && DATA.timeline.steps) || [];
  const RANGES = (DATA.timeline && DATA.timeline.ranges) || [];
  const TL_MODE = STEPS.length > 0;
  function rangeOf(ti) {
    for (const r of RANGES) if (ti >= r.from && ti <= r.to) return r;
    return RANGES[0];
  }
  function pctTI(ti) {
    const r = rangeOf(ti);
    return (ti - r.from) / Math.max(1, r.to - r.from) * 100;
  }
  const pctStep = s => pctTI(state.ti);

  /* 区间选择：史前 / 上古 / 中古 / 近世 / 近代 / 中国近代逐月 / 当代 */
  function renderRanges() {
    const sel = document.querySelector('#rangeSel');
    if (!sel) return;
    const cur = rangeOf(state.ti);
    if (!sel._init) {
      sel._init = true;
      RANGES.forEach(rg => {
        const o = document.createElement('option');
        o.value = String(RANGES.indexOf(rg));
        o.textContent = rg.name;
        sel.appendChild(o);
      });
      sel.addEventListener('change', e => {
        e.stopPropagation();
        const rg = RANGES[+sel.value];
        if (rg) { setTI(rg.from, true); renderRanges(); }
      });
    }
    const i = RANGES.indexOf(cur);
    if (i >= 0 && sel.value !== String(i)) sel.value = String(i);
  }


  (function drawEras() {
    (DATA.bands || []).forEach(b => {
      const from = clamp(b.from, Y0, Y1), to = clamp(b.to, Y0, Y1);
      if (to < from) return;
      const d = document.createElement('div');
      d.className = 'eraSeg';
      d.style.left = pctStep(SI(from, 1)) + '%';
      d.style.width = ((SI(to, 12) - SI(from, 1) + 1) / (M1 - M0 + 1) * 100) + '%';
      d.style.background = b.color;
      const years = to - from + 1;
      d.textContent = years >= 6 ? b.name : '';
      d.title = b.name + '（' + b.from + '—' + b.to + '）';
      erasBox.appendChild(d);
    });
  })();

  function clearNode(n) { while (n && n.firstChild) n.removeChild(n.firstChild); }
  /* 刻度随区间变化：中国段按年，其它段按切片/步 */
  function renderTicks() {
    if (!ticksBox) return;
    clearNode(ticksBox);
    const g = rangeOf(state.ti);
    const st = STEPS[state.ti];
    const inCn = st && st.kind === 'cn';
    if (!TL_MODE || inCn) {
      for (let y = Y0; y <= Y1; y++) {
        const decade = y % 10 === 0;
        const t = document.createElement('div');
        t.className = 'tk ' + (decade ? 'major' : 'minor');
        t.style.left = pctTI(state.ti >= 0 ? state.ti + (SI(y, 1) - state.step) : 0) + '%';
        ticksBox.appendChild(t);
        if (decade || y === Y0 || y === Y1) {
          const l = document.createElement('div');
          l.className = 'tkLabel'; l.style.left = t.style.left; l.textContent = y;
          ticksBox.appendChild(l);
        }
      }
      return;
    }
    for (let i = g.from; i <= g.to; i++) {
      const z = STEPS[i];
      if (!z) continue;
      const p = (i - g.from) / Math.max(1, g.to - g.from) * 100;
      const t = document.createElement('div');
      t.className = 'tk ' + (z.kind === 'world' ? 'major' : 'minor');
      t.style.left = p + '%';
      ticksBox.appendChild(t);
      if (z.kind === 'world' || (z.t % 100 === 0)) {
        const l = document.createElement('div');
        l.className = 'tkLabel'; l.style.left = p + '%';
        const tt = z.t;
        l.textContent = tt < 0 ? ('前' + Math.abs(tt)) : String(tt);
        ticksBox.appendChild(l);
      }
    }
  }
  (function drawTicksOld() {
    if (STEPS.length) return;                 // 有统一时间轴时由 renderTicks 绘制
    for (let y = Y0; y <= Y1; y++) {
      const decade = y % 10 === 0;
      const t = document.createElement('div');
      t.className = 'tk ' + (decade ? 'major' : 'minor');
      t.style.left = pctStep(SI(y, 1)) + '%';
      ticksBox.appendChild(t);
      if (decade || y === Y0 || y === Y1) {
        const l = document.createElement('div');
        l.className = 'tkLabel'; l.style.left = pctStep(SI(y, 1)) + '%'; l.textContent = y;
        ticksBox.appendChild(l);
      }
    }
  })();

  const monthMarks = [];
  (function drawEventMarks() {
    const byMonth = new Map();
    EV.forEach(e => { const k = SI(e.year, e.mo); byMonth.set(k, (byMonth.get(k) || 0) + 1); });
    for (let s = M0; s <= M1; s++) {
      const t = document.createElement('div');
      const n = byMonth.get(s) || 0;
      t.className = 'mmark' + (n ? ' has' : '');
      if (n) {
        t.classList.add('imp' + Math.min(3, n));
        t.style.height = (4 + Math.min(3, n) * 3) + 'px';
      }
      t.style.left = pctStep(s) + '%';
      monthMarks.push(t);
      evbar.appendChild(t);
    }
  })();

  /* 中国图层组：仅在“中国逐月”段时间显示，其余时间交给世界图层 */
  const CN_LAYERS = ['#worldLabelLayer', '#neighborLayer', '#cnBaseLayer', '#provLayer', '#histLayer',
                     '#dimdimWrap', '#southSeaLayer', '#terrLayer', '#sparkLayer', '#labelLayer'];
  function applyTimeMode() {
    const st = STEPS[state.ti];
    const inCn = !!(st && (st.kind === 'cn' || st.kind === 'cny'));
    document.body.classList.toggle('no-bands', !(st && st.kind === 'cn'));
    document.body.classList.toggle('no-month', !(st && st.kind === 'cn'));
    CN_LAYERS.forEach(sel => {
      const n = document.querySelector(sel);
      if (n) n.style.display = inCn ? '' : 'none';
    });
    const wl = $('#worldLayer');
    if (wl) wl.style.display = 'none';      // 世界图层常显由 renderWorld 控制（下面的 g 决定可见切片）
    if (wl) wl.style.display = '';
    document.body.classList.toggle('world-mode', !inCn);
  }
  /* 直接设置时间轴索引 */
  function setTI(i, force) {
    if (!STEPS.length) { setStep(i, force); return; }
    i = clamp(Math.round(i), 0, STEPS.length - 1);
    if (i === state.ti && !force) { renderCursor(); return; }
    state.ti = i;
    const st = STEPS[i];
    if (st.kind === 'cn') state.step = SI(st.y, st.mo);
    else if (st.kind === 'cny') state.step = SI(st.y, 1);
    CUR_YEAR = (st.y != null) ? st.y : Math.floor(state.step / 12);
    applyTimeMode();
    renderWorld();
    renderWorldEvents();
    applyHistorical(state.step);
    paintMap();
    renderSparks();
    renderNationLane();
    renderTicks();
    renderRanges();
    renderWorldEvents();
    renderCursor();
    renderDrawer();
    syncHeader();
  }
  /* 兼容旧接口：按月序号跳转（内部换算为时间轴索引） */
  function setStep(s, force) {
    s = clamp(Math.round(s), M0, M1);
    if (!STEPS.length) {
      if (s === state.step && !force) { renderCursor(); return; }
      state.step = s; applyHistorical(s); paintMap(); renderSparks();
      renderNationLane(); renderCursor(); renderDrawer(); syncHeader(); return;
    }
    const { y, mo } = stepInfo(s);
    let ti = -1;
    for (let i = 0; i < STEPS.length; i++) {
      const z = STEPS[i];
      if (z.kind === 'cn' && z.y === y && z.mo === mo) { ti = i; break; }
    }
    if (ti >= 0) setTI(ti, force);
  }
  function renderCursor() {
    const p = pctTI(state.ti);
    cursor.style.left = p + '%';
    fill.style.width = p + '%';
  }
  /* 时间文案：中国段显示年/月，其它段显示年代（公元前用「前」） */
  function timeLabel(st) {
    if (!st) return '';
    if (st.kind === 'cn') return st.y + '年' + st.mo + '月';
    const t = st.t;
    if (t < 0) {
      const a = Math.abs(t);
      if (a >= 10000) return '前' + (a / 10000).toFixed(a % 10000 === 0 ? 0 : 1) + '万年';
      return '前' + a + '年';
    }
    return t + '年';
  }
  function syncHeader() {
    const st = STEPS[state.ti];
    const inCn = st && st.kind === 'cn';
    const inCny = st && st.kind === 'cny';
    if (inCny) {
      $('#yearBig').textContent = (st.y < 0 ? '前' + Math.abs(st.y) : st.y);
      $('#monthSmall').textContent = '';
    } else if (inCn) {
      $('#yearBig').textContent = st.y;
      $('#monthSmall').textContent = pad2(st.mo);
      $('#monthSmall').parentNode && ($('#monthSmall').style.display = '');
    } else {
      const t = st ? st.t : 0;
      $('#yearBig').textContent = (t < 0 ? '前' + Math.abs(Math.round(t)) : Math.round(t));
      $('#monthSmall').textContent = '';
    }
    $('#tlYear').textContent = timeLabel(st);
    const band = (DATA.bands || []).find(b => inCn && st.y >= b.from && st.y <= b.to);
    $('#tlEra').textContent = inCn ? (band ? band.name : '')
      : (inCny ? ((PRE1893 && PRE1893.note && PRE1893.note[String(st.y)])
                  || (PRE1893 && PRE1893.eras || []).reduce((acc, er) => acc || ((er.note && er.note[String(st.y)]) || ''), '')
                  || ((HIST && histPeriodIndex(state.step) >= 0) ? HIST[histPeriodIndex(state.step)].label : '')
                  || rangeOf(state.ti).name || '')
               : (rangeOf(state.ti) || {}).name || '');
    const n = inCn ? (evByMonth.get(state.step) || []).length : 0;
    const late = !inCn && st && st.t > 2010;
    $('#tlCount').textContent = inCn ? (n ? '本月 ' + n + ' 件大事' : '本月无收录事件')
      : (late ? '现行国界（Natural Earth，2011 年后）' : '世界政体时间切片');
    if (curMark != null && monthMarks[curMark]) monthMarks[curMark].classList.remove('cur');
    curMark = inCn ? (state.step - M0) : null;
    if (curMark != null && monthMarks[curMark]) monthMarks[curMark].classList.add('cur');
    renderLegend();
  }
  let curMark = null;

  /* 拖动时间轴 */
  let tlDrag = false;
  const stepFromX = clientX => {
    const r = track.getBoundingClientRect();
    const p = clamp((clientX - r.left) / r.width, 0, 1);
    const g = rangeOf(state.ti);
    return clamp(Math.round(g.from + p * (g.to - g.from)), g.from, g.to);
  };
  track.addEventListener('pointerdown', e => {
    tlDrag = true;
    try { track.setPointerCapture(e.pointerId); } catch (_) {}
    setTI(stepFromX(e.clientX));
  });
  track.addEventListener('pointermove', e => {
    const r = track.getBoundingClientRect();
    hoverline.style.display = 'block';
    hoverline.style.left = ((e.clientX - r.left) / r.width * 100) + '%';
    if (tlDrag) setTI(stepFromX(e.clientX));
  });
  ['pointerup', 'pointercancel'].forEach(t => track.addEventListener(t, e => {
    tlDrag = false;
    try { track.releasePointerCapture(e.pointerId); } catch (_) {}
  }));
  track.addEventListener('pointerleave', () => { if (!tlDrag) hoverline.style.display = 'none'; });

  const BASE_MS = 1400;                       // 1x：每月 1.4 秒
  const RATES = [1, 2, 5, 10, 20];
  function setRate(r) {
    state.rate = r;
    state.speed = Math.max(30, Math.round(BASE_MS / r));
    const b = $('#btnSpeed');
    if (b) { b.textContent = r + 'x'; b.title = '播放倍速：' + r + 'x（每月 ' + (state.speed / 1000).toFixed(2) + ' 秒）'; }
    const menu = $('#speedMenu');
    if (menu) menu.querySelectorAll('.spitem').forEach(x => x.classList.toggle('cur', +x.dataset.rate === r));
    if (state.playing) { clearTimeout(state.timer); tickPlay(); }
  }
  (function buildSpeedMenu() {
    const menu = $('#speedMenu');
    if (!menu) return;
    menu.innerHTML = RATES.map(r => '<div class="spitem" data-rate="' + r + '" title="每月 ' +
      (BASE_MS / r / 1000).toFixed(2) + ' 秒">' + r + 'x</div>').join('');
    menu.querySelectorAll('.spitem').forEach(it => it.addEventListener('click', e => {
      e.stopPropagation();
      setRate(+it.dataset.rate);
      menu.classList.remove('open');
    }));
    const btn = $('#btnSpeed');
    if (btn) btn.addEventListener('click', e => {
      e.stopPropagation();
      menu.classList.toggle('open');
    });
    document.addEventListener('click', () => menu.classList.remove('open'));
  })();
  let toastTimer = null;
  function toast(msg) {
    const t = $('#toast');
    if (!t) return;
    t.textContent = msg;
    t.classList.add('on');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove('on'), 2600);
  }
  function togglePlay() {
    state.playing = !state.playing;
    $('#play').textContent = state.playing ? '❚❚' : '▶';
    $('#play').classList.toggle('on', state.playing);
    if (state.playing) tickPlay(); else clearTimeout(state.timer);
  }
  function tickPlay() {
    if (!state.playing) return;
    let next = state.step + 1;
    if (next > M1) next = M0;
    // 智能跳月：若未来 12 个月内无事件，则快进到下一个有事件的月份（保留势力变化观赏性）
    setStep(next, true);
    state.timer = setTimeout(tickPlay, state.speed);
  }
  $('#play').addEventListener('click', togglePlay);
  const inCnMode = () => { const st = STEPS[state.ti]; return !st || st.kind === 'cn'; };
  const stepBy = n => {
    if (inCnMode()) setStep(state.step + n);
    else {
      // 世界模式：按当前区间的步数比例跳转（月/年/五年）
      const g = rangeOf(state.ti);
      const unit = Math.max(1, Math.round((g.to - g.from) / 60));
      setTI(state.ti + n * (Math.abs(n) >= 60 ? 60 : Math.abs(n) >= 12 ? 12 : 1) * (unit > 1 ? unit : 1));
    }
  };
  $('#m1').addEventListener('click', () => stepBy(-1));
  $('#p1').addEventListener('click', () => stepBy(1));
  $('#m12').addEventListener('click', () => stepBy(-12));
  $('#p12').addEventListener('click', () => stepBy(12));
  $('#m5y').addEventListener('click', () => stepBy(-60));
  $('#p5y').addEventListener('click', () => stepBy(60));
  $('#btnEvents') && $('#btnEvents').addEventListener('click', () => {
    state.focus = null; state.view = 'overview'; state.curEvent = null; state.curPerson = null;
    for (const p in provNodes) provNodes[p].classList.remove('sel');
    dimPath.classList.remove('on');
    paintMap();
    drawer.classList.add('open');
    renderDrawer();
    const b = $('#dbody'); if (b) b.scrollTop = 0;
  });
  setRate(1);
  addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT') return;
    if (e.key === 'ArrowLeft') { setStep(state.step - (e.shiftKey ? 12 : 1)); e.preventDefault(); }
    if (e.key === 'ArrowRight') { setStep(state.step + (e.shiftKey ? 12 : 1)); e.preventDefault(); }
    if (e.key === ' ') { togglePlay(); e.preventDefault(); }
    if (e.key === 'Home') { clearSelection(); e.preventDefault(); }
    if (e.key === 'Escape') {
      if (state.view !== 'overview') { state.view = 'overview'; state.curEvent = null; state.curPerson = null; renderDrawer(); }
      else clearSelection();
    }
  });

  /* ---------- 9. 着色 + 图例 ---------- */
  function paintMap() {
    const m = at(state.step);
    const nbm = neighborsAt(state.step);
    for (const nm of Object.keys(nbNodes)) {
      const rec = nbm[nm];
      const fi = nbfOf(rec && rec.faction);
      nbNodes[nm].setAttribute('fill', fi.color);
      nbNodes[nm].setAttribute('fill-opacity', state.focus ? .28 : .62);
    }
    for (const nm of Object.keys(nbLabels)) {
      nbLabels[nm].style.display = (!state.focus) ? '' : 'none';
    }
    if (HIST && curLayer && curLayer._items) {
      curLayer._items.forEach(x => {
        const rec = histRec(HIST[histApplied], x.unitKey, x.name);
        const fi = facOf(rec && rec.faction);
        const belong = GEO.paths[x.unitKey] ? x.unitKey : null;   // 与现行省份对应者参与聚焦判断
        const dim = state.focus && belong && state.focus !== belong;
        x.node.setAttribute('fill', fi.color);
        x.node.setAttribute('stroke', fi.color);       // 同色描边盖住县界缝隙
        // 拼接形状用不透明填充与描边：半透明会让同色描边显出县界轮廓
        x.node.setAttribute('fill-opacity', dim ? .4 : 1);
        x.node.setAttribute('stroke-opacity', dim ? .4 : 1);
        x.label.style.display = dim ? 'none' : '';
      });
    }
    terrNodes.forEach(x => {
      const on = state.showTerr && terrActive(x.t, state.step);
      x.node.style.display = on ? '' : 'none';
      x.label.style.display = on && view.k >= 1.15 ? '' : 'none';
      const dim = state.focus && !(x.t.raw.provs || []).includes(state.focus);
      // 不透明填充+同色描边：半透明会让同色描边显出县界
      x.node.setAttribute('fill-opacity', dim ? .3 : 1);
      x.node.setAttribute('stroke-opacity', dim ? .3 : 1);
      (x.line || []).forEach(n => n.setAttribute('opacity', dim ? .3 : 1));
    });
    for (const p of PROVS) {
      const fi = facOf((facRec(p, state.step) || {}).faction);
      const n = provNodes[p];
      n.setAttribute('fill-opacity', state.focus && state.focus !== p ? .4 : 1);
      n.setAttribute('fill', fi.color);
      n.setAttribute('fill-opacity', state.focus && state.focus !== p ? .38 : .93);
    }
    for (const p of PROVS) {
      const t = labelNodes[p]; if (!t) continue;
      const hide = isReplaced(p) || (state.focus && state.focus !== p);
      t.style.display = hide ? 'none' : '';
    }
  }
  let worldLegendAll = false;
  function renderLegend() {
    // 1644—1892 用“入清年份”归属统计
    const box = $('#legend');
    const m = at(state.step), tally = {};
    PROVS.forEach(p => { const f = (facRec(p, state.step) || {}).faction; if (f) tally[f] = (tally[f] || 0) + 1; });
    const nbm = neighborsAt(state.step), nbtally = {};
    Object.keys(nbm).forEach(nm => {
      const f = (nbm[nm] || {}).faction;
      if (f) nbtally[f] = (nbtally[f] || 0) + 1;
    });
    const cell = (f, on, mark) =>
      '<div class="lg' + (on ? '' : ' off') + '" title="' + esc(f.desc || f.name) + '">' +
      '<span class="sw" style="background:' + f.color + '"></span>' + esc(f.name) +
      (on ? '<i>' + on + (mark || '') + '</i>' : '') + '</div>';
    // 只列当月实际出现的势力，避免图例过长
    const keys = Object.keys(FACTION).filter(k => tally[k]).sort((a, b) => tally[b] - tally[a]);
    let html = keys.map(k => cell(FACTION[k], tally[k] || 0)).join('');
    const nk = Object.keys(NBFAC).filter(k => nbtally[k]).sort((a, b) => nbtally[b] - nbtally[a]);
    if (nk.length) {
      html += '<div class="lgsep">周边</div>' + nk.map(k => cell(NBFAC[k], nbtally[k] || 0, '国')).join('');
    }
    const stW = STEPS[state.ti];
    if (WORLD && stW && stW.kind !== 'cn') {
      html = '';                       // 世界模式：只显示世界政体，不混入中国图层图例
      const sl = WORLD.slices[stW.slice | 0];
      const arr = (sl.p || []).map(rec => {
        const geo = WORLD.geoms[rec[1]] || { d: '' };
        return { name: rec[0], size: (geo.d || '').length };
      }).map(x => Object.assign(x, { zh: !!WNAMES[x.name] }))
        .sort((a, b) => (b.zh - a.zh) || (b.size - a.size));
      // 按名字去重（同一政权可能有多块几何）；中文优先，原文英语附在中文之后
      const uniq = [];
      const seenNm = {};
      arr.forEach(x => { if (!seenNm[x.name]) { seenNm[x.name] = 1; uniq.push(x); } });
      const shown = worldLegendAll ? uniq : uniq.slice(0, 30);
      html += '<div class="lgsep">世界政体（' + esc(sl.label) + '，共 ' + uniq.length + ' 个）</div>' +
        shown.map(x => {
          const _pe = polByName(x.name, sl.y);
          const zh = (_pe && _pe.zh) || WNAMES[x.name];
          return '<div class="lg wlg" data-name="' + esc(x.name) + '" title="' + esc(x.name) + '">' +
            '<span class="sw" style="background:' + worldColor(x.name, sl.y) + '"></span>' +
            '<span class="wt">' + esc(zh || x.name) + '</span>' +
            (zh ? '<span class="wen">' + esc(x.name) + '</span>' : '') + '</div>';
        }).join('') +
        (uniq.length > shown.length
          ? '<div class="lgnote lgexp" id="lgWorldMore">另有 ' + (uniq.length - shown.length) +
            ' 个政体未列出 —— 点击展开完整清单</div>'
          : (worldLegendAll && uniq.length > 30
             ? '<div class="lgnote lgexp" id="lgWorldMore">收起清单</div>' : ''));
    }
    const act = activeTerritories(state.step);
    if (state.showTerr && act.length) {
      // 同一势力的根据地颜色相同，按势力归为一组（一行），点击展开明细
      const byFac = {};
      act.forEach(t => { (byFac[t.raw.faction] = byFac[t.raw.faction] || []).push(t); });
      html += '<div class="lgsep">根据地 / 割据区</div>' +
        '<div class="lgnote">按现行县界近似绘制，历史县名对照见各条详情</div>';
      const opened = state.terrOpen || {};
      for (const fk in byFac) {
        const fi = facOf(fk), list = byFac[fk];
        html += '<div class="lg terrgroup' + (opened[fk] ? ' open' : '') + '" data-fac="' + esc(fk) + '"' +
          ' title="点击展开 / 收起各根据地名称">' +
          '<span class="sw" style="background:' + fi.color + ';outline:1px dashed #fff8"></span>' +
          esc(fi.name) + '<i>' + list.length + ' 处</i><b class="tgarrow">▸</b></div>' +
          '<div class="tglist" data-fac="' + esc(fk) + '"' + (opened[fk] ? '' : ' style="display:none"') + '>' +
          list.map(t => '<div class="tgitem" title="' + esc(t.raw.note || t.raw.name) + '">' +
            '<span class="sw small" style="background:' + fi.color + ';outline:1px dashed #fff6"></span>' +
            esc(shortTerrName(t.raw.name)) + '<i>' + t.raw.counties.length + '</i></div>').join('') +
          '</div>';
      }
    }
    if (box._html !== html) {
      box.innerHTML = html;
      // 图例交互（必须在写入 DOM 之后再绑定）
      const more = document.querySelector('#lgWorldMore');
      if (more) more.addEventListener('click', ev => {
        ev.stopPropagation(); worldLegendAll = !worldLegendAll; renderLegend();
      });
      document.querySelectorAll('#legendPanel .wlg').forEach(el2 => {
        el2.style.cursor = 'pointer';
        el2.addEventListener('click', ev => {
          ev.stopPropagation();
          const st2 = STEPS[state.ti];
          const sl2 = WORLD.slices[(st2 || {}).slice | 0];
          if (sl2) showWorldInfo(el2.getAttribute('data-name'), sl2);
        });
      });
      box._html = html;
      box.querySelectorAll('.terrgroup').forEach(g => {
        g.addEventListener('click', () => {
          const fk = g.getAttribute('data-fac');
          state.terrOpen = state.terrOpen || {};
          state.terrOpen[fk] = !state.terrOpen[fk];
          g.classList.toggle('open', state.terrOpen[fk]);
          const list = box.querySelector('.tglist[data-fac="' + fk + '"]');
          if (list) list.style.display = state.terrOpen[fk] ? '' : 'none';
        });
      });
    }
  }

  /* ---------- 10. 启动 ---------- */
  /* 初始化时间轴：定位到 1893 年 1 月（中国逐月段的起点） */
  function initTimeline() {
    if (!STEPS.length) return;
    let ti = 0;
    for (let i = 0; i < STEPS.length; i++) {
      const z = STEPS[i];
      if (z.kind === 'cn' && z.y === Y0 && z.mo === 1) { ti = i; break; }
    }
    state.ti = ti;
    const st = STEPS[ti];
    if (st && st.kind === 'cn') state.step = SI(st.y, st.mo);
  }

  function boot() {
    const b = $('#boot');
    // 画布范围由几何数据决定（含南海诸岛），保证取景与缩放锚点一致
    if (GEO.viewBox) svg.setAttribute('viewBox', GEO.viewBox.join(' '));
    buildLandBase();
    initTimeline();
    renderRegions();
    initSearch();
    initAbout();
    applyTimeMode();
    renderRanges();
    renderTicks();
    renderWorld();
    renderWorldEvents();
    applyHistorical(state.step);
    syncHeader(); paintMap(); renderSparks(); renderNationLane(); renderDrawer();
    b.style.opacity = 0;
    setTimeout(() => b.remove(), 520);
    // 首次进入：以国土（core）填满视口，南海诸岛在下方，可拖动或点按钮查看
    resetView();
  }
  if (EV.length) boot();
  else $('#boot .t').innerHTML = '<b>数据缺失</b>';

  /* ---------- 全国性事件栏：不隶属单一地点的事件用 ★ 芯片单独呈现 ---------- */
  function renderNationLane() {
    const lane = $('#nationLane');
    if (!lane) return;
    const list = (evByMonth.get(state.step) || []).filter(e => e.scope === 'nation');
    lane.innerHTML = '';
    lane.classList.toggle('on', list.length > 0);
    list.slice(0, 6).forEach(e => {
      const c = hel('div', 'nchip');
      c.innerHTML = '<b>★</b>' + esc(e.title) +
        '<i>' + esc((e.date || '').replace(/^\d{4}年/, '')) + '</i>';
      c.addEventListener('click', ev2 => { ev2.stopPropagation(); openEvent(e, true); });
      c.addEventListener('mouseenter', ev2 => showEventTip(ev2, e));
      c.addEventListener('mousemove', moveTip);
      c.addEventListener('mouseleave', hideTip);
      lane.appendChild(c);
    });
    if (list.length > 6) {
      const more = hel('div', 'nchip');
      more.innerHTML = '<i>另有 ' + (list.length - 6) + ' 件…</i>';
      more.addEventListener('click', () => openEvent(list[6], true));
      lane.appendChild(more);
    }
  }

  /* 统一底层：给定月份，返回该月全部图层状态（区划集合 / 各省势力 / 周边 / 割据区 / 事件） */
  function stateAt(step) {
    const s = clamp(step, M0, M1);
    const { y, mo } = stepInfo(s);
    const pi = histPeriodIndex(s);
    const per = pi >= 0 ? HIST[pi] : null;
    return {
      mi: s, year: y, month: mo,
      geom: histGeomId(s),
      period: per ? { label: per.label, note: per.note, replace: per.replace } : null,
      provinces: at(s),
      neighbors: neighborsAt(s),
      territories: activeTerritories(s).map(t => t.raw.name),
      events: (evByMonth.get(s) || []).map(e => e.title),
    };
  }

  window.__APP__ = {
    setStep, setTI, selectProvince, search: doSearch, pickSearch: pickSearch, polityInfo, showAbout, clearSelection, state, monthMap, EV, GEO, FACTION, stateAt,
    focusOn, resetView, stepInfo, view,
    /* 按月跳转：goto(1937, 7) */
    /* goto(1937,7) 按月跳转；idx(1937,7) 返回 0 基月索引（0..1007） */
    goto: (y, mo) => setStep(SI(clamp(+y, Y0, Y1), clamp(+mo || 1, 1, 12))),
    idx: (y, mo) => SI(clamp(+y, Y0, Y1), clamp(+mo || 1, 1, 12)) - M0,
    at: (y, mo) => at(SI(clamp(+y, Y0, Y1), clamp(+mo || 1, 1, 12))),
    M0: M0, M1: M1, NSTEP: NSTEP, TL: DATA.timeline, WORLD: DATA.world,
    WORLD_EV: WEV,
    getView: () => view,
    setView: (k, x, y) => { view.k = k; view.x = x; view.y = y; applyView(false); },
  };
})();
