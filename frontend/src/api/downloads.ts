import { api } from './client'

export type DownloadStatus = 'pending' | 'downloading' | 'seeding' | 'completed' | 'failed' | 'cancelled'

export interface Download {
  id: number
  title: string
  status: DownloadStatus
  progress: number
  size_bytes: number | null
  error_message: string | null
  indexer: string | null
  transmission_id: number | null
  audiobook_id: number | null
  metadata_asin: string | null
  metadata_open_library_key: string | null
  metadata_author: string | null
  metadata_narrator: string | null
  metadata_description: string | null
  metadata_duration_seconds: number | null
  metadata_cover_url: string | null
  metadata_series_name: string | null
  metadata_series_position: string | null
  metadata_language: string | null
  created_at: string
  updated_at: string
}

export interface DownloadCreate {
  title: string
  download_url?: string
  magnet_url?: string
  info_url?: string  // Link to the torrent page on the indexer
  indexer?: string
  size?: number
  metadata_asin?: string
  metadata_open_library_key?: string
  metadata_author?: string
  metadata_narrator?: string
  metadata_description?: string
  metadata_duration_seconds?: number
  metadata_cover_url?: string
  metadata_series_name?: string
  metadata_series_position?: string
  metadata_language?: string
}

export async function getDownloads(): Promise<Download[]> {
  return api.get<Download[]>('/downloads')
}

export async function getDownload(id: number): Promise<Download> {
  return api.get<Download>(`/downloads/${id}`)
}

export async function addDownload(data: DownloadCreate): Promise<Download> {
  return api.post<Download>('/downloads', data)
}

export async function deleteDownload(id: number, deleteData: boolean = false): Promise<void> {
  return api.delete(`/downloads/${id}?delete_data=${deleteData}`)
}
