const ORIGIN_LABELS: Record<string, string> = {
  experimental_record: "Experimental record",
  database_reported: "Database-reported",
  calculated: "Calculated",
  ml_prediction: "ML prediction",
  user_supplied: "User supplied",
}

export function originLabel(origin: string): string {
  return ORIGIN_LABELS[origin] ?? origin
}

export function capabilityLabel(key: string): string {
  const labels: Record<string, string> = {
    rdkit: "RDKit",
    biotite: "Biotite",
    mkdssp: "DSSP (mkdssp)",
    fpocket: "fpocket",
    vina: "AutoDock Vina",
    openmm: "OpenMM",
    pytorch: "PyTorch",
    gpu: "GPU",
  }
  return labels[key] ?? key
}
