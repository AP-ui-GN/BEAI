import { useCallback, useEffect, useState } from "react"

import { ApiError, apiGet, apiPost } from "@/api/client"
import { OriginBadge } from "@/components/OriginBadge"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { AnalysisDetail, ModelListResponse, RegisteredModel } from "@/types"

function gibibytes(bytes: number): string {
  return (bytes / 1024 ** 3).toFixed(2)
}

function SolubilityForm({ modelId }: { modelId: string }) {
  const [smiles, setSmiles] = useState("")
  const [result, setResult] = useState<AnalysisDetail | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const label = result?.result?.details?.label
  const domain = result?.result?.details?.in_applicability_domain

  async function predict(event: { preventDefault: () => void }) {
    event.preventDefault()
    setMessage(null)
    try {
      const detail = await apiPost<AnalysisDetail>(`/api/models/${modelId}/predict`, { smiles })
      setResult(detail)
    } catch (caught) {
      setResult(null)
      setMessage(caught instanceof Error ? caught.message : "The prediction failed.")
    }
  }

  return (
    <form className="space-y-2" onSubmit={(event) => void predict(event)}>
      <h3 className="text-base">Solubility prediction</h3>
      <p className="text-sm">Not an experimental measurement.</p>
      <label className="text-sm" htmlFor={`smiles-${modelId}`}>
        SMILES
      </label>
      <input
        id={`smiles-${modelId}`}
        className="w-full rounded border px-2 py-1 text-sm"
        value={smiles}
        onChange={(event) => setSmiles(event.target.value)}
      />
      <Button type="submit">Predict log solubility</Button>
      {message ? <p role="alert">{message}</p> : null}
      {typeof label === "string" ? <p>{label}</p> : null}
      {typeof domain === "boolean" ? (
        <p className="text-sm">{domain ? "Inside the applicability domain." : "Outside the applicability domain."}</p>
      ) : null}
      {result?.result?.measurements.map((measurement) => (
        <p key={measurement.name} className="text-sm">
          {measurement.name} <OriginBadge origin={measurement.origin} /> {String(measurement.value)}{" "}
          {measurement.unit ?? ""}
          {measurement.uncertainty == null ? "" : ` uncertainty ${measurement.uncertainty}`}
        </p>
      ))}
      {result?.result?.limitations.map((item) => (
        <p key={item} className="text-sm">
          {item}
        </p>
      ))}
    </form>
  )
}

function EmbeddingForm({
  model,
  sequences,
  chosen,
  onChoose,
  result,
  onEmbed,
}: {
  model: RegisteredModel
  sequences: Array<{ id: string; header: string; length: number }>
  chosen: string
  onChoose: (sequenceId: string) => void
  result: AnalysisDetail | null
  onEmbed: (detail: AnalysisDetail) => void
}) {
  const [pending, setPending] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const label = result?.result?.details?.label

  async function embed() {
    if (!chosen) {
      return
    }
    setPending(true)
    setMessage(null)
    try {
      const detail = await apiPost<AnalysisDetail>(`/api/sequences/${chosen}/embeddings`, { model_id: model.id })
      onEmbed(detail)
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "The embedding failed.")
    } finally {
      setPending(false)
    }
  }

  return (
    <section className="space-y-2">
      <h3 className="text-base">Stored sequences</h3>
      {sequences.length === 0 ? <p className="text-sm">No sequences are stored.</p> : null}
      {sequences.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          <label className="text-sm" htmlFor={`sequence-${model.id}`}>
            Sequence
          </label>
          <select
            id={`sequence-${model.id}`}
            className="rounded border px-2 py-1 text-sm"
            value={chosen}
            onChange={(event) => onChoose(event.target.value)}
          >
            <option value="">Choose a stored sequence</option>
            {sequences.map((sequence) => (
              <option key={sequence.id} value={sequence.id}>
                {sequence.header} ({sequence.length})
              </option>
            ))}
          </select>
          <Button type="button" disabled={!chosen || pending} onClick={() => void embed()}>
            Embed sequence
          </Button>
        </div>
      ) : null}
      {message ? <p role="alert">{message}</p> : null}
      {typeof label === "string" ? <p>{label}</p> : null}
      {result?.result?.measurements.map((measurement) => (
        <p key={measurement.name} className="text-sm">
          {measurement.name} <OriginBadge origin={measurement.origin} />
          {Array.isArray(measurement.value) ? ` ${measurement.value.length} values` : ` ${String(measurement.value)}`}
        </p>
      ))}
      {result?.result?.limitations.map((item) => (
        <p key={item} className="text-sm">
          {item}
        </p>
      ))}
    </section>
  )
}

