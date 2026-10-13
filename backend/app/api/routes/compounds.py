"""Compound routes. RDKit work stays in the chemistry service."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from backend.app.api.routes.analyses import _detail
from backend.app.core.config import Settings
from backend.app.core.errors import InvalidInput
from backend.app.core.timeutil import utc_iso
from backend.app.data_access.chembl import fetch_molecule
from backend.app.data_access.http import ExternalHttp
from backend.app.data_access.pubchem import lookup
from backend.app.db.models import CompoundRecord
from backend.app.db.session import get_session
from backend.app.schemas.analysis import AnalysisDetail
from backend.app.services.compounds.chemistry import depiction_svg, match_smarts, require_rdkit, similarity_matrix
from backend.app.services.compounds.compare import compare_activity_pair, group_activities
from backend.app.services.compounds.store import create_compound, get_compound, list_compounds

router = APIRouter(prefix="/api/compounds", tags=["compounds"])


class CompoundCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    smiles: str
    keep_largest_fragment: bool = False


class SimilarityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    compound_ids: list[str] = Field(min_length=2, max_length=20)


class SmartsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    smarts: str


class CompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    compound_ids: list[str] = Field(min_length=2, max_length=10)


class PubChemImport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    query_type: str


class ChemblImport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chembl_id: str


class ActivityCompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    left: dict
    right: dict


class CompoundResponse(BaseModel):
    id: str
    input_smiles: str
    canonical_smiles: str
    inchikey: str
    created_at: str
    source: dict | None
    analysis: AnalysisDetail
    already_stored: bool


class CompoundListResponse(BaseModel):
    compounds: list[CompoundResponse]


def _response(row: CompoundRecord, analysis, already: bool) -> CompoundResponse:
    return CompoundResponse(
        id=row.id,
        input_smiles=row.input_smiles,
        canonical_smiles=row.canonical_smiles,
        inchikey=row.inchikey,
        created_at=utc_iso(row.created_at),
        source=row.source_json,
        analysis=_detail(analysis, None),
        already_stored=already,
    )


def _with_analysis(session: Session, row: CompoundRecord) -> CompoundResponse:
    from sqlalchemy import select

    from backend.app.db.models import Analysis

    statement = (
        select(Analysis)
        .where(Analysis.compound_id == row.id, Analysis.kind == "compound_descriptors")
        .order_by(Analysis.created_at.desc())
    )
    analysis = session.scalars(statement).first()
    if analysis is None:
        raise InvalidInput("This compound has no descriptor analysis.")
    return _response(row, analysis, False)


@router.post("", status_code=201, response_model=CompoundResponse)
def create(
    body: CompoundCreate,
    request: Request,
    session: Session = Depends(get_session),
) -> CompoundResponse:
    require_rdkit()
    settings: Settings = request.app.state.settings
    row, analysis, already = create_compound(
        body.smiles,
        session,
        settings,
        keep_largest_fragment=body.keep_largest_fragment,
    )
    return _response(row, analysis, already)


@router.get("", response_model=CompoundListResponse)
def index(session: Session = Depends(get_session)) -> CompoundListResponse:
    require_rdkit()
    return CompoundListResponse(compounds=[_with_analysis(session, row) for row in list_compounds(session)])


@router.post("/similarity")
def similarity(body: SimilarityRequest, session: Session = Depends(get_session)) -> dict:
    require_rdkit()
    rows = [get_compound(session, compound_id) for compound_id in body.compound_ids]
    matrix = similarity_matrix([row.canonical_smiles for row in rows])
    return {
        "compound_ids": [row.id for row in rows],
        "morgan_radius": 2,
        "morgan_bits": 2048,
        "metric": "Tanimoto",
        "matrix": matrix,
    }


@router.post("/substructure")
def substructure(body: SmartsRequest, session: Session = Depends(get_session)) -> dict:
    require_rdkit()
    rows = list_compounds(session)
    hits = match_smarts(body.smarts, [(row.id, row.canonical_smiles) for row in rows])
    return {"smarts": body.smarts, "compound_ids": hits}


@router.post("/compare")
def compare(body: CompareRequest, session: Session = Depends(get_session)) -> dict:
    require_rdkit()
    rows = [_with_analysis(session, get_compound(session, compound_id)) for compound_id in body.compound_ids]
    names = ["MolWt", "MolLogP", "TPSA", "NumHDonors", "NumHAcceptors", "HeavyAtomCount", "FormalCharge"]
    table = []
    for name in names:
        values = []
        for row in rows:
            result = row.analysis.result
            measurement = None
            if result is not None:
                measurement = next((item for item in result.measurements if item.name == name), None)
            values.append(None if measurement is None else measurement.value)
        table.append({"name": name, "origin": "calculated", "values": values})
    activity_notes = []
    for index, left in enumerate(rows):
        for right in rows[index + 1 :]:
            left_groups = group_activities(_activities(left.source))
            right_groups = group_activities(_activities(right.source))
            def _key(item: dict) -> tuple[str, str, str]:
                return (item["target_chembl_id"], item["standard_type"], item["standard_units"])

            left_keys = {_key(item) for item in left_groups}
            right_keys = {_key(item) for item in right_groups}
            shared = left_keys & right_keys
            if not shared:
                activity_notes.append(
                    {
                        "left_id": left.id,
                        "right_id": right.id,
                        "status": "not comparable",
                        "reason": "No activity group shares target, standard type, and units.",
                    }
                )
            else:
                activity_notes.append(
                    {
                        "left_id": left.id,
                        "right_id": right.id,
                        "status": "comparable groups",
                        "groups": [list(item) for item in sorted(shared)],
                    }
                )
    return {"compound_ids": [row.id for row in rows], "descriptors": table, "activities": activity_notes}


@router.post("/activities/compare")
def compare_activities(body: ActivityCompareRequest) -> dict:
    """Compare two retrieved activity records without merging unlike assays."""

    require_rdkit()
    return compare_activity_pair(body.left, body.right)


@router.post("/import/pubchem", status_code=201, response_model=CompoundResponse)
def import_pubchem(
    body: PubChemImport,
    request: Request,
    session: Session = Depends(get_session),
) -> CompoundResponse:
    require_rdkit()
    http: ExternalHttp = request.app.state.http
    record = lookup(http, body.query, body.query_type)
    smiles = record.get("connectivity_smiles") or record.get("canonical_smiles")
    if not isinstance(smiles, str) or not smiles:
        raise InvalidInput("PubChem did not return a SMILES string for this record.")
    settings: Settings = request.app.state.settings
    row, analysis, already = create_compound(smiles, session, settings, source=record)
    return _response(row, analysis, already)


@router.post("/import/chembl", status_code=201, response_model=CompoundResponse)
def import_chembl(
    body: ChemblImport,
    request: Request,
    session: Session = Depends(get_session),
) -> CompoundResponse:
    require_rdkit()
    http: ExternalHttp = request.app.state.http
    record = fetch_molecule(http, body.chembl_id)
    settings: Settings = request.app.state.settings
    row, analysis, already = create_compound(str(record["canonical_smiles"]), session, settings, source=record)
    return _response(row, analysis, already)


@router.get("/{compound_id}", response_model=CompoundResponse)
def fetch_one(compound_id: str, session: Session = Depends(get_session)) -> CompoundResponse:
    require_rdkit()
    return _with_analysis(session, get_compound(session, compound_id))


@router.get("/{compound_id}/depiction")
def depict(compound_id: str, session: Session = Depends(get_session)) -> Response:
    require_rdkit()
    row = get_compound(session, compound_id)
    svg = depiction_svg(row.canonical_smiles)
    return Response(content=svg, media_type="image/svg+xml")


def _activities(source: dict | None) -> list[dict]:
    if not source:
        return []
    activities = source.get("activities")
    return activities if isinstance(activities, list) else []
