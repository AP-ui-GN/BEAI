"""Evidence categories for retrieved safety records.

FAERS counts are observational. Similarity suggestions are computational
predictions and unverified. Literature stays unclassified until a person
sets a category. This module does not give medical advice, doses, or
medication changes.
"""

from __future__ import annotations

NOT_CAUSAL = (
    "These are spontaneous reports. They do not establish causation and are affected by reporting bias."
)
EMERGENCY = (
    "If this concerns an overdose or poisoning, contact local emergency services or poison control "
    "(US: 1-800-222-1222) before any computational result."
)
RESEARCH_BANNER = (
    "Research use only. This is not medical advice, a diagnosis, dosing guidance, or a treatment recommendation."
)

_URGENT = ("overdose", "poison", "poisoning")


def show_emergency(query: str) -> bool:
    text = query.lower()
    return any(word in text for word in _URGENT)


def label_sections(record: dict) -> list[dict]:
    """Copy openFDA section lists verbatim. No summary is written."""

    names = [
        "boxed_warning",
        "contraindications",
        "warnings_and_cautions",
        "warnings",
        "adverse_reactions",
        "drug_interactions",
        "overdosage",
        "mechanism_of_action",
        "pharmacokinetics",
    ]
    sections = []
    for name in names:
        value = record.get(name)
        if value is None:
            continue
        if isinstance(value, list):
            text = value
        else:
            text = [str(value)]
        sections.append(
            {
                "section": name,
                "text": text,
                "set_id": record.get("set_id"),
                "version": record.get("version"),
                "effective_time": record.get("effective_time"),
                "category": "established",
            }
        )
    return sections


def faers_statement(counts: list[dict], query: str, window: str) -> dict:
    return {
        "category": "observational",
        "statement": NOT_CAUSAL,
        "query": query,
        "time_window": window,
        "counts": counts,
    }


def literature_item(summary: dict) -> dict:
    return {
        "category": "unclassified",
        "pmid": summary.get("uid"),
        "title": summary.get("title"),
        "journal": summary.get("source"),
        "pubdate": summary.get("pubdate"),
        "publication_types": summary.get("pubtype") or [],
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{summary.get('uid')}/" if summary.get("uid") else None,
    }


def europepmc_item(row: dict) -> dict:
    """Literature stays unclassified. Abstracts are kept only for open-access licensed records."""

    pub_types = (row.get("pubTypeList") or {}).get("pubType") if isinstance(row.get("pubTypeList"), dict) else None
    if isinstance(pub_types, str):
        publication_types = [pub_types]
    elif isinstance(pub_types, list):
        publication_types = [str(item) for item in pub_types]
    else:
        publication_types = []
    journal_info = row.get("journalInfo") if isinstance(row.get("journalInfo"), dict) else {}
    journal = journal_info.get("journal") if isinstance(journal_info.get("journal"), dict) else {}
    license_name = row.get("license") if isinstance(row.get("license"), str) and row.get("license") else None
    open_access = row.get("isOpenAccess") == "Y"
    abstract = None
    omitted = None
    if open_access and license_name:
        abstract = row.get("abstractText") if isinstance(row.get("abstractText"), str) else None
    elif row.get("abstractText"):
        omitted = "Abstract omitted because the record was not marked open access with a licence."
    source = row.get("source") if isinstance(row.get("source"), str) else None
    record_id = row.get("id") if isinstance(row.get("id"), str) else None
    url = f"https://europepmc.org/article/{source}/{record_id}" if source and record_id else None
    return {
        "category": "unclassified",
        "title": row.get("title"),
        "authors": row.get("authorString"),
        "journal": journal.get("title"),
        "year": row.get("pubYear"),
        "pmid": row.get("pmid"),
        "doi": row.get("doi"),
        "publication_types": publication_types,
        "url": url,
        "abstract": abstract,
        "abstract_omitted_reason": omitted,
        "is_open_access": row.get("isOpenAccess"),
        "license": license_name,
    }


ASSOCIATION_LIMIT = (
    "This is an Open Targets association score stored as retrieved. "
    "It is not evidence of efficacy and it is not a treatment recommendation."
)


def open_targets_safety(row: dict) -> dict:
    """Curated platform text stays unclassified until a person sets a category."""

    return {
        "category": "unclassified",
        "event": row.get("event"),
        "event_id": row.get("eventId"),
        "datasource": row.get("datasource"),
        "literature": row.get("literature"),
    }


def open_targets_disease(row: dict) -> dict:
    disease = row.get("disease") if isinstance(row.get("disease"), dict) else {}
    return {
        "category": "unclassified",
        "disease_id": disease.get("id"),
        "disease_name": disease.get("name"),
        "score": row.get("score"),
        "limitation": ASSOCIATION_LIMIT,
    }


def similarity_offtarget(target_id: str, similarity: float, ligands: list[str]) -> dict:
    return {
        "category": "computational_prediction",
        "label": "unverified",
        "target_chembl_id": target_id,
        "similarity": similarity,
        "supporting_ligands": ligands,
    }
