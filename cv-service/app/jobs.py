"""Async segmentation jobs (Phase 6).

The heavy ``/segment`` pipeline is CPU-bound and — once ML lands (Phase 7) —
slow enough to blow an HTTP request timeout. Here it runs in an ARQ worker
instead: the API enqueues a job, the worker reconstructs the image from the
shared cache dir (see :func:`cache.load_entry`), runs segmentation in a thread
(so the worker's event loop stays responsive to other jobs), and streams
per-stage progress into a Redis hash the API polls.

Redis holds only ephemeral job state — a ``job:{id}`` hash with the live stage,
progress fraction and, on completion, the finished result JSON — all
TTL-bounded. Durable data (the palette) is persisted by the backend into
Postgres once the job completes; the CV service itself stays DB-free.

Progress is written with a *synchronous* Redis client from inside the worker
thread, while the queue mechanics (enqueue/read) use the async client. This
avoids marshalling every progress tick back onto the event loop.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

logger = logging.getLogger("dwhiepaint.jobs")

from arq.connections import RedisSettings

from . import config
from . import paints as paints_mod
from . import segment as segment_mod
from .cache import load_entry


def redis_settings() -> RedisSettings:
    """ARQ connection settings parsed from ``REDIS_URL``."""
    return RedisSettings.from_dsn(config.REDIS_URL)


def job_key(job_id: str) -> str:
    return f"job:{job_id}"


def _serialize_palette(seg) -> list[dict]:
    out = []
    for c in seg.palette:
        entry = {
            "index": c.index,
            "hex": c.hex,
            "lab": list(c.lab),
            "name_ru": c.name_ru,
            "name_en": c.name_en,
        }
        # Nearest real acrylic paint (+ mixing hint) — extra fields the backend
        # ignores when persisting but the UI shows for physical painting.
        entry["paint"] = paints_mod.describe(c.lab)
        out.append(entry)
    return out


async def run_segment(
    ctx: dict, image_id: str, k: int, detail: str | None = None
) -> dict:
    """ARQ task: segment one image, streaming per-stage progress to Redis.

    ``ctx['progress_redis']`` is a synchronous Redis client set up in the
    worker's ``on_startup`` — safe to call from the segmentation thread.
    """
    job_id = ctx["job_id"]
    key = job_key(job_id)
    rp = ctx["progress_redis"]
    ttl = config.JOB_RESULT_TTL_SECONDS

    def mark(**fields: Any) -> None:
        rp.hset(key, mapping={name: str(val) for name, val in fields.items()})
        rp.expire(key, ttl)

    t0 = time.monotonic()
    stage_ts: dict[str, float] = {}
    mark(status="processing", stage="superpixels", progress=0.0, image_id=image_id)
    logger.info("job %s start image=%s k=%s detail=%s", job_id, image_id, k, detail)

    entry = load_entry(image_id)
    if entry is None:
        logger.warning("job %s FAILED image=%s: not found/expired", job_id, image_id)
        mark(status="failed", error="image_id not found or expired")
        return {"status": "failed"}

    def on_progress(stage: str, frac: float) -> None:
        stage_ts[stage] = round(time.monotonic() - t0, 2)
        mark(stage=stage, progress=round(frac, 3))

    try:
        seg, region_map_url = await asyncio.to_thread(
            segment_mod.segment, entry, k, detail, on_progress
        )
    except Exception as exc:  # noqa: BLE001 — record failure for the poller
        logger.warning("job %s FAILED image=%s after %.1fs: %s",
                       job_id, image_id, time.monotonic() - t0, exc)
        mark(status="failed", stage="failed", error=str(exc))
        return {"status": "failed", "error": str(exc)}

    logger.info("job %s done image=%s colors=%d total=%.1fs stages=%s",
                job_id, image_id, len(seg.palette), time.monotonic() - t0, stage_ts)

    result = {
        "palette": _serialize_palette(seg),
        "region_map_url": region_map_url,
        "painted_preview_url": seg.painted_preview_url,
        "svg_url": seg.svg_url,
        "k": seg.k,
    }
    rp.hset(
        key,
        mapping={
            "status": "complete",
            "stage": "done",
            "progress": "1.0",
            "result": json.dumps(result),
        },
    )
    rp.expire(key, ttl)
    return {"status": "complete"}


# --- API-side read helpers (async client) -----------------------------------

def _decode(raw: dict) -> dict[str, str]:
    """Redis may return bytes or str depending on client config; normalize."""
    out: dict[str, str] = {}
    for name, val in raw.items():
        k = name.decode() if isinstance(name, bytes) else name
        v = val.decode() if isinstance(val, bytes) else val
        out[k] = v
    return out


async def read_job(redis, job_id: str) -> dict[str, str] | None:
    """Return the decoded ``job:{id}`` hash, or None if unknown/expired."""
    raw = await redis.hgetall(job_key(job_id))
    if not raw:
        return None
    return _decode(raw)


def status_view(job: dict[str, str]) -> dict:
    """Public status projection (never leaks the full result blob)."""
    view: dict[str, Any] = {
        "status": job.get("status", "queued"),
        "stage": job.get("stage"),
        "progress": float(job.get("progress", 0.0) or 0.0),
    }
    if "error" in job:
        view["error"] = job["error"]
    return view
