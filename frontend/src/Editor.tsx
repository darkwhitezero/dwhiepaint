import { useCallback, useEffect, useRef, useState } from 'react'
import {
  exportBlob,
  getSegmentStatus,
  startSegment,
  triggerDownload,
  uploadImage,
  validateImageFile,
  type DetailPreset,
  type ExportFormat,
  type SegmentResult,
  type SegmentStage,
} from './api'
import { PalettePanel } from './PalettePanel'
import { ProgressBar } from './ProgressBar'
import { ResultViewer } from './ResultViewer'
import { SegmentedControl } from './SegmentedControl'
import { useToast } from './Toast'

const MIN_K = 4
const MAX_K = 32
const POLL_INTERVAL_MS = 700

const msg = (e: unknown) => String(e instanceof Error ? e.message : e)
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

interface Progress {
  stage: SegmentStage | null
  value: number
}

export function Editor({ onSaved }: { onSaved: () => void }) {
  const toast = useToast()
  const [file, setFile] = useState<File | null>(null)
  const [localPreview, setLocalPreview] = useState<string | null>(null)
  const [imageId, setImageId] = useState<string | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [k, setK] = useState(16)
  const [detail, setDetail] = useState<DetailPreset>('standard')
  const [seg, setSeg] = useState<SegmentResult | null>(null)
  const [activeColor, setActiveColor] = useState<number | null>(null)
  const [progress, setProgress] = useState<Progress | null>(null)
  const [busy, setBusy] = useState<'idle' | 'analyzing' | 'segmenting' | 'exporting'>('idle')
  const [error, setError] = useState<string | null>(null)
  const [pageSize, setPageSize] = useState('A4')
  const [format, setFormat] = useState<ExportFormat>('pdf')
  const [tiles, setTiles] = useState(1)
  const [includeLegend, setIncludeLegend] = useState(true)
  const [dragActive, setDragActive] = useState(false)

  const didInitialSegment = useRef(false)
  // Signature of the last segmentation (k + detail) so the debounce effect only
  // re-runs when one of them actually changes.
  const lastSegmentedSig = useRef<string | null>(null)
  const localPreviewRef = useRef<string | null>(null)
  // Bumped to supersede an in-flight poll loop (new k, new file, or unmount).
  const segRun = useRef(0)

  // Revoke the outstanding object URL and stop polling when the editor unmounts.
  useEffect(
    () => () => {
      segRun.current++
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
    segRun.current++ // cancel any in-flight poll from a previous image
    setFile(f)
    setImageId(null)
    setSeg(null)
    setActiveColor(null)
    setProgress(null)
    setPreviewUrl(null)
    setError(null)
    didInitialSegment.current = false
    lastSegmentedSig.current = null
    setPreviewFor(f)
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragActive(false)
    const f = e.dataTransfer.files?.[0]
    if (f) onPickFile(f)
  }

  // Enqueue a segmentation job and poll it to completion, streaming progress.
  // A run token (segRun) lets a newer call (slider change / new file / unmount)
  // supersede an older poll loop so stale results never land. Returns whether
  // segmentation completed successfully.
  const runSegment = useCallback(
    async (id: string, colors: number, preset: DetailPreset): Promise<boolean> => {
      const myRun = ++segRun.current
      const current = () => segRun.current === myRun
      setBusy('segmenting')
      setError(null)
      setProgress({ stage: 'queued', value: 0 })
      try {
        await startSegment(id, colors, preset)
        for (;;) {
          if (!current()) return false // superseded
          const st = await getSegmentStatus(id)
          if (!current()) return false

          if (st.status === 'complete') {
            setSeg({
              palette: st.palette ?? [],
              region_map_url: st.region_map_url ?? '',
              painted_preview_url: st.painted_preview_url,
              svg_url: st.svg_url,
              k: st.k ?? colors,
            })
            lastSegmentedSig.current = `${colors}|${preset}`
            setActiveColor(null)
            setProgress(null)
            setBusy('idle')
            return true
          }
          if (st.status === 'failed' || st.status === 'expired') {
            throw new Error(st.error ?? 'Не удалось обработать изображение')
          }

          setProgress({ stage: st.stage ?? 'queued', value: st.progress ?? 0 })
          await sleep(POLL_INTERVAL_MS)
        }
      } catch (e) {
        if (!current()) return false
        const m = msg(e)
        setError(m)
        toast.error(m)
        setProgress(null)
        setBusy('idle')
        return false
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
      // Mark this signature as handled so the debounce effect doesn't double-segment.
      lastSegmentedSig.current = `${res.predicted_k}|${detail}`
      const ok = await runSegment(res.image_id, res.predicted_k, detail)
      onSaved() // refresh history regardless — the painting row exists now
      if (ok) toast.success('Раскраска создана')
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
      const withLegend = (format === 'pdf' || format === 'zip') && includeLegend
      const t = format === 'pdf' ? tiles : 1
      const blob = await exportBlob(imageId, pageSize, withLegend, format, t)
      const suffix = t > 1 ? `-${t}x${t}` : ''
      triggerDownload(blob, `dwhiepaint-${pageSize}${suffix}.${format}`)
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

  // Re-segment (debounced) whenever k or the detail preset changes after the
  // first pass.
  useEffect(() => {
    if (!imageId || !didInitialSegment.current) return
    if (lastSegmentedSig.current === `${k}|${detail}`) return
    const t = setTimeout(() => runSegment(imageId, k, detail), 400)
    return () => clearTimeout(t)
  }, [k, detail, imageId, runSegment])

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
              <span className="control-label">Детализация</span>
              <SegmentedControl
                ariaLabel="Уровень детализации"
                value={detail}
                onChange={setDetail}
                options={[
                  { value: 'beginner', label: 'Новичок' },
                  { value: 'standard', label: 'Стандарт' },
                  { value: 'detailed', label: 'Детально' },
                ]}
              />
            </div>

            {busy === 'segmenting' && progress && (
              <ProgressBar progress={progress.value} stage={progress.stage} />
            )}

            <div className="control">
              <span className="control-label">Формат</span>
              <SegmentedControl
                ariaLabel="Формат экспорта"
                value={format}
                onChange={setFormat}
                options={[
                  { value: 'pdf', label: 'PDF' },
                  { value: 'png', label: 'PNG' },
                  { value: 'svg', label: 'SVG' },
                  { value: 'zip', label: 'ZIP' },
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
              <div className="control">
                <span className="control-label">Плитка (крупный холст)</span>
                <SegmentedControl
                  ariaLabel="Разбить на листы"
                  value={String(tiles)}
                  onChange={(v) => setTiles(Number(v))}
                  options={[
                    { value: '1', label: '1 лист' },
                    { value: '2', label: '2×2' },
                    { value: '3', label: '3×3' },
                  ]}
                />
              </div>
            )}

            {(format === 'pdf' || format === 'zip') && (
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

          <div className="result-area">
            {seg && previewUrl ? (
              <ResultViewer
                originalUrl={previewUrl}
                paintedUrl={seg.painted_preview_url}
                svgUrl={seg.svg_url}
                activeColor={activeColor}
              />
            ) : (
              <div className="result-canvas">
                <div className="skeleton" aria-hidden="true" />
              </div>
            )}
            {seg && (
              <PalettePanel
                palette={seg.palette}
                activeColor={activeColor}
                onSelect={setActiveColor}
              />
            )}
          </div>
        </div>
      )}
    </div>
  )
}
