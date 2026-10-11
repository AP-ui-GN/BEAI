import { useCallback, useEffect, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"

import { apiGet, apiPostFile } from "@/api/client"
import { Input } from "@/components/ui/input"
import { StructureDetail } from "@/pages/StructureDetail"
import type { StructureListResponse, StructureResponse } from "@/types"

export function ProteinExplorer() {
  const { structureId } = useParams()
  const navigate = useNavigate()
  const [structures, setStructures] = useState<StructureResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)

  const load = useCallback((signal?: AbortSignal) => {
    setLoading(true)
    apiGet<StructureListResponse>("/api/structures", signal)
      .then((body) => setStructures(body.structures))
      .catch((caught: unknown) => {
        if (signal?.aborted) {
          return
        }
        setError(caught instanceof Error ? caught.message : "Structures could not be loaded.")
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

  async function upload(file: File | undefined) {
    if (!file) {
      return
    }
    setUploading(true)
    setError(null)
    try {
      const created = await apiPostFile<StructureResponse>("/api/structures", file)
      await fetch(`/api/structures/${created.id}/analyses`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ kind: "structure_overview" }),
      }).then(async (response) => {
        if (!response.ok) {
          const body = (await response.json().catch(() => null)) as { message?: string } | null
          throw new Error(body?.message ?? "The overview could not be started.")
        }
      })
      navigate(`/proteins/${created.id}`)
      load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Upload failed.")
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
      <section className="space-y-4">
        <h1 className="text-3xl">Protein Explorer</h1>
        <form
          className="space-y-2 rounded-lg border border-dashed bg-card px-3 py-3"
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault()
            void upload(event.dataTransfer.files[0])
          }}
        >
          <label htmlFor="structure-file" className="block text-sm font-medium">
            Upload a PDB or mmCIF file
          </label>
          <Input
            id="structure-file"
            type="file"
            accept=".pdb,.ent,.cif,.mmcif"
            disabled={uploading}
            onChange={(event) => {
              const file = event.target.files?.[0]
              void upload(file)
              event.target.value = ""
            }}
          />
          <p className="text-muted-foreground text-xs">
            {uploading ? "Uploading and analyzing…" : "Drag a file here or choose one. .pdb, .ent, .cif, and .mmcif."}
          </p>
        </form>
        {error ? (
          <p role="alert" className="text-sm">
            {error}
          </p>
        ) : null}
        {loading ? <p className="text-sm">Loading structures…</p> : null}
        {!loading && structures.length === 0 ? <p className="text-sm">No structures have been uploaded.</p> : null}
        <ul className="space-y-1">
          {structures.map((structure) => (
            <li key={structure.id}>
              <Link
                to={`/proteins/${structure.id}`}
                className={
                  structure.id === structureId
                    ? "block rounded-md bg-primary px-2 py-1 text-sm text-primary-foreground"
                    : "block rounded-md px-2 py-1 text-sm hover:bg-muted"
                }
              >
                {structure.display_filename}
              </Link>
            </li>
          ))}
        </ul>
      </section>
      <section>
        {structureId ? (
          <StructureDetail key={structureId} structureId={structureId} />
        ) : (
          <p className="text-muted-foreground">Choose a structure or upload a file to see measurements and the 3D view.</p>
        )}
      </section>
    </div>
  )
}
