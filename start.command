#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "Starting HEPTA_GSApp from:"
pwd
echo

run_bundled_node() {
  node_path="$1"
  if [ -f "$node_path" ]; then
    if [ ! -x "$node_path" ]; then
      chmod +x "$node_path" 2>/dev/null || true
    fi
    if [ -x "$node_path" ]; then
      "$node_path" start-server.js
      exit $?
    fi
  fi
}

arch_name="$(uname -m)"
case "$arch_name" in
  arm64)
    bundled_node="./tools/node/darwin-arm64/node"
    fallback_bundled_node="./tools/node/darwin-x64/node"
    ;;
  x86_64)
    bundled_node="./tools/node/darwin-x64/node"
    fallback_bundled_node="./tools/node/darwin-arm64/node"
    ;;
  *)
    bundled_node=""
    fallback_bundled_node=""
    ;;
esac

if [ -n "$bundled_node" ]; then
  run_bundled_node "$bundled_node"
fi

if [ -n "$fallback_bundled_node" ]; then
  run_bundled_node "$fallback_bundled_node"
fi

if command -v node >/dev/null 2>&1; then
  node start-server.js
  exit $?
fi

if command -v python3 >/dev/null 2>&1; then
  echo "Node.js was not found. Starting with the macOS Python fallback server."
  python3 start-server.py
  exit $?
fi

if command -v python >/dev/null 2>&1; then
  echo "Node.js was not found. Starting with the Python fallback server."
  python start-server.py
  exit $?
fi

echo "Node.js or Python is required to start the local server."
echo "Opening the HTML file directly as a last resort."
if command -v open >/dev/null 2>&1; then
  open "hepta_ground_station_ui_compact_v36_wider_azel_graph.html"
else
  echo
  echo "Open hepta_ground_station_ui_compact_v36_wider_azel_graph.html manually."
fi
echo
echo "Press Enter to close this window."
read -r _
