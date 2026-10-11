import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"

import { apiGet } from "@/api/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { capabilityLabel } from "@/lib/labels"
import type { AnalysisListResponse, HealthResponse } from "@/types"

const CAPABILITY_ORDER = ["rdkit", "mkdssp", "vina", "openmm", "pytorch", "gpu"]

export function Dashboard() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [analyses, setAnalyses] = useState<AnalysisListResponse["analyses"]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback((signal?: AbortSignal) => {
    setLoading(true)
    setError(null)
    Promise.all([
      apiGet<HealthResponse>("/api/health", signal),
      apiGet<AnalysisListResponse>("/api/analyses", signal),
    ])
      .then(([healthBody, analysisBody]) => {
        setHealth(healthBody)
        setAnalyses(analysisBody.analyses)
      })
      .catch((caught: unknown) => {
        if (signal?.aborted) {
          return
        }
        setError(caught instanceof Error ? caught.message : "The dashboard could not load.")
      })
      .finally(() => {
        if (!signal?.aborted) {
          setLoading(false)
        }
      })
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    load(controller.signal)
    return () => controller.abort()
  }, [load])

  const running = analyses.filter((item) => item.status === "pending" || item.status === "running")

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-3xl">Dashboard</h1>
        <p className="text-muted-foreground max-w-2xl">
          Local status for this BEAI process. Counts and tool versions come from the API. Missing tools stay
          unavailable instead of being filled in.
        </p>
      </header>

      {loading ? (
        <p role="status" aria-live="polite" className="text-sm">
          Loading system status…
        </p>
      ) : null}

      {error ? (
        <div role="alert" className="space-y-3 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-3">
          <p>{error}</p>
          <Button type="button" variant="outline" onClick={() => load()}>
            Retry
          </Button>
        </div>
      ) : null}

      {health ? (
        <section className="grid gap-4 md:grid-cols-3" aria-label="System health">
          <Card>
            <CardHeader>
              <CardTitle>Service</CardTitle>
              <CardDescription>Version {health.version}</CardDescription>
            </CardHeader>
            <CardContent>
              <Badge variant={health.status === "ok" ? "default" : "destructive"}>{health.status}</Badge>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Database</CardTitle>
              <CardDescription>
                {health.database.connected ? "Connected" : "Not connected"}
                {health.database.revision ? ` · revision ${health.database.revision}` : ""}
              </CardDescription>
            </CardHeader>
            <CardContent className="text-sm">
              {health.database.reason ?? "Revision matches the migration head."}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Storage</CardTitle>
              <CardDescription>{health.storage.writable ? "Writable" : "Not writable"}</CardDescription>
            </CardHeader>
            <CardContent className="text-sm">{health.storage.reason ?? "Uploads can be stored."}</CardContent>
          </Card>
        </section>
      ) : null}

      <section className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Active jobs</CardTitle>
            <CardDescription>Analyses whose status is pending or running.</CardDescription>
          </CardHeader>
          <CardContent>
            {running.length === 0 ? (
              <p>No analysis is running.</p>
            ) : (
              <ul className="space-y-2">
                {running.map((item) => (
                  <li key={item.id} className="flex items-center justify-between gap-3 text-sm">
                    <span>{item.structure_filename ?? item.kind}</span>
                    <Badge variant="outline">{item.status}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Recent analyses</CardTitle>
            <CardDescription>Saved on this machine.</CardDescription>
          </CardHeader>
          <CardContent>
            {analyses.length === 0 ? (
              <p>No analyses have been saved yet.</p>
            ) : (
              <ul className="space-y-2">
                {analyses.slice(0, 8).map((item) => (
                  <li key={item.id} className="flex items-baseline justify-between gap-3 text-sm">
                    <span>
                      {item.structure_id ? (
                        <Link className="font-medium underline" to={`/proteins/${item.structure_id}`}>
                          {item.structure_filename ?? item.kind}
                        </Link>
                      ) : (
                        <span className="font-medium">{item.kind}</span>
                      )}
                      <span className="text-muted-foreground"> · {item.kind}</span>
                    </span>
                    <span className="mono text-xs">{item.status}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </section>

      {health ? (
        <section aria-label="Optional tools">
          <h2 className="mb-3 text-xl">Optional tools</h2>
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {CAPABILITY_ORDER.map((key) => {
              const status = health.capabilities[key]
              return (
                <li key={key} className="rounded-lg bg-card px-3 py-3 ring-1 ring-foreground/10">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">{capabilityLabel(key)}</span>
                    <Badge variant={status?.available ? "default" : "outline"}>
                      {status?.available ? "Available" : "Unavailable"}
                    </Badge>
                  </div>
                  <p className="text-muted-foreground mt-2 text-sm">
                    {status == null
                      ? "Not reported."
                      : status.available
                        ? (status.version ?? "Version not reported.")
                        : (status.reason ?? "No reason reported.")}
                  </p>
                </li>
              )
            })}
          </ul>
        </section>
      ) : null}
    </div>
  )
}
