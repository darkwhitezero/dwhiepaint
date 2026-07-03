import type { Tab } from './useTab'

type Health = 'checking' | 'ok' | 'down'

const TAB_LABELS: { id: Tab; label: string }[] = [
  { id: 'create', label: 'Создать' },
  { id: 'history', label: 'История' },
  { id: 'account', label: 'Кабинет' },
]

const HEALTH_TEXT: Record<Health, string> = {
  checking: 'Проверка',
  ok: 'Онлайн',
  down: 'Офлайн',
}

export function NavBar({
  tab,
  onTab,
  health,
  email,
}: {
  tab: Tab
  onTab: (t: Tab) => void
  health: Health
  email: string
}) {
  const initial = email.trim().charAt(0).toUpperCase() || '?'

  return (
    <header className="nav">
      <div className="nav-inner">
        <button className="nav-brand" onClick={() => onTab('create')} aria-label="dwhiepaint — на главную">
          <img src="/favicon.svg" alt="" className="nav-logo" width={22} height={21} />
          <span>dwhiepaint</span>
        </button>

        <nav className="nav-tabs" aria-label="Основная навигация">
          {TAB_LABELS.map((t) => (
            <button
              key={t.id}
              type="button"
              className={`nav-tab${tab === t.id ? ' is-active' : ''}`}
              aria-current={tab === t.id ? 'page' : undefined}
              onClick={() => onTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>

        <div className="nav-right">
          <span className={`status status--${health}`} title={`API: ${HEALTH_TEXT[health]}`}>
            <span className="status-dot" aria-hidden="true" />
            <span className="status-text">{HEALTH_TEXT[health]}</span>
          </span>
          <button
            className="avatar avatar-btn"
            onClick={() => onTab('account')}
            aria-label="Личный кабинет"
            title={email}
          >
            {initial}
          </button>
        </div>
      </div>
    </header>
  )
}
