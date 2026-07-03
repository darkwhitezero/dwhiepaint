import { useEffect, useState } from 'react'
import { checkHealth, getToken, setToken, setUnauthorizedHandler } from './api'
import { AuthScreen } from './AuthScreen'
import { NavBar } from './NavBar'
import { Editor } from './Editor'
import { History } from './History'
import { Account } from './Account'
import { ToastProvider } from './Toast'
import { useTab } from './useTab'
import './App.css'

type Health = 'checking' | 'ok' | 'down'
const EMAIL_KEY = 'dwhiepaint.email'

function App() {
  const [token, setTok] = useState<string | null>(getToken())
  const [email, setEmail] = useState<string>(localStorage.getItem(EMAIL_KEY) ?? '')
  const [health, setHealth] = useState<Health>('checking')
  const [reloadSignal, setReloadSignal] = useState(0)
  const [tab, setTab] = useTab()

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

  if (!token)
    return (
      <ToastProvider>
        <AuthScreen onAuth={onAuth} />
      </ToastProvider>
    )

  return (
    <ToastProvider>
      <div className="app-shell">
        <NavBar tab={tab} onTab={setTab} health={health} email={email} />
        <main className="app-main">
          {/* All panels stay mounted (Editor keeps in-progress work across tab
              switches); hiding an inactive panel restarts its enter animation. */}
          <section className="tab-panel" hidden={tab !== 'create'}>
            <Editor onSaved={() => setReloadSignal((n) => n + 1)} />
          </section>
          <section className="tab-panel" hidden={tab !== 'history'}>
            <History reloadSignal={reloadSignal} onCreateNew={() => setTab('create')} />
          </section>
          <section className="tab-panel" hidden={tab !== 'account'}>
            <Account email={email} reloadSignal={reloadSignal} onLogout={logout} />
          </section>
        </main>
      </div>
    </ToastProvider>
  )
}

export default App
