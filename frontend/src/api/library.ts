import { api } from './client'

export interface Audiobook {
  id: number
  title: string
  author: string | null
  narrator: string | null
  description: string | null
  path: string
  size_bytes: number | null
  duration_seconds: number | null
  added_at: string
}

export async function getAudiobooks(): Promise<Audiobook[]> {
  return api.get<Audiobook[]>('/library')
}

export async function getAudiobook(id: number): Promise<Audiobook> {
  return api.get<Audiobook>(`/library/${id}`)
}

export async function scanLibrary(): Promise<{ added: number; skipped: number }> {
  return api.post('/library/scan')
}
