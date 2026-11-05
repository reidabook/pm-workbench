#!/bin/bash
# PM Workbench launcher. First run installs deps; every run starts the server.
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
if [ "$1" = "--demo" ]; then   # fictional demo data, no Jira / Claude needed
  export PMWB_DATA="$PWD/demo/data"
  [ -f demo/data/workbench.db ] || NEED_SEED=1
fi
if ! $PY -c "import fastapi, uvicorn, openpyxl, requests, multipart" 2>/dev/null; then
  echo "Installing dependencies..."; $PY -m pip install --user -q -r requirements.txt
fi
[ -n "$NEED_SEED" ] && $PY scripts/seed_demo.py
[ -n "$PMWB_DATA" ] || [ -f data/config.json ] || { mkdir -p data; cp config.example.json data/config.json; echo "Created data/config.json — edit it for your team."; }
PORT=${PORT:-8765}
echo "PM Workbench → http://127.0.0.1:$PORT"
exec $PY -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" ${RELOAD:+--reload}
