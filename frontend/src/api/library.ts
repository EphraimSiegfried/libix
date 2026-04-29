import { api } from './client'

export interface UserInfo {
  id: number
  username: string
}

export interface Audiobook {
  id: number
  title: string
  author: string | null
  narrator: string | null
  description: string | null
  path: string
  size_bytes: number | null
  duration_seconds: number | null
  cover_image_url: string | null
  asin: string | null
  open_library_key: string | null
  series_name: string | null
  series_position: string | null
  release_date: string | null
  language: string | null
  indexer: string | null
  source_url: string | null
  added_by: UserInfo | null
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

export async function importDownload(downloadId: number): Promise<Audiobook[]> {
  return api.post<Audiobook[]>(`/library/import/${downloadId}`)
}

export interface AsinSearchResult {
  asin: string
  title: string | null
  author: string | null
  narrator: string | null
  duration_seconds: number | null
  cover_url: string | null
  series_name: string | null
  series_position: string | null
}

export async function searchAsinForAudiobook(audiobookId: number): Promise<AsinSearchResult[]> {
  return api.get<AsinSearchResult[]>(`/library/${audiobookId}/search-asin`)
}

export async function setAudiobookAsin(audiobookId: number, asin: string): Promise<Audiobook> {
  return api.post<Audiobook>(`/library/${audiobookId}/set-asin`, { asin })
}

export async function refreshAudiobookMetadata(audiobookId: number): Promise<Audiobook> {
  return api.post<Audiobook>(`/library/${audiobookId}/refresh-metadata`)
}

export async function setAudiobookOpenLibraryKey(audiobookId: number, openLibraryKey: string): Promise<Audiobook> {
  return api.post<Audiobook>(`/library/${audiobookId}/set-openlibrary-key`, { open_library_key: openLibraryKey })
}

export async function deleteAudiobook(audiobookId: number, deleteFiles: boolean = false): Promise<void> {
  return api.delete(`/library/${audiobookId}?delete_files=${deleteFiles}`)
}
