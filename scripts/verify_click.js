#!/usr/bin/env node
/**
 * 用 CDP 真实鼠标事件（Input.dispatchMouseEvent）验证交互，避免合成事件掩盖问题。
 * 用法: node scripts/verify_click.js <url>
 */
const { spawn } = require('child_process');
const fs = require('fs'), os = require('os'), path = require('path');
let url = process.argv[2] || 'http://localhost:8780/';
if (url && !url.includes('nocache=')) url += (url.includes('?')?'&':'?') + 'nocache=' + Date.now();

// —— 本地静态服务守卫：目标为 127.0.0.1:8777 且不可达时自动拉起（避免把环境问题误判成代码问题）
(function ensureServer(){
  try {
    const u = new URL(url);
    if (u.hostname !== '127.0.0.1' || u.port !== '8777') return;
    const cp = require('child_process');
    const res = cp.spawnSync('curl', ['-sf', '-o', '/dev/null', 'http://127.0.0.1:8777/index.html'], {timeout: 2500});
    if (res.status === 0) return;
    const repo = require('path').resolve(__dirname, '..');
    cp.spawn('python3', ['-m', 'http.server', '8777', '--bind', '127.0.0.1'],
             {cwd: repo, detached: true, stdio: 'ignore'}).unref();
    cp.spawnSync('sleep', ['2']);
  } catch (e) {}
})();
const EDGE = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge';
const P = fs.mkdtempSync(path.join(os.tmpdir(), 'cdp-'));
const PORT = 9337;
const ch = spawn(EDGE, ['--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
  `--remote-debugging-port=${PORT}`, `--user-data-dir=${P}`, '--window-size=1400,900', 'about:blank'], { stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  let wsUrl;
  for (let i = 0; i < 50; i++) {
    try { const r = await fetch(`http://127.0.0.1:${PORT}/json/version`); const j = await r.json();
      if (j.webSocketDebuggerUrl) { wsUrl = j.webSocketDebuggerUrl; break; } } catch (_) {}
    await sleep(200);
  }
  const ws = new WebSocket(wsUrl);
  let id = 0; const pend = new Map();
  ws.addEventListener('message', ev => { const m = JSON.parse(ev.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m.result); pend.delete(m.id); } });
  await new Promise(r => ws.addEventListener('open', r));
  const send = (method, params, sid) => new Promise(res => { const mid = ++id; pend.set(mid, res); ws.send(JSON.stringify({ id: mid, method, params: params || {}, sessionId: sid })); });
  const { targetInfos } = await send('Target.getTargets');
  const pg = targetInfos.find(t => t.type === 'page');
  const { sessionId } = await send('Target.attachToTarget', { targetId: pg.targetId, flatten: true });
  await send('Page.enable', {}, sessionId);
  await send('Runtime.enable', {}, sessionId);
  await send('Page.navigate', { url }, sessionId);
  await sleep(9000);

  const ev = async expr => {
    const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true }, sessionId);
    return r.exceptionDetails ? 'ERR ' + r.exceptionDetails.text : r.result.value;
  };
  // 真实鼠标点击
  const realClick = async (x, y) => {
    await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y, button: 'none', clickCount: 0 }, sessionId);
    await send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', clickCount: 1 }, sessionId);
    await sleep(60);
    await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', clickCount: 1 }, sessionId);
  };
  const realDrag = async (x, y, dx, dy) => {
    await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y, button: 'none' }, sessionId);
    await send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', clickCount: 1 }, sessionId);
    for (let i = 1; i <= 5; i++)
      await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: x + dx * i / 5, y: y + dy * i / 5, button: 'left' }, sessionId);
    await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: x + dx, y: y + dy, button: 'left', clickCount: 1 }, sessionId);
  };

  const results = [];
  const check = (name, pass, extra) => results.push({ name, pass: !!pass, extra: extra === undefined ? '' : String(extra) });

  // 1) 各年份下真实点击省份
  for (const [y, m, prov] of [[1929, 5, '山西'], [1937, 9, '四川'], [1949, 10, '广东'], [1893, 1, '新疆']]) {
    await ev(`(function(){var A=window.__APP__; A.clearSelection(); A.goto(${y},${m}); return 1;})()`);
    await sleep(1200);   // 等相机过渡结束
    // 用路径自身的 isPointInFill 取一个“确定在图形内部”的点（地名标注 pointer-events:none，不影响点击）
    const rc = await ev(`(function(){
      var svg=document.querySelector('#map'), pz=document.querySelector('#pz');
      var cands=[].slice.call(document.querySelectorAll('#provLayer .prov[data-name="${prov}"], #histLayer .hprov[data-name="${prov}"]'))
        .filter(function(p){ return p.style.display!=='none' && p.getClientRects().length; });
      if(!cands.length) return null;
      var p=cands[0], bb=p.getBBox();
      var pt=svg.createSVGPoint();
      for(var i=1;i<=14;i++) for(var j=1;j<=14;j++){
        var x=bb.x+bb.width*i/15, y=bb.y+bb.height*j/15;
        pt.x=x; pt.y=y;
        if(p.isPointInFill(pt)){
          var scr=pt.matrixTransform(p.getScreenCTM());
          if(scr.x<=0 || scr.y<=0 || scr.x>=innerWidth || scr.y>=innerHeight) continue;
          // 该点必须真的能点到目标（避免落在割据区等上层图形上）
          var top=document.elementFromPoint(scr.x, scr.y);
          if(top===p) return Math.round(scr.x)+','+Math.round(scr.y);
        }
      }
      return null;})()`);
    if (!rc) { check(`真实点击 ${y}.${m} ${prov} → 放大并弹出侧栏`, false, '未在地图上找到可点击的 ' + prov); continue; }
    const [cx, cy] = String(rc).split(',').map(Number);
    await ev(`(function(){window.__LC__=null;
      document.addEventListener('click', function(e){
        var t=e.target;
        window.__LC__ = (t.getAttribute && t.getAttribute('data-name')) || (t.className&&t.className.baseVal) || t.tagName;
        window.__LCNODE__ = t.tagName + '.' + ((t.className&&t.className.baseVal)||'');
      }, true);
      window.__AT__ = (function(){var el=document.elementFromPoint(${cx},${cy});
        return el ? (el.getAttribute && el.getAttribute('data-name') || el.tagName) : 'none';})();
      return 1;})()`);
    await realClick(cx, cy);
    await sleep(700);
    const st = await ev(`(function(){var A=window.__APP__;
      return JSON.stringify({focus:A.state.focus, k:+A.getView().k.toFixed(2),
        open:document.querySelector('#drawer').classList.contains('open'),
        title:document.querySelector('#dTitle').textContent,
        evCards:document.querySelectorAll('#dbody .ev').length});})()`);
    const o = JSON.parse(st);
    const dbg = await ev(`JSON.stringify({at:window.__AT__, clickTarget:window.__LC__, node:window.__LCNODE__})`);
    check(`真实点击 ${y}.${m} ${prov} → 放大并弹出侧栏`,
      o.focus === prov && o.k > 2 && o.open === true, st + ' ｜调试 ' + dbg);
  }

  // 2) 真实点击事件卡片 → 事件详情
  await ev(`(function(){var A=window.__APP__; A.clearSelection(); A.goto(1937,8); A.selectProvince('上海',false); return 1;})()`);
  await sleep(1200);
  const cardPos = await ev(`(function(){var c=document.querySelector('#dbody .ev'); if(!c) return 'none';
    var r=c.getBoundingClientRect(); return Math.round(r.left+r.width/2)+','+Math.round(r.top+20);})()`);
  if (cardPos !== 'none') {
    const [x, y] = cardPos.split(',').map(Number);
    await realClick(x, y);
    await sleep(400);
    const st = await ev(`JSON.stringify({cat:document.querySelector('#dCat').textContent,
      tl:document.querySelectorAll('#dbody .tli').length, figs:document.querySelectorAll('#dbody .fig').length})`);
    const o = JSON.parse(st);
    check('真实点击事件卡片 → 事件详情面板', o.cat.indexOf('事件详情') >= 0, st);
  } else check('事件卡片存在', false, 'none');

  // 3) 真实拖动仍可平移画布（拖动后不应误触发选中）
  await ev(`(function(){var A=window.__APP__; A.clearSelection(); return 1;})()`);
  await sleep(1200);
  const rc2 = await ev(`(function(){var p=document.querySelector('#provLayer .prov[data-name="四川"]');
    var r=p.getBoundingClientRect(); return Math.round(r.left+r.width/2)+','+Math.round(r.top+r.height/2);})()`);
  const [dx0, dy0] = String(rc2).split(',').map(Number);
  await realDrag(dx0, dy0, 60, 40);
  await sleep(400);
  const dragSt = await ev(`JSON.stringify({focus:window.__APP__.state.focus, open:document.querySelector('#drawer').classList.contains('open')})`);
  const od = JSON.parse(dragSt);
  check('拖动平移后不应误弹出侧栏', od.focus === null && od.open === false, dragSt);

  // 3.5) 世界模式：切到近世并点击政体
  await ev(`(function(){var A=window.__APP__;var rg=A.TL.ranges.filter(function(r){return r.name.indexOf('史前')>=0;})[0];
    A.setTI(rg.from+2,true); return 1;})()`);
  await sleep(700);
  await ev(`(function(){window.__APP__.resetView(); return 1;})()`);
  await sleep(700);
  // 取面积最大的可见政体，并找一个确实命中它自身的点（避免点到被上层遮挡的位置）
  const wp = await ev(`(function(){
    var list=[].slice.call(document.querySelectorAll('#worldLayer .wpol')).filter(function(e){return e.getClientRects().length;});
    if(!list.length) return null;
    list.sort(function(a,b){ var ra=a.getBBox(), rb=b.getBBox(); return rb.width*rb.height - ra.width*ra.height; });
    for (var i=0;i<Math.min(12,list.length);i++){
      var el=list[i], bb=el.getBBox(), svg=document.querySelector('#map'), pt=svg.createSVGPoint();
      for (var a=1;a<=10;a++) for (var b=1;b<=10;b++){
        pt.x=bb.x+bb.width*a/11; pt.y=bb.y+bb.height*b/11;
        if(!el.isPointInFill(pt)) continue;
        var scr=pt.matrixTransform(el.getScreenCTM());
        if(scr.x<4||scr.y<4||scr.x>innerWidth-4||scr.y>innerHeight-4) continue;
        if(document.elementFromPoint(scr.x,scr.y)===el) return Math.round(scr.x)+','+Math.round(scr.y);
      }
    }
    return null;})()`);
  if (wp) {
    const [wx, wy] = String(wp).split(',').map(Number);
    await realClick(wx, wy);
    await sleep(400);
    const cat = await ev(`(document.querySelector('#dCat')||{}).textContent||''`);
    check('世界模式点击政体 → 政体详情', cat.indexOf('世界政体') >= 0, cat);
  } else {
    check('世界模式点击政体 → 政体详情', false, '未找到可点政体');
  }
  await ev(`(function(){var A=window.__APP__;var rg=A.TL.ranges.filter(function(r){return r.name.indexOf('中国近代')>=0;})[0];
    A.setTI(rg.from,true); return 1;})()`);
  await sleep(600);

  // 4) 双击空白处回到全国视野
  await ev(`(function(){var A=window.__APP__; A.selectProvince('四川',true); return 1;})()`);
  await sleep(900);
  const st0 = JSON.parse(await ev(`JSON.stringify({k:+window.__APP__.getView().k.toFixed(2), focus:window.__APP__.state.focus})`));
  // 先向东拖一段，把海面移入视野
  const c0 = await ev(`(function(){var r=document.querySelector('#stage').getBoundingClientRect();
    return Math.round(r.left+r.width/2)+','+Math.round(r.top+r.height/2);})()`);
  { const [cx0, cy0] = String(c0).split(',').map(Number);
    await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: cx0, y: cy0, button: 'none' }, sessionId);
    await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: cx0, y: cy0, button: 'left', clickCount: 1 }, sessionId);
    for (let i = 1; i <= 6; i++)
      await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: cx0 - 40 * i, y: cy0, button: 'left' }, sessionId);
    await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: cx0 - 240, y: cy0, button: 'left', clickCount: 1 }, sessionId);
    await sleep(300);
  }
  // 找一个“海面/空白”点：命中元素既非省份也不是光点/割据区
  const findBlank = () => ev(`(function(){var r=document.querySelector('#stage').getBoundingClientRect();
    for (var iy=3; iy<=37; iy+=2) for (var ix=6; ix<=58; ix+=2) {
      var x=r.left+r.width*ix/60, y=r.top+r.height*iy/40;
      var el=document.elementFromPoint(x,y);
      if (!el) continue;
      // 必须是 SVG 内部的海面底图（rect）或 svg 本身，确保双击事件能到达 SVG
      var isSea = (el.tagName === 'rect') || (el.id === 'map');
      if (isSea) return Math.round(x)+','+Math.round(y);
    }
    return null;})()`);
  let vp = await findBlank();
  if (!vp) {
    // 视野内全是陆地：先缩小一档再找（不改变“双击回到全国”的验证含义）
    await ev(`(function(){var A=window.__APP__,v=A.getView();A.setView(v.k*0.4, v.x, v.y);return 1;})()`);
    await sleep(400);
    vp = await findBlank();
  }
  if (!vp) { check('双击空白处回到全国视野', false, '未找到空白点'); }
  else {
  const [vx, vy] = String(vp).split(',').map(Number);
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: vx, y: vy, button: 'left', clickCount: 1 }, sessionId);
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: vx, y: vy, button: 'left', clickCount: 1 }, sessionId);
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: vx, y: vy, button: 'left', clickCount: 2 }, sessionId);
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: vx, y: vy, button: 'left', clickCount: 2 }, sessionId);
  await sleep(900);
  const st1 = JSON.parse(await ev(`JSON.stringify({k:+window.__APP__.getView().k.toFixed(2), focus:window.__APP__.state.focus})`));
  // 关键行为：清除选中并退回整体取景（世界画布下中国取景 k 值与旧版不同，故只校验“确实拉远且清空选中”）
  check('双击空白处回到全国视野', !!st0.focus && !st1.focus && st1.k < st0.k,
        JSON.stringify(st0) + ' → ' + JSON.stringify(st1));
  }

  console.log('===== 真实鼠标交互验证 =====');
  let fail = 0;
  results.forEach(r => { if (!r.pass) fail++; console.log((r.pass ? '  PASS  ' : '  FAIL  ') + r.name + (r.extra ? '  ' + r.extra : '')); });
  console.log(`  —— ${results.length - fail}/${results.length} 通过`);
  ws.close(); ch.kill('SIGKILL'); process.exit(fail ? 1 : 0);
})();
