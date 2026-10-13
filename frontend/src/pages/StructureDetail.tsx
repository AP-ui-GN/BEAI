import { useCallback, useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"

import { apiGet, apiPost } from "@/api/client"
import { CompositionChart } from "@/components/CompositionChart"
import { ProteinPanels } from "@/components/ProteinPanels"
import { OriginBadge } from "@/components/OriginBadge"
import { StructureViewer } from "@/components/StructureViewer"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  asChainRows,
  asResidueRefs,
  displayValue,
  findMeasurement,
} from "@/lib/measurements"
import type { AnalysisDetail, AnalysisListResponse, StructureResponse } from "@/types"

const SCALAR_MEASUREMENTS = [
  "title",
  "experimental_method",
  "resolution",
  "r_free",
  "deposition_date",
  "model_count",
  "analyzed_model_index",
  "analyzed_model_serial",
  "chain_count",
  "residue_count_observed_polymer",
  "residue_count_seqres",
  "atom_count_total",
  "atom_count_heavy",
  "atom_count_hydrogen",
  "atom_count_hetatm",
  "atom_count_water",
  "water_residue_count",
]

export function StructureDetail({ structureId }: { structureId: string }) {
  const [structure, setStructure] = useState<StructureResponse | null>(null)
  const [analysis, setAnalysis] = useState<AnalysisDetail | null>(null)
  const [fileText, setFileText] = useState<string>("")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const [chainId, setChainId] = useState("all")
  const [showLigands, setShowLigands] = useState(true)
  const [showWaters, setShowWaters] = useState(false)
  const [highlight, setHighlight] = useState<{ chainId: string; resseq: number; missing: boolean } | null>(null)

  const load = useCallback(
    (signal?: AbortSignal) => {
      setLoading(true)
      setError(null)
      Promise.all([
        apiGet<StructureResponse>(`/api/structures/${structureId}`, signal),
        apiGet<AnalysisListResponse>("/api/analyses", signal),
        fetch(`/api/structures/${structureId}/file`, { signal }).then(async (response) => {
          if (!response.ok) {
            throw new Error("The structure file could not be loaded for the viewer.")
          }
          return response.text()
        }),
      ])
        .then(async ([structureBody, analysesBody, text]) => {
          setStructure(structureBody)
          setFileText(text)
          const forStructure = analysesBody.analyses.filter((item) => item.structure_id === structureId)
          const match =
            forStructure.find((item) => item.kind === "structure_overview" && item.status === "succeeded") ??
            forStructure[0]
          if (!match) {
            setAnalysis(null)
            return
          }
          const detail = await apiGet<AnalysisDetail>(`/api/analyses/${match.id}`, signal)
          setAnalysis(detail)
        })
        .catch((caught: unknown) => {
          if (signal?.aborted) {
            return
          }
          setError(caught instanceof Error ? caught.message : "The structure could not be loaded.")
        })
        .finally(() => {
          if (!signal?.aborted) {
            setLoading(false)
          }
        })
    },
    [structureId],
  )

  useEffect(() => {
    const controller = new AbortController()
    load(controller.signal)
    return () => controller.abort()
  }, [load])

  async function runOverview() {
    setRunning(true)
    setError(null)
    try {
      const detail = await apiPost<AnalysisDetail>(`/api/structures/${structureId}/analyses`, {
        kind: "structure_overview",
      })
      setAnalysis(detail)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The analysis failed.")
      load()
    } finally {
      setRunning(false)
    }
  }

  const result = analysis?.result ?? null
  const chains = result ? asChainRows(findMeasurement(result, "chains")?.value) : []
  const missing = result ? asResidueRefs(findMeasurement(result, "missing_residues")?.value) : []
  const incomplete = result ? asResidueRefs(findMeasurement(result, "incomplete_residues")?.value) : []
  const ligands = useMemo(() => ligandNames(result ? findMeasurement(result, "ligand_inventory")?.value : null), [result])
  const distances = result ? chainBreaks(findMeasurement(result, "ca_distances")?.value) : []
  const rg = result ? findMeasurement(result, "radius_of_gyration_ca")?.value : null

  return (
    <div className="space-y-6">
      <p>
        <Link to="/proteins" className="text-sm underline">
          All structures
        </Link>
      </p>
      {loading ? (
        <p role="status" aria-live="polite">
          Loading structure…
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2">
          {error}
        </p>
      ) : null}
      {structure ? (
        <header className="space-y-1">
          <h1 className="text-3xl">{structure.display_filename}</h1>
          <p className="text-muted-foreground text-sm">
            {structure.format} · {structure.size_bytes} bytes · sha256{" "}
            <span className="mono">{structure.sha256.slice(0, 12)}</span>
          </p>
          {typeof structure.metadata.title === "string" ? <p>{structure.metadata.title}</p> : null}
        </header>
      ) : null}

      {analysis == null && !loading ? (
        <div className="space-y-2">
          <p>This structure has no saved overview yet.</p>
          <Button type="button" onClick={() => void runOverview()} disabled={running}>
            {running ? "Running structure overview…" : "Run structure overview"}
          </Button>
        </div>
      ) : null}

      {analysis && analysis.status === "failed" ? (
        <div className="space-y-2" role="alert">
          <p>The overview failed. {analysis.error?.message}</p>
          <Button type="button" onClick={() => void runOverview()} disabled={running}>
            {running ? "Running structure overview…" : "Run structure overview again"}
          </Button>
        </div>
      ) : null}

      {result && fileText && structure ? (
        <>
          <section className="space-y-3" aria-label="3D viewer">
            <div className="flex flex-wrap items-end gap-3">
              <label className="text-sm">
                Chain
                <select
                  data-testid="chain-select"
                  className="mt-1 block rounded-md border bg-card px-2 py-1"
                  value={chainId}
                  onChange={(event) => setChainId(event.target.value)}
                >
                  <option value="all">All chains</option>
                  {chains.map((chain) => (
                    <option key={chain.chain_id} value={chain.chain_id}>
                      Chain {chain.chain_id}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={showLigands} onChange={(event) => setShowLigands(event.target.checked)} />
                Ligands
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={showWaters} onChange={(event) => setShowWaters(event.target.checked)} />
                Waters
              </label>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setChainId("all")
                  setShowLigands(true)
                  setShowWaters(false)
                  setHighlight(null)
                }}
              >
                Reset view
              </Button>
            </div>
            <StructureViewer
              text={fileText}
              format={structure.format}
              chainId={chainId}
              showLigands={showLigands}
              showWaters={showWaters}
              ligandResnames={ligands}
              highlight={highlight}
            />
            {highlight?.missing ? (
              <p className="text-sm">
                Residue {highlight.chainId}:{highlight.resseq} has no coordinates in the file, so the viewer cannot
                draw it.
              </p>
            ) : null}
          </section>

          {result ? (
            <ProteinPanels
              structureId={structureId}
              result={result}
              onHighlight={(residue) => setHighlight({ chainId: residue.chainId, resseq: residue.resseq, missing: false })}
            />
          ) : null}

          <section className="flex flex-wrap gap-2" aria-label="Report downloads">
            {(["html", "md", "json"] as const).map((format) => (
              <a
                key={format}
                className={buttonVariants({ variant: "outline" })}
                href={`/api/analyses/${analysis?.id}/report?format=${format}`}
              >
                Download {format.toUpperCase()}
              </a>
            ))}
          </section>

          <Card>
            <CardHeader>
              <CardTitle>Chains</CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left">
                    <th>Chain</th>
                    <th>Type</th>
                    <th>Observed residues</th>
                    <th>SEQRES</th>
                    <th>Waters</th>
                    <th>Hetero residues</th>
                  </tr>
                </thead>
                <tbody>
                  {chains.map((chain) => (
                    <tr key={chain.chain_id} className="border-t">
                      <td className="py-1">{chain.chain_id}</td>
                      <td>{chain.polymer_type}</td>
                      <td className="mono">{chain.observed_polymer_residue_count}</td>
                      <td className="mono">{chain.seqres_residue_count ?? "null"}</td>
                      <td className="mono">{chain.water_residue_count}</td>
                      <td className="mono">{chain.hetero_residue_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Composition</CardTitle>
            </CardHeader>
            <CardContent>
              <CompositionChart value={findMeasurement(result, "amino_acid_composition")?.value} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Measurements</CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left">
                    <th>Name</th>
                    <th>Value</th>
                    <th>Unit</th>
                    <th>Origin</th>
                  </tr>
                </thead>
                <tbody>
                  {SCALAR_MEASUREMENTS.map((name) => {
                    const measurement = findMeasurement(result, name)
                    if (!measurement) {
                      return null
                    }
                    return (
                      <tr key={name} className="border-t">
                        <td className="py-1 pr-3">{measurement.name}</td>
                        <td className="mono pr-3">{displayValue(measurement.value)}</td>
                        <td className="pr-3">{displayValue(measurement.unit)}</td>
                        <td>
                          <OriginBadge origin={measurement.origin} />
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              <RadiusBlock value={rg} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Missing data</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {result.warnings.length === 0 ? <p>No warnings were returned.</p> : null}
              <ul className="list-disc space-y-1 pl-5 text-sm">
                {result.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
              <ResidueTable
                title="Missing residues"
                rows={missing}
                onSelect={(row) => setHighlight({ chainId: row.chain_id, resseq: row.resseq, missing: true })}
              />
              <ResidueTable
                title="Incomplete residues"
                rows={incomplete}
                onSelect={(row) => setHighlight({ chainId: row.chain_id, resseq: row.resseq, missing: false })}
              />
              {distances.length === 0 ? (
                <p className="text-sm">No C-alpha pairs were flagged as chain breaks.</p>
              ) : (
                <div>
                  <h3 className="mb-2 text-base">Chain breaks</h3>
                  <ul className="text-sm">
                    {distances.map((item) => (
                      <li key={`${item.from}-${item.to}`}>
                        {item.from} to {item.to}: {item.distance} Å
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Limitations</CardTitle>
            </CardHeader>
            <CardContent>
              {result.limitations.length === 0 ? (
                <p>This result did not include limitation text.</p>
              ) : (
                <ul className="list-disc space-y-2 pl-5 text-sm">
                  {result.limitations.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  )
}

function ResidueTable({
  title,
  rows,
  onSelect,
}: {
  title: string
  rows: ReturnType<typeof asResidueRefs>
  onSelect: (row: ReturnType<typeof asResidueRefs>[number]) => void
}) {
  return (
    <div>
      <h3 className="mb-2 text-base">{title}</h3>
      {rows.length === 0 ? (
        <p className="text-sm">None reported.</p>
      ) : (
        <div className="max-h-80 overflow-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left">
                <th>Residue</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={`${row.chain_id}-${row.resseq}-${row.icode}-${row.resname}`} className="border-t">
                  <td className="py-1">
                    <button type="button" className="underline" onClick={() => onSelect(row)}>
                      {row.chain_id}:{row.resseq}
                      {row.icode} {row.resname}
                    </button>
                  </td>
                  <td>{row.missing_atoms?.join(", ") || row.reason || row.source || ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function RadiusBlock({ value }: { value: unknown }) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null
  }
  const record = value as {
    overall_angstrom?: number | null
    ca_count?: number
    per_chain?: Array<{ chain_id: string; radius_of_gyration_angstrom: number | null; ca_count: number }>
  }
  return (
    <div className="mt-4 space-y-1 text-sm">
      <p>
        Radius of gyration (C-alpha, unweighted):{" "}
        <span className="mono">{displayValue(record.overall_angstrom)} Å</span>{" "}
        <OriginBadge origin="calculated" />
      </p>
      <p className="text-muted-foreground">C-alpha atoms used: {displayValue(record.ca_count)}</p>
      <ul>
        {(record.per_chain ?? []).map((chain) => (
          <li key={chain.chain_id}>
            Chain {chain.chain_id}: {displayValue(chain.radius_of_gyration_angstrom)} Å ({chain.ca_count} atoms)
          </li>
        ))}
      </ul>
    </div>
  )
}

function ligandNames(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value
    .map((item) => (item && typeof item === "object" && "resname" in item ? String(item.resname) : ""))
    .filter(Boolean)
}

function chainBreaks(value: unknown): Array<{ from: string; to: string; distance: string }> {
  if (!Array.isArray(value)) {
    return []
  }
  const breaks: Array<{ from: string; to: string; distance: string }> = []
  for (const item of value) {
    if (!item || typeof item !== "object" || !("chain_break" in item) || item.chain_break !== true) {
      continue
    }
    const record = item as {
      chain_id?: string
      from_residue?: { resseq?: number }
      to_residue?: { resseq?: number }
      distance_angstrom?: number
    }
    breaks.push({
      from: `${record.chain_id ?? "?"}:${record.from_residue?.resseq ?? "?"}`,
      to: `${record.chain_id ?? "?"}:${record.to_residue?.resseq ?? "?"}`,
      distance: displayValue(record.distance_angstrom),
    })
  }
  return breaks
}
