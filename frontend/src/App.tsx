import { BrowserRouter, Route, Routes } from "react-router-dom"

import { Layout } from "@/components/Layout"
import { TooltipProvider } from "@/components/ui/tooltip"
import { Dashboard } from "@/pages/Dashboard"
import { PlannedRoute } from "@/pages/Planned"

export default function App() {
  return (
    <TooltipProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route
              path="proteins"
              element={
                <PlannedRoute
                  title="Protein Explorer"
                  summary="Upload, measurement tables, and the 3D viewer are the next part of this milestone. This page has no upload control yet."
                />
              }
            />
            <Route
              path="compounds"
              element={
                <PlannedRoute
                  title="Compound Explorer"
                  summary="Compound sanitization, descriptors, and depiction are planned for a later milestone. Nothing here submits a structure or a SMILES string."
                  capabilityKey="rdkit"
                  toolName="RDKit"
                />
              }
            />
            <Route
              path="discovery"
              element={
                <PlannedRoute
                  title="Drug Discovery"
                  summary="Docking is planned for a later milestone. BEAI will not invent a pose when Vina is absent."
                  capabilityKey="vina"
                  toolName="AutoDock Vina"
                />
              }
            />
            <Route
              path="safety"
              element={
                <PlannedRoute
                  title="Drug Safety"
                  summary="Source-linked evidence review is planned. This page does not score interactions, suggest doses, or store medication lists."
                  safety
                />
              }
            />
            <Route
              path="simulation"
              element={
                <PlannedRoute
                  title="Simulation Center"
                  summary="Molecular simulation is planned for a later milestone. A short run, when it exists, will not be presented as proof of stability."
                  capabilityKey="openmm"
                  toolName="OpenMM"
                />
              }
            />
            <Route
              path="library"
              element={
                <PlannedRoute
                  title="Research Library"
                  summary="Saved analyses and report downloads will be listed here. The dashboard already shows analyses returned by the API."
                />
              }
            />
            <Route
              path="models"
              element={
                <PlannedRoute
                  title="Model Laboratory"
                  summary="Model registry and benchmarks are planned. No weights are loaded, and this page does not start a training run."
                  capabilityKey="pytorch"
                  toolName="PyTorch"
                />
              }
            />
          </Route>
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  )
}
