import { api } from './client'

export interface SearchResult {
  guid: string
  title: string
  indexer: string
  size: number
  seeders: number
  leechers: number
  download_url: string | null
  magnet_url: string | null
  info_url: string | null
  publish_date: string | null
  categories: number[]
}

export async function search(query: string): Promise<SearchResult[]> {
  return api.get<SearchResult[]>(`/search?q=${encodeURIComponent(query)}`)
}
