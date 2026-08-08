# Compose → Zerops

A docker-compose → Zerops migration assistant. Paste a docker-compose.yml and instantly get the Zerops service mapping, migration warnings, and a ready-to-import zerops.yaml.

Live app: https://python-2b0f-8000.prg1.zerops.app

Built for the Zerops Challenge (WeMakeDevs × Zerops).

## What it does

Moving an existing docker-compose app to Zerops means knowing which Zerops service each container maps to, and spotting the things that don't translate directly. This tool does that automatically:

- Service mapping — maps each compose service to its Zerops equivalent (e.g. postgres to postgresql@16, redis to valkey@7, built services to a Python runtime).
- Migration warnings — flags three common issues: exposed host ports, host volume mounts, and hardcoded secrets in environment variables.
- zerops.yaml generation — outputs a ready-to-import Zerops project YAML you can paste straight into the dashboard.

## How it works

- Backend: FastAPI (Python 3.12). A deterministic parser reads the compose YAML, maps services against a lookup table, scans for issues, and generates the Zerops import YAML. POST /convert accepts the compose text and returns the mapping, warnings, and generated YAML as JSON.
- Frontend: a single self-contained HTML page served from /, with a paste box, live results, and a copy button.

## How Zerops is used

The app itself runs on Zerops as a Python service, deployed continuously from this GitHub repo:

- zerops.yaml defines the build (dependencies vendored via pip install --target) and run pipeline.
- The service is connected to this repository, so every push to main auto-builds and redeploys.
- Public access is served through the Zerops subdomain.

## Run locally

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload

Then open http://127.0.0.1:8000

## AI usage disclosure

AI assistance (Claude) was used for guidance, debugging, and drafting during the 48-hour build. All architecture and code decisions were reviewed and understood by the author.