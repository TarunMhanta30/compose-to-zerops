from fastapi import FastAPI
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


@app.get("/")
def home():
    return {"greeting": "Hello from Compose-to-Zerops!", "status": "running"}


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