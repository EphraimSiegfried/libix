import { api } from './client'

export interface User {
  id: number
  username: string
  role: 'admin' | 'user'
  created_at: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  const formData = new URLSearchParams()
  formData.append('username', username)
  formData.append('password', password)

  const response = await fetch('/api/auth/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: formData,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Login failed' }))
    throw new Error(error.detail || 'Login failed')
  }

  return response.json()
}

export async function getCurrentUser(): Promise<User> {
  return api.get<User>('/auth/me')
}

export async function getUsers(): Promise<User[]> {
  return api.get<User[]>('/users')
}

export async function createUser(username: string, password: string, role: 'admin' | 'user'): Promise<User> {
  return api.post<User>('/users', { username, password, role })
}

export async function deleteUser(userId: number): Promise<void> {
  return api.delete(`/users/${userId}`)
}

export async function changePassword(userId: number, password: string): Promise<void> {
  return api.put(`/users/${userId}/password`, { password })
}
