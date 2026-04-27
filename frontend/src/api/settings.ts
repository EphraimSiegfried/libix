import { api } from './client'

export interface Settings {
  server_port: number
  database_path: string
  library: {
    path: string
  }
  prowlarr: {
    url: string
    categories: number[]
    limit: number
    has_api_key: boolean
  }
  transmission: {
    url: string
    username: string | null
    has_password: boolean
    download_dir: string
  }
}

export interface ConnectionTestResult {
  success: boolean
  message: string
  details: Record<string, unknown> | null
}

export async function getSettings(): Promise<Settings> {
  return api.get<Settings>('/settings')
}

export async function testProwlarr(): Promise<ConnectionTestResult> {
  return api.post<ConnectionTestResult>('/settings/test-prowlarr')
}

export async function testTransmission(): Promise<ConnectionTestResult> {
  return api.post<ConnectionTestResult>('/settings/test-transmission')
}
