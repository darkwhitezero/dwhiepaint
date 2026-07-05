import { useState } from 'react'
import { login, register } from './api'
import { Footer } from './Footer'

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
      <div className="auth-brand">
        <img src="/favicon.svg" alt="" width={34} height={33} />
        <span>dwhiepaint</span>
      </div>
      <h1 className="auth-title">Раскраска по номерам из&nbsp;фото</h1>
      <p className="auth-lead">Войдите, чтобы создавать и хранить свои работы.</p>

      <form className="auth-card panel" onSubmit={submit}>
        <div className="auth-tabs" role="radiogroup" aria-label="Вход или регистрация">
          <button
            type="button"
            role="radio"
            aria-checked={mode === 'login'}
            className={`auth-tab${mode === 'login' ? ' is-active' : ''}`}
            onClick={() => setMode('login')}
          >
            Вход
          </button>
          <button
            type="button"
            role="radio"
            aria-checked={mode === 'register'}
            className={`auth-tab${mode === 'register' ? ' is-active' : ''}`}
            onClick={() => setMode('register')}
          >
            Регистрация
          </button>
        </div>

        <label className="field">
          <span>Email</span>
          <input
            type="email"
            value={email}
            autoComplete="username"
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>
        <label className="field">
          <span>Пароль</span>
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
          <p className="inline-error" role="alert">
            {error}
          </p>
        )}

        <button className="btn btn-primary btn-block btn-cta" type="submit" disabled={busy}>
          {busy ? 'Подождите…' : mode === 'login' ? 'Войти' : 'Создать аккаунт'}
        </button>
        {mode === 'register' && <small className="field-hint">Пароль — минимум 8 символов.</small>}
      </form>

      <Footer />
    </div>
  )
}
