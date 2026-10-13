import { BrowserRouter, Route, Routes } from "react-router-dom"

import { Layout } from "@/components/Layout"
import { TooltipProvider } from "@/components/ui/tooltip"
import { Dashboard } from "@/pages/Dashboard"
import { CompoundExplorer } from "@/pages/CompoundExplorer"
import { DrugDiscovery } from "@/pages/DrugDiscovery"
import { DrugSafety } from "@/pages/DrugSafety"
import { ModelLaboratory } from "@/pages/ModelLaboratory"
import { SimulationCenter } from "@/pages/SimulationCenter"
import { ProteinExplorer } from "@/pages/ProteinExplorer"
import { ResearchLibrary } from "@/pages/ResearchLibrary"

export default function App() {
  return (
    <TooltipProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="proteins" element={<ProteinExplorer />} />
            <Route path="proteins/:structureId" element={<ProteinExplorer />} />
            <Route path="compounds" element={<CompoundExplorer />} />
            <Route path="discovery" element={<DrugDiscovery />} />
            <Route path="safety" element={<DrugSafety />} />
            <Route path="simulation" element={<SimulationCenter />} />
            <Route path="library" element={<ResearchLibrary />} />
            <Route path="models" element={<ModelLaboratory />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  )
}
