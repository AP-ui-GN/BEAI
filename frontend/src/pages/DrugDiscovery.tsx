import { useEffect, useState, type FormEvent } from "react"

import { apiGet, apiPost } from "@/api/client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { AnalysisDetail, HealthResponse, JobResponse } from "@/types"

export function DrugDiscovery() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [structureId, setStructureId] = useState("")
  const [smiles, setSmiles] = useState("")
  const [resname, setResname] = useState("")
  const [job, setJob] = useState<JobResponse | null>(null)
  const [score, setScore] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    apiGet<HealthResponse>("/api/health", controller.signal)
      .then(setHealth)
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) setError(caught instanceof Error ? caught.message : "Health failed.")
      })
    return () => controller.abort()
  }, [])

  const HYPOTHESIS = "computational hypothesis: unsynthesized, unvalidated"
  const [references, setReferences] = useState("CC(=O)Oc1ccccc1C(=O)O\nCCOC(=O)c1ccc(N)cc1")
  const [generated, setGenerated] = useState<AnalysisDetail | null>(null)
  const vina = health?.capabilities.vina
  const meeko = health?.capabilities.meeko
  const ready = Boolean(vina?.available && meeko?.available)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setScore(null)
    const created = await apiPost<JobResponse>("/api/docking", {
      structure_id: structureId,
      ligand_smiles: smiles,
      ligand_resname: resname || null,
      exhaustiveness: 8,
      num_modes: 3,
      seed: 1,
    })
    let current = created
    for (let attempt = 0; attempt < 80 && !["succeeded", "failed", "cancelled"].includes(current.status); attempt += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, 500))
      current = await apiGet<JobResponse>(`/api/jobs/${created.id}`)
    }
    setJob(current)
    if (current.status === "succeeded" && current.analysis_id) {
      const detail = await apiGet<AnalysisDetail>(`/api/analyses/${current.analysis_id}`)
      const measurement = detail.result?.measurements.find((item) => item.name === "docking_score")
      setScore(measurement ? `${measurement.value} ${measurement.unit ?? ""}` : null)
    } else if (current.error) {
      setError(current.error.message)
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-3xl">Drug Discovery</h1>
      <p className="text-muted-foreground max-w-2xl text-sm">
        A docking score is not a binding affinity and does not show biological efficacy. Protonation states and
        tautomers are not enumerated.
      </p>
      {!health ? <p role="status">Checking docking tools…</p> : null}
      {health && !ready ? (
        <p>
          Unavailable: {vina?.available ? "" : vina?.reason} {meeko?.available ? "" : meeko?.reason}
        </p>
      ) : null}
      {ready ? (
        <form className="max-w-xl space-y-2" onSubmit={(event) => void submit(event)}>
          <label className="block text-sm" htmlFor="dock-structure">
            Structure id
          </label>
          <Input id="dock-structure" value={structureId} onChange={(event) => setStructureId(event.target.value)} />
          <label className="block text-sm" htmlFor="dock-smiles">
            Ligand SMILES
          </label>
          <Input id="dock-smiles" value={smiles} onChange={(event) => setSmiles(event.target.value)} />
          <label className="block text-sm" htmlFor="dock-resname">
            Co-crystallized residue name for the box
          </label>
          <Input id="dock-resname" value={resname} onChange={(event) => setResname(event.target.value)} />
          <Button type="submit">Dock</Button>
        </form>
      ) : null}
      {job ? (
        <p role="status" aria-live="polite">
          {job.status}
          {job.progress === null ? "" : ` · progress ${job.progress}`}
          {score ? ` · docking score ${score}, not an experimental affinity` : ""}
        </p>
      ) : null}
      {error ? <p role="alert">{error}</p> : null}
      <section className="max-w-xl space-y-2">
        <h2 className="text-xl">Hypothesis generation</h2>
        <p className="text-sm">{HYPOTHESIS}</p>
        <fieldset className="space-y-1 text-sm">
          <legend>Liability filters</legend>
          <label className="block">
            <input type="checkbox" checked disabled /> PAINS
          </label>
          <label className="block">
            <input type="checkbox" checked disabled /> Brenk
          </label>
          <label className="block">
            <input type="checkbox" checked disabled /> NIH
          </label>
        </fieldset>
        <label className="block text-sm" htmlFor="gen-references">
          Reference SMILES, one per line
        </label>
        <textarea
          id="gen-references"
          className="min-h-20 w-full rounded border px-2 py-1 text-sm"
          value={references}
          onChange={(event) => setReferences(event.target.value)}
        />
        <Button
          type="button"
          onClick={() => {
            setError(null)
            void apiPost<AnalysisDetail>("/api/generation", {
              references: references.split("\n").map((line) => line.trim()).filter(Boolean),
              objectives: [{ kind: "property_range", property: "MolWt", minimum: 50, maximum: 800 }],
              seed: 1,
              count: 5,
            })
              .then(setGenerated)
              .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "Generation failed."))
          }}
        >
          Recombine fragments
        </Button>
        {generated?.result?.details?.outputs ? (
          <ul className="space-y-1 text-sm">
            {(generated.result.details.outputs as Array<{ smiles: string; label: string }>).map((item) => (
              <li key={item.smiles}>
                {item.smiles} — {item.label}
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    </div>
  )
}
