import { useEffect, useState } from "react"
import { Link } from "react-router-dom"

import { apiGet, apiPost } from "@/api/client"
import { Button, buttonVariants } from "@/components/ui/button"
import type { AnalysisListResponse } from "@/types"

export function ResearchLibrary() {
  const [analyses, setAnalyses] = useState<AnalysisListResponse["analyses"]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [workflow, setWorkflow] = useState(
    '{\n  "name": "example",\n  "steps": [\n    {"id": "compound", "service": "compound_descriptors", "parameters": {"smiles": "CCO"}}\n  ]\n}',
  )
  const [workflowNote, setWorkflowNote] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    apiGet<AnalysisListResponse>("/api/analyses", controller.signal)
      .then((body) => setAnalyses(body.analyses))
      .catch((caught: unknown) => {
        if (controller.signal.aborted) {
          return
        }
        setError(caught instanceof Error ? caught.message : "Saved analyses could not be loaded.")
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      })
    return () => controller.abort()
  }, [])

  return (
    <div className="space-y-4">
      <header className="space-y-2">
        <h1 className="text-3xl">Research Library</h1>
        <p className="text-muted-foreground max-w-2xl">
          Analyses stored in the local database. Downloads use the saved result, not a new calculation.
        </p>
      </header>
      <form
        className="max-w-xl space-y-2"
        onSubmit={(event) => {
          event.preventDefault()
          setError(null)
          try {
            const body = JSON.parse(workflow) as unknown
            void apiPost<{ id: string; result: { limitations: string[] } }>("/api/workflows", body)
              .then((created) => {
                setWorkflowNote(created.result.limitations.join(" "))
                return apiGet<AnalysisListResponse>("/api/analyses")
              })
              .then((body) => setAnalyses(body.analyses))
              .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "The workflow failed."))
          } catch {
            setError("The workflow text is not JSON.")
          }
        }}
      >
        <h2 className="text-xl">Workflow</h2>
        <p className="text-sm">A workflow does not draw a scientific conclusion. LLM drafting is off unless the server enables it.</p>
        <label className="block text-sm" htmlFor="workflow-json">
          Workflow JSON
        </label>
        <textarea
          id="workflow-json"
          className="min-h-28 w-full rounded border px-2 py-1 font-mono text-xs"
          value={workflow}
          onChange={(event) => setWorkflow(event.target.value)}
        />
        <Button type="submit">Run workflow</Button>
        {workflowNote ? <p className="text-sm">{workflowNote}</p> : null}
      </form>
      {loading ? <p role="status">Loading saved analyses…</p> : null}
      {error ? <p role="alert">{error}</p> : null}
      {!loading && analyses.length === 0 ? <p>No analyses have been saved yet.</p> : null}
      <ul className="space-y-3">
        {analyses.map((item) => (
          <li key={item.id} className="rounded-lg bg-card px-3 py-3 ring-1 ring-foreground/10">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="font-medium">
                {item.structure_id ? (
                  <Link to={`/proteins/${item.structure_id}`} className="underline">
                    {item.structure_filename ?? item.kind}
                  </Link>
                ) : (
                  item.kind
                )}
              </p>
              <p className="mono text-xs">{item.status}</p>
            </div>
            <p className="text-muted-foreground text-sm">{item.created_at}</p>
            {item.error ? <p className="text-sm">{item.error.message}</p> : null}
            {item.status === "succeeded" ? (
              <div className="mt-2 flex flex-wrap gap-2">
                {(["html", "md", "json"] as const).map((format) => (
                  <a
                    key={format}
                    className={buttonVariants({ variant: "outline", size: "sm" })}
                    href={`/api/analyses/${item.id}/report?format=${format}`}
                  >
                    {format.toUpperCase()}
                  </a>
                ))}
              </div>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  )
}
