import { useState, type FormEvent } from "react"

import { apiPost } from "@/api/client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

const BANNER =
  "Research use only. This is not medical advice, a diagnosis, dosing guidance, or a treatment recommendation."

type LabelResponse = {
  banner: string
  emergency: string | null
  source?: string
  retrieved_at?: string
  openfda_error?: string | null
  sections?: Array<{ section: string; text: string[]; category: string; set_id?: string; version?: string }>
  statement?: string
  category?: string
  counts?: Array<{ term: string; count: number }>
}

type Article = {
  category: string
  title?: string | null
  authors?: string | null
  journal?: string | null
  year?: string | number | null
  pmid?: string | null
  doi?: string | null
  url?: string | null
  publication_types?: string[]
  abstract?: string | null
  abstract_omitted_reason?: string | null
}

type EuropePmcResponse = {
  banner: string
  emergency: string | null
  source?: string
  retrieved_at?: string
  items?: Article[]
}

type OpenTargetsResponse = {
  banner: string
  emergency: string | null
  source?: string
  retrieved_at?: string
  approved_symbol?: string | null
  limitation?: string
  safety_liabilities?: Array<{ category: string; event?: string | null; datasource?: string | null; literature?: string | null }>
  disease_associations?: Array<{
    category: string
    disease_id?: string | null
    disease_name?: string | null
    score?: number | null
    limitation?: string
  }>
}

export function DrugSafety() {
  const [name, setName] = useState("")
  const [label, setLabel] = useState<LabelResponse | null>(null)
  const [events, setEvents] = useState<LabelResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [articleQuery, setArticleQuery] = useState("")
  const [articles, setArticles] = useState<EuropePmcResponse | null>(null)
  const [articleError, setArticleError] = useState<string | null>(null)
  const [ensemblId, setEnsemblId] = useState("")
  const [target, setTarget] = useState<OpenTargetsResponse | null>(null)
  const [targetError, setTargetError] = useState<string | null>(null)

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

  async function searchArticles(event: FormEvent) {
    event.preventDefault()
    setArticleError(null)
    setArticles(null)
    try {
      setArticles(await apiPost<EuropePmcResponse>("/api/safety/europepmc", { query: articleQuery }))
    } catch (caught) {
      setArticleError(caught instanceof Error ? caught.message : "Europe PMC search failed.")
    }
  }

  async function searchTarget(event: FormEvent) {
    event.preventDefault()
    setTargetError(null)
    setTarget(null)
    try {
      setTarget(await apiPost<OpenTargetsResponse>("/api/safety/open-targets", { ensembl_id: ensemblId }))
    } catch (caught) {
      setTargetError(caught instanceof Error ? caught.message : "Open Targets lookup failed.")
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
      {label?.source ? (
        <p className="text-sm">
          Label source: {label.source}
          {label.retrieved_at ? ` retrieved ${label.retrieved_at}` : ""}.
          {label.openfda_error ? " openFDA did not return a label, so DailyMed was used." : ""}
        </p>
      ) : null}

      <h2 className="text-2xl">Europe PMC</h2>
      <p className="text-muted-foreground max-w-2xl text-sm">
        Search results stay unclassified until a person sets a category. An abstract is shown only when the record is
        marked open access and includes a licence.
      </p>
      <form className="flex max-w-xl flex-wrap gap-2" onSubmit={(event) => void searchArticles(event)}>
        <label className="sr-only" htmlFor="europepmc-query">
          Europe PMC query
        </label>
        <Input id="europepmc-query" value={articleQuery} onChange={(event) => setArticleQuery(event.target.value)} />
        <Button type="submit">Search Europe PMC</Button>
      </form>
      {articleError ? <p role="alert">{articleError}</p> : null}
      {articles && (articles.items?.length ?? 0) === 0 ? <p>Europe PMC returned no records.</p> : null}
      {articles?.items?.map((item) => (
        <article key={item.pmid ?? item.title} className="space-y-1 text-sm">
          <h3 className="text-lg">
            {item.title} <span>({item.category})</span>
          </h3>
          <p>
            {item.authors} {item.journal} {item.year}
          </p>
          <p>{item.publication_types?.join(", ")}</p>
          {item.url ? (
            <a href={item.url} rel="noreferrer">
              {item.url}
            </a>
          ) : null}
          {item.abstract ? <p>{item.abstract}</p> : null}
          {item.abstract_omitted_reason ? <p>{item.abstract_omitted_reason}</p> : null}
        </article>
      ))}

      <h2 className="text-2xl">Open Targets</h2>
      <p className="text-muted-foreground max-w-2xl text-sm">
        Safety liabilities and disease associations are stored as retrieved and stay unclassified. An association score
        is not evidence that a compound treats a disease.
      </p>
      <form className="flex max-w-xl flex-wrap gap-2" onSubmit={(event) => void searchTarget(event)}>
        <label className="sr-only" htmlFor="ensembl-id">
          Ensembl gene id
        </label>
        <Input
          id="ensembl-id"
          value={ensemblId}
          onChange={(event) => setEnsemblId(event.target.value)}
          placeholder="ENSG00000167397"
        />
        <Button type="submit">Look up target</Button>
      </form>
      {targetError ? <p role="alert">{targetError}</p> : null}
      {target?.approved_symbol ? (
        <p className="text-sm">
          {target.approved_symbol} from {target.source}
          {target.retrieved_at ? `, retrieved ${target.retrieved_at}` : ""}.
        </p>
      ) : null}
      {target?.limitation ? <p className="text-sm">{target.limitation}</p> : null}
      {target && (target.safety_liabilities?.length ?? 0) === 0 && (target.disease_associations?.length ?? 0) === 0 ? (
        <p>Open Targets returned no safety liabilities or disease rows.</p>
      ) : null}
      {target?.safety_liabilities?.map((row) => (
        <p key={`${row.event}-${row.datasource}`} className="text-sm">
          {row.event} ({row.category}
          {row.datasource ? `, ${row.datasource}` : ""})
        </p>
      ))}
      {target?.disease_associations?.map((row) => (
        <p key={row.disease_id ?? row.disease_name} className="text-sm">
          {row.disease_name} ({row.disease_id}) score {row.score} ({row.category}). {row.limitation}
        </p>
      ))}
    </div>
  )
}
