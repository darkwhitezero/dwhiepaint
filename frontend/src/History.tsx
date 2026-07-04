import { useEffect, useState } from 'react'
import {
  assetUrl,
  listPaintings,
  resultBlob,
  shareLink,
  triggerDownload,
  unshareLink,
  type PaintingSummary,
} from './api'
import { useToast } from './Toast'

const DATE_FMT: Intl.DateTimeFormatOptions = {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
}

export function History({
  reloadSignal,
  onCreateNew,
}: {
  reloadSignal: number
  onCreateNew: () => void
}) {
  const toast = useToast()
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
      const blob = await resultBlob(id)
      const ext = blob.type === 'image/png' ? 'png' : 'pdf'
      triggerDownload(blob, `dwhiepaint-${id}.${ext}`)
    } catch (e) {
      toast.error(String(e instanceof Error ? e.message : e))
    }
  }

  async function share(p: PaintingSummary) {
    try {
      if (p.share_url) {
        await unshareLink(p.image_id)
        setItems((list) =>
          list.map((x) => (x.image_id === p.image_id ? { ...x, share_url: null } : x)),
        )
        toast.success('Ссылка отозвана')
        return
      }
      const { share_url } = await shareLink(p.image_id)
      setItems((list) =>
        list.map((x) => (x.image_id === p.image_id ? { ...x, share_url } : x)),
      )
      await navigator.clipboard.writeText(`${window.location.origin}${share_url}`)
      toast.success('Ссылка скопирована')
    } catch (e) {
      toast.error(String(e instanceof Error ? e.message : e))
    }
  }

  return (
    <div className="history">
      <div className="section-head">
        <h1>История</h1>
        <p className="lead">Ваши раскраски — скачивайте готовые файлы в любой момент.</p>
      </div>

      {loading && (
        <div className="grid">
          {Array.from({ length: 4 }).map((_, i) => (
            <div className="card card-skeleton" key={i}>
              <div className="card-thumb skeleton" />
              <div className="card-body">
                <div className="skeleton skeleton-line" />
                <div className="skeleton skeleton-line short" />
              </div>
            </div>
          ))}
        </div>
      )}

      {error && (
        <p className="inline-error" role="alert">
          {error}
        </p>
      )}

      {!loading && !error && items.length === 0 && (
        <div className="empty panel">
          <span className="empty-title">Пока пусто</span>
          <span className="empty-sub">Создайте первую раскраску из фотографии.</span>
          <button className="btn btn-primary" onClick={onCreateNew}>
            Создать раскраску
          </button>
        </div>
      )}

      {!loading && items.length > 0 && (
        <div className="grid">
          {items.map((p, i) => (
            <article
              className="card"
              key={p.image_id}
              style={{ '--i': i } as React.CSSProperties}
            >
              <div className="card-thumb">
                <img src={assetUrl(p.original_url)} alt="" loading="lazy" />
              </div>
              <div className="card-body">
                <span className="card-title">{p.color_count} цветов</span>
                <span className="card-date">
                  {new Date(p.created_at).toLocaleString('ru-RU', DATE_FMT)}
                </span>
              </div>
              {p.has_result ? (
                <div className="card-actions">
                  <button className="btn btn-ghost btn-sm" onClick={() => download(p.image_id)}>
                    Скачать
                  </button>
                  <button className="btn btn-ghost btn-sm" onClick={() => share(p)}>
                    {p.share_url ? 'Отозвать' : 'Поделиться'}
                  </button>
                </div>
              ) : (
                <span className="card-status">{p.status}</span>
              )}
            </article>
          ))}
        </div>
      )}
    </div>
  )
}
