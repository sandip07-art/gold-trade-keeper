import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || '/api'

const api = axios.create({ baseURL: BASE, timeout: 10000 })

export const getDecision = (strictMode = false) =>
  api.get(`/decision?strict_mode=${strictMode}`).then(r => r.data)

export const getLogs = (limit = 50) =>
  api.get(`/logs?limit=${limit}`).then(r => r.data)

export const getStats = () =>
  api.get('/stats').then(r => r.data)

export const ingestSimulate = () =>
  api.post('/ingest/simulate').then(r => r.data)

export const recordTrade = (payload) =>
  api.post('/trades', payload).then(r => r.data)

export const exportLogsUrl = () => `${BASE}/logs/export`

export const health = () =>
  api.get('/health').then(r => r.data)
