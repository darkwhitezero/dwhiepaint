import { useEffect, useState } from 'react'
import { listPaintings } from './api'
import { useToast } from './Toast'
import { ThemeToggleFull } from './ThemeToggle'
import type { Theme } from './useTheme'

export function Account({
  email,
  reloadSignal,
  onLogout,
  theme,
  onTheme,
}: {
  email: string
  reloadSignal: number
  onLogout: () => void
  theme: Theme
  onTheme: (t: Theme) => void
}) {
  const toast = useToast()
  const [total, setTotal] = useState<number | null>(null)
  const [exported, setExported] = useState<number | null>(null)

  useEffect(() => {
    listPaintings()
      .then((items) => {
        setTotal(items.length)
        setExported(items.filter((i) => i.has_result).length)
      })
      .catch(() => {
        setTotal(null)
        setExported(null)
      })
  }, [reloadSignal])

  async function copyEmail() {
    try {
      await navigator.clipboard.writeText(email)
      toast.success('Email скопирован')
    } catch {
      toast.error('Не удалось скопировать')
    }
  }

  const initial = email.trim().charAt(0).toUpperCase() || '?'

  return (
    <div className="account">
      <div className="section-head">
        <h1>Личный кабинет</h1>
        <p className="lead">Профиль и статистика ваших раскрасок.</p>
      </div>

      <div className="account-card panel">
        <div className="avatar avatar-lg" aria-hidden="true">
          {initial}
        </div>
        <div className="account-id">
          <span className="account-email">{email}</span>
          <button className="btn btn-ghost btn-sm" onClick={copyEmail}>
            Скопировать email
          </button>
        </div>
      </div>

      <div className="stats">
        <div className="stat panel">
          <span className="stat-value">{total ?? '—'}</span>
          <span className="stat-label">Всего работ</span>
        </div>
        <div className="stat panel">
          <span className="stat-value">{exported ?? '—'}</span>
          <span className="stat-label">С экспортом</span>
        </div>
      </div>

      <div className="panel appearance-card">
        <span className="control-label">Оформление</span>
        <ThemeToggleFull theme={theme} onChange={onTheme} />
      </div>

      <button className="btn btn-danger" onClick={onLogout}>
        Выйти из аккаунта
      </button>
    </div>
  )
}
