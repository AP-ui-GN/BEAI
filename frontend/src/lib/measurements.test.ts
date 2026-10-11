import { describe, expect, it } from "vitest"

import { compositionRows, displayValue } from "@/lib/measurements"

describe("compositionRows", () => {
  it("sorts residue counts from an API composition object", () => {
    const rows = compositionRows({ GLY: 1, ALA: 3 })
    expect(rows).toEqual([
      { name: "ALA", count: 3 },
      { name: "GLY", count: 1 },
    ])
  })

  it("returns nothing for a missing composition", () => {
    expect(compositionRows(null)).toEqual([])
  })
})

describe("displayValue", () => {
  it("keeps null visible", () => {
    expect(displayValue(null)).toBe("null")
  })
})
