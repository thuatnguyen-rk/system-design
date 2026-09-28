# Caching

Status: in progress

## Problem

After **uncached** vs **warm**, write what caching is for and what it is not for.

## Constraints

Lab knobs: origin delay, TTL, 16MB Redis, one API replica. What would change with many replicas or a real database?

## Design

Sketch cache-aside for `GET /items/{id}`. Where does TTL live? Who fills Redis on a miss?

## Trade-offs

Hit latency vs freshness vs origin load. What did **mixed** vs **warm** do to the hit ratio?

## Failure modes

Redis stop, stampede, stale after write (this lab has no writes — note the gap). Fail-open vs fail-closed.

## SLOs and observability

Which signals from `/stats` and `X-Cache` would you alert on? Hit ratio alone is not an SLO.

## Capacity and cost

16MB `allkeys-lru`. What evicts first? When is origin cheaper than a bigger cache?

## Lab

From `primitives/caching/lab`:

```bash
docker compose up -d --build
```

Scenarios (`load` is a one-shot service):

```bash
docker compose --profile load run --rm load
SCENARIO=uncached docker compose --profile load run --rm load
SCENARIO=stampede N=50 CONCURRENCY=50 docker compose --profile load run --rm load
SCENARIO=mixed KEYS=50 docker compose --profile load run --rm load
```

PowerShell:

```powershell
docker compose --profile load run --rm load
$env:SCENARIO="uncached"; docker compose --profile load run --rm load
$env:SCENARIO="stampede"; $env:N="50"; $env:CONCURRENCY="50"; docker compose --profile load run --rm load
$env:SCENARIO="mixed"; $env:KEYS="50"; docker compose --profile load run --rm load
```

Then compare stampede with a singleflight lock (one process only — that is the point):

```bash
docker compose down
CACHE_SINGLEFLIGHT=true docker compose up -d --build
SCENARIO=stampede N=50 CONCURRENCY=50 docker compose --profile load run --rm load
```

Redis down (fail-open):

```bash
docker compose stop redis
curl -sD - http://127.0.0.1:8080/items/1 -o -
curl -s http://127.0.0.1:8080/stats
curl -s http://127.0.0.1:8080/health
docker compose start redis
```

Tear down:

```bash
docker compose down -v
```

Measure: `HIT`/`MISS`/`BYPASS`, latency p50/p99, `origin_calls`, `origin_in_flight_peak`, `cache_errors`. Write conclusions in the sections above, not only in notes.

## What I learned
