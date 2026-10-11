export type CapabilityStatus = {
  available: boolean
  version: string | null
  reason: string | null
}

export type HealthResponse = {
  status: "ok" | "degraded"
  version: string
  database: {
    connected: boolean
    revision: string | null
    head: string | null
    reason: string | null
  }
  storage: {
    writable: boolean
    reason: string | null
  }
  capabilities: Record<string, CapabilityStatus>
}

export type AnalysisErrorBody = {
  code: string
  message: string
}

export type AnalysisSummary = {
  id: string
  kind: string
  status: string
  created_at: string
  started_at: string | null
  completed_at: string | null
  structure_id: string | null
  structure_filename: string | null
  error: AnalysisErrorBody | null
}

export type AnalysisListResponse = {
  analyses: AnalysisSummary[]
}
