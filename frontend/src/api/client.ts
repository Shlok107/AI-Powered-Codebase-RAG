import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from 'axios'
import type { Repository, FileContentResponse, ChatResponse, SecurityFinding, SecurityScan, Job, ApiError } from '../types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

class ApiClient {
  private client: AxiosInstance

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    })

    this.client.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => {
        // Add request ID for tracing
        config.headers['X-Request-ID'] = crypto.randomUUID()
        return config
      },
      (error) => Promise.reject(error)
    )

    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        // Normalize error responses
        const data = error.response?.data as { error?: ApiError } | undefined
        if (data?.error) {
          return Promise.reject(data.error)
        }
        return Promise.reject({
          code: 'NETWORK_ERROR',
          message: error.message,
          details: {},
        } as ApiError)
      }
    )
  }

  // Health
  async health() {
    const response = await this.client.get<{ status: string; database: string; llm_provider: string; embedding_provider: string }>('/health')
    return response.data
  }

  // Repositories
  async listRepositories(params?: { limit?: number; offset?: number }) {
    const response = await this.client.get<{ repositories: Repository[]; total: number }>('/repositories', { params })
    return response.data
  }

  async uploadRepository(file: File, onProgress?: (progress: number) => void) {
    const formData = new FormData()
    formData.append('file', file)

    const response = await this.client.post<Repository>('/repositories/upload', formData, {
      // Don't set Content-Type manually - let axios set it with the proper boundary
      headers: {
        'Content-Type': undefined,
      },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total && onProgress) {
          onProgress(Math.round((progressEvent.loaded * 100) / progressEvent.total))
        }
      },
    })
    return response.data
  }

  async getRepository(id: string) {
    const response = await this.client.get<Repository>(`/repositories/${id}`)
    return response.data
  }

  async deleteRepository(id: string) {
    await this.client.delete(`/repositories/${id}`)
  }

  async listFiles(repositoryId: string, params?: { limit?: number; offset?: number }) {
    const response = await this.client.get<File[]>(`/repositories/${repositoryId}/files`, { params })
    return response.data
  }

  async getFileContent(repositoryId: string, path: string, startLine?: number, endLine?: number) {
    const response = await this.client.get<FileContentResponse>(`/repositories/${repositoryId}/files/content`, {
      params: { path, start_line: startLine, end_line: endLine },
    })
    return response.data
  }

  async triggerIndexing(repositoryId: string, force = false) {
    const response = await this.client.post<Job>(`/repositories/${repositoryId}/index`, { force })
    return response.data
  }

  // Chat
  async chat(repositoryId: string, question: string, conversationId?: string) {
    const response = await this.client.post<ChatResponse>(`/repositories/${repositoryId}/chat`, {
      question,
      conversation_id: conversationId,
    })
    return response.data
  }

  // Security
  async listScans(repositoryId: string) {
    const response = await this.client.get<SecurityScan[]>(`/repositories/${repositoryId}/scans`)
    return response.data
  }

  async runScan(repositoryId: string) {
    const response = await this.client.post<SecurityScan>(`/repositories/${repositoryId}/scans`, {})
    return response.data
  }

  async listFindings(repositoryId: string, params?: Record<string, string>) {
    const response = await this.client.get<{ findings: SecurityFinding[]; total: number }>(`/repositories/${repositoryId}/findings`, { params })
    return response.data
  }

  async updateFinding(findingId: string, status: 'open' | 'dismissed' | 'resolved') {
    const response = await this.client.patch<SecurityFinding>(`/findings/${findingId}`, { status })
    return response.data
  }
}

export const api = new ApiClient()