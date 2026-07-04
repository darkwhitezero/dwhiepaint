import type { SegmentStage } from './api'

const STAGE_LABELS: Record<SegmentStage, string> = {
  queued: 'В очереди…',
  superpixels: 'Разбиение на области',
  merge: 'Объединение мелких участков',
  smooth: 'Сглаживание границ',
  render: 'Отрисовка',
  vectorize: 'Векторизация',
  done: 'Готово',
  failed: 'Ошибка',
}

export function stageLabel(stage?: SegmentStage | null): string {
  return (stage && STAGE_LABELS[stage]) || 'Обработка…'
}

/**
 * Determinate progress bar for the async segmentation job. `progress` is a
 * fraction in [0, 1]; while queued (progress 0) the fill animates as an
 * indeterminate shimmer so it never looks stuck.
 */
export function ProgressBar({
  progress,
  stage,
}: {
  progress: number
  stage?: SegmentStage | null
}) {
  const pct = Math.round(Math.max(0, Math.min(1, progress)) * 100)
  const indeterminate = pct === 0

  return (
    <div className="progress" role="status" aria-live="polite">
      <div className="progress-head">
        <span className="progress-stage">{stageLabel(stage)}</span>
        {!indeterminate && <span className="progress-pct">{pct}%</span>}
      </div>
      <div
        className="progress-track"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={indeterminate ? undefined : pct}
      >
        <div
          className={`progress-fill${indeterminate ? ' is-indeterminate' : ''}`}
          style={indeterminate ? undefined : { width: `${pct}%` }}
        />
      </div>
    </div>
  )
}
