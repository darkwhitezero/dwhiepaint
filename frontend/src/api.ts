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
  k: number
}
export interface PaintingSummary {
  image_id: string
  color_count: number
  status: string
  created_at: string
  has_result: boolean
  original_url: string
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
  return handle(
    await fetch(`${API_BASE_URL}/api/paintings`, {
      method: 'POST',
      headers: authHeaders(),
      body: form,
    }),
  )
}

export async function segment(imageId: string, k: number): Promise<SegmentResult> {
  return handle(
    await fetch(`${API_BASE_URL}/api/paintings/${imageId}/colors`, {
      method: 'PATCH',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ k }),
    }),
  )
}

export async function listPaintings(): Promise<PaintingSummary[]> {
  return handle(await fetch(`${API_BASE_URL}/api/paintings`, { headers: authHeaders() }))
}

async function fetchBlob(url: string): Promise<Blob> {
  const res = await fetch(url, { headers: authHeaders() })
  if (!res.ok) throw new ApiError(`HTTP ${res.status}`, res.status)
  return res.blob()
}

export async function exportBlob(imageId: string, pageSize: string): Promise<Blob> {
  return fetchBlob(`${API_BASE_URL}/api/paintings/${imageId}/export?pageSize=${pageSize}`)
}
export async function resultBlob(imageId: string): Promise<Blob> {
  return fetchBlob(`${API_BASE_URL}/api/paintings/${imageId}/result`)
}

export function assetUrl(path: string): string {
  return `${API_BASE_URL}${path}`
}

export function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
