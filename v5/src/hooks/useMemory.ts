import { useCallback, useState } from 'react'

export interface SearchResult {
  id: string
  content: string
  metadata: Record<string, unknown>
  score: number
}

export interface RAGResult {
  answer: string
  sources: SearchResult[]
  latency_ms: number
  tokens_used: number
}

export interface CollectionInfo {
  name: string
  vector_size: number
  distance: string
  points_count: number
  status: string
}

/** Hook for vector memory and RAG operations */
export function useMemory() {
  const [isSearching, setIsSearching] = useState(false)
  const [isEmbedding, setIsEmbedding] = useState(false)

  const addDocuments = useCallback(async (documents: Array<{
    content: string
    metadata?: Record<string, unknown>
    collection?: string
  }>): Promise<{ added: number; ids: string[]; collection: string }> => {
    const api = window.electronAPI
    if (api?.memoryVectorAdd) {
      return await api.memoryVectorAdd(documents) as { added: number; ids: string[]; collection: string }
    }

    const response = await fetch('/api/memory/vector/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(documents),
    })
    return await response.json()
  }, [])

  const search = useCallback(async (
    query: string,
    collection: string = 'default',
    topK: number = 10
  ): Promise<{ total: number; results: SearchResult[] }> => {
    setIsSearching(true)
    try {
      const response = await fetch('/api/memory/vector/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, collection, top_k: topK }),
      })
      return await response.json()
    } finally {
      setIsSearching(false)
    }
  }, [])

  const ragQuery = useCallback(async (
    query: string,
    collection: string = 'default',
    topK: number = 5
  ): Promise<RAGResult> => {
    const api = window.electronAPI
    if (api?.memoryRagQuery) {
      return await api.memoryRagQuery(query, collection) as RAGResult
    }

    const response = await fetch('/api/memory/vector/rag', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, collection, top_k: topK }),
    })
    return await response.json()
  }, [])

  const listCollections = useCallback(async (): Promise<CollectionInfo[]> => {
    const response = await fetch('/api/memory/vector/collections')
    return await response.json()
  }, [])

  const createCollection = useCallback(async (
    name: string,
    vectorSize: number = 384
  ): Promise<{ status: string; collection: string }> => {
    const response = await fetch('/api/memory/vector/collections', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, vector_size: vectorSize, distance: 'cosine' }),
    })
    return await response.json()
  }, [])

  const embedText = useCallback(async (texts: string[]): Promise<{ embeddings: number[][]; latency_ms: number }> => {
    setIsEmbedding(true)
    try {
      const response = await fetch('/api/memory/vector/embed', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ texts }),
      })
      return await response.json()
    } finally {
      setIsEmbedding(false)
    }
  }, [])

  return {
    addDocuments,
    search,
    ragQuery,
    listCollections,
    createCollection,
    embedText,
    isSearching,
    isEmbedding,
  }
}