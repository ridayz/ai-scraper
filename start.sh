#!/bin/bash
cd /home/don-ai/Documents/Dev.Team/projects/ai-scraper
pkill -9 -f "uvicorn src.server:app" 2>/dev/null
sleep 1
exec /tmp/proxy_venv/bin/python -m uvicorn src.server:app --host 0.0.0.0 --port 9100 --log-level error
