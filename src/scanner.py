"""
AI API Scraper - Benchmark and continuous scanning logic
Runs a never-stopping loop: check alive, replace dead, discover new.
"""
import asyncio
import httpx
from typing import List, Dict, Any, Optional
from database import Database
from data import get_seed_endpoints, get_web_sources
from credentials import load_credentials

# Global database instance (set in main)
db: Optional[Database] = None


def set_db(database: Database):
    global db
    db = database


# ─── Benchmark ───────────────────────────────────────────────────────────────

async def benchmark_endpoint(client: httpx.AsyncClient, endpoint: str, timeout: float = 4.0) -> Dict[str, Any]:
    try:
        start = asyncio.get_event_loop().time()
        resp = await client.get(
            endpoint,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept": "*/*"},
            follow_redirects=True,
        )
        elapsed = (asyncio.get_event_loop().time() - start) * 1000
        alive = resp.status_code < 500
        speed_label = "fast" if elapsed < 1000 else "slow"
        return {"alive": alive, "responseTime": round(elapsed), "speedLabel": speed_label}
    except Exception:
        return {"alive": False, "responseTime": None, "speedLabel": "unknown"}


# ─── Discovery ────────────────────────────────────────────────────────────────

async def fetch_openrouter_models() -> List[Dict[str, Any]]:
    """Fetch all models from OpenRouter — stores benchmarks + modality for smart scoring."""
    discovered = []
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            headers = {"User-Agent": "AIScraper/1.0"}
            # Use stored API key if available
            from credentials import get_headers_for_provider
            headers.update(get_headers_for_provider("openrouter"))
            resp = await client.get("https://openrouter.ai/api/v1/models", headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                count = len(data.get("data", []))
                print(f"[discover] OpenRouter → {count} models (smart-scored)")
                for m in data.get("data", []):
                    model_id = m.get("id", "")
                    name = m.get("name", model_id)
                    pricing = m.get("pricing", {})
                    prompt_price = float(pricing.get("prompt", 0) or 0)
                    completion_price = float(pricing.get("completion", 0) or 0)
                    is_free = prompt_price == 0 and completion_price == 0

                    arch = m.get("architecture", {}) or {}
                    modalities = arch.get("input_modalities", []) or []
                    modality = "+".join(modalities) if modalities else "text"
                    ctx_len = int(m.get("context_length") or 0)
                    bench_score = _calc_benchmark_score(m.get("benchmarks") or {})

                    ep_id = f"or-{model_id.replace('/', '--').replace('.', '-').lower()}"
                    discovered.append({
                        "id": ep_id,
                        "modelName": name,
                        "endpoint": "https://openrouter.ai/api/v1/models",
                        "apiKey": "free" if is_free else "key-required",
                        "source": f"openrouter.ai/{model_id}",
                        "modality": modality,
                        "contextLength": ctx_len,
                        "benchmarkScore": bench_score,
                        "isFree": is_free,
                    })
                print(f"[discover] OpenRouter → {len(discovered)} models (smart-scored)")
    except Exception as e:
        print(f"[discover] OpenRouter failed: {e}")
    return discovered


def _calc_benchmark_score(benchmarks: Dict) -> float:
    """Compute a 0-100 'intelligence score' from OpenRouter benchmark data."""
    if not benchmarks:
        return 0.0
    weights = {
        "MMLU": 15, "MMLU-Pro": 20, "MMLU-Pro-Cot": 15,
        "HumanEval": 15, "HumanEval+": 15,
        "SWE-bench": 10, "SWE-bench Verified": 10,
        "GSM8K": 8, "Math500": 8, "AIME": 10, "AIME 2024": 10,
        "GPQA": 8, "GAIA": 5, "IFEval": 5,
    }
    total = 0.0
    applied = 0
    for key, w in weights.items():
        val = benchmarks.get(key)
        if isinstance(val, (int, float)) and val > 0:
            total += min(float(val), 100.0) * w / 100.0
            applied += 1
    if applied == 0:
        return 0.0
    coverage_bonus = min(applied / 5.0, 1.0) * 10
    return round(total + coverage_bonus, 1)


async def fetch_deepinfra_models() -> List[Dict[str, Any]]:
    """Fetch models from DeepInfra — public listing, no key needed."""
    discovered = []
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                "https://api.deepinfra.com/v1/models",
                headers={"User-Agent": "AIScraper/1.0"},
            )
            if resp.status_code == 200:
                data = resp.json()
                for m in data.get("data", []):
                    model_id = m.get("id", "")
                    if not model_id:
                        continue
                    # DeepInfra pricing check for free models
                    pricing = m.get("pricing", {}) or {}
                    # If pricing not present, assume free tier available
                    ep_id = f"di-{model_id.replace('/', '--').replace('.', '-').lower()}"
                    discovered.append({
                        "id": ep_id,
                        "modelName": model_id,
                        # Health-check via the public /v1/models endpoint — individual inference needs POST+key
                        "endpoint": "https://api.deepinfra.com/v1/models",
                        "apiKey": "free",
                        "source": f"deepinfra.com/{model_id}",
                        "modality": "text",
                        "contextLength": 0,
                        "benchmarkScore": 0.0,
                        "isFree": True,
                    })
                print(f"[discover] DeepInfra → {len(discovered)} models")
    except Exception as e:
        print(f"[discover] DeepInfra failed: {e}")
    return discovered


async def fetch_hf_trending() -> List[Dict[str, Any]]:
    discovered = []
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                "https://huggingface.co/api/models",
                params={"limit": 50, "sort": "trending", "pipeline_tag": "text-generation"},
                headers={"User-Agent": "AIScraper/1.0"},
            )
            if resp.status_code == 200:
                for m in resp.json():
                    model_id = m.get("id", "")
                    cfg = m.get("config", {}) or {}
                    name = cfg.get("model_name", model_id)
                    ep_id = f"hf-{model_id.replace('/', '--').replace('.', '-')}"
                    discovered.append({
                        "id": ep_id,
                        "modelName": name,
                        "endpoint": f"https://api-inference.huggingface.co/models/{model_id}",
                        "apiKey": "key-required",
                        "source": "huggingface.co",
                        "modality": "text",
                        "contextLength": 0,
                        "benchmarkScore": 0.0,
                        "isFree": False,
                    })
                print(f"[discover] HuggingFace → {len(discovered)} models")
    except Exception as e:
        print(f"[discover] HF failed: {e}")
    return discovered


# ─── One scan cycle ───────────────────────────────────────────────────────────

async def _benchmark_one(client: httpx.AsyncClient, row: dict, progress: Dict[str, str]):
    global db
    try:
        result = await benchmark_endpoint(client, row["endpoint"])
        progress["progress"] = f"Checking {row['model_name']} ({row.get('death_count', 0)})..."
        if db is None:
            return
        if result["alive"]:
            await db.mark_alive(row["id"], result["responseTime"], result["speedLabel"])
            print(f"[bench] ✅ {row['model_name']}: {result['responseTime']}ms")
        else:
            await db.mark_dead(row["id"])
    except Exception as e:
        print(f"[bench] ⚠️ {row['model_name']}: error {type(e).__name__}")


async def run_discovery_round(scan_progress: Dict[str, str]):
    """Fetch fresh models from OpenRouter + HF and insert any not yet in DB."""
    if db is None:
        return
    await db.init_db()

    all_new = []
    scan_progress["progress"] = "Discovering OpenRouter..."
    or_models = await fetch_openrouter_models()
    all_new.extend(or_models)

    scan_progress["progress"] = "Discovering DeepInfra..."
    di_models = await fetch_deepinfra_models()
    all_new.extend(di_models)

    scan_progress["progress"] = "Discovering HuggingFace..."
    hf_models = await fetch_hf_trending()
    all_new.extend(hf_models)

    if all_new:
        await db.insert_new(all_new)
        print(f"[discover] Added {len(all_new)} total candidates to DB")


async def run_benchmark_cycle(scan_progress: Dict[str, str]):
    """Benchmark ALL non-alive entries one by one to avoid SQLite lock."""
    global db
    if db is None:
        return

    to_check = await db.get_all_pending()
    if not to_check:
        return

    print(f"[benchmark] Testing {len(to_check)} entries sequentially...")

    async with httpx.AsyncClient(timeout=3.0) as client:
        for row in to_check:
            await _benchmark_one(client, row, scan_progress)
            await asyncio.sleep(0.05)

    stats = await db.get_stats()
    print(f"[benchmark] Done: ✅ {stats['aliveCount']} alive · ❌ {stats['deadCount']} dead")
    await _replace_dead(scan_progress)


async def _replace_dead(scan_progress: Dict[str, str]):
    """Remove very-dead entries and pull fresh candidates from discovery."""
    if db is None:
        return
    stats = await db.get_stats()
    dead_count = stats["deadCount"]
    alive_count = stats["aliveCount"]
    total = stats["totalDiscovered"]
    print(f"[cycle] alive={alive_count} dead={dead_count} total={total}")
    if dead_count > 5 or (total > 0 and alive_count == 0):
        scan_progress["progress"] = "⚠️ Many dead — refreshing candidates..."
        await run_discovery_round(scan_progress)


# ─── Continuous loop ──────────────────────────────────────────────────────────

SCAN_INTERVAL_SEC = 60
DISCOVERY_INTERVAL_SEC = 300

_loop_running = False


async def start_continuous_scan(scan_progress: Dict[str, str]):
    """Never-stop scanner: discovers + benchmarks on a timer."""
    global _loop_running
    if _loop_running or db is None:
        return
    _loop_running = True
    print("[scan] Starting continuous scan loop...")
    scan_progress["scanning"] = True
    scan_progress["progress"] = "Initializing..."
    scan_progress["lastScanAt"] = _now_iso()

    await db.init_db()
    seeds = get_seed_endpoints()
    await db.seed_endpoints(seeds)
    print(f"[scan] Seeded {len(seeds)} starter models")

    cycle_num = 0
    last_discovery = 0

    while _loop_running:
        cycle_num += 1
        now = asyncio.get_event_loop().time()
        need_discovery = (cycle_num == 1) or (now - last_discovery > DISCOVERY_INTERVAL_SEC)
        if need_discovery:
            await run_discovery_round(scan_progress)
            last_discovery = now
        await run_benchmark_cycle(scan_progress)
        stats = await db.get_stats()
        smart_free = await db.get_smart_free_alive()
        scan_progress["progress"] = (
            f"✅ {stats['aliveCount']} alive · ❌ {stats['deadCount']} dead"
            f" · 🧠🟢 {len(smart_free)} smart-free"
            f" · ⏱ avg {stats['avgResponseTime']}ms"
        )
        scan_progress["lastScanAt"] = _now_iso()
        print(f"[cycle {cycle_num}] {scan_progress['progress']}")
        await asyncio.sleep(SCAN_INTERVAL_SEC)


async def stop_continuous_scan():
    global _loop_running
    _loop_running = False


def _now_iso():
    import datetime
    return datetime.datetime.utcnow().isoformat()
