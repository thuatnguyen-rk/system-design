import asyncio
import json
import os
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
ORIGIN_DELAY_MS = int(os.environ.get("ORIGIN_DELAY_MS", "200"))
CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", "30"))
CACHE_ENABLED = os.environ.get("CACHE_ENABLED", "true").lower() == "true"
CACHE_SINGLEFLIGHT = os.environ.get("CACHE_SINGLEFLIGHT", "false").lower() == "true"

stats = {
    "hits": 0,
    "misses": 0,
    "bypasses": 0,
    "origin_calls": 0,
    "cache_errors": 0,
    "origin_in_flight": 0,
    "origin_in_flight_peak": 0,
}
stats_lock = asyncio.Lock()
local_locks: dict[str, asyncio.Lock] = {}
local_locks_mu = asyncio.Lock()
r: redis.Redis | None = None


async def bump(name: str, n: int = 1) -> None:
    async with stats_lock:
        stats[name] += n


async def origin_fetch(item_id: str) -> dict:
    async with stats_lock:
        stats["origin_calls"] += 1
        stats["origin_in_flight"] += 1
        if stats["origin_in_flight"] > stats["origin_in_flight_peak"]:
            stats["origin_in_flight_peak"] = stats["origin_in_flight"]
    try:
        await asyncio.sleep(ORIGIN_DELAY_MS / 1000)
        return {"id": item_id, "name": f"item-{item_id}", "origin": "db"}
    finally:
        async with stats_lock:
            stats["origin_in_flight"] -= 1


async def cache_get(key: str) -> str | None:
    try:
        return await r.get(key)
    except redis.RedisError:
        await bump("cache_errors")
        return None


async def cache_set(key: str, item: dict) -> None:
    try:
        await r.set(key, json.dumps(item), ex=CACHE_TTL_SECONDS)
    except redis.RedisError:
        await bump("cache_errors")


async def load_item(item_id: str) -> dict:
    item = await origin_fetch(item_id)
    await cache_set(f"item:{item_id}", item)
    return item


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global r
    r = redis.from_url(REDIS_URL, decode_responses=True)
    yield
    await r.aclose()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health():
    try:
        await r.ping()
    except redis.RedisError:
        return JSONResponse({"ok": False}, status_code=503)
    return {"ok": True}


@app.get("/stats")
async def get_stats():
    async with stats_lock:
        body = dict(stats)
    body.update(
        {
            "cache_enabled": CACHE_ENABLED,
            "singleflight": CACHE_SINGLEFLIGHT,
            "ttl_seconds": CACHE_TTL_SECONDS,
            "origin_delay_ms": ORIGIN_DELAY_MS,
        }
    )
    return body


@app.post("/admin/flush")
async def flush():
    await r.flushdb()
    return {"flushed": True}


@app.post("/admin/reset-stats")
async def reset_stats():
    async with stats_lock:
        for key in list(stats):
            stats[key] = 0
        return dict(stats)


@app.get("/items/{item_id}")
async def get_item(item_id: str, bypass: bool = False):
    if not item_id.isalnum() or len(item_id) > 32:
        raise HTTPException(status_code=400, detail="invalid id")

    key = f"item:{item_id}"
    skip_cache = bypass or not CACHE_ENABLED
    if skip_cache:
        await bump("bypasses")
        item = await origin_fetch(item_id)
        return JSONResponse(item, headers={"X-Cache": "BYPASS"})

    cached = await cache_get(key)
    if cached is not None:
        await bump("hits")
        return JSONResponse(json.loads(cached), headers={"X-Cache": "HIT"})

    if CACHE_SINGLEFLIGHT:
        async with local_locks_mu:
            lock = local_locks.setdefault(item_id, asyncio.Lock())
        async with lock:
            cached = await cache_get(key)
            if cached is not None:
                await bump("hits")
                return JSONResponse(json.loads(cached), headers={"X-Cache": "HIT"})
            await bump("misses")
            item = await load_item(item_id)
            return JSONResponse(item, headers={"X-Cache": "MISS"})

    await bump("misses")
    item = await load_item(item_id)
    return JSONResponse(item, headers={"X-Cache": "MISS"})
