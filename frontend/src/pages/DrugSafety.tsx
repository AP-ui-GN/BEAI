import { useState, type FormEvent } from "react"

import { apiPost } from "@/api/client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

const BANNER =
  "Research use only. This is not medical advice, a diagnosis, dosing guidance, or a treatment recommendation."

type LabelResponse = {
  banner: string
  emergency: string | null
  sections?: Array<{ section: string; text: string[]; category: string; set_id?: string; version?: string }>
  statement?: string
  category?: string
  counts?: Array<{ term: string; count: number }>
}

export function DrugSafety() {
  const [name, setName] = useState("")
  const [label, setLabel] = useState<LabelResponse | null>(null)
  const [events, setEvents] = useState<LabelResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function lookup(event: FormEvent) {
    event.preventDefault()
    setError(null)
    try {
      const [labelBody, eventBody] = await Promise.all([
        apiPost<LabelResponse>("/api/safety/label", { name }),
        apiPost<LabelResponse>("/api/safety/events", { name }),
      ])
      setLabel(labelBody)
      setEvents(eventBody)
    } catch (caught) {
      setLabel(null)
      setEvents(null)
      setError(caught instanceof Error ? caught.message : "The lookup failed.")
    }
  }

  const emergency = label?.emergency || events?.emergency

  return (
    <div className="space-y-4">
      <p className="rounded-md border px-3 py-2 text-sm" role="note">
        {BANNER}
      </p>
      {emergency ? (
        <p className="rounded-md border border-destructive/40 px-3 py-2 text-sm" role="alert">
          {emergency}
        </p>
      ) : null}
      <h1 className="text-3xl">Drug Safety</h1>
      <p className="text-muted-foreground max-w-2xl text-sm">
        Label text is stored as retrieved. Adverse-event counts are spontaneous reports and are not causal. This page
        does not recommend a dose or a change to someone's medication.
      </p>
      <form className="flex max-w-xl flex-wrap gap-2" onSubmit={(event) => void lookup(event)}>
        <label className="sr-only" htmlFor="safety-name">
          Drug name
        </label>
        <Input id="safety-name" value={name} onChange={(event) => setName(event.target.value)} />
        <Button type="submit">Look up evidence</Button>
      </form>
      {error ? <p role="alert">{error}</p> : null}
      {label?.sections?.map((section) => (
        <section key={section.section} className="space-y-1">
          <h2 className="text-lg">
            {section.section} <span className="text-sm">({section.category})</span>
          </h2>
          {section.text.map((paragraph) => (
            <p key={paragraph.slice(0, 40)} className="text-sm">
              {paragraph}
            </p>
          ))}
        </section>
      ))}
      {events?.statement ? <p className="text-sm">{events.statement}</p> : null}
      {events?.counts ? (
        <ul className="text-sm">
          {events.counts.map((row) => (
            <li key={row.term}>
              {row.term}: {row.count}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
