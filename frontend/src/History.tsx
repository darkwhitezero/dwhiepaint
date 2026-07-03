import { useEffect, useState } from 'react'
import {
  assetUrl,
  listPaintings,
  resultBlob,
  triggerDownload,
  type PaintingSummary,
} from './api'

export function History({ reloadSignal }: { reloadSignal: number }) {
  const [items, setItems] = useState<PaintingSummary[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    listPaintings()
      .then((r) => {
        setItems(r)
        setError(null)
      })
      .catch((e) => setError(String(e instanceof Error ? e.message : e)))
      .finally(() => setLoading(false))
  }, [reloadSignal])

  async function download(id: string) {
    try {
      triggerDownload(await resultBlob(id), `dwhiepaint-${id}.png`)
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e))
    }
  }

  return (
    <aside className="history">
      <h2>Мои работы</h2>
      {loading && <p className="muted">Загрузка…</p>}
      {error && <p className="error">{error}</p>}
      {!loading && items.length === 0 && <p className="muted">Пока нет работ.</p>}

      <ul>
        {items.map((p) => (
          <li key={p.image_id}>
            <img src={assetUrl(p.original_url)} alt="" />
            <div className="meta">
              <span>{p.color_count} цветов</span>
              <span className="muted">{new Date(p.created_at).toLocaleString('ru-RU')}</span>
            </div>
            {p.has_result ? (
              <button onClick={() => download(p.image_id)}>Скачать</button>
            ) : (
              <span className="muted small">{p.status}</span>
            )}
          </li>
        ))}
      </ul>
    </aside>
  )
}
