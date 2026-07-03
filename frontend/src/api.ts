export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:5000'

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

async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error((body as { error?: string }).error ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

export async function checkHealth(): Promise<{ status: string }> {
  return asJson(await fetch(`${API_BASE_URL}/health`))
}

export async function uploadImage(file: File): Promise<AnalyzeResult> {
  const form = new FormData()
  form.append('file', file)
  return asJson(await fetch(`${API_BASE_URL}/api/paintings`, { method: 'POST', body: form }))
}

export async function segment(imageId: string, k: number): Promise<SegmentResult> {
  return asJson(
    await fetch(`${API_BASE_URL}/api/paintings/${imageId}/colors`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ k }),
    }),
  )
}

export function assetUrl(path: string): string {
  return `${API_BASE_URL}${path}`
}

export function exportUrl(imageId: string, pageSize: string): string {
  return `${API_BASE_URL}/api/paintings/${imageId}/export?pageSize=${pageSize}`
}
