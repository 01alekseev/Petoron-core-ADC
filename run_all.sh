#!/bin/bash

# 🧬 PETORON GLOBAL NETWORK — RESTART SCRIPT
# Used to restart all network components if already installed.
# NOT for first-time setup (use setup_all.sh for that).

export PYTHONPATH=.

if [[ -z "$PETORON_ROLE" ]]; then
  if [[ "$(uname -n)" == *"vps"* ]] || [[ "$(hostname)" == *"server"* ]]; then
    export PETORON_ROLE="SERVER"
  else
    export PETORON_ROLE="CLIENT"
  fi
fi

MODE=${1:-clean-once}

echo "🔧 Node Role: $PETORON_ROLE"

echo "🧹 Stopping previous processes..."
pkill -f p2p_node.py
pkill -f verifier.py
pkill -f miner.py
pkill -f autopeer.py

echo "🔒 Removing lock files..."
rm -f network/node.lock
rm -f storage/node.lock
rm -f storage/verifier.lock
rm -f network/miner.lock
rm -f p2p_node_alive.txt
rm -f god_eye.locked

echo "📂 Ensuring folder structure..."
mkdir -p storage wallets logs

echo "🗑️ Clearing mempool..."
rm -f storage/mempool.*

clean_logs() {
  echo "🧼 Cleaning logs..."
  > logs/node.log
  > logs/verifier.log
  > logs/miner.log
  > logs/autopeer.log
  > logs/firewall_rejections.log
  > logs/debug.log 2>/dev/null || true
}

auto_clean_logs() {
  while true; do
    sleep 86400
    echo "🕓 Daily auto-log cleanup..."
    clean_logs
  done
}

if [ "$MODE" = "clean-once" ]; then
  clean_logs
elif [ "$MODE" = "clean-daily" ]; then
  echo "🕒 Auto log cleaning every 24 hours activated."
  auto_clean_logs &
else
  echo "⚠️ Unknown mode: $MODE. Defaulting to clean-once."
  clean_logs
fi

echo "🔎 Verifying chain integrity..."
python3 core/chain_guard.py
guard_status=$?
if [ "$guard_status" != "0" ]; then
  echo "🛠️ Chain integrity failed. Attempting restore from latest snapshot..."
  python3 core/backup.py
fi

# 🛡️ GOD EYE — SECURITY LAYER BEFORE NETWORK LAUNCH
echo "👁️ Running God Eye preflight security check..."
python3 god_eye.py

# 👁️ If it's first run (hashes just created), run again to validate
if [ ! -f god_eye.locked ] && grep -q "Reference hashes created" logs/god_eye.log 2>/dev/null; then
  echo "🔁 God Eye hashes were just created. Re-validating..."
  python3 god_eye.py
fi

if [ ! -f god_eye.locked ]; then
  echo "❌ God Eye verification failed. Aborting launch."
  exit 1
fi

echo "🛑 Checking TCP port 5007 availability..."

MAX_RETRIES=5
RETRY_DELAY=2
retry_count=0

while lsof -ti udp:5007 >/dev/null 2>&1; do
  pids=$(lsof -ti udp:5007)
  echo "🛑 Port 5007 is used by: $pids. Killing..."
  kill -9 $pids
  sleep $RETRY_DELAY
  retry_count=$((retry_count + 1))
  if [ $retry_count -ge $MAX_RETRIES ]; then
    echo "⚠️ Failed to free port 5007 after $MAX_RETRIES retries. Aborted."
    exit 1
  fi
done

echo "✅ Port 5007 is available."
sleep 1

echo "🚀 Starting Petoron global network services..."

nohup python3 network/p2p_node.py >> logs/node.log 2>&1 &
nohup python3 network/autopeer.py >> logs/autopeer.log 2>&1 &
nohup python3 core/verifier.py >> logs/verifier.log 2>&1 &

sleep 3

# 🔄 Peer status check
echo -n "🔄 Checking network peers..."
sleep 2
if [ -s storage/peers.dat ]; then
  echo -ne "\r🟢 Peers connected — network is active.        \n"
else
  echo -ne "\r🟡 No peers connected — waiting...             \n"
fi

echo "✅ Petoron Network launched. All services are online."
echo "🧬 Launch CLI to manage wallet, mining and transactions."
echo ""

# ▶️ CLI interface start
python3 cli/interface.py
