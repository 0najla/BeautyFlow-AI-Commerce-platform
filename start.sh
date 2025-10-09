#!/bin/bash
set -e

echo "🚀 Starting BeautyFlow..."


DIR="$( cd -- "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$DIR"


if [ -d ".venv" ]; then
  source ".venv/bin/activate"
  echo "✅ Activated venv: $DIR/.venv"
elif [ -d "backend/venv" ]; then
  source "backend/venv/bin/activate"
  echo "✅ Activated venv: $DIR/backend/venv"
else
  echo "❌ No virtual env found (.venv or backend/venv)."
  echo "   Create one, e.g.: python3 -m venv .venv && source .venv/bin/activate && pip install flask"
  exit 1
fi


cd "$DIR/backend"

echo "�� Running Flask at http://127.0.0.1:5005"
open "http://127.0.0.1:5005"


sudo -E python app.py



