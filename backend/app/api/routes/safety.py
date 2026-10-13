"""Safety evidence routes. Retrieved text only. No dosing or medication advice."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.app.core.errors import InvalidInput
from backend.app.data_access.europepmc import search_articles
from backend.app.data_access.http import ExternalHttp
from backend.app.data_access.openfda import fetch_faers_counts, fetch_label
from backend.app.data_access.opentargets import fetch_target
from backend.app.data_access.pubmed import search_summaries
from backend.app.db.models import SafetyLookup
from backend.app.db.session import get_session
from backend.app.services.compounds.compare import group_activities
from backend.app.services.safety.evidence import (
    EMERGENCY,
    RESEARCH_BANNER,
    europepmc_item,
    faers_statement,
    label_sections,
    literature_item,
    open_targets_disease,
    open_targets_safety,
    show_emergency,
    similarity_offtarget,
)

router = APIRouter(prefix="/api/safety", tags=["safety"])


class NameQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str


class LiteratureQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str


class EnsemblQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ensembl_id: str


class OffTargetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activities: list[dict]
    similarity_hits: list[dict] = []


def _store(session: Session, query: str, kind: str, payload: dict) -> str:
    row = SafetyLookup(
        id=str(uuid.uuid4()),
        query=query,
        kind=kind,
        payload_json=payload,
        created_at=datetime.now(UTC),
    )
    session.add(row)
    session.commit()
    return row.id


def _envelope(query: str, payload: dict, lookup_id: str) -> dict:
    return {
        "id": lookup_id,
        "banner": RESEARCH_BANNER,
        "emergency": EMERGENCY if show_emergency(query) else None,
        **payload,
    }


@router.post("/label")
def label(body: NameQuery, request: Request, session: Session = Depends(get_session)) -> dict:
    if not body.name.strip():
        raise InvalidInput("The drug name is empty.")
    http: ExternalHttp = request.app.state.http
    fetched = fetch_label(http, body.name.strip())
    sections = label_sections(fetched["record"])
    interactions = fetched["record"].get("drug_interactions")
    payload = {
        "source": fetched["source"],
        "url": fetched["url"],
        "retrieved_at": fetched["retrieved_at"],
        "license": fetched["license"],
        "set_id": fetched["record"].get("set_id"),
        "version": fetched["record"].get("version"),
        "effective_time": fetched["record"].get("effective_time"),
        "sections": sections,
        "drug_interactions": interactions,
        "openfda_error": fetched.get("openfda_error"),
        "search_url": fetched.get("search_url"),
    }
    lookup_id = _store(session, body.name, "label", payload)
    return _envelope(body.name, payload, lookup_id)


@router.post("/events")
def events(body: NameQuery, request: Request, session: Session = Depends(get_session)) -> dict:
    if not body.name.strip():
        raise InvalidInput("The drug name is empty.")
    http: ExternalHttp = request.app.state.http
    fetched = fetch_faers_counts(http, body.name.strip())
    statement = faers_statement(fetched["counts"], body.name, "openFDA current public dashboard window")
    payload = {
        "source": fetched["source"],
        "url": fetched["url"],
        "retrieved_at": fetched["retrieved_at"],
        "license": fetched["license"],
        **statement,
    }
    lookup_id = _store(session, body.name, "faers", payload)
    return _envelope(body.name, payload, lookup_id)


@router.post("/literature")
def literature(body: LiteratureQuery, request: Request, session: Session = Depends(get_session)) -> dict:
    if not body.query.strip():
        raise InvalidInput("The literature query is empty.")
    http: ExternalHttp = request.app.state.http
    fetched = search_summaries(http, body.query.strip())
    items = [literature_item(row) for row in fetched["summaries"]]
    payload = {
        "source": fetched["source"],
        "url": fetched["url"],
        "retrieved_at": fetched["retrieved_at"],
        "items": items,
    }
    lookup_id = _store(session, body.query, "literature", payload)
    return _envelope(body.query, payload, lookup_id)


@router.post("/europepmc")
def europepmc(body: LiteratureQuery, request: Request, session: Session = Depends(get_session)) -> dict:
    if not body.query.strip():
        raise InvalidInput("The literature query is empty.")
    http: ExternalHttp = request.app.state.http
    fetched = search_articles(http, body.query.strip())
    items = [europepmc_item(row) for row in fetched["results"]]
    payload = {
        "source": fetched["source"],
        "url": fetched["url"],
        "retrieved_at": fetched["retrieved_at"],
        "hit_count": fetched["hit_count"],
        "items": items,
    }
    lookup_id = _store(session, body.query, "europepmc", payload)
    return _envelope(body.query, payload, lookup_id)


@router.post("/open-targets")
def open_targets(body: EnsemblQuery, request: Request, session: Session = Depends(get_session)) -> dict:
    http: ExternalHttp = request.app.state.http
    fetched = fetch_target(http, body.ensembl_id.strip())
    target = fetched["target"]
    liabilities = target.get("safetyLiabilities") if isinstance(target.get("safetyLiabilities"), list) else []
    diseases = target.get("associatedDiseases") if isinstance(target.get("associatedDiseases"), dict) else {}
    rows = diseases.get("rows") if isinstance(diseases.get("rows"), list) else []
    payload = {
        "source": fetched["source"],
        "url": fetched["url"],
        "retrieved_at": fetched["retrieved_at"],
        "ensembl_id": fetched["ensembl_id"],
        "approved_symbol": target.get("approvedSymbol"),
        "safety_liabilities": [open_targets_safety(row) for row in liabilities if isinstance(row, dict)],
        "disease_count": diseases.get("count"),
        "disease_associations": [open_targets_disease(row) for row in rows if isinstance(row, dict)],
        "limitation": (
            "Open Targets records are unclassified until a person sets a category. "
            "They are not dosing guidance and not a statement that a compound treats a disease."
        ),
    }
    lookup_id = _store(session, body.ensembl_id, "open_targets", payload)
    return _envelope(body.ensembl_id, payload, lookup_id)


@router.post("/off-targets")
def off_targets(body: OffTargetRequest) -> dict:
    """Group measured activities and keep similarity hits unverified."""

    measured = group_activities(body.activities)
    predicted = []
    for hit in body.similarity_hits:
        predicted.append(
            similarity_offtarget(
                str(hit.get("target_chembl_id") or ""),
                float(hit.get("similarity") or 0.0),
                list(hit.get("supporting_ligands") or []),
            )
        )
    return {
        "banner": RESEARCH_BANNER,
        "measured_groups": measured,
        "similarity_offtargets": predicted,
    }
