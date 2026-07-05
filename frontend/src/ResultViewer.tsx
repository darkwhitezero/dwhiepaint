import { useEffect, useMemo, useRef, useState } from 'react'
import { TransformComponent, TransformWrapper } from 'react-zoom-pan-pinch'
import { assetUrl } from './api'
import { SegmentedControl } from './SegmentedControl'

type Layer = 'original' | 'painted' | 'outline'

/**
 * Interactive result viewer: zoom/pan across three cross-faded layers — the
 * original photo, the painted preview, and the numbered outline. The outline is
 * inlined SVG so a chosen palette colour can be highlighted in place; picking a
 * colour auto-switches to the outline layer.
 */
export function ResultViewer({
  originalUrl,
  paintedUrl,
  svgUrl,
  activeColor,
}: {
  originalUrl: string
  paintedUrl?: string | null
  svgUrl?: string | null
  activeColor: number | null
}) {
  const [layer, setLayer] = useState<Layer>('painted')
  const [svgText, setSvgText] = useState<string | null>(null)
  const outlineRef = useRef<HTMLDivElement>(null)

  const layerOptions = useMemo(
    () =>
      [
        { value: 'original' as const, label: 'Оригинал' },
        paintedUrl ? { value: 'painted' as const, label: 'Закрашено' } : null,
        svgUrl ? { value: 'outline' as const, label: 'Контур' } : null,
      ].filter((o): o is { value: Layer; label: string } => o !== null),
    [paintedUrl, svgUrl],
  )

  // Load the SVG as text so we can inline it (enables per-colour highlighting).
  useEffect(() => {
    if (!svgUrl) {
      setSvgText(null)
      return
    }
    let alive = true
    fetch(assetUrl(svgUrl))
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error(String(r.status)))))
      .then((t) => alive && setSvgText(t))
      .catch(() => alive && setSvgText(null))
    return () => {
      alive = false
    }
  }, [svgUrl])

  // Inject the inline SVG once loaded.
  useEffect(() => {
    if (outlineRef.current) outlineRef.current.innerHTML = svgText ?? ''
  }, [svgText])

  // Picking a colour highlights its regions and reveals the outline layer.
  useEffect(() => {
    const root = outlineRef.current
    if (!root) return
    root.querySelectorAll('.rg.is-active').forEach((el) => el.classList.remove('is-active'))
    if (activeColor != null) {
      root.querySelectorAll(`.rg-${activeColor}`).forEach((el) => el.classList.add('is-active'))
      setLayer('outline')
    }
  }, [activeColor, svgText])

  return (
    <div className="rv">
      <div className="rv-toolbar">
        <SegmentedControl
          ariaLabel="Слой предпросмотра"
          value={layer}
          onChange={(v) => setLayer(v as Layer)}
          options={layerOptions}
        />
      </div>

      <TransformWrapper
        minScale={1}
        maxScale={8}
        doubleClick={{ mode: 'toggle', step: 2.4 }}
        wheel={{ step: 0.15 }}
      >
        {({ zoomIn, zoomOut, resetTransform }) => (
          <>
            <div className="rv-zoom">
              <button type="button" aria-label="Приблизить" onClick={() => zoomIn()}>
                +
              </button>
              <button type="button" aria-label="Отдалить" onClick={() => zoomOut()}>
                −
              </button>
              <button type="button" aria-label="Сбросить масштаб" onClick={() => resetTransform()}>
                ↺
              </button>
            </div>
            <TransformComponent wrapperClass="rv-canvas" contentClass="rv-stack">
              {/* Hidden sizer keeps the box at the artwork's aspect ratio so the
                  absolutely-positioned layers can cross-fade over it. */}
              <img className="rv-sizer" src={assetUrl(originalUrl)} alt="" aria-hidden="true" />
              <img
                className="rv-layer"
                data-on={layer === 'original'}
                src={assetUrl(originalUrl)}
                alt="Оригинал"
                draggable={false}
              />
              {paintedUrl && (
                <img
                  className="rv-layer"
                  data-on={layer === 'painted'}
                  src={assetUrl(paintedUrl)}
                  alt="Закрашенный предпросмотр"
                  draggable={false}
                />
              )}
              <div
                className="rv-layer rv-outline"
                data-on={layer === 'outline'}
                ref={outlineRef}
                aria-label="Контур по номерам"
                role="img"
              />
            </TransformComponent>
          </>
        )}
      </TransformWrapper>
    </div>
  )
}
