import { useEffect, useState } from "react"

import { apiGet, apiPost } from "@/api/client"
import { StructureViewer } from "@/components/StructureViewer"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { AnalysisDetail, HealthResponse, JobResponse, StructureListResponse } from "@/types"

const MINIMIZATION = "energy minimization, not molecular dynamics"
const DYNAMICS = "short simulation: no evidence of long-term stability, binding or efficacy"

export function SimulationCenter() {
  const [structures, setStructures] = useState<StructureListResponse["structures"]>([])
  const [structureId, setStructureId] = useState("")
  const [platforms, setPlatforms] = useState<string[]>([])
  const [openmm, setOpenmm] = useState<string>("")
  const [error, setError] = useState<string | null>(null)
  const [job, setJob] = useState<JobResponse | null>(null)
  const [result, setResult] = useState<AnalysisDetail | null>(null)
  const [frame, setFrame] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([
      apiGet<StructureListResponse>("/api/structures", controller.signal),
      apiGet<HealthResponse>("/api/health", controller.signal),
    ])
      .then(([stored, health]) => {
        setStructures(stored.structures)
        setPlatforms(health.openmm_platforms ?? [])
        const tool = health.capabilities.openmm
        setOpenmm(tool?.available ? `OpenMM ${tool.version ?? ""}` : `Unavailable: ${tool?.reason ?? "not reported"}`)
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) {
          setError(caught instanceof Error ? caught.message : "Simulation status could not be loaded.")
        }
      })
    return () => controller.abort()
  }, [])

  async function start(mode: "minimization" | "dynamics") {
    setError(null)
    setResult(null)
    try {
      const created = await apiPost<JobResponse>("/api/simulation", { structure_id: structureId, mode, seed: 1 })
      setJob(created)
      let current = created
      while (current.status === "pending" || current.status === "running") {
        await new Promise((resolve) => setTimeout(resolve, 500))
        current = await apiGet<JobResponse>(`/api/jobs/${created.id}`)
        setJob(current)
      }
      if (current.analysis_id) {
        const analysis = await apiGet<AnalysisDetail>(`/api/analyses/${current.analysis_id}`)
        setResult(analysis)
        setFrame(0)
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The simulation could not be started.")
    }
  }

  const frames = (result?.result?.details?.frames as Array<{ step: number; pdb?: string; potential_energy_kj_mol?: number }> | undefined) ?? []
  const selected = frames[frame]

  return (
    <div className="space-y-4">
      <h1 className="text-3xl">Simulation Center</h1>
      <p className="text-sm">{MINIMIZATION}</p>
      <p className="text-sm">{DYNAMICS}</p>
      <p className="text-sm">{openmm || "Loading OpenMM status…"}</p>
      <p className="text-sm">Platforms reported by this process: {platforms.length ? platforms.join(", ") : "none"}</p>
      {error ? <p role="alert">{error}</p> : null}
      {structures.length === 0 ? <p>No structures are stored.</p> : null}
      <label className="block text-sm" htmlFor="simulation-structure">
        Structure
      </label>
      <select
        id="simulation-structure"
        className="rounded border px-2 py-1 text-sm"
        value={structureId}
        onChange={(event) => setStructureId(event.target.value)}
      >
        <option value="">Choose a stored structure</option>
        {structures.map((structure) => (
          <option key={structure.id} value={structure.id}>
            {structure.display_filename}
          </option>
        ))}
      </select>
      <div className="flex flex-wrap gap-2">
        <Button type="button" disabled={!structureId || openmm.startsWith("Unavailable")} onClick={() => void start("minimization")}>
          Minimize
        </Button>
        <Button type="button" disabled={!structureId || openmm.startsWith("Unavailable")} onClick={() => void start("dynamics")}>
          Short dynamics
        </Button>
      </div>
      {job ? (
        <p role="status">
          Job {job.status}
          {job.progress == null ? "" : ` · progress ${job.progress}`}
        </p>
      ) : null}
      {result?.result?.limitations.map((item) => (
        <p key={item} className="text-sm">
          {item}
        </p>
      ))}
      {result?.result?.measurements.map((item) => (
        <p key={item.name} className="text-sm">
          {item.name}: {String(item.value)} {item.unit ?? ""}
        </p>
      ))}
      {frames.length > 0 ? (
        <div className="space-y-2">
          <label className="block text-sm" htmlFor="frame-slider">
            Frame {selected?.step ?? ""}
          </label>
          <Input
            id="frame-slider"
            type="range"
            min={0}
            max={frames.length - 1}
            value={frame}
            onChange={(event) => setFrame(Number(event.target.value))}
          />
          {selected?.pdb ? (
            <StructureViewer
              text={selected.pdb}
              format="pdb"
              chainId=""
              showLigands={false}
              showWaters={false}
              ligandResnames={[]}
              highlight={null}
            />
          ) : null}
        </div>
      ) : null}
    </div>
  )
}