"""Transparent ranking. There is no default composite score.

Activity values are comparable only when target, standard type, and units match.
A difference smaller than the seed-to-seed spread is not treated as meaningful.
"""

from __future__ import annotations

from typing import Any


def pareto_flags(rows: list[dict[str, Any]], columns: list[str], senses: dict[str, str]) -> list[bool]:
    """True when no other row is better in every column and strictly better in one.

    ``senses`` values are ``min`` or ``max``. Missing values cannot dominate.
    """

    flags = []
    for index, row in enumerate(rows):
        dominated = False
        for other_index, other in enumerate(rows):
            if other_index == index:
                continue
            better_or_equal = True
            strictly = False
            for column in columns:
                if row.get(column) is None or other.get(column) is None:
                    better_or_equal = False
                    break
                sense = senses[column]
                if sense == "min":
                    if other[column] > row[column]:
                        better_or_equal = False
                        break
                    if other[column] < row[column]:
                        strictly = True
                else:
                    if other[column] < row[column]:
                        better_or_equal = False
                        break
                    if other[column] > row[column]:
                        strictly = True
            if better_or_equal and strictly:
                dominated = True
                break
        flags.append(not dominated)
    return flags
