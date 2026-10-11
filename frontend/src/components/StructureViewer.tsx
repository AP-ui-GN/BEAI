import { createViewer, type GLViewer } from "3dmol"
import { useEffect, useRef, useState } from "react"

type Highlight = {
  chainId: string
  resseq: number
}

type StructureViewerProps = {
  text: string
  format: "pdb" | "mmcif"
  chainId: string
  showLigands: boolean
  showWaters: boolean
  ligandResnames: string[]
  highlight: Highlight | null
}

export function StructureViewer({
  text,
  format,
  chainId,
  showLigands,
  showWaters,
  ligandResnames,
  highlight,
}: StructureViewerProps) {
  const host = useRef<HTMLDivElement>(null)
  const viewer = useRef<GLViewer | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const element = host.current
    if (!element) {
      return
    }
    try {
      viewer.current = createViewer(element, { backgroundColor: "#f7f4ee" })
      setError(null)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The 3D viewer could not start.")
    }
    return () => {
      viewer.current?.clear()
      viewer.current = null
      element.replaceChildren()
    }
  }, [])

  useEffect(() => {
    const current = viewer.current
    if (!current || !text) {
      return
    }
    current.removeAllModels()
    current.addModel(text, format === "mmcif" ? "cif" : "pdb")
    const chainSelection = chainId === "all" ? {} : { chain: chainId }
    current.setStyle({}, {})
    current.setStyle(chainSelection, { cartoon: { color: "spectrum" } })
    if (showLigands) {
      for (const resn of ligandResnames) {
        current.addStyle({ ...chainSelection, resn }, { stick: { radius: 0.2 } })
      }
    }
    if (showWaters) {
      for (const resn of ["HOH", "WAT"]) {
        current.addStyle({ ...chainSelection, resn }, { sphere: { radius: 0.35, color: "skyblue" } })
      }
    }
    const focus = highlight ? { chain: highlight.chainId, resi: highlight.resseq } : chainSelection
    if (highlight) {
      current.addStyle(focus, { stick: { color: "#9a4e32", radius: 0.25 } })
    }
    current.zoomTo(focus)
    current.render()
  }, [text, format, chainId, showLigands, showWaters, ligandResnames, highlight])

  return (
    <div className="space-y-2">
      {error ? (
        <p role="alert">The 3D viewer could not start. {error}</p>
      ) : (
        <div ref={host} data-testid="structure-viewer" className="h-80 w-full rounded-md bg-[#f7f4ee] md:h-[28rem]" />
      )}
    </div>
  )
}
