"""A4S-4 executable diagnosis rule: does a finding name the injected fault?

No model judges anything here. A faulty item counts as correctly diagnosed by a reading when at
least one of the reading's BLOCKER texts meets the rule for the item's fault, read from the
injection manifest:

  F1 mixed units, F2 negated values, F4 shuffled target, F6 sentinel, F7 rounding
      the text names the injected column (any alias below, word-bounded, case-insensitive);
  F5 swapped columns
      the text names both swapped columns;
  F3 duplicated rows
      the text contains a duplication term (duplicat*, identical row*, repeated row*, same row*).

The validator's diagnosis uses the same rule on its fired check names ("negative:<column>",
"duplicates", ...), so both tiers are scored by one function.

The alias table is frozen with the registration. Each alias is a name a reader could use for the
column: the column header itself, and for the long concrete headers their leading noun.
"""
from __future__ import annotations

import re

from data_spec import DATASETS

ALIASES: dict[str, dict[str, list[str]]] = {
    "concrete": {
        "Cement (component 1)(kg in a m^3 mixture)": ["cement"],
        "Blast Furnace Slag (component 2)(kg in a m^3 mixture)": ["blast furnace slag", "slag"],
        "Fly Ash (component 3)(kg in a m^3 mixture)": ["fly ash"],
        "Water  (component 4)(kg in a m^3 mixture)": ["water"],
        "Superplasticizer (component 5)(kg in a m^3 mixture)": ["superplasticizer", "superplasticiser"],
        "Coarse Aggregate  (component 6)(kg in a m^3 mixture)": ["coarse aggregate"],
        "Fine Aggregate (component 7)(kg in a m^3 mixture)": ["fine aggregate"],
        "Age (day)": ["age"],
        "Concrete compressive strength(MPa, megapascals)": ["compressive strength", "strength"],
    },
    "airfoil": {
        "frequency_Hz": ["frequency_hz", "frequency"],
        "attack_angle_deg": ["attack_angle_deg", "attack angle", "angle of attack"],
        "chord_length_m": ["chord_length_m", "chord length", "chord"],
        "free_stream_velocity_m_s": ["free_stream_velocity_m_s", "free-stream velocity",
                                     "free stream velocity", "velocity"],
        "suction_side_displacement_thickness_m": ["suction_side_displacement_thickness_m",
                                                  "displacement thickness", "suction side"],
        "scaled_sound_pressure_dB": ["scaled_sound_pressure_db", "sound pressure"],
    },
    "ccpp": {
        "AT": ["AT", "ambient temperature"],
        "V": ["V", "exhaust vacuum", "vacuum"],
        "AP": ["AP", "ambient pressure"],
        "RH": ["RH", "relative humidity", "humidity"],
        "PE": ["PE", "electrical energy output", "energy output", "net hourly electrical energy"],
    },
    "supercond": {c: [c.lower(), c.lower().replace("_", " ")] for c in DATASETS["supercond"]["columns"]},
}

DUP = re.compile(r"duplicat|identical rows?|repeated rows?|same rows?", re.I)


def _names(dataset: str, column: str, text: str) -> bool:
    for alias in ALIASES[dataset][column]:
        # word-bounded; "_" counts as a word character, so "at" does not match inside "mean_at"
        # an all-capitals alias (the power-plant headers AT, V, AP, RH, PE) matches case-sensitively,
        # so the English words "at" and "pe" never count
        flags = 0 if alias.isupper() else re.I
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(alias)}(?![A-Za-z0-9_])", text, flags):
            return True
    return False


def diagnoses(dataset: str, fault: str, params: dict, text: str) -> bool:
    """True if one text meets the rule for this item's injected fault."""
    if fault == "F3":
        return bool(DUP.search(text))
    if fault == "F5":
        a, b = params["columns"]
        return _names(dataset, a, text) and _names(dataset, b, text)
    return _names(dataset, params["column"], text)


def reading_diagnoses(dataset: str, fault: str, params: dict, blocker_texts: list[str]) -> bool:
    return any(diagnoses(dataset, fault, params, t) for t in blocker_texts)


def validator_texts(checks: list[str]) -> list[str]:
    """The validator's fired checks as one text the same rule can read ("negative:RH" -> "negative RH").

    One text, not one per check: a swap is diagnosed when the fired checks name both columns."""
    parts = []
    for c in checks:
        kind, _, col = c.partition(":")
        parts.append(f"{kind} {col}".strip() if kind != "duplicates" else "duplicate rows")
    return ["; ".join(parts)] if parts else []
