#!/usr/bin/env node
/** 在页面里执行一段脚本后截图：node scripts/cdp_shot.js <url> <out.png> [jsFile] */
const { spawn } = require('child_process');
const fs=require('fs'),os=require('os'),path=require('path');
let url = process.argv[2], out=process.argv[3], jsFile=process.argv[4];
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
// 附加唯一参数，避免浏览器缓存使验证落到旧产物
const SIZE=(process.argv[5]||process.env.SHOT_SIZE||'1400,940');
const EDGE='/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge';
const P=fs.mkdtempSync(path.join(os.tmpdir(),'cdp-')); const PORT=9336;
const ch=spawn(EDGE,['--headless=new','--disable-gpu','--no-sandbox','--hide-scrollbars',
  `--remote-debugging-port=${PORT}`,`--user-data-dir=${P}`,`--window-size=${SIZE}`,'about:blank'],{stdio:'ignore'});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
  let u;
  for(let i=0;i<50;i++){try{const r=await fetch(`http://127.0.0.1:${PORT}/json/version`);const j=await r.json();if(j.webSocketDebuggerUrl){u=j.webSocketDebuggerUrl;break;}}catch(e){} await sleep(200);}
  const ws=new WebSocket(u); let id=0; const pend=new Map();
  ws.addEventListener('message',ev=>{const m=JSON.parse(ev.data); if(m.id&&pend.has(m.id)){pend.get(m.id)(m.result);pend.delete(m.id);}});
  await new Promise(r=>ws.addEventListener('open',r));
  const send=(method,params,sid)=>new Promise(res=>{const mid=++id;pend.set(mid,res);ws.send(JSON.stringify({id:mid,method,params:params||{},sessionId:sid}));});
  const {targetInfos}=await send('Target.getTargets'); const pg=targetInfos.find(t=>t.type==='page');
  const {sessionId}=await send('Target.attachToTarget',{targetId:pg.targetId,flatten:true});
  await send('Page.enable',{},sessionId); await send('Runtime.enable',{},sessionId);
  await send('Page.navigate',{url},sessionId); await sleep(9000);
  if(jsFile){
    const expr=fs.readFileSync(jsFile,'utf8');
    const r=await send('Runtime.evaluate',{expression:expr,returnByValue:true,awaitPromise:true},sessionId);
    if(r.exceptionDetails) console.log('注入异常:',r.exceptionDetails.text);
    else console.log('注入结果:',JSON.stringify(r.result.value));
    await sleep(1600);
  }
  const shot=await send('Page.captureScreenshot',{format:'png'},sessionId);
  fs.writeFileSync(out,Buffer.from(shot.data,'base64'));
  console.log('已截图:',out);
  ws.close(); ch.kill('SIGKILL'); process.exit(0);
})();
