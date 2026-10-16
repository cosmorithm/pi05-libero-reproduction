#!/usr/bin/env python3
"""Authenticated, dependency-free web dashboard for LIBERO visualization."""

from __future__ import annotations

import argparse
import hmac
import json
import os
import secrets
import subprocess
import threading
import time
from collections import deque
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path("/root/autodl-tmp/pi05-libero-reproduction")
OUTPUT = ROOT / "outputs" / "smoke"
REPORT = OUTPUT / "report.json"
PROGRESS = OUTPUT / "progress.json"
TOKEN_FILE = ROOT / ".dashboard_token"
RUN_LOG = ROOT / "logs" / "dashboard-run.log"
FRAME_NAMES = {f"image{suffix}.png" for suffix in ("", "2", "3", "4", "5", "6", "7")}
SUITES = {
    "libero_spatial": 10,
    "libero_object": 10,
    "libero_goal": 10,
    "libero_10": 10,
    "libero_90": 90,
}
SUITE_MAX_STEPS = {
    "libero_spatial": 280,
    "libero_object": 280,
    "libero_goal": 300,
    "libero_10": 520,
    "libero_90": 400,
}

INDEX_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LIBERO Observation Deck · 4090D</title>
  <style>
    :root{--ink:#eff8f9;--muted:#8fa6ad;--bg:#071013;--panel:#0e1a1f;--line:#20353b;--cyan:#55e6cf;--amber:#ffba66;--red:#ff7373;--blue:#6cb8ff}
    *{box-sizing:border-box}body{margin:0;color:var(--ink);background:radial-gradient(circle at 8% -10%,#163d3a 0,transparent 30%),radial-gradient(circle at 96% 0,#142f43 0,transparent 28%),var(--bg);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
    .shell{width:min(1480px,calc(100% - 32px));margin:auto;padding:26px 0 48px}header{display:flex;align-items:flex-end;justify-content:space-between;gap:18px;margin-bottom:18px}
    .eyebrow{color:var(--cyan);font:750 11px/1 ui-monospace,SFMono-Regular,monospace;letter-spacing:.17em;text-transform:uppercase}.title{margin:8px 0 0;font-size:clamp(27px,4vw,46px);line-height:1;letter-spacing:-.045em}.subtitle{margin:10px 0 0;color:var(--muted);font-size:13px}
    .connection{display:flex;align-items:center;gap:9px;color:var(--muted);font:650 12px/1 ui-monospace,SFMono-Regular,monospace}.dot{width:9px;height:9px;border-radius:50%;background:var(--amber);box-shadow:0 0 16px currentColor}.dot.ok{background:var(--cyan)}.dot.error{background:var(--red)}
    .card{border:1px solid var(--line);border-radius:16px;background:rgba(14,26,31,.94);box-shadow:0 18px 60px #0004;overflow:hidden}.mission{display:grid;grid-template-columns:1fr auto;gap:18px;align-items:center;padding:18px 20px;margin-bottom:14px}.mission small{color:var(--cyan);font:700 10px/1 ui-monospace,monospace;letter-spacing:.13em;text-transform:uppercase}.mission h2{margin:8px 0 0;font-size:clamp(17px,2.4vw,25px);font-weight:650;line-height:1.35}.pill{padding:8px 11px;border-radius:999px;border:1px solid #31525a;color:#b9ced3;background:#0a1519;font:650 11px/1 ui-monospace,monospace;white-space:nowrap}
    .progress-wrap{display:grid;grid-template-columns:auto 1fr auto;gap:12px;align-items:center;padding:0 2px;margin:0 0 14px;color:var(--muted);font:650 11px/1 ui-monospace,monospace}.track{height:7px;border-radius:999px;background:#132329;overflow:hidden}.bar{height:100%;width:0;background:linear-gradient(90deg,var(--cyan),var(--blue));transition:width .35s ease}.progress-state{color:var(--ink)}
    .gallery-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:18px 2px 10px}.gallery-head h2{margin:0;font-size:14px}.size-control{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:11px}.size-control select{width:auto;padding:7px 30px 7px 9px}.camera-grid{--camera-min:290px;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,var(--camera-min)),1fr));gap:12px}.camera-head{display:flex;align-items:center;justify-content:space-between;padding:10px 12px;border-bottom:1px solid var(--line)}.camera-title{display:flex;align-items:center;gap:7px;font:700 10px/1 ui-monospace,monospace;text-transform:uppercase;letter-spacing:.06em}.tag{padding:4px 6px;border-radius:5px;background:#183038;color:var(--cyan);font-size:8px}.tag.observe{background:#2f281c;color:var(--amber)}.camera-meta{color:var(--muted);font:600 9px/1 ui-monospace,monospace}.viewport{aspect-ratio:1;display:grid;place-items:center;background:linear-gradient(135deg,#050a0c,#091116)}.viewport img{display:block;width:100%;height:100%;object-fit:contain}.viewport img:not([src]){visibility:hidden}
    .lower{display:grid;grid-template-columns:minmax(320px,.72fr) 1.28fr;gap:12px;margin-top:12px}.controls,.telemetry{padding:18px}.section-title{display:flex;align-items:center;justify-content:space-between;margin:0 0 15px;font-size:14px}.fields{display:grid;grid-template-columns:1fr 1fr;gap:11px}label{display:grid;gap:6px;color:var(--muted);font-size:11px}select,input{width:100%;padding:10px 11px;border:1px solid var(--line);border-radius:9px;background:#081216;color:var(--ink);outline:none}select:focus,input:focus{border-color:var(--cyan)}.buttons{display:flex;gap:9px;margin-top:14px}button{flex:1;border:0;border-radius:9px;padding:11px 12px;background:var(--cyan);color:#04231d;font-weight:800;cursor:pointer}button.secondary{background:#24363d;color:var(--ink)}button.danger{background:#ff7a72;color:#2b0808}button:disabled{opacity:.42;cursor:not-allowed}.hint{margin:12px 0 0;color:var(--muted);font-size:11px;line-height:1.55}
    .metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:9px}.metric{padding:12px;border:1px solid var(--line);border-radius:10px;background:#081216}.metric span{display:block;color:var(--muted);font:650 9px/1.2 ui-monospace,monospace;text-transform:uppercase;letter-spacing:.06em}.metric strong{display:block;margin-top:7px;font:750 14px/1.2 ui-monospace,monospace;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.friendly{margin-top:10px;padding:13px;border:1px solid #26424a;border-radius:10px;background:#0b181c;color:#c9dadd;font-size:12px;line-height:1.55}details{margin-top:10px;border:1px solid var(--line);border-radius:10px;background:#071014}summary{padding:11px 13px;color:var(--muted);font-size:11px;cursor:pointer}pre{max-height:220px;overflow:auto;margin:0;padding:0 13px 13px;color:#9eb2b9;font:10px/1.55 ui-monospace,monospace;white-space:pre-wrap}
    @media(max-width:980px){.lower{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(4,1fr)}}@media(max-width:650px){.shell{width:min(100% - 20px,1480px);padding-top:18px}header,.mission{align-items:flex-start;grid-template-columns:1fr;flex-direction:column}.camera-grid{--camera-min:100%!important}.metrics{grid-template-columns:1fr 1fr}.fields{grid-template-columns:1fr}.buttons{flex-wrap:wrap}.buttons button{min-width:40%}.gallery-head{align-items:flex-start;flex-direction:column}}
  </style>
</head>
<body><main class="shell">
  <header><div><div class="eyebrow">Pi0.5 Reproduction · All Camera Monitor</div><h1 class="title">LIBERO Observation Deck</h1><p class="subtitle">7 路 MuJoCo 相机 · π0.5 策略 · GPU 遥测</p></div><div class="connection"><i id="dot" class="dot"></i><span id="connection">正在连接</span></div></header>
  <section class="card mission"><div><small>Current language instruction</small><h2 id="instruction">运行仿真后显示当前任务指令</h2></div><div id="missionTag" class="pill">NO ACTIVE EPISODE</div></section>
  <div class="progress-wrap"><span id="phase" class="progress-state">等待运行</span><div class="track"><div id="bar" class="bar"></div></div><span id="stepCount">0 / 0</span></div>
  <section class="lower">
    <article class="card controls"><h2 class="section-title"><span>运行设置</span><span class="pill">20 Hz</span></h2><div class="fields">
      <label>任务集合<select id="suite"><option>libero_spatial</option><option>libero_object</option><option>libero_goal</option><option>libero_10</option><option>libero_90</option></select></label>
      <label>Task ID<input id="task" type="number" min="0" max="9" value="0"></label>
      <label>动作模式<select id="actionMode"><option value="pi05">π0.5 真实策略</option><option value="demo">可视化演示动作</option><option value="idle">静止 / 接口检查</option></select></label>
      <label>随机种子<input id="seed" type="number" min="0" value="7"></label>
      <label>仿真步数<input id="steps" type="number" min="1" max="1000" value="80"></label>
    </div><div class="buttons"><button id="run">运行可视化</button><button id="stop" class="danger">停止</button><button id="refresh" class="secondary">刷新</button></div>
    <p class="hint">π0.5 模式会加载微调 checkpoint、执行真实模型动作，并将 7 路画面逐帧录制为 MP4。首次运行需要等待模型加载。</p></article>
    <article class="card telemetry"><h2 class="section-title"><span>运行状态</span><span id="elapsed" class="pill">—</span></h2><div class="metrics">
      <div class="metric"><span>Episode</span><strong id="state">READY</strong></div><div class="metric"><span>Suite / Task</span><strong id="active">—</strong></div>
      <div class="metric"><span>GPU</span><strong id="gpu">—</strong></div><div class="metric"><span>VRAM / Temp</span><strong id="vram">—</strong></div>
      <div class="metric"><span>Reward</span><strong id="reward">—</strong></div><div class="metric"><span>Success</span><strong id="success">—</strong></div>
      <div class="metric"><span>Action</span><strong id="mode">—</strong></div><div class="metric"><span>Runtime</span><strong id="runtime">—</strong></div>
      <div class="metric"><span>Model Load</span><strong id="modelLoad">—</strong></div><div class="metric"><span>Inference</span><strong id="inference">—</strong></div>
    </div><div id="friendly" class="friendly">服务准备就绪。选择参数后点击“运行可视化”。</div><details><summary>技术日志（一般不需要查看）</summary><pre id="log">暂无日志</pre></details></article>
  </section>
  <div class="gallery-head"><h2>全部相机视角</h2><label class="size-control">画面大小<select id="viewSize"><option value="220">紧凑</option><option value="290" selected>标准</option><option value="400">大图</option></select></label></div>
  <section id="cameraGrid" class="camera-grid">
    <article class="card camera"><div class="camera-head"><div class="camera-title">Agent View <span class="tag">策略主视角</span></div><span class="camera-meta">image · 256²</span></div><div class="viewport"><img id="cam1" alt="Agent view"></div></article>
    <article class="card camera"><div class="camera-head"><div class="camera-title">Eye in Hand <span class="tag">腕部策略相机</span></div><span class="camera-meta">image2 · 256²</span></div><div class="viewport"><img id="cam2" alt="Wrist camera"></div></article>
    <article class="card camera"><div class="camera-head"><div class="camera-title">Gallery View <span class="tag observe">展示广角</span></div><span class="camera-meta">image3 · 256²</span></div><div class="viewport"><img id="cam3" alt="Gallery view"></div></article>
    <article class="card camera"><div class="camera-head"><div class="camera-title">Bird View <span class="tag observe">俯视</span></div><span class="camera-meta">image4 · 256²</span></div><div class="viewport"><img id="cam4" alt="Bird view"></div></article>
    <article class="card camera"><div class="camera-head"><div class="camera-title">Front View <span class="tag observe">正面</span></div><span class="camera-meta">image5 · 256²</span></div><div class="viewport"><img id="cam5" alt="Front view"></div></article>
    <article class="card camera"><div class="camera-head"><div class="camera-title">Side View <span class="tag observe">侧面</span></div><span class="camera-meta">image6 · 256²</span></div><div class="viewport"><img id="cam6" alt="Side view"></div></article>
    <article class="card camera"><div class="camera-head"><div class="camera-title">Robot View <span class="tag observe">机器人本体</span></div><span class="camera-meta">image7 · 256²</span></div><div class="viewport"><img id="cam7" alt="Robot view"></div></article>
  </section>
</main>
<script>
  const q=new URLSearchParams(location.search);let token=q.get('token')||localStorage.getItem('liberoToken')||'';if(q.get('token'))localStorage.setItem('liberoToken',token);
  const api=p=>`${p}?token=${encodeURIComponent(token)}`,el=id=>document.getElementById(id);let lastStamp='';const cams=['','2','3','4','5','6','7'];
  const maxSteps={libero_spatial:280,libero_object:280,libero_goal:300,libero_10:520,libero_90:400};
  const syncStepLimit=()=>{const suite=el('suite').value,mode=el('actionMode').value;el('task').max=suite==='libero_90'?89:9;if(mode==='pi05'){el('steps').max=maxSteps[suite]||280;if(el('steps').value==='80')el('steps').value=maxSteps[suite]||280}else{el('steps').max=1000}};
  el('suite').addEventListener('change',syncStepLimit);el('actionMode').addEventListener('change',syncStepLimit);
  syncStepLimit();
  const savedSize=localStorage.getItem('liberoViewSize')||'290';el('viewSize').value=savedSize;el('cameraGrid').style.setProperty('--camera-min',`${savedSize}px`);el('viewSize').addEventListener('change',event=>{const size=event.target.value;localStorage.setItem('liberoViewSize',size);el('cameraGrid').style.setProperty('--camera-min',`${size}px`)});
  function friendlyText(d,p,r){if(d.error)return `运行失败：${d.error}`;if(d.running&&p.phase==='loading_model')return `正在加载 π0.5 checkpoint 和 processor，通常需要两分钟左右。加载完成后会自动开始 episode。`;if(d.running&&p.phase==='initializing')return '正在创建 MuJoCo 场景、加载初始状态和 7 路相机。';if(d.running&&p.action_mode==='pi05')return `π0.5 正在控制机械臂：第 ${p.current_step||0} / ${p.total_steps||d.request?.steps||0} 步，画面会实时更新。`;if(d.running)return `物理仿真正在推进：第 ${p.current_step||0} / ${p.total_steps||d.request?.steps||0} 步。画面会随相机帧自动更新。`;if(p.phase==='complete'&&p.action_mode==='pi05'){const videoCount=r.video_paths?Object.keys(r.video_paths).length:0;return `π0.5 episode 已完成 ${p.current_step||r.steps_executed||0} 步，${p.is_success?'任务成功':'任务未成功'}，已生成 ${videoCount} 路 MP4 录像。`}if(p.phase==='complete')return `本次 episode 已完成 ${p.current_step||r.steps_executed||0} 步。${p.is_success?'任务成功。':'当前是演示动作，没有完成任务是正常结果。'}`;return '服务准备就绪。选择参数后点击“运行可视化”。'}
  async function status(){try{const response=await fetch(api('/api/status'),{cache:'no-store'});if(!response.ok)throw new Error(response.status===401?'访问 token 无效':`HTTP ${response.status}`);const d=await response.json(),r=d.report||{},p=d.progress||r||{};
    el('dot').className='dot '+(d.error?'error':'ok');el('connection').textContent=d.running?(p.action_mode==='pi05'?'π0.5 ROLLOUT':'SIMULATION RUNNING'):'SERVER ONLINE';el('state').textContent=d.running?(p.phase==='loading_model'?'LOADING':'RUNNING'):(d.error?'ERROR':(p.phase==='complete'?'COMPLETE':'READY'));
    const suite=p.suite||d.request?.suite||r.suite,task=p.task_id??d.request?.task_id??r.task_id;el('active').textContent=suite?`${suite} / ${task}`:'—';el('missionTag').textContent=suite?`${suite.toUpperCase()} · TASK ${task}`:'NO ACTIVE EPISODE';el('instruction').textContent=p.task_instruction||r.task_instruction||'运行仿真后显示当前任务指令';
    const current=+(p.current_step??r.steps_executed??0),total=+(p.total_steps??r.steps_requested??0),pct=total?Math.min(100,current/total*100):0;el('bar').style.width=`${pct}%`;el('stepCount').textContent=`${current} / ${total}`;el('phase').textContent=p.phase==='loading_model'?'加载 π0.5 模型':(p.phase==='initializing'?'初始化场景':(d.running?(p.action_mode==='pi05'?'π0.5 控制仿真':'推进物理仿真'):(p.phase==='complete'?'Episode 完成':'等待运行')));
    el('gpu').textContent=d.gpu?`${d.gpu.utilization}%`:'—';el('vram').textContent=d.gpu?`${d.gpu.memory_used} MiB / ${d.gpu.temperature}°C`:'—';el('reward').textContent=p.reward??(Array.isArray(r.reward)?r.reward[0]:'—');const success=p.is_success??(Array.isArray(r.is_success)?r.is_success[0]:null);el('success').textContent=success===null?'—':(success?'YES':'NO');el('mode').textContent=((p.action_mode||r.action_mode||d.request?.action_mode||'—')==='pi05')?'π0.5':((p.action_mode||r.action_mode||d.request?.action_mode||'—').toUpperCase());el('runtime').textContent=r.duration_seconds?`${r.duration_seconds}s`:'—';el('modelLoad').textContent=r.model_load_seconds?`${r.model_load_seconds.toFixed(1)}s`:'—';const inference=p.mean_inference_seconds??r.mean_inference_seconds;el('inference').textContent=inference!==null&&inference!==undefined?`${(inference*1000).toFixed(1)} ms`:'—';
    const started=d.started_at||0;el('elapsed').textContent=d.running&&started?`${Math.floor(Date.now()/1000-started)}s elapsed`:(r.duration_seconds?`${r.duration_seconds}s total`:'—');el('friendly').textContent=friendlyText(d,p,r);el('log').textContent=(d.log||[]).join('\n')||'暂无日志';el('run').disabled=d.running;el('stop').disabled=!d.running;
    if(d.image_stamp&&d.image_stamp!==lastStamp){lastStamp=d.image_stamp;for(const suffix of cams)el(`cam${suffix||'1'}`).src=api(`/frames/image${suffix}.png`)+`&v=${lastStamp}`;}}
    catch(error){el('dot').className='dot error';el('connection').textContent=error.message;el('state').textContent='OFFLINE';el('friendly').textContent=`无法读取状态：${error.message}`;}}
  async function post(path,body={}){const response=await fetch(api(path),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),data=await response.json();if(!response.ok)throw new Error(data.error||`HTTP ${response.status}`);return data}
  el('run').onclick=async()=>{try{await post('/api/run',{suite:el('suite').value,task_id:+el('task').value,seed:+el('seed').value,steps:+el('steps').value,action_mode:el('actionMode').value});lastStamp='';status()}catch(error){alert(error.message)}};
  el('stop').onclick=async()=>{try{await post('/api/stop');status()}catch(error){alert(error.message)}};el('refresh').onclick=()=>{lastStamp='';status()};status();setInterval(status,700);
</script></body></html>"""


state_lock = threading.Lock()
state = {"running": False, "error": None, "request": None, "started_at": None, "finished_at": None, "log": deque(maxlen=120), "process": None}
gpu_cache = {"time": 0.0, "value": None}


def load_or_create_token() -> str:
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    token = secrets.token_urlsafe(24)
    TOKEN_FILE.write_text(token + "\n", encoding="utf-8")
    TOKEN_FILE.chmod(0o600)
    return token


TOKEN = os.environ.get("LIBERO_DASHBOARD_TOKEN") or load_or_create_token()


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    except Exception:
        return None


def gpu_status() -> dict | None:
    now = time.monotonic()
    if now - gpu_cache["time"] < 2:
        return gpu_cache["value"]
    try:
        output = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,temperature.gpu", "--format=csv,noheader,nounits"],
            text=True,
            timeout=2,
        ).strip().splitlines()[0]
        utilization, memory_used, temperature = [part.strip() for part in output.split(",")]
        value = {"utilization": int(utilization), "memory_used": int(memory_used), "temperature": int(temperature)}
    except Exception:
        value = None
    gpu_cache.update(time=now, value=value)
    return value


def run_simulation(request: dict) -> None:
    script = (
        "pi05_episode.py"
        if request["action_mode"] == "pi05"
        else "smoke_libero.py"
    )
    command = [
        str(ROOT / ".venv/bin/python"), str(ROOT / "scripts" / script),
        "--suite", request["suite"], "--task-id", str(request["task_id"]),
        "--seed", str(request["seed"]), "--steps", str(request["steps"]),
    ]
    if request["action_mode"] == "pi05":
        command.extend(["--image-every", "1"])
    else:
        command.extend([
            "--action-mode", request["action_mode"],
            "--image-every", "2",
            "--step-delay", "0.04",
        ])
    environment = os.environ.copy()
    environment.update(MUJOCO_GL="egl", LIBERO_CONFIG_PATH=str(ROOT / "home/.libero"), HF_HOME=str(ROOT / "cache/huggingface"), HF_ENDPOINT="https://hf-mirror.com", HF_HUB_DISABLE_XET="1")
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    try:
        with RUN_LOG.open("w", encoding="utf-8") as log_file:
            process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            with state_lock:
                state["process"] = process
            assert process.stdout is not None
            for line in process.stdout:
                line = line.rstrip()
                log_file.write(line + "\n")
                log_file.flush()
                with state_lock:
                    state["log"].append(line)
            return_code = process.wait()
        with state_lock:
            state["error"] = None if return_code == 0 else f"仿真进程退出码 {return_code}"
    except Exception as exc:
        with state_lock:
            state["error"] = f"{type(exc).__name__}: {exc}"
            state["log"].append(state["error"])
    finally:
        with state_lock:
            state["running"] = False
            state["process"] = None
            state["finished_at"] = time.time()


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "LIBERODashboard/3.0"

    def log_message(self, format: str, *args) -> None:
        message = format % args
        if TOKEN:
            message = message.replace(TOKEN, "[REDACTED]")
        print(f"{self.address_string()} - {message}", flush=True)

    def send_bytes(self, payload: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.end_headers()
        self.wfile.write(payload)

    def send_json(self, payload: dict, status: int = 200) -> None:
        self.send_bytes(json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8", status)

    def authorized(self, query: dict[str, list[str]]) -> bool:
        supplied = query.get("token", [""])[0]
        return bool(supplied) and hmac.compare_digest(supplied, TOKEN)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/":
            self.send_bytes(INDEX_HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if parsed.path == "/healthz":
            self.send_json({"status": "ok", "version": 3})
            return
        if not self.authorized(query):
            self.send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return
        if parsed.path == "/api/status":
            frame_paths = [OUTPUT / name for name in FRAME_NAMES]
            stamp = max((path.stat().st_mtime_ns for path in frame_paths if path.exists()), default=0)
            with state_lock:
                snapshot = {key: value for key, value in state.items() if key not in {"process", "log"}}
                snapshot["log"] = list(state["log"])
            snapshot.update(report=read_json(REPORT), progress=read_json(PROGRESS), gpu=gpu_status(), image_stamp=str(stamp))
            self.send_json(snapshot)
            return
        if parsed.path.startswith("/frames/"):
            name = parsed.path.removeprefix("/frames/")
            if name not in FRAME_NAMES:
                self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                return
            path = OUTPUT / name
            if not path.is_file():
                self.send_json({"error": "frame not ready"}, HTTPStatus.NOT_FOUND)
                return
            self.send_bytes(path.read_bytes(), "image/png")
            return
        self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if not self.authorized(query):
            self.send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length > 4096:
            self.send_json({"error": "request too large"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            self.send_json({"error": "invalid JSON"}, HTTPStatus.BAD_REQUEST)
            return
        if parsed.path == "/api/run":
            try:
                suite = str(body.get("suite", "libero_spatial"))
                task_id = int(body.get("task_id", 0))
                seed = int(body.get("seed", 7))
                default_steps = (
                    SUITE_MAX_STEPS.get(suite, 280)
                    if str(body.get("action_mode", "demo")) == "pi05"
                    else 80
                )
                steps = int(body.get("steps", default_steps))
                action_mode = str(body.get("action_mode", "demo"))
                if suite not in SUITES or not 0 <= task_id < SUITES[suite]:
                    raise ValueError("suite 或 task ID 不合法")
                if action_mode not in {"idle", "demo", "pi05"}:
                    raise ValueError("动作模式不合法")
                if not 0 <= seed <= 2_147_483_647 or not 1 <= steps <= 1000:
                    raise ValueError("seed 或 steps 超出范围")
            except (TypeError, ValueError) as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            request = {"suite": suite, "task_id": task_id, "seed": seed, "steps": steps, "action_mode": action_mode}
            with state_lock:
                if state["running"]:
                    self.send_json({"error": "已有仿真正在运行"}, HTTPStatus.CONFLICT)
                    return
                state.update(running=True, error=None, request=request, started_at=time.time(), finished_at=None)
                state["log"].clear()
                state["log"].append(f"Starting {suite} task {task_id}, seed={seed}, steps={steps}, mode={action_mode}")
            threading.Thread(target=run_simulation, args=(request,), daemon=True).start()
            self.send_json({"accepted": True, "request": request}, HTTPStatus.ACCEPTED)
            return
        if parsed.path == "/api/stop":
            with state_lock:
                process = state["process"]
            if process is not None and process.poll() is None:
                process.terminate()
                self.send_json({"stopping": True})
            else:
                self.send_json({"stopping": False})
            return
        self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=6006)
    args = parser.parse_args()
    print(f"LIBERO dashboard v3 listening on http://{args.host}:{args.port}", flush=True)
    print("Access token: loaded from .dashboard_token", flush=True)
    ThreadingHTTPServer((args.host, args.port), DashboardHandler).serve_forever()


if __name__ == "__main__":
    main()
