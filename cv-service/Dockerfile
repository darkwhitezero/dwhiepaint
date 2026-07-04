FROM python:3.12-slim

# opencv-python-headless needs glib; fonts-dejavu gives Cyrillic glyphs for the
# legend; libcairo2 backs cairosvg, which rasterizes the canonical SVG line art
# for the PDF/PNG export so print matches the smooth vector.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    fonts-dejavu-core \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY data ./data

ENV CACHE_DIR=/tmp/dwhiepaint-cache
EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
