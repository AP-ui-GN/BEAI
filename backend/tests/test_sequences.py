"""Sequence statistics and alignment.

The ubiquitin sequence is built from SEQRES names in 1UBQ.pdb and the bundled
chemical-component one-letter codes. It is not typed from memory.

Molecular weight is checked against an independent sum of free amino-acid
elemental formulas. Atomic weights are the conventional IUPAC values
C 12.0107, H 1.00794, N 14.0067, O 15.9994, S 32.065. The polypeptide mass is
the sum of those free-amino-acid masses minus (n - 1) water molecules, where
water is 2H+O from the same weights. Biopython subtracts 18.0153 Da per bond.
The acceptance window is 1 Da.
"""

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.services.structure.ccd import component_table
from backend.app.services.structure.header import read_sequences

FIXTURES = Path(__file__).parent / "fixtures"

_ATOMIC = {"C": 12.0107, "H": 1.00794, "N": 14.0067, "O": 15.9994, "S": 32.065}
# Free amino-acid elemental counts (C, H, N, O, S), not residue masses copied from Biopython.
_FORMULA = {
    "A": (3, 7, 1, 2, 0),
    "R": (6, 14, 4, 2, 0),
    "N": (4, 8, 2, 3, 0),
    "D": (4, 7, 1, 4, 0),
    "C": (3, 7, 1, 2, 1),
    "E": (5, 9, 1, 4, 0),
    "Q": (5, 10, 2, 3, 0),
    "G": (2, 5, 1, 2, 0),
    "H": (6, 9, 3, 2, 0),
    "I": (6, 13, 1, 2, 0),
    "L": (6, 13, 1, 2, 0),
    "K": (6, 14, 2, 2, 0),
    "M": (5, 11, 1, 2, 1),
    "F": (9, 11, 1, 2, 0),
    "P": (5, 9, 1, 2, 0),
    "S": (3, 7, 1, 3, 0),
    "T": (4, 9, 1, 3, 0),
    "W": (11, 12, 2, 2, 0),
    "Y": (9, 11, 1, 3, 0),
    "V": (5, 11, 1, 2, 0),
}


def _free_mass(counts: tuple[int, int, int, int, int]) -> float:
    carbon, hydrogen, nitrogen, oxygen, sulfur = counts
    return (
        carbon * _ATOMIC["C"]
        + hydrogen * _ATOMIC["H"]
        + nitrogen * _ATOMIC["N"]
        + oxygen * _ATOMIC["O"]
        + sulfur * _ATOMIC["S"]
    )


def _polypeptide_mass(sequence: str) -> float:
    water = 2 * _ATOMIC["H"] + _ATOMIC["O"]
    total = sum(_free_mass(_FORMULA[letter]) for letter in sequence)
    return total - (len(sequence) - 1) * water


def ubiquitin_sequence() -> str:
    parsed = read_sequences(FIXTURES / "1UBQ.pdb", "pdb")
    table = component_table()
    letters: list[str] = []
    for name in parsed[0].residue_names:
        component = table.get(name)
        assert component is not None and component.one_letter
        letters.append(component.one_letter)
    return "".join(letters)


def _measurement(result: dict, name: str) -> dict:
    matches = [item for item in result["measurements"] if item["name"] == name]
    assert len(matches) == 1, name
    return matches[0]


def test_ubiquitin_length_and_mass_match_an_independent_sum(client: TestClient) -> None:
    sequence = ubiquitin_sequence()
    assert len(sequence) == 76
    created = client.post("/api/sequences", json={"text": f">1UBQ chain A SEQRES\n{sequence}\n"})
    assert created.status_code == 201, created.text
    body = created.json()["sequences"][0]
    assert body["length"] == 76
    result = body["analysis"]["result"]
    assert _measurement(result, "length")["value"] == 76
    expected = _polypeptide_mass(sequence)
    reported = _measurement(result, "molecular_weight")["value"]
    assert abs(reported - expected) <= 1.0
    assert _measurement(result, "molecular_weight")["origin"] == "calculated"
    assert _measurement(result, "molecular_weight")["unit"] == "dalton"
    assert "18.0153" in _measurement(result, "molecular_weight")["method"]


def test_invalid_characters_are_rejected_and_store_nothing(client: TestClient) -> None:
    rejected = client.post("/api/sequences", json={"text": ">bad\nACDE1\n"})
    assert rejected.status_code == 422
    assert rejected.json()["code"] == "invalid_input"
    listing = client.get("/api/sequences")
    assert listing.status_code == 200
    assert listing.json()["sequences"] == []


def test_one_bad_record_in_a_fasta_stores_nothing(client: TestClient) -> None:
    text = ">ok\nACDE\n>bad\nACDE*\nACDE\n"
    rejected = client.post("/api/sequences", json={"text": text})
    assert rejected.status_code == 422
    assert client.get("/api/sequences").json()["sequences"] == []


def test_lowercase_gaps_and_terminal_stop_are_normalised(client: TestClient) -> None:
    created = client.post("/api/sequences", json={"text": ">pep\nac-de*\n"})
    assert created.status_code == 201, created.text
    body = created.json()["sequences"][0]
    assert body["sequence"] == "ACDE"
    assert any("gap" in message.lower() for message in body["validation_messages"])
    assert any("stop" in message.lower() for message in body["validation_messages"])


def test_ambiguous_sequence_keeps_mass_null(client: TestClient) -> None:
    created = client.post("/api/sequences", json={"text": ">amb\nACXDE\n"})
    assert created.status_code == 201, created.text
    result = created.json()["sequences"][0]["analysis"]["result"]
    assert _measurement(result, "molecular_weight")["value"] is None
    assert _measurement(result, "isoelectric_point")["value"] is None
    assert any(item["stage"] == "molecular_weight" for item in result["skipped_stages"])


def test_self_alignment_identity_is_one_and_different_lengths_align(client: TestClient) -> None:
    sequence = ubiquitin_sequence()
    created = client.post(
        "/api/sequences",
        json={"text": f">full\n{sequence}\n>prefix\n{sequence[:20]}\n"},
    )
    assert created.status_code == 201, created.text
    rows = created.json()["sequences"]
    full_id = next(item["id"] for item in rows if item["header"] == "full")
    prefix_id = next(item["id"] for item in rows if item["header"] == "prefix")
    same = client.post("/api/sequences/align", json={"left_id": full_id, "right_id": full_id})
    assert same.status_code == 201, same.text
    result = same.json()["result"]
    assert _measurement(result, "identity_over_aligned_pairs")["value"] == 1.0
    assert "not a statement of homology" in " ".join(result["limitations"]).lower() or any(
        "homology" in item.lower() for item in result["limitations"]
    )
    different = client.post("/api/sequences/align", json={"left_id": full_id, "right_id": prefix_id})
    assert different.status_code == 201, different.text
    different_result = different.json()["result"]
    assert _measurement(different_result, "alignment_column_count")["value"] >= 76
    alignment = different_result["details"]["alignment"]
    assert "-" in alignment["left"] or "-" in alignment["right"]
