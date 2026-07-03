from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import analyze as analyze_mod
from . import config
from . import export as export_mod
from . import segment as segment_mod
from .cache import cache

app = FastAPI(title="dwhiepaint CV service", version="0.1.0")
app.mount("/cache", StaticFiles(directory=str(config.CACHE_DIR)), name="cache")


class SegmentRequest(BaseModel):
    image_id: str
    k: int


class ExportRequest(BaseModel):
    image_id: str
    page_size: str = "A4"
    include_legend: bool = True


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
    entry = cache.get(req.image_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="image_id not found or expired")

    seg, region_map_url = segment_mod.segment(entry, req.k)
    palette = [
        PaletteColor(
            index=c.index, hex=c.hex, lab=list(c.lab),
            name_ru=c.name_ru, name_en=c.name_en,
        )
        for c in seg.palette
    ]
    return {"palette": palette, "region_map_url": region_map_url, "k": seg.k}


@app.post("/export")
def export(req: ExportRequest):
    entry = cache.get(req.image_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="image_id not found or expired")
    if entry.segmentation is None:
        raise HTTPException(status_code=409, detail="segment the image before export")

    pdf = export_mod.compose_export(entry, req.page_size, req.include_legend)
    return Response(content=pdf, media_type="application/pdf")
