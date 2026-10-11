import type { AnalysisResult, Measurement } from "@/types"

export function findMeasurement(result: AnalysisResult, name: string): Measurement | undefined {
  return result.measurements.find((item) => item.name === name)
}

export function compositionRows(value: unknown): Array<{ name: string; count: number }> {
  if (value == null || typeof value !== "object" || Array.isArray(value)) {
    return []
  }
  const rows: Array<{ name: string; count: number }> = []
  for (const [name, count] of Object.entries(value)) {
    if (typeof count === "number") {
      rows.push({ name, count })
    }
  }
  rows.sort((left, right) => right.count - left.count || left.name.localeCompare(right.name))
  return rows
}

export function displayValue(value: unknown): string {
  if (value == null) {
    return "null"
  }
  if (typeof value === "number" || typeof value === "string" || typeof value === "boolean") {
    return String(value)
  }
  return JSON.stringify(value)
}

export type ChainRow = {
  chain_id: string
  polymer: boolean
  polymer_type: string
  observed_polymer_residue_count: number
  seqres_residue_count: number | null
  water_residue_count: number
  hetero_residue_count: number
}

export function asChainRows(value: unknown): ChainRow[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value.filter((item): item is ChainRow => {
    return Boolean(item) && typeof item === "object" && "chain_id" in item
  })
}

export type ResidueRef = {
  chain_id: string
  resname: string
  resseq: number
  icode: string
  missing_atoms?: string[]
  reason?: string
  source?: string
}

export function asResidueRefs(value: unknown): ResidueRef[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value.filter((item): item is ResidueRef => {
    return Boolean(item) && typeof item === "object" && "resseq" in item && "chain_id" in item
  })
}
