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

export type Measurement = {
  name: string
  value: unknown
  unit: string | null
  origin: string
  method: string
  uncertainty: number | null
  source: string | null
}

export type AnalysisResult = {
  analysis_id: string
  kind: string
  created_at: string
  status: string
  inputs: Array<{
    role: string
    filename: string | null
    source_id: string | null
    sha256: string | null
    validation_status: string
    validation_messages: string[]
  }>
  methods: Array<{
    name: string
    software: string
    version: string | null
    parameters: Record<string, unknown>
  }>
  measurements: Measurement[]
  evidence: unknown[]
  limitations: string[]
  warnings: string[]
  skipped_stages: Array<{ stage: string; reason: string }>
  errors: Array<{ code: string; message: string }>
  reproducibility: {
    software_versions: Record<string, string>
    random_seed: number | null
    config_hash: string
    platform: string
  }
}

export type AnalysisDetail = AnalysisSummary & {
  result: AnalysisResult | null
}

export type StructureResponse = {
  id: string
  display_filename: string
  format: "pdb" | "mmcif"
  size_bytes: number
  sha256: string
  created_at: string
  metadata: {
    title?: string | null
    model_count?: number
    chain_ids?: string[]
    coordinate_record_count?: number
  }
}

export type StructureListResponse = {
  structures: StructureResponse[]
}
