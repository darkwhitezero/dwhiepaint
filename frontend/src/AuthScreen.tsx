import { useState } from 'react'
import { login, register } from './api'

export function AuthScreen({ onAuth }: { onAuth: (token: string, email: string) => void }) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const fn = mode === 'login' ? login : register
      const res = await fn(email.trim(), password)
      onAuth(res.token, res.email)
    } catch (err) {
      setError(String(err instanceof Error ? err.message : err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth">
      <h1 className="wordmark">dwhiepaint</h1>
      <p className="subtitle">Фото → раскраска по номерам</p>

      <form className="auth-card" onSubmit={submit}>
        <div className="tabs">
          <button
            type="button"
            className={mode === 'login' ? 'active' : ''}
            onClick={() => setMode('login')}
          >
            Вход
          </button>
          <button
            type="button"
            className={mode === 'register' ? 'active' : ''}
            onClick={() => setMode('register')}
          >
            Регистрация
          </button>
        </div>

        <label>
          Email
          <input
            type="email"
            value={email}
            autoComplete="username"
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>
        <label>
          Пароль
          <input
            type="password"
            value={password}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            onChange={(e) => setPassword(e.target.value)}
            minLength={8}
            required
          />
        </label>

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        <button className="primary" type="submit" disabled={busy}>
          {busy ? '…' : mode === 'login' ? 'Войти' : 'Создать аккаунт'}
        </button>
        {mode === 'register' && <small>Пароль — минимум 8 символов.</small>}
      </form>
    </div>
  )
}
