#!/bin/bash

# -----------------------------------------------------
# 🚀 Petoron Network — Setup Script (enhanced version)
# -----------------------------------------------------

echo "🔍 Checking Python and pip installation..."
sleep 1

if ! command -v python3 &>/dev/null; then
    echo "❌ Python3 is not installed. Please install Python 3 and rerun this script."
    exit 1
fi

if ! command -v pip3 &>/dev/null; then
    echo "❌ pip3 not found. Installing pip..."
    sleep 1
    curl -sS https://bootstrap.pypa.io/get-pip.py -o get-pip.py
    python3 get-pip.py && rm get-pip.py || { echo "❌ pip installation failed."; exit 1; }
fi

echo "✅ Python and pip are ready."
sleep 1

if [ ! -f requirements.txt ]; then
    echo "❌ requirements.txt not found in current directory. Abort."
    exit 1
fi

echo "📦 Installing Python packages from requirements.txt..."
sleep 1
pip3 install -r requirements.txt || { echo "❌ Failed to install requirements."; exit 1; }

echo "📦 Ensuring 'ecdsa' package is installed..."
pip3 install ecdsa || { echo "❌ Failed to install ecdsa."; exit 1; }

echo "✅ Dependencies installed."
sleep 1

echo "📂 Creating folder structure if missing..."
mkdir -p storage logs

echo "📄 Checking and initializing required .bin files..."
touch storage/chain.bin
touch storage/balances.bin
touch storage/daily_rewards.bin
touch storage/peers.bin
sleep 1

echo "🔑 Making all scripts executable..."
chmod +x run_all.sh
chmod +x setup_all.sh
sleep 1

echo "✅ Setup complete."
echo "👉 If you are on a VPS, run: export PETH_ROLE=server"
echo "👉 Then start the node with: ./run_all.sh"
