#!/bin/bash
# TrendPulse — Startup script
# Usage: bash ~/trendpulse/start.sh
set -e
cd "$(dirname "$0")"
echo "[TrendPulse] Starting server on port 8766..."
PYTHONUNBUFFERED=1 python3 app.py
