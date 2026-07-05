import { Github } from 'lucide-react'

const REPO = 'https://github.com/darkwhitezero/dwhiepaint'

export function Footer() {
  return (
    <footer className="site-footer">
      <span>
        Сделал <strong>darkwhitezero</strong>
      </span>
      <span className="site-footer-dot" aria-hidden="true">
        ·
      </span>
      <a href={REPO} target="_blank" rel="noopener noreferrer" className="site-footer-link">
        <Github size={15} strokeWidth={1.9} aria-hidden="true" />
        Репозиторий на GitHub
      </a>
    </footer>
  )
}
