import { useCallback, useEffect, useState, type FormEvent } from "react"

import { apiGet, apiPost } from "@/api/client"
import { OriginBadge } from "@/components/OriginBadge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import type { AnalysisDetail, Measurement } from "@/types"

type CompoundResponse = {
  id: string
  input_smiles: string
  canonical_smiles: string
  inchikey: string
  created_at: string
  source: Record<string, unknown> | null
  analysis: AnalysisDetail
  already_stored: boolean
}

type CompoundList = { compounds: CompoundResponse[] }

export function CompoundExplorer() {
  const [smiles, setSmiles] = useState("")
  const [name, setName] = useState("")
  const [compounds, setCompounds] = useState<CompoundResponse[]>([])
  const [selected, setSelected] = useState<CompoundResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [compareNote, setCompareNote] = useState<string | null>(null)

  const load = useCallback((signal?: AbortSignal) => {
    setLoading(true)
    apiGet<CompoundList>("/api/compounds", signal)
      .then((body) => setCompounds(body.compounds))
      .catch((caught: unknown) => {
        if (!signal?.aborted) setError(caught instanceof Error ? caught.message : "Compounds could not be loaded.")
      })
      .finally(() => {
        if (!signal?.aborted) setLoading(false)
      })
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    load(controller.signal)
    return () => controller.abort()
  }, [load])

  async function submitSmiles(event: FormEvent) {
    event.preventDefault()
    setError(null)
    try {
      const created = await apiPost<CompoundResponse>("/api/compounds", { smiles })
      setSelected(created)
      load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The SMILES was rejected.")
    }
  }

  async function importName(event: FormEvent) {
    event.preventDefault()
    setError(null)
    try {
      const created = await apiPost<CompoundResponse>("/api/compounds/import/pubchem", {
        query: name,
        query_type: "name",
      })
      setSelected(created)
      load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "PubChem import failed.")
    }
  }

  async function compareFirstTwo() {
    if (compounds.length < 2) return
    setError(null)
    const body = await apiPost<{ activities: Array<{ status: string; reason?: string }> }>("/api/compounds/compare", {
      compound_ids: compounds.slice(0, 2).map((item) => item.id),
    })
    const note = body.activities[0]
    setCompareNote(note ? `${note.status}${note.reason ? `: ${note.reason}` : ""}` : "No activity comparison was returned.")
  }

  const measurements = selected?.analysis.result?.measurements ?? []

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-3xl">Compound Explorer</h1>
        <p className="text-muted-foreground max-w-2xl text-sm">
          RDKit sanitizes the SMILES and calculates named descriptors. Retrieved PubChem fields stay separate from
          those calculations. Descriptors are not a drug-likeness or safety label.
        </p>
      </header>
      {loading ? <p role="status">Loading compounds…</p> : null}
      {error ? (
        <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2">
          {error}
        </p>
      ) : null}
      <div className="grid gap-4 lg:grid-cols-2">
        <form className="space-y-2 rounded-lg border bg-card p-3" onSubmit={(event) => void submitSmiles(event)}>
          <label htmlFor="smiles" className="text-sm font-medium">
            SMILES
          </label>
          <Input id="smiles" value={smiles} onChange={(event) => setSmiles(event.target.value)} />
          <Button type="submit">Validate and store</Button>
        </form>
        <form className="space-y-2 rounded-lg border bg-card p-3" onSubmit={(event) => void importName(event)}>
          <label htmlFor="pubchem-name" className="text-sm font-medium">
            PubChem name
          </label>
          <Input id="pubchem-name" value={name} onChange={(event) => setName(event.target.value)} />
          <Button type="submit" variant="outline">
            Retrieve from PubChem
          </Button>
        </form>
      </div>
      {compounds.length === 0 ? <p>No compounds have been stored.</p> : null}
      <ul className="space-y-1 text-sm">
        {compounds.map((item) => (
          <li key={item.id}>
            <button type="button" className="underline" onClick={() => setSelected(item)}>
              {item.canonical_smiles}
            </button>
          </li>
        ))}
      </ul>
      {compounds.length >= 2 ? (
        <div className="space-y-2">
          <Button type="button" variant="outline" onClick={() => void compareFirstTwo()}>
            Compare the first two stored compounds
          </Button>
          {compareNote ? <p className="text-sm">{compareNote}</p> : null}
        </div>
      ) : null}
      {selected ? (
        <Card>
          <CardHeader>
            <CardTitle className="font-mono text-base">{selected.canonical_smiles}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <img
              alt={`Depiction of ${selected.canonical_smiles}`}
              src={`/api/compounds/${selected.id}/depiction`}
              className="max-w-full bg-white"
            />
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
                {measurements.map((item: Measurement) => (
                  <tr key={item.name} className="border-t">
                    <td className="py-1 pr-2">{item.name}</td>
                    <td className="mono pr-2">{formatMeasurement(item.value)}</td>
                    <td className="pr-2">{item.unit ?? "null"}</td>
                    <td>
                      <OriginBadge origin={item.origin} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {selected.analysis.id ? (
              <a className="underline" href={`/api/analyses/${selected.analysis.id}/report?format=html`}>
                Download HTML report
              </a>
            ) : null}
            {selected.analysis.result ? (
              <ul className="list-disc pl-5 text-sm">
                {selected.analysis.result.limitations.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : null}
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}

function formatMeasurement(value: unknown): string {
  if (value === null || value === undefined) return "null"
  if (typeof value === "number") return String(value)
  if (typeof value === "string") return value
  return JSON.stringify(value)
}
