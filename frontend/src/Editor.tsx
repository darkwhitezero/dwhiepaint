import { useCallback, useEffect, useRef, useState } from 'react'
import {
  assetUrl,
  exportBlob,
  segment,
  triggerDownload,
  uploadImage,
  validateImageFile,
  type ExportFormat,
  type SegmentResult,
} from './api'
import { Legend } from './Legend'
import { SegmentedControl } from './SegmentedControl'
import { useToast } from './Toast'

const MIN_K = 4
const MAX_K = 32

const msg = (e: unknown) => String(e instanceof Error ? e.message : e)

export function Editor({ onSaved }: { onSaved: () => void }) {
  const toast = useToast()
  const [file, setFile] = useState<File | null>(null)
  const [localPreview, setLocalPreview] = useState<string | null>(null)
  const [imageId, setImageId] = useState<string | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [k, setK] = useState(16)
  const [seg, setSeg] = useState<SegmentResult | null>(null)
  const [busy, setBusy] = useState<'idle' | 'analyzing' | 'segmenting' | 'exporting'>('idle')
  const [error, setError] = useState<string | null>(null)
  const [pageSize, setPageSize] = useState('A4')
  const [format, setFormat] = useState<ExportFormat>('pdf')
  const [includeLegend, setIncludeLegend] = useState(true)
  const [dragActive, setDragActive] = useState(false)

  const didInitialSegment = useRef(false)
  const lastSegmentedK = useRef<number | null>(null)
  const localPreviewRef = useRef<string | null>(null)

  // Revoke the outstanding object URL when the editor unmounts.
  useEffect(
    () => () => {
      if (localPreviewRef.current) URL.revokeObjectURL(localPreviewRef.current)
    },
    [],
  )

  function setPreviewFor(f: File | null) {
    if (localPreviewRef.current) URL.revokeObjectURL(localPreviewRef.current)
    const url = f ? URL.createObjectURL(f) : null
    localPreviewRef.current = url
    setLocalPreview(url)
  }

  function onPickFile(f: File | null) {
    if (f) {
      const err = validateImageFile(f)
      if (err) {
        toast.error(err)
        return
      }
    }
    setFile(f)
    setImageId(null)
    setSeg(null)
    setPreviewUrl(null)
    setError(null)
    didInitialSegment.current = false
    lastSegmentedK.current = null
    setPreviewFor(f)
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragActive(false)
    const f = e.dataTransfer.files?.[0]
    if (f) onPickFile(f)
  }

  const runSegment = useCallback(
    async (id: string, colors: number) => {
      setBusy('segmenting')
      setError(null)
      try {
        setSeg(await segment(id, colors))
        lastSegmentedK.current = colors
      } catch (e) {
        const m = msg(e)
        setError(m)
        toast.error(m)
      } finally {
        setBusy('idle')
      }
    },
    [toast],
  )

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
      // Mark this k as handled so the debounce effect doesn't double-segment.
      lastSegmentedK.current = res.predicted_k
      await runSegment(res.image_id, res.predicted_k)
      onSaved()
      toast.success('Раскраска создана')
    } catch (e) {
      const m = msg(e)
      setError(m)
      toast.error(m)
      setBusy('idle')
    }
  }

  async function onExport() {
    if (!imageId) return
    setBusy('exporting')
    setError(null)
    try {
      const withLegend = format === 'pdf' && includeLegend
      const blob = await exportBlob(imageId, pageSize, withLegend, format)
      triggerDownload(blob, `dwhiepaint-${pageSize}.${format}`)
      onSaved()
      toast.success(`${format.toUpperCase()} готов к печати`)
    } catch (e) {
      const m = msg(e)
      setError(m)
      toast.error(m)
    } finally {
      setBusy('idle')
    }
  }

  // Re-segment (debounced) whenever the user changes k after the first pass.
  useEffect(() => {
    if (!imageId || !didInitialSegment.current) return
    if (lastSegmentedK.current === k) return
    const t = setTimeout(() => runSegment(imageId, k), 400)
    return () => clearTimeout(t)
  }, [k, imageId, runSegment])

  return (
    <div className="editor">
      <div className="section-head">
        <h1>Создать раскраску</h1>
        <p className="lead">
          Загрузите фото — получите раскраску по номерам, готовую к печати в 600&nbsp;dpi.
        </p>
      </div>

      <label
        className={`dropzone${dragActive ? ' is-drag' : ''}${localPreview ? ' has-image' : ''}`}
        onDragOver={(e) => {
          e.preventDefault()
          setDragActive(true)
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={onDrop}
      >
        <input
          type="file"
          accept="image/*"
          onChange={(e) => onPickFile(e.target.files?.[0] ?? null)}
        />
        {localPreview ? (
          <img src={localPreview} alt="Предпросмотр загруженного фото" className="dropzone-img" />
        ) : (
          <div className="dropzone-empty">
            <svg className="dropzone-icon" viewBox="0 0 24 24" aria-hidden="true">
              <path
                d="M12 15V4m0 0L8 8m4-4 4 4M5 15v3a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-3"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            <span className="dropzone-title">Перетащите фото сюда</span>
            <span className="dropzone-sub">или нажмите, чтобы выбрать · JPG, PNG · до 15&nbsp;МБ</span>
          </div>
        )}
      </label>

      {file && !imageId && (
        <div className="editor-actions">
          <button className="btn btn-primary" disabled={busy !== 'idle'} onClick={onCreate}>
            {busy === 'analyzing' && <span className="spinner" aria-hidden="true" />}
            {busy === 'analyzing' ? 'Анализируем…' : 'Создать раскраску'}
          </button>
        </div>
      )}

      {error && (
        <p className="inline-error" role="alert">
          {error}
        </p>
      )}

      {imageId && (
        <div className="workspace">
          <div className="panel controls">
            <div className="control control-slider">
              <div className="control-label">
                <span>Количество цветов</span>
                {/* Keying by k remounts the node on every change, replaying
                    the pulse keyframe as instant visual feedback. */}
                <strong key={k} className="k-pulse">
                  {k}
                  {busy === 'segmenting' && <em> · пересчёт…</em>}
                </strong>
              </div>
              <input
                type="range"
                min={MIN_K}
                max={MAX_K}
                value={k}
                onChange={(e) => setK(Number(e.target.value))}
              />
            </div>

            <div className="control">
              <span className="control-label">Формат</span>
              <SegmentedControl
                ariaLabel="Формат экспорта"
                value={format}
                onChange={setFormat}
                options={[
                  { value: 'pdf', label: 'PDF' },
                  { value: 'png', label: 'PNG' },
                ]}
              />
            </div>

            <div className="control">
              <span className="control-label">Размер</span>
              <SegmentedControl
                ariaLabel="Размер листа"
                value={pageSize}
                onChange={setPageSize}
                options={[
                  { value: 'A4', label: 'A4' },
                  { value: 'A3', label: 'A3' },
                ]}
              />
            </div>

            {format === 'pdf' && (
              <label className="switch">
                <input
                  type="checkbox"
                  checked={includeLegend}
                  onChange={(e) => setIncludeLegend(e.target.checked)}
                />
                <span className="switch-track" aria-hidden="true">
                  <span className="switch-thumb" />
                </span>
                <span>Лист с легендой</span>
              </label>
            )}

            <button
              className="btn btn-primary control-export"
              onClick={onExport}
              disabled={!seg || busy !== 'idle'}
            >
              {busy === 'exporting' && <span className="spinner" aria-hidden="true" />}
              {busy === 'exporting' ? 'Готовим…' : `Скачать ${format.toUpperCase()}`}
            </button>
          </div>

          <div className="result">
            <figure>
              <figcaption>Оригинал</figcaption>
              {previewUrl && <img src={assetUrl(previewUrl)} alt="Оригинал" />}
            </figure>
            <figure>
              <figcaption>Раскраска</figcaption>
              <div className="result-canvas">
                {seg && (
                  <img
                    key={seg.region_map_url}
                    className={`result-art${busy === 'segmenting' ? ' is-loading' : ''}`}
                    src={assetUrl(seg.region_map_url)}
                    alt="Раскраска по номерам"
                  />
                )}
                {(!seg || busy === 'segmenting') && <div className="skeleton" aria-hidden="true" />}
              </div>
            </figure>
          </div>

          {seg && <Legend palette={seg.palette} />}
        </div>
      )}
    </div>
  )
}
