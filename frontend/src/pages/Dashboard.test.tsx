import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { Dashboard } from "@/pages/Dashboard"

const health = {
  status: "ok",
  version: "0.1.0",
  database: { connected: true, revision: "0001_initial", head: "0001_initial", reason: null },
  storage: { writable: true, reason: null },
  capabilities: {
    rdkit: { available: false, version: null, reason: "RDKit is not installed" },
    mkdssp: { available: false, version: null, reason: "mkdssp is not on PATH" },
    vina: { available: false, version: null, reason: "Vina is not on PATH" },
    openmm: { available: false, version: null, reason: "OpenMM is not installed" },
    pytorch: { available: false, version: null, reason: "PyTorch is not installed" },
    gpu: { available: false, version: null, reason: "nvidia-smi is not on PATH" },
  },
}

describe("Dashboard", () => {
  it("shows an empty job list and the health reason for a missing tool", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        const body = url.endsWith("/api/analyses")
          ? { analyses: [] }
          : url.endsWith("/api/jobs")
            ? { jobs: [] }
            : health
        return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } })
      }),
    )
    render(<Dashboard />)
    expect(await screen.findByText("No analysis is running.")).toBeInTheDocument()
    expect(screen.getByText("No analyses have been saved yet.")).toBeInTheDocument()
    expect(screen.getByText("RDKit is not installed")).toBeInTheDocument()
    expect(screen.getByText("ok")).toBeInTheDocument()
    vi.unstubAllGlobals()
  })
})
