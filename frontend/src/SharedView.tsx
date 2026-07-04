import { useEffect, useState } from 'react'
import { assetUrl, getSharedPainting, sharedResultBlob, triggerDownload, type SharedPainting } from './api'
import { Legend } from './Legend'
import { useToast } from './Toast'

export function SharedView({ token }: { token: string }) {
  const toast = useToast()
  const [painting, setPainting] = useState<SharedPainting | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState(false)

  useEffect(() => {
    getSharedPainting(token)
      .then(setPainting)
      .catch((e) => setError(String(e instanceof Error ? e.message : e)))
  }, [token])

  async function download() {
    setDownloading(true)
    try {
      const blob = await sharedResultBlob(token)
      const ext = blob.type === 'image/png' ? 'png' : 'pdf'
      triggerDownload(blob, `dwhiepaint-${token}.${ext}`)
    } catch (e) {
      toast.error(String(e instanceof Error ? e.message : e))
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="app-shell">
      <header className="nav">
        <div className="nav-inner">
          <a className="nav-brand" href="/">
            <img src="/favicon.svg" alt="" className="nav-logo" width={22} height={21} />
            <span>dwhiepaint</span>
          </a>
        </div>
      </header>

      <main className="app-main">
        <div className="section-head">
          <h1>Раскраска, которой поделились</h1>
          <p className="lead">Кто-то прислал вам ссылку на готовую работу — можно скачать файл для печати.</p>
        </div>

        {error && (
          <p className="inline-error" role="alert">
            {error}
          </p>
        )}

        {!painting && !error && <div className="skeleton shared-skeleton" aria-hidden="true" />}

        {painting && (
          <div className="workspace">
            <div className="result">
              <figure>
                <figcaption>Оригинал</figcaption>
                <img src={assetUrl(painting.original_url)} alt="Оригинал" />
              </figure>
              <figure>
                <figcaption>{painting.color_count} цветов</figcaption>
                <div className="empty panel">
                  <span className="empty-sub">Предпросмотр раскраски виден только автору — скачайте готовый файл ниже.</span>
                </div>
              </figure>
            </div>

            <Legend palette={painting.palette} />

            <div className="editor-actions">
              {painting.has_result ? (
                <button className="btn btn-primary" onClick={download} disabled={downloading}>
                  {downloading && <span className="spinner" aria-hidden="true" />}
                  {downloading ? 'Готовим…' : 'Скачать файл'}
                </button>
              ) : (
                <p className="inline-error" role="status">
                  Автор ещё не экспортировал эту работу — файла для скачивания пока нет.
                </p>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
