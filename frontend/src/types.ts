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

export type JobResponse = {
  id: string
  kind: string
  status: string
  progress: number | null
  cancel_requested: boolean
  created_at: string
  started_at: string | null
  completed_at: string | null
  error: AnalysisErrorBody | null
  analysis_id: string | null
  structure_id: string | null
}

export type JobListResponse = {
  jobs: JobResponse[]
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
  details?: Record<string, unknown>
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

export type AcceleratorStatus = {
  available: boolean
  version: string | null
  reason: string | null
}

export type HardwareReport = {
  ram_total_bytes: number
  ram_available_bytes: number
  cuda: AcceleratorStatus
  mps: AcceleratorStatus
}

export type RegisteredModel = {
  id: string
  name: string
  version: string
  task: string
  source_url: string
  licence: string
  dependencies: Array<{
    kind: string
    name: string
    available: boolean
    version: string | null
    reason: string | null
  }>
  hardware_requirements: {
    min_ram_bytes: number
    device: string
  }
  hardware_compatibility: {
    compatible: boolean
    reasons: string[]
  }
  input_format: string
  output_format: string
  benchmark: Record<string, unknown> | null
  known_limitations: string
  status: "disabled" | "incompatible" | "ready" | "loaded"
  status_reason: string | null
  loaded: boolean
  weights_loaded: boolean
  load_note: string | null
  training_jobs: Array<{
    id: string
    status: string
    progress: number | null
    created_at: string
  }>
  created_at: string
  card_markdown: string
}

export type ModelListResponse = {
  hardware: HardwareReport
  models: RegisteredModel[]
}
