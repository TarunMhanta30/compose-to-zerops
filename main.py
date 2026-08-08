from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import yaml

app = FastAPI()

# docker-compose image/name keyword  ->  Zerops managed service
SERVICE_MAP = {
    "postgres": "postgresql@16",
    "postgresql": "postgresql@16",
    "mysql": "mariadb@11",
    "mariadb": "mariadb@11",
    "redis": "valkey@7",
    "valkey": "valkey@7",
    "elasticsearch": "elasticsearch@8",
    "nats": "nats@2",
    "minio": "object-storage",
}


@app.get("/", response_class=HTMLResponse)
def home():
    return PAGE


def detect_type(name, definition):
    image = (definition.get("image") or "").lower()
    for keyword, ztype in SERVICE_MAP.items():
        if keyword in image or keyword in name.lower():
            return ztype
    if "build" in definition:
        return "app-runtime"
    return "unknown"


def find_issues(name, definition):
    issues = []
    if "ports" in definition:
        issues.append(
            f"'{name}' exposes ports {definition['ports']}. On Zerops use httpSupport + subdomain instead."
        )
    for vol in (definition.get("volumes") or []):
        if isinstance(vol, str) and vol.startswith((".", "/", "~")):
            issues.append(
                f"'{name}' uses a host mount ({vol}). Zerops uses managed shared storage instead."
            )
    env = definition.get("environment", {})
    items = env if isinstance(env, list) else [f"{k}={v}" for k, v in (env or {}).items()]
    for item in items:
        low = item.lower()
        if "=" in item and any(s in low for s in ["password", "secret", "token", "apikey"]):
            value = item.split("=", 1)[1]
            if value and "${" not in value:
                key = item.split("=", 1)[0]
                issues.append(
                    f"'{name}' has a hardcoded secret: {key}. Move it to Zerops secret env variables."
                )
    return issues


class ConvertRequest(BaseModel):
    compose: str


@app.post("/convert")
def convert(req: ConvertRequest):
    try:
        data = yaml.safe_load(req.compose)
    except Exception as e:
        return {"error": f"Invalid YAML: {e}"}

    if not data or "services" not in data:
        return {"error": "No 'services' found in the compose file."}

    mapping = []
    issues = []
    zerops_services = []

    for name, definition in data["services"].items():
        definition = definition or {}
        ztype = detect_type(name, definition)
        mapping.append({"service": name, "zerops_type": ztype})
        issues.extend(find_issues(name, definition))

        if ztype == "app-runtime":
            zerops_services.append(
                {"hostname": name, "type": "python@3.12", "enableSubdomainAccess": True}
            )
        elif ztype == "unknown":
            zerops_services.append(
                {"hostname": name, "type": "NO-DIRECT-EQUIVALENT-review-manually"}
            )
        else:
            zerops_services.append({"hostname": name, "type": ztype})

    import_yaml = {"project": {"name": "migrated-project"}, "services": zerops_services}

    return {
        "mapping": mapping,
        "issues": issues,
        "zerops_import_yaml": yaml.dump(import_yaml, sort_keys=False),
    }
PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Compose to Zerops</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, system-ui, 'Segoe UI', sans-serif;
    background: radial-gradient(circle at 20% 0%, #14203a 0%, #0a0e17 55%);
    color: #e6edf3; min-height: 100vh; padding: 40px 20px;
  }
  .wrap { max-width: 1080px; margin: 0 auto; }
  .badge {
    display:inline-block; background:rgba(46,160,67,0.15); color:#7ee787;
    border:1px solid rgba(46,160,67,0.4); padding:4px 12px; border-radius:20px;
    font-size:12px; font-weight:600; letter-spacing:0.5px; margin-bottom:16px;
  }
  h1 { font-size: 34px; font-weight: 800; letter-spacing:-0.5px;
    background: linear-gradient(90deg,#58a6ff,#7ee787);
    -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
  }
  p.sub { color:#8b949e; margin: 8px 0 28px; font-size:15px; }
  .panel {
    background: rgba(22,27,34,0.7); border:1px solid #2d333b; border-radius:14px;
    padding: 20px; backdrop-filter: blur(6px);
  }
  label { display:block; font-size:13px; color:#8b949e; margin-bottom:8px; font-weight:600; }
  textarea {
    width:100%; height:220px; background:#0d1117; color:#e6edf3;
    border:1px solid #30363d; border-radius:10px; padding:14px;
    font-family: 'Consolas', monospace; font-size:13px; resize:vertical; outline:none;
  }
  textarea:focus { border-color:#58a6ff; }
  .row { display:flex; gap:12px; align-items:center; margin-top:14px; flex-wrap:wrap; }
  button {
    background: linear-gradient(90deg,#238636,#2ea043); color:#fff; border:none;
    padding:12px 24px; border-radius:10px; font-size:15px; font-weight:600; cursor:pointer;
    transition: transform .1s, box-shadow .2s;
  }
  button:hover { transform: translateY(-1px); box-shadow:0 6px 20px rgba(46,160,67,0.35); }
  button.ghost { background:transparent; border:1px solid #30363d; color:#8b949e; }
  button.ghost:hover { box-shadow:none; border-color:#58a6ff; color:#58a6ff; }
  .summary { display:none; gap:12px; margin:24px 0 8px; flex-wrap:wrap; }
  .stat {
    flex:1; min-width:150px; background:rgba(22,27,34,0.7); border:1px solid #2d333b;
    border-radius:12px; padding:16px 18px;
  }
  .stat .num { font-size:28px; font-weight:800; }
  .stat .lbl { font-size:12px; color:#8b949e; margin-top:2px; }
  .cols { display:none; gap:16px; flex-wrap:wrap; margin-top:16px; }
  .card { flex:1; min-width:300px; background: rgba(22,27,34,0.7);
    border:1px solid #2d333b; border-radius:14px; padding:20px; }
  .card h2 { font-size:14px; color:#58a6ff; margin-bottom:14px; text-transform:uppercase; letter-spacing:0.5px; }
  .map-row { padding:10px 0; border-bottom:1px solid #21262d; font-size:14px; display:flex; align-items:center; gap:8px; }
  .map-row:last-child { border-bottom:none; }
  .zt { color:#7ee787; font-family:monospace; }
  .issue { background:rgba(248,81,73,0.08); border-left:3px solid #f85149;
    padding:10px 12px; margin:8px 0; border-radius:6px; font-size:13px; line-height:1.5; }
  .ok { color:#7ee787; font-size:14px; }
  pre { white-space:pre-wrap; font-size:12px; color:#e6edf3; font-family:'Consolas',monospace; line-height:1.6; }
  .yaml-head { display:flex; justify-content:space-between; align-items:center; }
  .copied { color:#7ee787; font-size:12px; margin-left:8px; display:none; }
</style>
</head>
<body>
<div class="wrap">
  <span class="badge">● DOCKER-COMPOSE MIGRATION ASSISTANT</span>
  <h1>Compose → Zerops</h1>
  <p class="sub">Paste a docker-compose file. Instantly get the Zerops service mapping, migration warnings, and a ready-to-import zerops.yaml.</p>

  <div class="panel">
    <label>docker-compose.yml</label>
    <textarea id="input" placeholder="Paste your docker-compose.yml here..."></textarea>
    <div class="row">
      <button onclick="convert()">⚡ Convert to Zerops</button>
      <button class="ghost" onclick="loadSample()">Load sample</button>
    </div>
  </div>

  <div class="summary" id="summary">
    <div class="stat"><div class="num" id="s-services" style="color:#58a6ff">0</div><div class="lbl">Services mapped</div></div>
    <div class="stat"><div class="num" id="s-issues" style="color:#f85149">0</div><div class="lbl">Warnings found</div></div>
    <div class="stat"><div class="num" style="color:#7ee787">✓</div><div class="lbl">zerops.yaml generated</div></div>
  </div>

  <div class="cols" id="results">
    <div class="card">
      <h2>Service Mapping</h2>
      <div id="mapping"></div>
    </div>
    <div class="card">
      <h2>Migration Warnings</h2>
      <div id="issues"></div>
    </div>
    <div class="card">
      <div class="yaml-head">
        <h2>Generated zerops.yaml <span class="copied" id="copied">copied!</span></h2>
        <button class="ghost" style="padding:6px 12px;font-size:12px" onclick="copyYaml()">Copy</button>
      </div>
      <pre id="yaml"></pre>
    </div>
  </div>
</div>

<script>
const SAMPLE = `services:
  web:
    build: .
    ports:
      - 8000:8000
    environment:
      DB_PASSWORD: mysecret123
  db:
    image: postgres:16
    volumes:
      - ./data:/var/lib/postgresql/data
  cache:
    image: redis:7`;

function loadSample() { document.getElementById('input').value = SAMPLE; }

function copyYaml() {
  navigator.clipboard.writeText(document.getElementById('yaml').textContent);
  const c = document.getElementById('copied');
  c.style.display = 'inline';
  setTimeout(() => c.style.display = 'none', 1500);
}

async function convert() {
  const compose = document.getElementById('input').value;
  const res = await fetch('/convert', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ compose })
  });
  const data = await res.json();
  document.getElementById('summary').style.display = 'flex';
  document.getElementById('results').style.display = 'flex';
  if (data.error) {
    document.getElementById('mapping').innerHTML = '<div class="issue">' + data.error + '</div>';
    document.getElementById('issues').innerHTML = '';
    document.getElementById('yaml').textContent = '';
    document.getElementById('s-services').textContent = '0';
    document.getElementById('s-issues').textContent = '0';
    return;
  }
  document.getElementById('s-services').textContent = data.mapping.length;
  document.getElementById('s-issues').textContent = data.issues.length;
  document.getElementById('mapping').innerHTML = data.mapping.map(m =>
    '<div class="map-row">' + m.service + ' <span style="color:#8b949e">&rarr;</span> <span class="zt">' + m.zerops_type + '</span></div>'
  ).join('');
  document.getElementById('issues').innerHTML = data.issues.length
    ? data.issues.map(i => '<div class="issue">⚠ ' + i + '</div>').join('')
    : '<p class="ok">✓ No migration issues found.</p>';
  document.getElementById('yaml').textContent = data.zerops_import_yaml;
}
</script>
</body>
</html>
"""