import asyncio
import os
import time

import httpx

API = os.environ.get("API_URL", "http://127.0.0.1:8080").rstrip("/")
SCENARIO = os.environ.get("SCENARIO", "warm")
N = int(os.environ.get("N", "200"))
CONCURRENCY = int(os.environ.get("CONCURRENCY", "20"))
KEY = os.environ.get("KEY", "1")
KEYS = int(os.environ.get("KEYS", "50"))


def pct(sorted_ms: list[float], p: float) -> float:
    if not sorted_ms:
        return 0.0
    i = min(len(sorted_ms) - 1, int(round((p / 100) * (len(sorted_ms) - 1))))
    return sorted_ms[i]


def report(label: str, rows: list[tuple[int, str, float]], extra: dict) -> None:
    lat = sorted(ms for _, _, ms in rows)
    hits = sum(1 for _, c, _ in rows if c == "HIT")
    misses = sum(1 for _, c, _ in rows if c == "MISS")
    bypasses = sum(1 for _, c, _ in rows if c == "BYPASS")
    errors = sum(1 for status, _, _ in rows if status != 200)
    print(f"scenario={SCENARIO} phase={label} n={len(rows)} conc={CONCURRENCY}")
    print(f"ok={len(rows) - errors} errors={errors} HIT={hits} MISS={misses} BYPASS={bypasses}")
    if lat:
        print(
            "latency_ms "
            f"p50={pct(lat, 50):.1f} p95={pct(lat, 95):.1f} "
            f"p99={pct(lat, 99):.1f} max={lat[-1]:.1f}"
        )
    print(
        "origin_calls="
        f"{extra.get('origin_calls')} "
        f"origin_in_flight_peak={extra.get('origin_in_flight_peak')} "
        f"cache_errors={extra.get('cache_errors')}"
    )
    print()


async def call(client: httpx.AsyncClient, path: str) -> tuple[int, str, float]:
    t0 = time.perf_counter()
    try:
        response = await client.get(path)
        ms = (time.perf_counter() - t0) * 1000
        return response.status_code, response.headers.get("x-cache", ""), ms
    except httpx.HTTPError:
        ms = (time.perf_counter() - t0) * 1000
        return 0, "", ms


async def run_many(client: httpx.AsyncClient, n: int, conc: int, path_for) -> list:
    sem = asyncio.Semaphore(conc)
    rows: list[tuple[int, str, float]] = [None] * n  # type: ignore[list-item]

    async def one(i: int) -> None:
        async with sem:
            rows[i] = await call(client, path_for(i))

    await asyncio.gather(*[one(i) for i in range(n)])
    return rows


async def stats(client: httpx.AsyncClient) -> dict:
    response = await client.get(f"{API}/stats")
    response.raise_for_status()
    return response.json()


async def reset(client: httpx.AsyncClient) -> None:
    await client.post(f"{API}/admin/flush")
    await client.post(f"{API}/admin/reset-stats")


async def main() -> None:
    timeout = httpx.Timeout(15.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        await reset(client)
        if SCENARIO == "uncached":
            rows = await run_many(
                client, N, CONCURRENCY, lambda i: f"{API}/items/{KEY}?bypass=true"
            )
            report("bypass", rows, await stats(client))
        elif SCENARIO == "warm":
            miss = await run_many(client, 1, 1, lambda i: f"{API}/items/{KEY}")
            report("cold", miss, await stats(client))
            rows = await run_many(client, N, CONCURRENCY, lambda i: f"{API}/items/{KEY}")
            report("warm", rows, await stats(client))
        elif SCENARIO == "stampede":
            rows = await run_many(client, N, CONCURRENCY, lambda i: f"{API}/items/{KEY}")
            report("cold-key", rows, await stats(client))
        elif SCENARIO == "mixed":
            rows = await run_many(
                client,
                N,
                CONCURRENCY,
                lambda i: f"{API}/items/{(i % KEYS) + 1}",
            )
            report("uniform-keys", rows, await stats(client))
        else:
            raise SystemExit(f"unknown SCENARIO={SCENARIO}")


if __name__ == "__main__":
    asyncio.run(main())
