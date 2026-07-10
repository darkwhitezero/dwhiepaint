import json
from contextlib import asynccontextmanager

from arq import create_pool
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import analyze as analyze_mod
from . import config
from . import export as export_mod
from . import jobs as jobs_mod
from . import segment as segment_mod
from .cache import ensure_segmentation, load_entry


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ARQ pool for enqueuing/polling async segmentation jobs. If Redis is
    # unavailable the sync endpoints (/analyze, /segment, /export) still work;
    # only the /jobs routes degrade to 503.
    try:
        app.state.arq = await create_pool(jobs_mod.redis_settings())
    except Exception:  # noqa: BLE001 — keep the API up without the queue
        app.state.arq = None
    yield
    if app.state.arq is not None:
        await app.state.arq.close()


app = FastAPI(title="dwhiepaint CV service", version="0.1.0", lifespan=lifespan)
app.mount("/cache", StaticFiles(directory=str(config.CACHE_DIR)), name="cache")


class SegmentRequest(BaseModel):
    image_id: str
    k: int
    detail: str | None = None


class ExportRequest(BaseModel):
    image_id: str
    page_size: str = "A4"
    include_legend: bool = True
    format: str = "pdf"
    tiles: int = 1


class PaletteColor(BaseModel):
    index: int
    hex: str
    lab: list[float]
    name_ru: str
    name_en: str | None = None


@app.get("/health")
def health():
    return {"status": "ok", "service": "cv-service"}


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty upload")
    try:
        return analyze_mod.analyze(data)
    except Exception as exc:  # noqa: BLE001 — surface decode/processing failures
        raise HTTPException(status_code=422, detail=f"could not process image: {exc}")


@app.post("/segment")
def segment(req: SegmentRequest):
    entry = load_entry(req.image_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="image_id not found or expired")

    seg, region_map_url = segment_mod.segment(entry, req.k, req.detail)
    palette = [
        PaletteColor(
            index=c.index, hex=c.hex, lab=list(c.lab),
            name_ru=c.name_ru, name_en=c.name_en,
        )
        for c in seg.palette
    ]
    return {
        "palette": palette,
        "region_map_url": region_map_url,
        "painted_preview_url": seg.painted_preview_url,
        "svg_url": seg.svg_url,
        "k": seg.k,
    }


# --- async jobs (Phase 6) ---------------------------------------------------

def _require_arq(request: Request):
    arq = request.app.state.arq
    if arq is None:
        raise HTTPException(status_code=503, detail="job queue unavailable")
    return arq


@app.post("/jobs")
async def enqueue_segment(req: SegmentRequest, request: Request):
    """Enqueue a segmentation job; returns a job_id to poll."""
    arq = _require_arq(request)
    job = await arq.enqueue_job("run_segment", req.image_id, req.k, req.detail)
    if job is None:  # a job with this id already exists / couldn't enqueue
        raise HTTPException(status_code=409, detail="could not enqueue job")
    # Seed the hash so an immediate poll reports "queued" before the worker picks it up.
    key = jobs_mod.job_key(job.job_id)
    await arq.hset(key, mapping={"status": "queued", "stage": "queued", "progress": "0.0"})
    await arq.expire(key, config.JOB_RESULT_TTL_SECONDS)
    return {"job_id": job.job_id}


@app.get("/jobs/{job_id}")
async def job_status(job_id: str, request: Request):
    arq = _require_arq(request)
    job = await jobs_mod.read_job(arq, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found or expired")
    return jobs_mod.status_view(job)


@app.get("/jobs/{job_id}/result")
async def job_result(job_id: str, request: Request):
    arq = _require_arq(request)
    job = await jobs_mod.read_job(arq, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found or expired")
    if job.get("status") != "complete":
        raise HTTPException(status_code=409, detail=f"job not complete: {job.get('status')}")
    return json.loads(job["result"])


@app.post("/export")
def export(req: ExportRequest):
    entry = load_entry(req.image_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="image_id not found or expired")
    # The async job path segments in the WORKER container, a separate process
    # from this API container — they share only CACHE_DIR and Redis, never
    # in-memory state, so entry.segmentation is normally None here even right
    # after a successful segment. ensure_segmentation reconstructs it from the
    # files segment() persisted (see cache.save_segmentation).
    if ensure_segmentation(entry) is None:
        raise HTTPException(status_code=409, detail="segment the image before export")

    fmt = req.format.lower()
    if fmt == "png":
        png = export_mod.compose_png(entry, req.page_size)
        return Response(content=png, media_type="image/png")
    if fmt == "pdf":
        if req.tiles > 1:
            pdf = export_mod.compose_tiled(entry, req.page_size, req.tiles, req.include_legend)
        else:
            pdf = export_mod.compose_export(entry, req.page_size, req.include_legend)
        return Response(content=pdf, media_type="application/pdf")
    if fmt == "svg":
        return Response(content=export_mod.export_svg(entry), media_type="image/svg+xml")
    if fmt == "zip":
        bundle = export_mod.compose_bundle(entry, req.page_size, req.include_legend)
        return Response(content=bundle, media_type="application/zip")
    raise HTTPException(status_code=400, detail=f"unsupported format: {req.format}")
