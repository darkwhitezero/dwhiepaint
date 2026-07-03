import { useEffect, useRef, useState } from 'react'
import {
  assetUrl,
  exportBlob,
  segment,
  triggerDownload,
  uploadImage,
  type SegmentResult,
} from './api'
import { Legend } from './Legend'

const MIN_K = 4
const MAX_K = 32

export function Editor({ onSaved }: { onSaved: () => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [localPreview, setLocalPreview] = useState<string | null>(null)
  const [imageId, setImageId] = useState<string | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [k, setK] = useState(16)
  const [seg, setSeg] = useState<SegmentResult | null>(null)
  const [busy, setBusy] = useState<'idle' | 'analyzing' | 'segmenting' | 'exporting'>('idle')
  const [error, setError] = useState<string | null>(null)
  const [pageSize, setPageSize] = useState('A4')

  const didInitialSegment = useRef(false)

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
      onSaved()
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e))
      setBusy('idle')
    }
  }

  async function onExport() {
    if (!imageId) return
    setBusy('exporting')
    setError(null)
    try {
      const blob = await exportBlob(imageId, pageSize)
      triggerDownload(blob, `dwhiepaint-${pageSize}.png`)
      onSaved()
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e))
    } finally {
      setBusy('idle')
    }
  }

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
    <section className="editor">
      <div className="uploader">
        <label className="dropzone">
          <input type="file" accept="image/*" onChange={(e) => onPickFile(e.target.files?.[0] ?? null)} />
          {localPreview ? (
            <img src={localPreview} alt="preview" className="preview" />
          ) : (
            <span>Выберите фото для загрузки</span>
          )}
        </label>
        <button className="primary" disabled={!file || busy !== 'idle'} onClick={onCreate}>
          {busy === 'analyzing' ? 'Анализируем…' : 'Создать раскраску'}
        </button>
      </div>

      {error && <p className="error">Ошибка: {error}</p>}

      {imageId && (
        <div className="workspace">
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
              <button className="primary" onClick={onExport} disabled={!seg || busy !== 'idle'}>
                {busy === 'exporting' ? 'Готовим…' : 'Скачать PNG'}
              </button>
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
        </div>
      )}
    </section>
  )
}
