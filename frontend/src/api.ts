export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:5000'

const TOKEN_KEY = 'dwhiepaint.token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}
export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const token = getToken()
  return { ...(extra ?? {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) }
}

export interface PaletteColor {
  index: number
  hex: string
  lab: number[]
  name_ru: string
  name_en: string | null
}
export interface AnalyzeResult {
  image_id: string
  predicted_k: number
  preview_url: string
}
export interface SegmentResult {
  palette: PaletteColor[]
  region_map_url: string
  painted_preview_url?: string | null
  svg_url?: string | null
  k: number
}

// Live status of an async segmentation job (Phase 6). While running it carries
// the current stage + progress fraction; when complete it also carries the full
// SegmentResult fields.
export type SegmentStage =
  | 'queued'
  | 'subject'
  | 'superpixels'
  | 'merge'
  | 'smooth'
  | 'render'
  | 'vectorize'
  | 'done'
  | 'failed'

export interface SegmentStatus {
  status: 'idle' | 'queued' | 'processing' | 'complete' | 'failed' | 'expired'
  stage?: SegmentStage | null
  progress?: number
  error?: string
  // Present only when status === 'complete'.
  palette?: PaletteColor[]
  region_map_url?: string
  painted_preview_url?: string | null
  svg_url?: string | null
  k?: number
}
export interface PaintingSummary {
  image_id: string
  color_count: number
  status: string
  created_at: string
  has_result: boolean
  original_url: string
  share_url: string | null
}
export interface SharedPainting {
  image_id: string
  color_count: number
  status: string
  has_result: boolean
  original_url: string
  palette: PaletteColor[]
}

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new ApiError((body as { error?: string }).error ?? `HTTP ${res.status}`, res.status)
  }
  return res.json() as Promise<T>
}

// Called when an authenticated request is rejected (expired/invalid token).
let onUnauthorized: () => void = () => {}
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn
}

function checkAuth(res: Response) {
  if (res.status === 401) {
    setToken(null)
    onUnauthorized()
    throw new ApiError('Сессия истекла — войдите снова', 401)
  }
}

async function handleAuthed<T>(res: Response): Promise<T> {
  checkAuth(res)
  return handle<T>(res)
}

// --- auth -----------------------------------------------------------------
export async function register(email: string, password: string): Promise<{ token: string; email: string }> {
  return handle(
    await fetch(`${API_BASE_URL}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    }),
  )
}
export async function login(email: string, password: string): Promise<{ token: string; email: string }> {
  return handle(
    await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    }),
  )
}

export async function checkHealth(): Promise<{ status: string }> {
  return handle(await fetch(`${API_BASE_URL}/health`))
}

// --- paintings ------------------------------------------------------------
export async function uploadImage(file: File): Promise<AnalyzeResult> {
  const form = new FormData()
  form.append('file', file)
  return handleAuthed(
    await fetch(`${API_BASE_URL}/api/paintings`, {
      method: 'POST',
      headers: authHeaders(),
      body: form,
    }),
  )
}

// Enqueue an async segmentation job; poll getSegmentStatus for progress/result.
export async function startSegment(imageId: string, k: number): Promise<{ job_id: string }> {
  return handleAuthed(
    await fetch(`${API_BASE_URL}/api/paintings/${imageId}/segment`, {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ k }),
    }),
  )
}

export async function getSegmentStatus(imageId: string): Promise<SegmentStatus> {
  return handleAuthed(
    await fetch(`${API_BASE_URL}/api/paintings/${imageId}/segment`, { headers: authHeaders() }),
  )
}

export async function listPaintings(): Promise<PaintingSummary[]> {
  return handleAuthed(await fetch(`${API_BASE_URL}/api/paintings`, { headers: authHeaders() }))
}

async function fetchBlob(url: string): Promise<Blob> {
  const res = await fetch(url, { headers: authHeaders() })
  checkAuth(res)
  if (!res.ok) throw new ApiError(`HTTP ${res.status}`, res.status)
  return res.blob()
}

export type ExportFormat = 'pdf' | 'png'

export async function exportBlob(
  imageId: string,
  pageSize: string,
  includeLegend: boolean,
  format: ExportFormat,
): Promise<Blob> {
  const q = new URLSearchParams({
    pageSize,
    includeLegend: String(includeLegend),
    format,
  })
  return fetchBlob(`${API_BASE_URL}/api/paintings/${imageId}/export?${q}`)
}
export async function resultBlob(imageId: string): Promise<Blob> {
  return fetchBlob(`${API_BASE_URL}/api/paintings/${imageId}/result`)
}

export async function shareLink(imageId: string): Promise<{ share_url: string }> {
  return handleAuthed(
    await fetch(`${API_BASE_URL}/api/paintings/${imageId}/share`, {
      method: 'POST',
      headers: authHeaders(),
    }),
  )
}
export async function unshareLink(imageId: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/paintings/${imageId}/share`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  checkAuth(res)
  if (!res.ok) throw new ApiError(`HTTP ${res.status}`, res.status)
}

// --- shared (anonymous) -----------------------------------------------------
export async function getSharedPainting(token: string): Promise<SharedPainting> {
  return handle(await fetch(`${API_BASE_URL}/api/shared/${token}`))
}
export async function sharedResultBlob(token: string): Promise<Blob> {
  const res = await fetch(`${API_BASE_URL}/api/shared/${token}/result`)
  if (!res.ok) throw new ApiError(`HTTP ${res.status}`, res.status)
  return res.blob()
}

export function assetUrl(path: string): string {
  return `${API_BASE_URL}${path}`
}

// Client-side guard so obviously-wrong files never hit the network.
const MAX_UPLOAD_BYTES = 15 * 1024 * 1024
export function validateImageFile(file: File): string | null {
  if (!file.type.startsWith('image/')) return 'Нужен файл изображения (JPG или PNG).'
  if (file.size > MAX_UPLOAD_BYTES) return 'Файл больше 15 МБ — выберите поменьше.'
  return null
}

export function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
