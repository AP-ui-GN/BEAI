import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { ModelLaboratory } from "@/pages/ModelLaboratory"

const hardware = {
  ram_total_bytes: 16000000000,
  ram_available_bytes: 4000000000,
  cuda: { available: false, version: null, reason: "PyTorch is not installed, so CUDA was not queried." },
  mps: { available: false, version: null, reason: "PyTorch is not installed, so MPS was not queried." },
}

describe("ModelLaboratory", () => {
  it("shows an empty registry without inventing a model", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        return new Response(JSON.stringify({ hardware, models: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      }),
    )
    render(<ModelLaboratory />)
    expect(await screen.findByText(/No models are registered/)).toBeInTheDocument()
    expect(screen.getByText(/16000000000 bytes/)).toBeInTheDocument()
    expect(screen.getByText(/PyTorch is not installed, so CUDA was not queried/)).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /Load/ })).not.toBeInTheDocument()
    vi.unstubAllGlobals()
  })

  it("shows a missing dependency as disabled with the reason", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        return new Response(
          JSON.stringify({
            hardware,
            models: [
              {
                id: "m1",
                name: "stand-in",
                version: "0",
                task: "registry plumbing",
                source_url: "https://example.invalid/stand-in",
                licence: "test-only",
                dependencies: [],
                hardware_requirements: { min_ram_bytes: 1, device: "cpu" },
                hardware_compatibility: { compatible: false, reasons: ["missing"] },
                input_format: "none",
                output_format: "none",
                benchmark: null,
                known_limitations: "No weights.",
                status: "disabled",
                status_reason: "beai_module_that_is_not_installed is not installed",
                loaded: false,
                weights_loaded: false,
                load_note: null,
                training_jobs: [],
                created_at: "2026-10-13T00:00:00.000000Z",
                card_markdown: "",
              },
            ],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        )
      }),
    )
    render(<ModelLaboratory />)
    expect(await screen.findByRole("heading", { name: /stand-in/ })).toBeInTheDocument()
    expect(screen.getByText("disabled")).toBeInTheDocument()
    expect(screen.getByText(/Unavailable: beai_module_that_is_not_installed/)).toBeInTheDocument()
    expect(screen.getByText("No benchmark result is stored.")).toBeInTheDocument()
    expect(screen.getByText("No training jobs are stored for this model.")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Load stand-in" })).toBeDisabled()
    vi.unstubAllGlobals()
  })
})