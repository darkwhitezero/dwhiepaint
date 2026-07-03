import { useEffect, useRef, useState } from 'react'
import {
  assetUrl,
  checkHealth,
  exportUrl,
  segment,
  uploadImage,
  type PaletteColor,
  type SegmentResult,
} from './api'
import './App.css'

type Health = 'checking' | 'ok' | 'down'
const MIN_K = 4
const MAX_K = 32

function App() {
  const [health, setHealth] = useState<Health>('checking')
  const [file, setFile] = useState<File | null>(null)
  const [localPreview, setLocalPreview] = useState<string | null>(null)

  const [imageId, setImageId] = useState<string | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [k, setK] = useState<number>(16)
  const [seg, setSeg] = useState<SegmentResult | null>(null)

  const [busy, setBusy] = useState<'idle' | 'analyzing' | 'segmenting'>('idle')
  const [error, setError] = useState<string | null>(null)
  const [pageSize, setPageSize] = useState('A4')

  const didInitialSegment = useRef(false)

  useEffect(() => {
    checkHealth()
      .then((r) => setHealth(r.status === 'ok' ? 'ok' : 'down'))
      .catch(() => setHealth('down'))
  }, [])

  function onPickFile(f: File | null) {
    setFile(f)
    setImageId(null)
    setSeg(null)
    setPreviewUrl(null)
    setError(null)
    didInitialSegment.current = false
    if (localPreview) URL.revokeObjectURL(localPreview)
    setLocalPreview(f ? URL.createObjectURL(f) : null)
  }

  async function runSegment(id: string, colors: number) {
    setBusy('segmenting')
    setError(null)
    try {
      setSeg(await segment(id, colors))
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e))
    } finally {
      setBusy('idle')
    }
  }

  async function onCreate() {
    if (!file) return
    setBusy('analyzing')
    setError(null)
    try {
      const res = await uploadImage(file)
      setImageId(res.image_id)
      setPreviewUrl(res.preview_url)
      setK(res.predicted_k)
      didInitialSegment.current = true
      await runSegment(res.image_id, res.predicted_k)
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e))
      setBusy('idle')
    }
  }

  // Re-segment (debounced) whenever the user changes k after the first pass.
  useEffect(() => {
    if (!imageId || !didInitialSegment.current) return
    const t = setTimeout(() => {
      if (seg && seg.k === k) return
      runSegment(imageId, k)
    }, 400)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [k, imageId])

  return (
    <main className="app">
      <header className="header">
        <h1>dwhiepaint</h1>
        <p className="subtitle">Фото → раскраска по номерам</p>
        <span className={`badge badge--${health}`}>
          API:{' '}
          {health === 'checking' ? 'проверка…' : health === 'ok' ? 'на связи' : 'недоступен'}
        </span>
      </header>

      <section className="uploader">
        <label className="dropzone">
          <input
            type="file"
            accept="image/*"
            onChange={(e) => onPickFile(e.target.files?.[0] ?? null)}
          />
          {localPreview ? (
            <img src={localPreview} alt="preview" className="preview" />
          ) : (
            <span>Выберите фото для загрузки</span>
          )}
        </label>

        <button className="primary" disabled={!file || busy !== 'idle'} onClick={onCreate}>
          {busy === 'analyzing' ? 'Анализируем…' : 'Создать раскраску'}
        </button>
      </section>

      {error && <p className="error">Ошибка: {error}</p>}

      {imageId && (
        <section className="workspace">
          <div className="controls">
            <label className="slider">
              <span>
                Количество цветов: <strong>{k}</strong>
                {busy === 'segmenting' && <em> — пересчёт…</em>}
              </span>
              <input
                type="range"
                min={MIN_K}
                max={MAX_K}
                value={k}
                onChange={(e) => setK(Number(e.target.value))}
              />
            </label>

            <div className="export">
              <select value={pageSize} onChange={(e) => setPageSize(e.target.value)}>
                <option value="A4">A4</option>
                <option value="A3">A3</option>
              </select>
              <a
                className="primary"
                href={seg ? exportUrl(imageId, pageSize) : undefined}
                aria-disabled={!seg}
              >
                Скачать PNG
              </a>
            </div>
          </div>

          <div className="result">
            <figure>
              <figcaption>Оригинал</figcaption>
              {previewUrl && <img src={assetUrl(previewUrl)} alt="original" />}
            </figure>
            <figure>
              <figcaption>Раскраска</figcaption>
              {seg ? (
                <img src={assetUrl(seg.region_map_url)} alt="line art" />
              ) : (
                <div className="placeholder">…</div>
              )}
            </figure>
          </div>

          {seg && <Legend palette={seg.palette} />}
        </section>
      )}
    </main>
  )
}

function Legend({ palette }: { palette: PaletteColor[] }) {
  return (
    <ul className="legend">
      {palette.map((c) => (
        <li key={c.index}>
          <span className="swatch" style={{ background: c.hex }} />
          <span className="num">{c.index}</span>
          <span className="name">{c.name_ru}</span>
          <span className="hex">{c.hex}</span>
        </li>
      ))}
    </ul>
  )
}

export default App
