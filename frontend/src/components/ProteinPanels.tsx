import { useState } from "react"

import { apiGet, apiPost } from "@/api/client"
import { OriginBadge } from "@/components/OriginBadge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { findMeasurement } from "@/lib/measurements"
import type { AnalysisDetail, AnalysisResult, JobResponse, StructureListResponse } from "@/types"

type ResiduePoint = {
  chain_id?: string
  resseq?: number
  icode?: string
  phi_degrees?: number | null
  psi_degrees?: number | null
  code?: string
  sasa_angstrom2?: number
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null
}

function asRows(value: unknown): ResiduePoint[] {
  return Array.isArray(value) ? (value as ResiduePoint[]) : []
}

export function ProteinPanels({
  structureId,
  result,
  onHighlight,
}: {
  structureId: string
  result: AnalysisResult
  onHighlight: (residue: { chainId: string; resseq: number }) => void
}) {
  const details = result.details ?? {}
  const ss = asRecord(details.secondary_structure)
  const sasa = asRecord(details.sasa)
  const contacts = asRecord(details.contacts)
  const ramachandran = asRows(asRecord(details.ramachandran)?.residues)
  const codes = asRows(ss?.per_residue)
  const areas = asRows(sasa?.per_residue).filter((row) => typeof row.sasa_angstrom2 === "number")
  const pairs = Array.isArray(contacts?.pairs) ? contacts.pairs.length : 0
  const disagreement = findMeasurement(result, "secondary_structure_disagreement")
  const sasaTotal = findMeasurement(result, "sasa_total")
  const hbond = findMeasurement(result, "hydrogen_bond_estimate_count")

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Secondary structure</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {codes.length === 0 ? <p>No computed secondary-structure codes were returned.</p> : <SsTrack rows={codes} />}
          {disagreement ? (
            <p className="text-sm">
              File versus computed counts are in the measurement table.{" "}
              <OriginBadge origin={disagreement.origin} />
            </p>
          ) : null}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Ramachandran</CardTitle>
        </CardHeader>
        <CardContent>
          {ramachandran.length === 0 ? (
            <p>No phi or psi angles were returned.</p>
          ) : (
            <Ramachandran rows={ramachandran} onSelect={onHighlight} />
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Solvent-accessible surface</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {sasaTotal ? (
            <p className="text-sm">
              Total {String(sasaTotal.value)} {sasaTotal.unit ?? ""} <OriginBadge origin={sasaTotal.origin} />
            </p>
          ) : (
            <p>No SASA total was returned.</p>
          )}
          {areas.length === 0 ? null : <SasaChart rows={areas} />}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Contacts and hydrogen-bond estimates</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p>
            {pairs} residue pairs within {String(contacts?.cutoff_angstrom ?? "the recorded")} Å. Atom set:{" "}
            {String(contacts?.atom_selection ?? "not recorded")}.
          </p>
          {hbond ? (
            <p>
              {String(hbond.value)} hydrogen-bond estimates. <OriginBadge origin={hbond.origin} />
            </p>
          ) : null}
          <ContactMap pairs={Array.isArray(contacts?.pairs) ? (contacts.pairs as ContactPair[]) : []} />
        </CardContent>
      </Card>
      <PocketPanel structureId={structureId} onHighlight={onHighlight} />
      <ComparePanel structureId={structureId} />
    </div>
  )
}

function SsTrack({ rows }: { rows: ResiduePoint[] }) {
  return (
    <div className="flex flex-wrap gap-px" aria-label="Secondary structure track">
      {rows.map((row) => (
        <span
          key={`${row.chain_id}-${row.resseq}-${row.icode}`}
          title={`${row.chain_id ?? ""} ${row.resseq ?? ""} ${row.code ?? ""}`}
          className="inline-block h-4 w-2"
          style={{ background: ssColor(row.code) }}
        />
      ))}
    </div>
  )
}

function ssColor(code: string | undefined): string {
  if (code === "H" || code === "G" || code === "I") return "#c45c26"
  if (code === "E" || code === "B") return "#2f6f4e"
  return "#d9d3c7"
}

function Ramachandran({
  rows,
  onSelect,
}: {
  rows: ResiduePoint[]
  onSelect: (residue: { chainId: string; resseq: number }) => void
}) {
  const width = 280
  const height = 280
  const defined = rows.filter((row) => typeof row.phi_degrees === "number" && typeof row.psi_degrees === "number")
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-64 w-full max-w-sm bg-[#f7f4ee]" role="img" aria-label="Ramachandran plot">
      <title>Phi and psi from the analysis</title>
      {defined.map((row) => {
        const x = ((Number(row.phi_degrees) + 180) / 360) * width
        const y = ((180 - Number(row.psi_degrees)) / 360) * height
        return (
          <circle
            key={`${row.chain_id}-${row.resseq}-${row.icode}`}
            cx={x}
            cy={y}
            r={3}
            fill="#9a4e32"
            onClick={() => {
              if (row.chain_id && row.resseq) onSelect({ chainId: row.chain_id, resseq: row.resseq })
            }}
          />
        )
      })}
    </svg>
  )
}

function SasaChart({ rows }: { rows: ResiduePoint[] }) {
  const values = rows.map((row) => Number(row.sasa_angstrom2))
  const max = Math.max(...values, 1)
  const width = Math.max(rows.length, 1)
  return (
    <svg viewBox={`0 0 ${width} 40`} className="h-16 w-full" role="img" aria-label="Per-residue SASA">
      {values.map((value, index) => (
        <rect key={index} x={index} y={40 - (value / max) * 40} width={1} height={(value / max) * 40} fill="#3d6b8c" />
      ))}
    </svg>
  )
}

type ContactPair = { left?: { resseq?: number }; right?: { resseq?: number } }

function ContactMap({ pairs }: { pairs: ContactPair[] }) {
  if (pairs.length === 0) return <p>No contact pairs were returned.</p>
  const indexes = pairs.flatMap((pair) => [pair.left?.resseq, pair.right?.resseq]).filter((value): value is number => typeof value === "number")
  const min = Math.min(...indexes)
  const max = Math.max(...indexes)
  const span = Math.max(max - min + 1, 1)
  return (
    <svg viewBox={`0 0 ${span} ${span}`} className="h-48 w-full max-w-sm bg-[#f7f4ee]" role="img" aria-label="Contact map">
      {pairs.map((pair, index) =>
        typeof pair.left?.resseq === "number" && typeof pair.right?.resseq === "number" ? (
          <rect
            key={index}
            x={pair.left.resseq - min}
            y={pair.right.resseq - min}
            width={1}
            height={1}
            fill="#243042"
          />
        ) : null,
      )}
    </svg>
  )
}

function PocketPanel({
  structureId,
  onHighlight,
}: {
  structureId: string
  onHighlight: (residue: { chainId: string; resseq: number }) => void
}) {
  const [job, setJob] = useState<JobResponse | null>(null)
  const [analysis, setAnalysis] = useState<AnalysisDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function run() {
    setBusy(true)
    setError(null)
    try {
      const created = await apiPost<JobResponse>(`/api/structures/${structureId}/pockets`, {})
      let current = created
      for (let attempt = 0; attempt < 60 && !["succeeded", "failed", "cancelled"].includes(current.status); attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 500))
        current = await apiGet<JobResponse>(`/api/jobs/${created.id}`)
      }
      setJob(current)
      if (current.status === "succeeded" && current.analysis_id) {
        setAnalysis(await apiGet<AnalysisDetail>(`/api/analyses/${current.analysis_id}`))
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Pocket detection failed.")
    } finally {
      setBusy(false)
    }
  }

  async function cancel() {
    if (!job) return
    const updated = await apiPost<JobResponse>(`/api/jobs/${job.id}/cancel`, {})
    setJob(updated)
  }

  const pockets = asRows(asRecord(analysis?.result?.details)?.pockets)
  const label = analysis?.result ? findMeasurement(analysis.result, "pocket_method_label") : null

  return (
    <Card>
      <CardHeader>
        <CardTitle>Pockets</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap gap-2">
          <Button type="button" onClick={() => void run()} disabled={busy}>
            {busy ? "Detecting pockets…" : "Detect pockets"}
          </Button>
          {job && (job.status === "pending" || job.status === "running") ? (
            <Button type="button" variant="outline" onClick={() => void cancel()}>
              Cancel
            </Button>
          ) : null}
        </div>
        {job ? (
          <p role="status" aria-live="polite" className="text-sm">
            {job.status}
            {job.progress === null ? "" : ` · progress ${job.progress}`}
          </p>
        ) : (
          <p className="text-sm">No pocket job has been started for this view.</p>
        )}
        {error ? <p role="alert">{error}</p> : null}
        {label ? <p className="text-sm">{String(label.value)}</p> : null}
        {pockets.length === 0 ? null : (
          <ul className="space-y-2 text-sm">
            {pockets.slice(0, 5).map((pocket) => {
              const record = pocket as ResiduePoint & { rank?: number; volume_angstrom3?: number; lining_residues?: ResiduePoint[] }
              return (
                <li key={record.rank}>
                  Rank {record.rank}: {record.volume_angstrom3} Å³
                  <div className="mt-1 flex flex-wrap gap-1">
                    {(record.lining_residues ?? []).slice(0, 12).map((residue) => (
                      <button
                        key={`${residue.chain_id}-${residue.resseq}`}
                        type="button"
                        className="underline"
                        onClick={() => {
                          if (residue.chain_id && residue.resseq) {
                            onHighlight({ chainId: residue.chain_id, resseq: residue.resseq })
                          }
                        }}
                      >
                        {residue.chain_id}:{residue.resseq}
                      </button>
                    ))}
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

function ComparePanel({ structureId }: { structureId: string }) {
  const [structures, setStructures] = useState<StructureListResponse["structures"]>([])
  const [otherId, setOtherId] = useState(structureId)
  const [chainId, setChainId] = useState("A")
  const [otherChain, setOtherChain] = useState("A")
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function loadStructures() {
    const body = await apiGet<StructureListResponse>("/api/structures")
    setStructures(body.structures)
  }

  async function compare() {
    setBusy(true)
    setError(null)
    try {
      if (structures.length === 0) await loadStructures()
      const created = await apiPost<JobResponse>("/api/structures/compare", {
        structure_id: structureId,
        chain_id: chainId,
        other_structure_id: otherId,
        other_chain_id: otherChain,
      })
      let current = created
      for (let attempt = 0; attempt < 40 && !["succeeded", "failed", "cancelled"].includes(current.status); attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 300))
        current = await apiGet<JobResponse>(`/api/jobs/${created.id}`)
      }
      if (current.status !== "succeeded" || !current.analysis_id) {
        throw new Error(current.error?.message ?? `Comparison ${current.status}.`)
      }
      const detail = await apiGet<AnalysisDetail>(`/api/analyses/${current.analysis_id}`)
      setResult(detail.result)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Comparison failed.")
    } finally {
      setBusy(false)
    }
  }

  const rmsd = result ? findMeasurement(result, "rmsd_ca") : null
  const superposed = asRecord(result?.details)?.superposed_pdb

  return (
    <Card>
      <CardHeader>
        <CardTitle>Structure comparison</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" onClick={() => void loadStructures()}>
            Load structures
          </Button>
          <label className="text-sm">
            Other structure
            <select className="ml-2 rounded border px-2 py-1" value={otherId} onChange={(event) => setOtherId(event.target.value)}>
              <option value={structureId}>This structure</option>
              {structures.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.display_filename}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            Reference chain
            <input className="ml-2 w-12 rounded border px-2 py-1" value={chainId} onChange={(event) => setChainId(event.target.value)} />
          </label>
          <label className="text-sm">
            Mobile chain
            <input className="ml-2 w-12 rounded border px-2 py-1" value={otherChain} onChange={(event) => setOtherChain(event.target.value)} />
          </label>
          <Button type="button" onClick={() => void compare()} disabled={busy}>
            {busy ? "Comparing…" : "Compare chains"}
          </Button>
        </div>
        {error ? <p role="alert">{error}</p> : null}
        {rmsd ? (
          <p className="text-sm">
            C-alpha RMSD {String(rmsd.value)} {rmsd.unit} <OriginBadge origin={rmsd.origin} />
          </p>
        ) : null}
        {typeof superposed === "string" ? (
          <p className="text-sm">A superposed PDB for the mobile chain is in the analysis details.</p>
        ) : null}
      </CardContent>
    </Card>
  )
}
