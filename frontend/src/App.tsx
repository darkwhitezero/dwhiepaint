import { useEffect, useState } from 'react'
import { checkHealth, getToken, setToken, setUnauthorizedHandler } from './api'
import { AuthScreen } from './AuthScreen'
import { Editor } from './Editor'
import { History } from './History'
import './App.css'

type Health = 'checking' | 'ok' | 'down'
const EMAIL_KEY = 'dwhiepaint.email'

function App() {
  const [token, setTok] = useState<string | null>(getToken())
  const [email, setEmail] = useState<string>(localStorage.getItem(EMAIL_KEY) ?? '')
  const [health, setHealth] = useState<Health>('checking')
  const [reloadSignal, setReloadSignal] = useState(0)

  useEffect(() => {
    checkHealth()
      .then((r) => setHealth(r.status === 'ok' ? 'ok' : 'down'))
      .catch(() => setHealth('down'))
  }, [])

  // Log out automatically if an authenticated request is rejected (expired token).
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setToken(null)
      localStorage.removeItem(EMAIL_KEY)
      setTok(null)
      setEmail('')
    })
  }, [])

  function onAuth(newToken: string, newEmail: string) {
    setToken(newToken)
    localStorage.setItem(EMAIL_KEY, newEmail)
    setTok(newToken)
    setEmail(newEmail)
  }

  function logout() {
    setToken(null)
    localStorage.removeItem(EMAIL_KEY)
    setTok(null)
    setEmail('')
  }

  if (!token) return <AuthScreen onAuth={onAuth} />

  return (
    <main className="app">
      <header className="header">
        <div>
          <h1 className="wordmark">dwhiepaint</h1>
          <p className="subtitle">Фото → раскраска по номерам</p>
        </div>
        <div className="header-right">
          <span className={`badge badge--${health}`}>
            API:{' '}
            {health === 'checking' ? 'проверка…' : health === 'ok' ? 'на связи' : 'недоступен'}
          </span>
          <span className="user">{email}</span>
          <button className="link" onClick={logout}>
            Выйти
          </button>
        </div>
      </header>

      <div className="layout">
        <Editor onSaved={() => setReloadSignal((n) => n + 1)} />
        <History reloadSignal={reloadSignal} />
      </div>
    </main>
  )
}

export default App
