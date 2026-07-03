import { useEffect, useState } from 'react'

export type Tab = 'create' | 'history' | 'account'
export const TABS: Tab[] = ['create', 'history', 'account']

function parseHash(): Tab {
  const h = window.location.hash.replace(/^#/, '') as Tab
  return TABS.includes(h) ? h : 'create'
}

/**
 * Tab state mirrored in `location.hash` so tabs are deep-linkable and the
 * browser back button moves between them. `setTab` writes the hash; the
 * `hashchange` listener is the single source that updates React state.
 */
export function useTab(): [Tab, (t: Tab) => void] {
  const [tab, setTab] = useState<Tab>(parseHash)

  useEffect(() => {
    const onHash = () => setTab(parseHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  return [tab, (t: Tab) => { window.location.hash = t }]
}
