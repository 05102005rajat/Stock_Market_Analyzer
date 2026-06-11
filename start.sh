#!/usr/bin/env bash
# Launch the Flask backend and the Vite dev server together.
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- backend ---
cd "$ROOT/backend"
if [ ! -d venv ]; then
  python3 -m venv venv
  ./venv/bin/pip install -q -r requirements.txt
fi
./venv/bin/python app.py &
BACKEND_PID=$!

# --- frontend ---
cd "$ROOT/frontend"
if [ ! -d node_modules ]; then
  npm install
fi
npm run dev &
FRONTEND_PID=$!

echo ""
echo "Backend  -> http://127.0.0.1:5001"
echo "Frontend -> http://localhost:5173"
echo "Press Ctrl+C to stop both."

# Stop both servers on exit.
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
