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


def similarity_offtarget(target_id: str, similarity: float, ligands: list[str]) -> dict:
    return {
        "category": "computational_prediction",
        "label": "unverified",
        "target_chembl_id": target_id,
        "similarity": similarity,
        "supporting_ligands": ligands,
    }
