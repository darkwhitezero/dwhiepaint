"""ARQ worker entrypoint for async segmentation jobs.

Run (see docker-compose ``worker`` service)::

    arq app.worker.WorkerSettings

Shares the cv-service image and the on-disk cache volume, so it reconstructs
images from ``preview.png`` and writes rendered artifacts where the API's
``/cache`` static mount serves them.
"""

from __future__ import annotations

import numpy as np
import redis as redis_sync

from . import config, jobs, matte


async def on_startup(ctx: dict) -> None:
    # Synchronous client used to write progress from the segmentation thread.
    ctx["progress_redis"] = redis_sync.Redis.from_url(
        config.REDIS_URL, decode_responses=True
    )
    # Warm the rembg session now (cold onnxruntime init is ~30s) so the first
    # real job doesn't eat that latency. Fails soft if matting is unavailable.
    if config.SUBJECT_AWARE:
        try:
            matte.subject_mask(np.zeros((512, 512, 3), dtype=np.uint8))
        except Exception:  # noqa: BLE001 — warmup is best-effort
            pass


async def on_shutdown(ctx: dict) -> None:
    rp = ctx.get("progress_redis")
    if rp is not None:
        rp.close()


class WorkerSettings:
    functions = [jobs.run_segment]
    redis_settings = jobs.redis_settings()
    on_startup = on_startup
    on_shutdown = on_shutdown
    # Segmentation is CPU-bound (numpy/opencv release the GIL, so a couple can
    # overlap without starving the loop); keep concurrency modest.
    max_jobs = 2
    job_timeout = 300
