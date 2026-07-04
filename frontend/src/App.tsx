import { useEffect, useRef, useState } from 'react'
import { checkHealth, getToken, setToken, setUnauthorizedHandler } from './api'
import { AuthScreen } from './AuthScreen'
import { NavBar } from './NavBar'
import { Editor } from './Editor'
import { History } from './History'
import { Account } from './Account'
import { SharedView } from './SharedView'
import { ToastProvider } from './Toast'
import { useTab } from './useTab'
import { useTheme } from './useTheme'
import './App.css'

type Health = 'checking' | 'ok' | 'down'
const EMAIL_KEY = 'dwhiepaint.email'

// A share link (/s/{token}) is a plain server-rendered path, not a client
// route — read once, never changes without a full page reload.
const SHARED_TOKEN = /^\/s\/([^/]+)/.exec(window.location.pathname)?.[1] ?? null

function App() {
  const [token, setTok] = useState<string | null>(getToken())
  const [email, setEmail] = useState<string>(localStorage.getItem(EMAIL_KEY) ?? '')
  const [health, setHealth] = useState<Health>('checking')
  const [reloadSignal, setReloadSignal] = useState(0)
  const [tab, setTab] = useTab()
  const [theme, setTheme] = useTheme()
  const panelRefs = useRef<Partial<Record<typeof tab, HTMLElement>>>({})

  // Restart the panel's entrance animation on every tab switch (a plain
  // display:none toggle isn't guaranteed to replay CSS animations across
  // browsers) — remove the class, force a reflow, then re-add it.
  useEffect(() => {
    const el = panelRefs.current[tab]
    if (!el) return
    el.classList.remove('panel-in')
    void el.offsetWidth
    el.classList.add('panel-in')
  }, [tab])

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
    setTab('create')
  }

  function logout() {
    setToken(null)
    localStorage.removeItem(EMAIL_KEY)
    setTok(null)
    setEmail('')
  }

  // Public share link — bypasses auth entirely, whether or not the visitor
  // has an account.
  if (SHARED_TOKEN)
    return (
      <ToastProvider>
        <SharedView token={SHARED_TOKEN} />
      </ToastProvider>
    )

  if (!token)
    return (
      <ToastProvider>
        <AuthScreen onAuth={onAuth} />
      </ToastProvider>
    )

  return (
    <ToastProvider>
      <div className="app-shell">
        <NavBar
          tab={tab}
          onTab={setTab}
          health={health}
          email={email}
          theme={theme}
          onTheme={setTheme}
        />
        <main className="app-main">
          {/* All panels stay mounted (Editor keeps in-progress work across tab
              switches); the effect above replays each panel's entrance
              animation when it becomes active. */}
          <section
            className="tab-panel"
            hidden={tab !== 'create'}
            ref={(el) => {
              if (el) panelRefs.current.create = el
            }}
          >
            <Editor onSaved={() => setReloadSignal((n) => n + 1)} />
          </section>
          <section
            className="tab-panel"
            hidden={tab !== 'history'}
            ref={(el) => {
              if (el) panelRefs.current.history = el
            }}
          >
            <History reloadSignal={reloadSignal} onCreateNew={() => setTab('create')} />
          </section>
          <section
            className="tab-panel"
            hidden={tab !== 'account'}
            ref={(el) => {
              if (el) panelRefs.current.account = el
            }}
          >
            <Account
              email={email}
              reloadSignal={reloadSignal}
              onLogout={logout}
              theme={theme}
              onTheme={setTheme}
            />
          </section>
        </main>
      </div>
    </ToastProvider>
  )
}

export default App
