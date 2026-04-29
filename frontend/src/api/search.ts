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

export interface MetadataSearchResult {
  asin: string | null  // Audible ASIN (starts with B)
  open_library_key: string | null  // OpenLibrary work key
  title: string
  author: string | null
  narrator: string | null
  description: string | null
  duration_seconds: number | null
  release_date: string | null
  cover_url: string | null
  series_name: string | null
  series_position: string | null
  language: string | null
}

export interface MetadataSearchResponse {
  results: MetadataSearchResult[]
  query: string
}

export interface TorrentSearchRequest {
  title: string
  author?: string
  asin?: string
}

export async function search(query: string): Promise<SearchResult[]> {
  return api.get<SearchResult[]>(`/search?q=${encodeURIComponent(query)}`)
}

export async function searchMetadata(query: string, author?: string): Promise<MetadataSearchResponse> {
  let url = `/search/metadata?q=${encodeURIComponent(query)}`
  if (author) {
    url += `&author=${encodeURIComponent(author)}`
  }
  return api.get<MetadataSearchResponse>(url)
}

export async function searchTorrentsForAudiobook(request: TorrentSearchRequest): Promise<SearchResult[]> {
  return api.post<SearchResult[]>('/search/torrents', request)
}

export interface TorrentAvailabilityResult {
  asin: string | null
  title: string
  available: boolean
  count: number
}

export interface TorrentAvailabilityResponse {
  results: TorrentAvailabilityResult[]
}

export async function checkTorrentAvailability(items: TorrentSearchRequest[]): Promise<TorrentAvailabilityResponse> {
  return api.post<TorrentAvailabilityResponse>('/search/torrents/availability', { items })
}

export async function getMagnetLink(infoUrl: string): Promise<string | null> {
  const response = await api.post<{ magnet_url: string | null }>('/search/magnet', { info_url: infoUrl })
  return response.magnet_url
}
