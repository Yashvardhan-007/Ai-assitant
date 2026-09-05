#!/usr/bin/env bash
# Convenience launcher for local demo / judging.
# Usage: ./run_demo.sh   (Ctrl+C stops both servers)
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "== AI Teacher demo launcher =="
if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "NOTE: ANTHROPIC_API_KEY is not set — running in rule-based fallback mode."
  echo "      export ANTHROPIC_API_KEY=sk-ant-... before running for full LLM-generated lessons."
fi

cd "$DIR/backend"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt

python main.py &
BACKEND_PID=$!

cd "$DIR/frontend"
python3 -m http.server 8080 &
FRONTEND_PID=$!

echo ""
echo "Backend running (PID $BACKEND_PID) on http://localhost:5000"
echo "Frontend running (PID $FRONTEND_PID) on http://localhost:8080"
echo "Open http://localhost:8080 in your browser. Press Ctrl+C to stop both."

trap "kill $BACKEND_PID $FRONTEND_PID" EXIT
wait
