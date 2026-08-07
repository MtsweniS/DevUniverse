import os, sys, io, zipfile, tarfile, json, glob, secrets
from datetime import datetime
from flask import Flask, request, jsonify, send_file, render_template_string
from werkzeug.utils import secure_filename

# ===== ENV SECURITY FIX =====
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(16))
JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_hex(16))
ENV_MODE = os.getenv("ENV", "production")

def is_safe_path(p):
    if ".." in p or p.startswith("/"): return False
    if any(c in p for c in [";", "|", "`", "$", "&"]): return False
    return True

app = Flask(__name__)
app.secret_key = SECRET_KEY
BASE = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.join(BASE, "workspace")
SNAPSHOT_DIR = os.path.join(BASE, "snapshots")
os.makedirs(WORKSPACE, exist_ok=True)
os.makedirs(SNAPSHOT_DIR, exist_ok=True)

def create_snapshot(trigger="manual"):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"snap_{trigger}_{ts}.tar.gz"
    path = os.path.join(SNAPSHOT_DIR, name)
    try:
        with tarfile.open(path, "w:gz") as tar:
            for root, dirs, files in os.walk(WORKSPACE):
                dirs[:] = [d for d in dirs if d not in ['__pycache__', 'node_modules', '.git']]
                for f in files:
                    full = os.path.join(root, f)
                    tar.add(full, arcname=os.path.relpath(full, BASE))
        meta = {"s3Key": path, "trigger": trigger, "time": ts, "size": os.path.getsize(path)}
        json.dump(meta, open(os.path.join(SNAPSHOT_DIR, "latest.json"), "w"))
        return meta
    except Exception as e:
        return {"error": str(e)}

HTML = """
<!DOCTYPE html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{background:#0f0f10;color:#e8e8e8;font-family:system-ui;margin:0;padding:12px}
.card{background:#1a1a1d;border:1px solid #2a2a2e;border-radius:16px;padding:16px;margin-bottom:14px}
.badge{background:#22c55e;color:#000;padding:4px 10px;border-radius:20px;font-size:12px;font-weight:700}
.badge-sec{background:#f59e0b;color:#000;padding:3px 8px;border-radius:20px;font-size:10px;margin-left:6px}
.btn{border:none;border-radius:24px;padding:12px 20px;font-weight:700;cursor:pointer;font-size:14px}
.btn-blue{background:#3b82f6;color:white}.btn-dark{background:#2a2a2e;color:#d0d0d0;border:1px solid #333}
textarea{width:100%;height:300px;background:#0a0a0a;color:#22c55e;border:1px solid #2a2a2e;border-radius:12px;padding:12px;font-family:monospace;font-size:14px;box-sizing:border-box}
#output{background:#0a0a0a;border:1px solid #2a2a2e;border-radius:12px;padding:12px;min-height:60px;white-space:pre-wrap;color:#22c55e;margin-top:10px}
.small{color:#6b7280;font-size:12px}
</style></head><body>

<h2 style="margin:8px 0 2px 0">🚀 SydDev v0.5 <span class="badge">PANDAS 3.0.3 ✅</span> <span class="badge-sec">ENV 🔒 {{env_mode}}</span></h2>
<div class="small" style="margin-bottom:12px">Your 8 Sheets in 1 App - Built on phone - Pretoria - Secrets from .env</div>

<div class="card">
<div style="font-weight:700;margin-bottom:10px">Sheet 1: Choose Language</div>
<button class="btn btn-blue" id="btnPy" onclick="setLang('python')">🐍 Python</button>
<button class="btn btn-dark" id="btnJs" onclick="setLang('js')">🟨 JS</button>
<div style="margin-top:10px"><button class="btn btn-dark" id="btnPd" onclick="setLang('pandas')">🐼 Pandas 3.0.3</button></div>
<div class="small" style="margin-top:10px">Current: <span id="curLang">Python - Env Ready</span> | <span id="snapInfo">Snapshot idle</span></div>

<div style="font-weight:700;margin:18px 0 8px 0">Sheet 8: Upload</div>
<div style="background:#0a0a0a;border-radius:12px;padding:10px;display:flex;gap:8px;align-items:center;flex-wrap:wrap">
<input type="file" id="fileInput" style="color:#aaa"><span id="upStatus" class="small"></span>
</div>
<div class="small" style="margin-top:6px">Upload CSV/JPG/PDF -> workspace/ (secured, traversal blocked)</div>
</div>

<div class="card">
<div style="font-weight:700">Sheet 2+3: Code Editor + Run (Sheet 5 Env Ready ✅)</div>
<textarea id="editor">print("Hello DevUniverse!")
print("I built this on my phone in Pretoria")
# Sheet 4 will show output below
# Sheet 8 auto-saves every 5 sec
# ENV secured - secrets from .env not hardcoded</textarea>
<div style="margin-top:12px;display:flex;gap:10px;flex-wrap:wrap">
<button class="btn btn-blue" onclick="run()">▶ Run (Sheet 4)</button>
<button class="btn btn-blue" onclick="makeZip()">📦 Make ZIP</button>
<a id="dlLink" href="/download-zip" style="display:none;text-decoration:none"><button class="btn" style="background:#22c55e;color:#000">⬇ Download</button></a>
</div>
<div id="output">Output will appear here...</div>
</div>

<script>
let curLang='python', runCount=0
function setLang(l){
 curLang=l
 document.getElementById('curLang').innerText=l.charAt(0).toUpperCase()+l.slice(1)+' - Env Ready'
 document.getElementById('btnPy').className=l==='python'?'btn btn-blue':'btn btn-dark'
 document.getElementById('btnJs').className=l==='js'?'btn btn-blue':'btn btn-dark'
 document.getElementById('btnPd').className=l==='pandas'?'btn btn-blue':'btn btn-dark'
 let code='print("Hello "+l)'
 if(l==='js') code='console.log("Hello JS")'
 if(l==='pandas') code='import pandas as pd\\nprint(pd.__version__)'
 document.getElementById('editor').value=code
 fetch('/snapshot',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({trigger:'lang_switch_'+l})}).then(r=>r.json()).then(d=>{document.getElementById('snapInfo').innerText='Snap: '+d.time})
}
async function run(){
 const code=document.getElementById('editor').value
 const r=await fetch('/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code,lang:curLang})})
 const d=await r.json(); document.getElementById('output').innerText=d.output
 runCount++; if(runCount===1 && d.output.indexOf('Traceback')===-1 && d.output.indexOf('Error:')===-1){
   fetch('/snapshot',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({trigger:'first_run'})}).then(r=>r.json()).then(d=>document.getElementById('snapInfo').innerText='Snap: '+d.time+' first_run')
 }
}
async function makeZip(){
 document.getElementById('output').innerText='Making ZIP (workspace only - fast, no .env)...'
 const r=await fetch('/make-zip',{method:'POST'}); const d=await r.json()
 document.getElementById('output').innerText='ZIP ready: '+d.file+' ('+d.size+' bytes) - .env excluded for security'
 document.getElementById('dlLink').style.display='inline'
 window.location.href='/download-zip'
}
document.getElementById('fileInput').addEventListener('change', async (e)=>{
 if(!e.target.files[0]) return
 const fd=new FormData(); fd.append('file', e.target.files[0])
 document.getElementById('upStatus').innerText='Uploading...'
 const r=await fetch('/upload',{method:'POST',body:fd}); const d=await r.json()
 if(d.error) document.getElementById('upStatus').innerText='❌ '+d.error
 else document.getElementById('upStatus').innerText='✅ Uploaded: '+d.saved+' -> workspace/'
})
setInterval(()=>{ fetch('/snapshot',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({trigger:'auto_60s'})}).then(r=>r.json()).then(d=>document.getElementById('snapInfo').innerText='Snap: '+d.time+' auto') },60000)
setInterval(()=>{ const code=document.getElementById('editor').value; fetch('/autosave',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code})}) },5000)
</script>
</body></html>
"""

