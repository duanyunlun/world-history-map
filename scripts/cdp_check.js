#!/usr/bin/env node
/**
 * CDP 检查器：启动无头 Edge，打开被测页，抓取 console/异常/自检结果后退出。
 * 用法： node scripts/cdp_check.js <url> [waitMs]
 */
const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const url = process.argv[2] || 'http://127.0.0.1:8777/index.html';
const waitMs = parseInt(process.argv[3] || '12000', 10);
const EDGE = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge';
const PROFILE = fs.mkdtempSync(path.join(os.tmpdir(), 'cdp-'));
const PORT = 9333;

const child = spawn(EDGE, [
  '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
  `--remote-debugging-port=${PORT}`, `--user-data-dir=${PROFILE}`,
  '--window-size=1400,900', 'about:blank',
], { stdio: 'ignore' });

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function getWs() {
  for (let i = 0; i < 50; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/version`);
      const j = await r.json();
      if (j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl;
    } catch (_) {}
    await sleep(200);
  }
  throw new Error('无法连接 DevTools');
}

(async () => {
  const wsUrl = await getWs();
  const ws = new WebSocket(wsUrl);
  let id = 0;
  const pending = new Map();
  const logs = [], errors = [];

  const send = (method, params, sessionId) => new Promise((res, rej) => {
    const mid = ++id;
    pending.set(mid, { res, rej });
    ws.send(JSON.stringify({ id: mid, method, params: params || {}, sessionId }));
  });

  ws.addEventListener('message', ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id).res(m.result); pending.delete(m.id); return; }
    if (m.method === 'Runtime.consoleAPICalled') {
      logs.push('[' + m.params.type + '] ' + (m.params.args || []).map(a =>
        a.value !== undefined ? a.value : (a.description || a.type)).join(' '));
    }
    if (m.method === 'Runtime.exceptionThrown') {
      const d = m.params.exceptionDetails;
      const st = (d.stackTrace && d.stackTrace.callFrames || [])
        .slice(0, 6).map(f => `      ${f.functionName || '<anon>'} @ ${f.url}:${f.lineNumber + 1}:${f.columnNumber}`).join('\n');
      errors.push(`${d.text} ${d.exception && d.exception.description || ''}\n${st}`);
    }
  });

  await new Promise(r => ws.addEventListener('open', r));
  const { targetInfos } = await send('Target.getTargets');
  const page = targetInfos.find(t => t.type === 'page');
  const { sessionId } = await send('Target.attachToTarget', { targetId: page.targetId, flatten: true });
  await send('Page.enable', {}, sessionId);
  await send('Runtime.enable', {}, sessionId);
  await send('Page.navigate', { url }, sessionId);
  await sleep(waitMs);

  const evalJs = async expr => {
    const r = await send('Runtime.evaluate', {
      expression: expr, returnByValue: true, awaitPromise: true,
    }, sessionId);
    if (r.exceptionDetails) return { error: r.exceptionDetails.text + ' ' +
      (r.exceptionDetails.exception && r.exceptionDetails.exception.description) };
    return { value: r.result && r.result.value };
  };

  const out = {};
  out.title = (await evalJs('document.title')).value;
  out.app = (await evalJs(`(function(){try{
      var W=window, A=W.__APP__;
      if(!A){ var F=document.querySelector('iframe'); if(F&&F.contentWindow){W=F.contentWindow;A=W.__APP__;} }
      if(!A) return 'no __APP__';
      return JSON.stringify({step:A.state.step, months:A.monthMap.length, events:A.EV.length,
        header:W.document.querySelector('#yearBig').textContent,
        fill:W.document.querySelector('#provLayer .prov').getAttribute('fill')});
    }catch(e){return 'ERR '+e.message}})()`)).value;
  out.testResult = (await evalJs(`(function(){try{
      var R=window.__TEST_RESULT__;
      if(!R){ var F=document.querySelector('iframe'); R=F&&F.contentWindow?F.contentWindow.__TEST_RESULT__:null; }
      if(!R) return 'none';
      return JSON.stringify({fails:R.checks.filter(c=>!c.pass), errors:R.errors, info:R.info});
    }catch(e){return 'ERR '+e.message}})()`)).value;

  // 交互探测：按月跳转 + 聚焦
  out.probe = (await evalJs(`(function(){try{
      var W=window, A=W.__APP__, out=[];
      if(!A){ var F=document.querySelector('iframe'); if(F&&F.contentWindow){W=F.contentWindow;A=W.__APP__;} }
      var D=W.document;
      if(!A) return 'no __APP__';
      var cases=[[1893,1],[1916,7],[1928,6],[1931,8],[1931,9],[1937,7],[1937,9],[1945,10],[1949,4],[1949,5],[1949,10],[1959,3],[1966,5],[1976,10]];
      var nm=function(y,m,p){return A.FACTION[A.at(y,m)[p].faction].name;};
      cases.forEach(function(c){ A.goto(c[0],c[1]);
        out.push(c[0]+'.'+c[1]+' -> header='+document.querySelector('#yearBig').textContent
          +'.'+document.querySelector('#monthSmall').textContent
          +' 北京='+nm(c[0],c[1],'北京')+' 四川='+nm(c[0],c[1],'四川')+' 辽宁='+nm(c[0],c[1],'辽宁')); });
      A.goto(1949,10); A.selectProvince('四川',true);
      var v=A.getView();
      out.push('focus 四川 k='+v.k.toFixed(2)+' drawerOpen='+document.querySelector('#drawer').classList.contains('open')
        +' evCards='+document.querySelectorAll('#dbody .ev').length
        +' srcLinks='+document.querySelectorAll('#dbody a.src').length
        +' ftlRows='+document.querySelectorAll('#dbody .ftlrow').length);
      out.push('legend='+document.querySelectorAll('#legend .lg').length
        +' sparks='+document.querySelectorAll('#sparkLayer .spark').length
        +' mmark='+document.querySelectorAll('#evbar .mmark').length);
      return out.join('\\n');
    }catch(e){return 'ERR '+e.message+' @ '+(e.stack||'').split('\\n')[1];}})()`)).value;

  console.log('===== 页面标题 =====\n' + out.title);
  console.log('===== 应用状态 =====\n' + out.app);
  console.log('===== 交互探测 =====\n' + out.probe);
  console.log('===== 自检结果 =====\n' + out.testResult);
  console.log('===== 页面异常 (' + errors.length + ') =====');
  errors.slice(0, 8).forEach(e => console.log('  ✗ ' + e));
  console.log('===== console (' + logs.length + ') =====');
  logs.slice(0, 20).forEach(l => console.log('  ' + l));

  try { ws.close(); } catch (_) {}
  child.kill('SIGKILL');
  try { fs.rmSync(PROFILE, { recursive: true, force: true }); } catch (_) {}
  process.exit(0);
})().catch(e => { console.error('检查器失败:', e.message); child.kill('SIGKILL'); process.exit(1); });
