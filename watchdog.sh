#!/bin/bash
# AI API Scanner - Auto-restart watchdog
cd /home/don-ai/Documents/Dev.Team/projects/ai-scraper

while true; do
    # Kill any existing instance
    pkill -9 -f "uvicorn src.server:app" 2>/dev/null
    sleep 1
    
    # Clear old DB for fresh start
    rm -f ai_apis.db src/__pycache__/*.pyc 2>/dev/null
    
    # Start server
    exec /tmp/proxy_venv/bin/python -m uvicorn src.server:app --host 0.0.0.0 --port 9100 --log-level info
done