@app.route('/')
def index(): return render_template_string(HTML, env_mode=ENV_MODE)

@app.route('/run', methods=['POST'])
def run_code():
    data=request.json; code=data.get('code','')
    if not is_safe_path(data.get('lang','')): return jsonify({"output":"invalid lang"})
    open(os.path.join(WORKSPACE, "main.py"),"w").write(code)
    old=sys.stdout; sys.stdout=io.StringIO()
    try: exec(code, {}); out=sys.stdout.getvalue()
    except Exception as e: out=f"Error: {e}"
    sys.stdout=old
    return jsonify({"output": out or "(no output)"})

@app.route('/autosave', methods=['POST'])
def autosave():
    code=request.json.get('code',''); open(os.path.join(WORKSPACE,"main.py"),"w").write(code); return jsonify({"ok":1})

@app.route('/snapshot', methods=['POST'])
def snapshot(): 
    trig=request.json.get('trigger','manual') if request.json else 'manual'
    return jsonify(create_snapshot(trig))

@app.route('/upload', methods=['POST'])
def upload():
    f=request.files['file']; name=secure_filename(f.filename)
    if not is_safe_path(name): return jsonify({"error":"unsafe filename"}),400
    path=os.path.join(WORKSPACE,name); f.save(path)
    return jsonify({"saved":name})

@app.route('/make-zip', methods=['POST'])
def make_zip():
    zip_name="SydDev_v0.5.1_ENV_SECURE.zip"
    zip_path=os.path.join(BASE, zip_name)
    try: 
        os.makedirs("/sdcard/Download", exist_ok=True)
        zip_path=os.path.join("/sdcard/Download", zip_name)
    except: pass
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(WORKSPACE):
            for file in files:
                if not is_safe_path(file): continue
                full=os.path.join(root,file); rel=os.path.relpath(full, BASE); z.write(full, rel)
        z.write(__file__, os.path.basename(__file__))
        z.writestr(".env.example", "SECRET_KEY=change-me-please\\nJWT_SECRET=change-me-please\\nENV=production\\n")
        z.writestr(".gitignore", ".env\\n__pycache__/\\n*.tar.gz\\n")
    return jsonify({"file": zip_path, "size": os.path.getsize(zip_path)})

@app.route('/download-zip')
def download_zip():
    for p in [os.path.join(BASE,"SydDev_v0.5.1_ENV_SECURE.zip"), os.path.join("/sdcard/Download","SydDev_v0.5.1_ENV_SECURE.zip")]:
        if os.path.exists(p): return send_file(p, as_attachment=True)
    return "Make ZIP first",404

if __name__=='__main__':
    print(f"ENV MODE: {ENV_MODE} - Secrets loaded from .env")
    print(f"SECRET_KEY set: {len(SECRET_KEY)>10} - JWT set: {len(JWT_SECRET)>10}")
    app.run(host='127.0.0.1', port=5000, debug=False)