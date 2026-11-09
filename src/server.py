import asyncio
import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

# Add src to path
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))
from database import Database
from scanner import start_continuous_scan, stop_continuous_scan
from data import get_seed_endpoints
from credentials import load_credentials, set_credential, get_headers_for_provider, has_google_account

# State
db = Database()
scan_progress = {
    "scanning": False,
    "progress": "",
    "lastScanAt": None,
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(BASE_DIR, "..", "templates", "index.html")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()
    from scanner import set_db as _set_scanner_db
    _set_scanner_db(db)
    # Seed initial models immediately so dashboard shows something fast
    seeds = get_seed_endpoints()
    await db.seed_endpoints(seeds)
    asyncio.create_task(start_continuous_scan(scan_progress))
    yield
    await stop_continuous_scan()

app = FastAPI(title="AI API Scanner", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    entries = await db.get_all()
    stats = await db.get_stats()
    stats["scanning"] = scan_progress["scanning"]
    stats["progress"] = scan_progress["progress"]
    stats["lastScanAt"] = scan_progress["lastScanAt"]
    with open(TEMPLATE_PATH) as f:
        html = f.read()
    import json as _json
    data_json = _json.dumps({"entries": [e.to_dict() for e in entries], "stats": stats})
    # Find and replace the placeholder safely (no regex to avoid \u issues)
    placeholder_start = html.find('__INITIAL_JSON__ = ')
    if placeholder_start >= 0:
        # Find the end of the JSON object (matching braces)
        brace_start = html.find('{', placeholder_start)
        depth = 0
        i = brace_start
        while i < len(html):
            if html[i] == '{':
                depth += 1
            elif html[i] == '}':
                depth -= 1
                if depth == 0:
                    break
            i += 1
        if depth == 0:
            html = html[:placeholder_start] + f'__INITIAL_JSON__ = {data_json}' + html[i+1:]
    return HTMLResponse(content=html)


@app.get("/api/scan")
async def api_scan():
    entries = await db.get_all()
    stats = await db.get_stats()
    stats["scanning"] = scan_progress["scanning"]
    stats["progress"] = scan_progress["progress"]
    stats["lastScanAt"] = scan_progress["lastScanAt"]
    return JSONResponse({
        "entries": [e.to_dict() for e in entries],
        "stats": stats,
    })


@app.post("/api/scan/manual")
async def api_manual_scan():
    from scanner import run_discovery_round, run_benchmark_cycle
    asyncio.create_task(_run_one_cycle())
    return JSONResponse({"message": "Manual scan triggered"})


async def _run_one_cycle():
    from scanner import run_discovery_round, run_benchmark_cycle
    await run_discovery_round(scan_progress)
    await run_benchmark_cycle(scan_progress)


@app.get("/api/alive")
async def api_alive():
    entries = await db.get_alive()
    return JSONResponse({"entries": [e.to_dict() for e in entries]})


@app.get("/api/smart-free")
async def api_smart_free():
    """Return only alive, free, smart-ranked models — top candidates for 'pinter & cepet'."""
    entries = await db.get_smart_free_alive()
    return JSONResponse({"entries": [e.to_dict() for e in entries]})


@app.get("/api/top-alive")
async def api_top_alive():
    """Top alive models sorted by quality (free first, then smart score + speed)."""
    entries = await db.get_top_alive(limit=100)
    return JSONResponse({"entries": [e.to_dict() for e in entries]})


@app.get("/api/credentials")
async def api_get_credentials():
    """Return current credentials config (passwords masked)."""
    creds = load_credentials()
    result = {}
    for k, v in creds.items():
        if "PASSWORD" in k.upper() or "KEY" in k.upper():
            result[k] = v[:3] + "****" + v[-4:] if len(v) > 7 else "****"
        else:
            result[k] = v
    result["has_openrouter_key"] = has_google_account()
    result["gmail_account"] = creds.get("GMAIL_ACCOUNT", "")[:10] + "@..."
    return JSONResponse(result)


@app.post("/api/credentials")
async def api_set_credentials(request: dict):
    """Set a credential."""
    key = request.get("key", "")
    value = request.get("value", "")
    if key and value:
        set_credential(key, value)
        return JSONResponse({"message": f"Credential '{key}' saved", "masked": value[:3] + "****"})
    return JSONResponse({"error": "Missing key or value"}, status_code=400)
