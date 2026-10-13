"""Side-by-side compound comparison. Assay groups are never merged across type or unit."""

from __future__ import annotations

from typing import Any


def compare_activity_pair(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Return comparable only when target, standard type, and units all match."""

    reasons = []
    if left.get("target_chembl_id") != right.get("target_chembl_id"):
        reasons.append("target identifiers differ")
    if left.get("standard_type") != right.get("standard_type"):
        reasons.append("standard types differ")
    if left.get("standard_units") != right.get("standard_units"):
        reasons.append("standard units differ")
    if reasons:
        return {"comparable": False, "reason": "; ".join(reasons)}
    return {
        "comparable": True,
        "target_chembl_id": left.get("target_chembl_id"),
        "standard_type": left.get("standard_type"),
        "standard_units": left.get("standard_units"),
        "left_value": left.get("standard_value"),
        "right_value": right.get("standard_value"),
        "left_relation": left.get("standard_relation"),
        "right_relation": right.get("standard_relation"),
    }


def group_activities(activities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One group per (target, standard type, units). Values inside a group are not averaged."""

    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for activity in activities:
        key = (
            str(activity.get("target_chembl_id") or ""),
            str(activity.get("standard_type") or ""),
            str(activity.get("standard_units") or ""),
        )
        groups.setdefault(key, []).append(activity)
    rows = []
    for (target, standard_type, units), items in sorted(groups.items()):
        rows.append(
            {
                "target_chembl_id": target,
                "standard_type": standard_type,
                "standard_units": units,
                "n": len(items),
                "values": [
                    {
                        "relation": item.get("standard_relation"),
                        "value": item.get("standard_value"),
                        "assay_chembl_id": item.get("assay_chembl_id"),
                        "document_chembl_id": item.get("document_chembl_id"),
                    }
                    for item in items
                ],
            }
        )
    return rows
