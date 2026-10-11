import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { PlannedPage } from "@/pages/Planned"

describe("PlannedPage", () => {
  it("explains the gap and does not render an action button", () => {
    render(
      <PlannedPage
        title="Compound Explorer"
        summary="Compound work is planned."
        toolName="RDKit"
        tool={{ available: false, version: null, reason: "RDKit is not installed" }}
      />,
    )
    expect(screen.getByRole("heading", { name: "Compound Explorer" })).toBeInTheDocument()
    expect(screen.getByText(/Unavailable: RDKit is not installed/)).toBeInTheDocument()
    expect(screen.queryByRole("button")).not.toBeInTheDocument()
    expect(screen.getByText(/no actions/i)).toBeInTheDocument()
  })
})
