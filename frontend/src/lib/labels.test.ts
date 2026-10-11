import { describe, expect, it } from "vitest"

import { capabilityLabel, originLabel } from "@/lib/labels"

describe("originLabel", () => {
  it("names each origin in the analysis envelope", () => {
    expect(originLabel("experimental_record")).toBe("Experimental record")
    expect(originLabel("database_reported")).toBe("Database-reported")
    expect(originLabel("calculated")).toBe("Calculated")
    expect(originLabel("ml_prediction")).toBe("ML prediction")
    expect(originLabel("user_supplied")).toBe("User supplied")
  })
})

describe("capabilityLabel", () => {
  it("uses the tool name rather than a shortened key", () => {
    expect(capabilityLabel("rdkit")).toBe("RDKit")
    expect(capabilityLabel("vina")).toBe("AutoDock Vina")
  })
})
