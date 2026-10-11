import { useState } from "react"
import { NavLink, Outlet } from "react-router-dom"

import { Button } from "@/components/ui/button"

const LINKS = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/proteins", label: "Protein Explorer", end: false },
  { to: "/compounds", label: "Compound Explorer", end: false },
  { to: "/discovery", label: "Drug Discovery", end: false },
  { to: "/safety", label: "Drug Safety", end: false },
  { to: "/simulation", label: "Simulation Center", end: false },
  { to: "/library", label: "Research Library", end: false },
  { to: "/models", label: "Model Laboratory", end: false },
]

export function Layout() {
  const [open, setOpen] = useState(false)

  return (
    <div className="min-h-svh md:grid md:grid-cols-[240px_1fr]">
      <aside className="border-b bg-sidebar md:border-r md:border-b-0">
        <div className="flex items-center justify-between gap-3 px-4 py-4">
          <div>
            <p className="font-[Literata,Georgia,serif] text-xl leading-none">BEAI</p>
            <p className="text-muted-foreground mt-1 text-xs">Research software for structures and evidence</p>
          </div>
          <Button
            variant="outline"
            className="md:hidden"
            aria-expanded={open}
            aria-controls="beai-nav"
            onClick={() => setOpen((value) => !value)}
          >
            {open ? "Close" : "Menu"}
          </Button>
        </div>
        <nav id="beai-nav" className={open ? "block px-2 pb-4" : "hidden px-2 pb-4 md:block"} aria-label="Primary">
          <ul className="space-y-1">
            {LINKS.map((link) => (
              <li key={link.to}>
                <NavLink
                  to={link.to}
                  end={link.end}
                  onClick={() => setOpen(false)}
                  className={({ isActive }) =>
                    [
                      "block rounded-md px-3 py-2 text-sm focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
                      isActive ? "bg-primary text-primary-foreground" : "hover:bg-sidebar-accent",
                    ].join(" ")
                  }
                >
                  {link.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </aside>
      <div className="min-w-0">
        <main className="mx-auto w-full max-w-6xl px-4 py-6 md:px-8 md:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
