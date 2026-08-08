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
  * { box-sizing: border-box; }
  body { font-family: -apple-system, system-ui, sans-serif; background:#0d1117; color:#e6edf3; margin:0; padding:24px; }
  .wrap { max-width: 1000px; margin: 0 auto; }
  h1 { font-size: 24px; margin-bottom: 4px; }
  p.sub { color:#8b949e; margin-top:0; }
  textarea { width:100%; height:220px; background:#161b22; color:#e6edf3; border:1px solid #30363d; border-radius:8px; padding:12px; font-family:monospace; font-size:13px; }
  button { margin-top:12px; background:#238636; color:#fff; border:none; padding:10px 20px; border-radius:8px; font-size:15px; cursor:pointer; }
  button:hover { background:#2ea043; }
  .cols { display:flex; gap:16px; flex-wrap:wrap; margin-top:20px; }
  .card { flex:1; min-width:280px; background:#161b22; border:1px solid #30363d; border-radius:8px; padding:16px; }
  .card h2 { font-size:15px; margin-top:0; color:#58a6ff; }
  pre { white-space:pre-wrap; font-size:12px; color:#e6edf3; }
  .issue { background:#3d1c1c; border-left:3px solid #f85149; padding:8px; margin:6px 0; border-radius:4px; font-size:13px; }
  .map-row { padding:6px 0; border-bottom:1px solid #21262d; font-size:13px; }
  .zt { color:#7ee787; }
</style>
</head>
<body>
<div class="wrap">
  <h1>Compose → Zerops</h1>
  <p class="sub">Paste a docker-compose file. Get the Zerops config, service mapping, and migration warnings.</p>
  <textarea id="input" placeholder="Paste your docker-compose.yml here..."></textarea>
  <br>
  <button onclick="convert()">Convert to Zerops</button>
  <div class="cols" id="results" style="display:none;">
    <div class="card">
      <h2>Service Mapping</h2>
      <div id="mapping"></div>
    </div>
    <div class="card">
      <h2>Migration Warnings</h2>
      <div id="issues"></div>
    </div>
    <div class="card">
      <h2>Generated zerops import YAML</h2>
      <pre id="yaml"></pre>
    </div>
  </div>
</div>
<script>
async function convert() {
  const compose = document.getElementById('input').value;
  const res = await fetch('/convert', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ compose })
  });
  const data = await res.json();
  document.getElementById('results').style.display = 'flex';
  if (data.error) {
    document.getElementById('mapping').innerHTML = '<div class="issue">' + data.error + '</div>';
    document.getElementById('issues').innerHTML = '';
    document.getElementById('yaml').textContent = '';
    return;
  }
  document.getElementById('mapping').innerHTML = data.mapping.map(m =>
    '<div class="map-row">' + m.service + ' &rarr; <span class="zt">' + m.zerops_type + '</span></div>'
  ).join('');
  document.getElementById('issues').innerHTML = data.issues.length
    ? data.issues.map(i => '<div class="issue">' + i + '</div>').join('')
    : '<p style="color:#7ee787">No issues found.</p>';
  document.getElementById('yaml').textContent = data.zerops_import_yaml;
}
</script>
</body>
</html>
"""