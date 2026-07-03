import { useEffect, useState } from 'react'
import { checkHealth } from './api'
import './App.css'

type Health = 'checking' | 'ok' | 'down'

function App() {
  const [health, setHealth] = useState<Health>('checking')
  const [file, setFile] = useState<File | null>(null)

  useEffect(() => {
    checkHealth()
      .then((r) => setHealth(r.status === 'ok' ? 'ok' : 'down'))
      .catch(() => setHealth('down'))
  }, [])

  const preview = file ? URL.createObjectURL(file) : null

  return (
    <main className="app">
      <header className="header">
        <h1>dwhiepaint</h1>
        <p className="subtitle">Фото → раскраска по номерам</p>
        <span className={`badge badge--${health}`}>
          API:{' '}
          {health === 'checking'
            ? 'проверка…'
            : health === 'ok'
              ? 'на связи'
              : 'недоступен'}
        </span>
      </header>

      <section className="uploader">
        <label className="dropzone">
          <input
            type="file"
            accept="image/*"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
          {preview ? (
            <img src={preview} alt="preview" className="preview" />
          ) : (
            <span>Выберите фото для загрузки</span>
          )}
        </label>
        <button className="primary" disabled={!file}>
          Загрузить (скоро)
        </button>
      </section>
    </main>
  )
}

export default App
