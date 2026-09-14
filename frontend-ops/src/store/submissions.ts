import { create } from 'zustand'
import type { Submission, SubmissionFilters } from '../types'
import { api } from '../api/client'

interface SubmissionState {
  submissions: Submission[]
  current: Submission | null
  loading: boolean
  error: string | null
  filters: SubmissionFilters
  setFilters: (filters: SubmissionFilters) => void
  load: () => Promise<void>
  loadOne: (id: number) => Promise<Submission>
  refreshCurrent: () => Promise<void>
}

export const useSubmissionStore = create<SubmissionState>((set, get) => ({
  submissions: [],
  current: null,
  loading: false,
  error: null,
  filters: {},
  setFilters: (filters) => set({ filters }),
  load: async () => {
    set({ loading: true, error: null })
    try {
      const submissions = await api.submissions.list(get().filters)
      set({ submissions })
    } catch (error) {
      set({ error: error instanceof Error ? error.message : '加载失败' })
    } finally {
      set({ loading: false })
    }
  },
  loadOne: async (id) => {
    set({ loading: true, error: null })
    try {
      const current = await api.submissions.detail(id)
      set({ current })
      return current
    } finally {
      set({ loading: false })
    }
  },
  refreshCurrent: async () => {
    const id = get().current?.id
    if (id) await get().loadOne(id)
  },
}))
