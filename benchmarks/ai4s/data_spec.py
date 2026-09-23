"""A4S-3 data specification, frozen with the registration: cards, units, fault candidates.

Every unit and range below is from the dataset's UCI page (retrieved 2026-09-23) or, for the
superconductivity features, from Hamidieh (2018), Table 1. Nothing here is inferred.
"""
from __future__ import annotations

CONC = [
    "Cement (component 1)(kg in a m^3 mixture)",
    "Blast Furnace Slag (component 2)(kg in a m^3 mixture)",
    "Fly Ash (component 3)(kg in a m^3 mixture)",
    "Water  (component 4)(kg in a m^3 mixture)",
    "Superplasticizer (component 5)(kg in a m^3 mixture)",
    "Coarse Aggregate  (component 6)(kg in a m^3 mixture)",
    "Fine Aggregate (component 7)(kg in a m^3 mixture)",
    "Age (day)",
    "Concrete compressive strength(MPa, megapascals)",
]
SUPER = ["number_of_elements", "mean_atomic_mass", "mean_fie", "mean_atomic_radius",
         "mean_Density", "mean_ElectronAffinity", "mean_FusionHeat", "mean_ThermalConductivity",
         "mean_Valence", "range_atomic_radius", "wtd_mean_ThermalConductivity", "critical_temp"]

DATASETS = {
    "concrete": {
        "title": "Concrete Compressive Strength (UCI 165, Yeh 1998)",
        "columns": CONC,
        "units": {CONC[i]: "kg per m^3 of mixture" for i in range(7)} | {CONC[7]: "days",
                                                                          CONC[8]: "MPa"},
        "describe": "Mixture proportions of concrete samples, their age, and measured compressive strength.",
        "ranges": {},
        "nonneg": CONC,
        "continuous": [CONC[8]],
        "target": CONC[8],
        # F1: (column, factor, offset, what the converted rows become)
        "unit_mix": [(CONC[0], 1000.0, 0.0, "g per m^3"), (CONC[3], 1000.0, 0.0, "g per m^3"),
                     (CONC[8], 145.038, 0.0, "psi")],
    },
    "airfoil": {
        "title": "Airfoil Self-Noise (UCI 291, NASA)",
        "columns": ["frequency_Hz", "attack_angle_deg", "chord_length_m", "free_stream_velocity_m_s",
                    "suction_side_displacement_thickness_m", "scaled_sound_pressure_dB"],
        "units": {"frequency_Hz": "Hz", "attack_angle_deg": "degrees", "chord_length_m": "m",
                  "free_stream_velocity_m_s": "m/s", "suction_side_displacement_thickness_m": "m",
                  "scaled_sound_pressure_dB": "dB"},
        "describe": "NACA 0012 airfoil sections tested in an anechoic wind tunnel; scaled sound pressure level of self-noise.",
        "ranges": {},
        "nonneg": ["frequency_Hz", "chord_length_m", "free_stream_velocity_m_s",
                   "suction_side_displacement_thickness_m"],
        "continuous": ["chord_length_m", "free_stream_velocity_m_s",
                       "suction_side_displacement_thickness_m", "scaled_sound_pressure_dB"],
        "target": "scaled_sound_pressure_dB",
        "unit_mix": [("frequency_Hz", 0.001, 0.0, "kHz"), ("chord_length_m", 1000.0, 0.0, "mm"),
                     ("suction_side_displacement_thickness_m", 1000.0, 0.0, "mm")],
    },
    "ccpp": {
        "title": "Combined Cycle Power Plant (UCI 294, Tufekci 2014)",
        "columns": ["AT", "V", "AP", "RH", "PE"],
        "units": {"AT": "degrees C (ambient temperature)", "V": "cm Hg (exhaust vacuum)",
                  "AP": "millibar (ambient pressure)", "RH": "% (relative humidity)",
                  "PE": "MW (net hourly electrical energy output)"},
        "describe": "Hourly averages of ambient variables and net electrical output of a combined cycle power plant at full load.",
        "ranges": {"AT": (1.81, 37.11), "V": (25.36, 81.56), "AP": (992.89, 1033.30),
                   "RH": (25.56, 100.16), "PE": (420.26, 495.76)},
        "nonneg": ["V", "AP", "RH", "PE"],
        "continuous": ["AT", "V", "AP", "RH", "PE"],
        "target": "PE",
        "unit_mix": [("AT", 1.0, 273.15, "kelvin"), ("AP", 0.1, 0.0, "kPa"), ("PE", 1000.0, 0.0, "kW")],
    },
    "supercond": {
        "title": "Superconductivity Data (UCI 464, Hamidieh 2018), 11 features and the target",
        "columns": SUPER,
        "units": {"number_of_elements": "count", "mean_atomic_mass": "atomic mass units (mean over elements)",
                  "mean_fie": "kJ/mol (mean first ionization energy)",
                  "mean_atomic_radius": "pm (mean)", "mean_Density": "kg/m^3 (mean)",
                  "mean_ElectronAffinity": "kJ/mol (mean; the source adds 1.5 to every element's value)",
                  "mean_FusionHeat": "kJ/mol (mean)", "mean_ThermalConductivity": "W/(m K) (mean)",
                  "mean_Valence": "no units (mean)", "range_atomic_radius": "pm (max minus min)",
                  "wtd_mean_ThermalConductivity": "W/(m K) (weighted mean)",
                  "critical_temp": "K (critical temperature)"},
        "describe": "Features of superconducting compounds derived from elemental properties, and their critical temperature.",
        "ranges": {},
        "nonneg": SUPER,
        "continuous": ["mean_atomic_mass", "mean_ElectronAffinity", "mean_FusionHeat",
                       "wtd_mean_ThermalConductivity"],
        "target": "critical_temp",
        "unit_mix": [("critical_temp", 1.0, -273.15, "degrees C"), ("mean_atomic_radius", 0.01, 0.0, "angstrom"),
                     ("mean_Density", 0.001, 0.0, "g/cm^3")],
    },
}
FAULTS = ["F1", "F2", "F3", "F4", "F5", "F6", "F7"]
SENTINELS = {-999.0, -9999.0, 9999.0}


def card(name: str) -> str:
    d = DATASETS[name]
    lines = [f"# {d['title']}", "", d["describe"], "", "Source licence: CC BY 4.0.", "",
             "| column | unit | stated range |", "|---|---|---|"]
    for c in d["columns"]:
        r = d["ranges"].get(c)
        lines.append(f"| {c} | {d['units'].get(c, '')} | {f'{r[0]} to {r[1]}' if r else ''} |")
    lines += ["", f"Target column: {d['target']}.", ""]
    return "\n".join(lines)
