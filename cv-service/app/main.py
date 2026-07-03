from fastapi import FastAPI

app = FastAPI(title="dwhiepaint CV service", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok", "service": "cv-service"}
