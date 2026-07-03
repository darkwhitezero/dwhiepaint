export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:5000'

export async function checkHealth(): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE_URL}/health`)
  if (!res.ok) throw new Error(`health ${res.status}`)
  return res.json()
}
