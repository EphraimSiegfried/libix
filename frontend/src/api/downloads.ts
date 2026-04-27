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
  created_at: string
  updated_at: string
}

export interface DownloadCreate {
  title: string
  download_url?: string
  magnet_url?: string
  indexer?: string
  size?: number
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