type StoredSequence = { id: string; header: string; length: number }

export function ModelLaboratory() {
  const [report, setReport] = useState<ModelListResponse | null>(null)
  const [sequences, setSequences] = useState<StoredSequence[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [chosen, setChosen] = useState<Record<string, string>>({})
  const [embeddings, setEmbeddings] = useState<Record<string, AnalysisDetail>>({})

  const load = useCallback((signal?: AbortSignal) => {
    setLoading(true)
    setError(null)
    Promise.all([
      apiGet<ModelListResponse>("/api/models", signal),
      apiGet<{ sequences: StoredSequence[] }>("/api/sequences", signal),
    ])
      .then(([models, stored]) => {
        setReport(models)
        setSequences(stored.sequences)
      })
      .catch((caught: unknown) => {
        if (signal?.aborted) {
          return
        }
        setError(caught instanceof Error ? caught.message : "The model list could not be loaded.")
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

  async function activate(model: RegisteredModel, action: "load" | "unload") {
    setActionError(null)
    setBusyId(model.id)
    try {
      const updated = await apiPost<RegisteredModel>(`/api/models/${model.id}/${action}`, {})
      setReport((current) =>
        current
          ? { ...current, models: current.models.map((item) => (item.id === updated.id ? updated : item)) }
          : current,
      )
    } catch (caught) {
      setActionError(caught instanceof ApiError ? caught.message : "The model request failed.")
    } finally {
      setBusyId(null)
    }
  }

  async function train(model: RegisteredModel) {
    setActionError(null)
    setBusyId(model.id)
    try {
      const job = await apiPost<{ id: string; status: string }>(`/api/models/${model.id}/train`, {})
      let status = job.status
      while (status === "pending" || status === "running") {
        await new Promise((resolve) => setTimeout(resolve, 500))
        const current = await apiGet<{ status: string; progress: number | null }>(`/api/jobs/${job.id}`)
        status = current.status
      }
      if (status !== "succeeded") {
        setActionError(`Training finished with status ${status}.`)
      }
      load()
    } catch (caught) {
      setActionError(caught instanceof ApiError ? caught.message : "Training could not be started.")
    } finally {
      setBusyId(null)
    }
  }

  async function download(model: RegisteredModel) {
    setActionError(null)
    setBusyId(model.id)
    try {
      await apiPost<{ checksum_sha256: string }>(`/api/models/${model.id}/download`, {})
      load()
    } catch (caught) {
      setActionError(caught instanceof ApiError ? caught.message : "The download failed.")
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-3xl">Model Laboratory</h1>
        <p className="text-muted-foreground max-w-2xl text-sm">
          Registry rows, hardware, and training jobs come from this process. Nothing is loaded when the server starts.
          Predictions, when a later loader produces them, are ML predictions and are labelled not experimental.
        </p>
      </header>

      {loading ? (
        <p role="status" aria-live="polite">
          Loading the model registry…
        </p>
      ) : null}
      {error ? (
        <div role="alert" className="space-y-3">
          <p>{error}</p>
          <Button type="button" variant="outline" onClick={() => load()}>
            Retry
          </Button>
        </div>
      ) : null}
      {actionError ? (
        <p role="alert" className="text-sm">
          {actionError}
        </p>
      ) : null}

      {report ? (
        <section aria-label="Hardware" className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle>RAM</CardTitle>
              <CardDescription>Bytes reported by the host</CardDescription>
            </CardHeader>
            <CardContent className="space-y-1 text-sm">
              <p>Total {report.hardware.ram_total_bytes} bytes</p>
              <p>Available {report.hardware.ram_available_bytes} bytes</p>
              <p className="text-muted-foreground">
                {gibibytes(report.hardware.ram_available_bytes)} GiB available, calculated from the byte count.
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>CUDA</CardTitle>
            </CardHeader>
            <CardContent className="text-sm">
              {report.hardware.cuda.available
                ? `Available${report.hardware.cuda.version ? ` (${report.hardware.cuda.version})` : ""}`
                : `Unavailable: ${report.hardware.cuda.reason ?? "no reason reported"}`}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>MPS</CardTitle>
            </CardHeader>
            <CardContent className="text-sm">
              {report.hardware.mps.available
                ? `Available${report.hardware.mps.version ? ` (${report.hardware.mps.version})` : ""}`
                : `Unavailable: ${report.hardware.mps.reason ?? "no reason reported"}`}
            </CardContent>
          </Card>
        </section>
      ) : null}

      {report && report.models.length === 0 ? (
        <p>No models are registered. This page does not invent a model list, a benchmark, or a training run.</p>
      ) : null}

      {report?.models.map((model) => {
        const blocked = model.status === "disabled" || model.status === "incompatible"
        const reason = model.status_reason
        return (
          <article key={model.id} className="space-y-3 rounded-lg bg-card px-4 py-4 ring-1 ring-foreground/10">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-xl">
                  {model.name} <span className="text-base">{model.version}</span>
                </h2>
                <p className="text-muted-foreground text-sm">{model.task}</p>
              </div>
              <Badge variant={model.status === "disabled" || model.status === "incompatible" ? "outline" : "default"}>
                {model.status}
              </Badge>
            </div>
            <dl className="grid gap-2 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-muted-foreground">Licence</dt>
                <dd>{model.licence}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Source</dt>
                <dd>
                  <a className="underline" href={model.source_url}>
                    {model.source_url}
                  </a>
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Hardware compatibility</dt>
                <dd>{model.hardware_compatibility.compatible ? "Compatible with this machine" : "Not compatible"}</dd>
              </div>
            <div>
              <dt className="text-muted-foreground">Weights loaded</dt>
              <dd>{model.weights_loaded ? "Yes" : "No"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Token limit</dt>
              <dd>{model.token_limit == null ? "None stored" : model.token_limit}</dd>
            </div>
          </dl>
            <section>
              <h3 className="text-base">Benchmark</h3>
              {model.benchmark == null ? (
                <p className="text-sm">No benchmark result is stored.</p>
              ) : (
                <pre className="overflow-x-auto text-xs">{JSON.stringify(model.benchmark, null, 2)}</pre>
              )}
            </section>
            <section>
              <h3 className="text-base">Training jobs</h3>
              {model.training_jobs.length === 0 ? (
                <p className="text-sm">No training jobs are stored for this model.</p>
              ) : (
                <ul className="space-y-1 text-sm">
                  {model.training_jobs.map((job) => (
                    <li key={job.id}>
                      {job.status}
                      {job.progress === null ? "" : ` · progress ${job.progress}`}
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <p className="text-sm">{model.known_limitations}</p>
            {model.load_note ? <p className="text-sm">{model.load_note}</p> : null}
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                disabled={blocked || busyId === model.id || model.loaded}
                aria-describedby={blocked ? `${model.id}-reason` : undefined}
                onClick={() => void activate(model, "load")}
              >
                Load {model.name}
              </Button>
              <Button
                type="button"
                variant="outline"
                disabled={!model.loaded || busyId === model.id}
                onClick={() => void activate(model, "unload")}
              >
                Unload {model.name}
              </Button>
              {model.can_download ? (
                <Button
                  type="button"
                  variant="outline"
                  disabled={busyId === model.id}
                  onClick={() => void download(model)}
                >
                  Download weights
                </Button>
              ) : null}
              {model.can_train ? (
                <Button type="button" variant="outline" disabled={busyId === model.id} onClick={() => void train(model)}>
                  Train solubility models
                </Button>
              ) : null}
            </div>
            {model.trained ? <SolubilityForm modelId={model.id} /> : null}
            {model.status === "ready" || model.status === "loaded" ? (
              <EmbeddingForm
                model={model}
                sequences={sequences}
                chosen={chosen[model.id] ?? ""}
                onChoose={(sequenceId) => setChosen((current) => ({ ...current, [model.id]: sequenceId }))}
                result={embeddings[model.id] ?? null}
                onEmbed={(detail) => setEmbeddings((current) => ({ ...current, [model.id]: detail }))}
              />
            ) : null}
            {blocked && reason ? (
              <p id={`${model.id}-reason`} className="text-muted-foreground text-sm">
                Unavailable: {reason}
              </p>
            ) : null}
          </article>
        )
      })}
    </div>
  )
}
