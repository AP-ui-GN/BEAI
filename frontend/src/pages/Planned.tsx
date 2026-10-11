import { useEffect, useState } from "react"

import { apiGet } from "@/api/client"
import type { CapabilityStatus, HealthResponse } from "@/types"

type PlannedPageProps = {
  title: string
  summary: string
  toolName?: string
  tool?: CapabilityStatus | null
  safety?: boolean
}

export function PlannedPage({ title, summary, toolName, tool, safety = false }: PlannedPageProps) {
  return (
    <article className="max-w-2xl space-y-4">
      {safety ? (
        <p className="rounded-md border border-amber-700/30 bg-amber-50 px-3 py-2 text-sm text-amber-950">
          BEAI is research software. It does not provide medical advice, diagnosis, dosing, or treatment.
        </p>
      ) : null}
      <p className="text-muted-foreground text-sm tracking-wide uppercase">Planned</p>
      <h1 className="text-3xl">{title}</h1>
      <p className="text-base leading-relaxed">{summary}</p>
      {toolName ? (
        <p className="text-sm">
          {toolName}:{" "}
          {tool == null
            ? "status was not loaded"
            : tool.available
              ? `Available${tool.version ? ` (${tool.version})` : ""}`
              : `Unavailable: ${tool.reason ?? "no reason reported"}`}
        </p>
      ) : null}
      <p className="text-muted-foreground text-sm">This area has no actions in the current milestone.</p>
    </article>
  )
}

type PlannedRouteProps = {
  title: string
  summary: string
  capabilityKey?: string
  toolName?: string
  safety?: boolean
}

export function PlannedRoute({ title, summary, capabilityKey, toolName, safety }: PlannedRouteProps) {
  const [tool, setTool] = useState<CapabilityStatus | null>(null)
  const [loaded, setLoaded] = useState(capabilityKey == null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!capabilityKey) {
      return
    }
    const controller = new AbortController()
    apiGet<HealthResponse>("/api/health", controller.signal)
      .then((health) => {
        setTool(health.capabilities[capabilityKey] ?? null)
        setLoaded(true)
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) {
          return
        }
        setError(caught instanceof Error ? caught.message : "Health could not be loaded.")
        setLoaded(true)
      })
    return () => controller.abort()
  }, [capabilityKey])

  return (
    <div className="space-y-3">
      {error ? <p role="alert">{error}</p> : null}
      <PlannedPage
        title={title}
        summary={summary}
        toolName={toolName}
        tool={capabilityKey && !loaded ? null : tool}
        safety={safety}
      />
    </div>
  )
}
