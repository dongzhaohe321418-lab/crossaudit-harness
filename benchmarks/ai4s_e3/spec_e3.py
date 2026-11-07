"""E3 data specification: twelve CC BY 4.0 UCI tables, their cards, and realistic fault parameters.

Units and stated ranges are taken from each dataset's UCI page (variable information, retrieved 2026-11-07
through ucimlrepo) or, for wine, from Cortez et al. (2009); nothing is inferred from the data. Four tables are
the earlier A4S-3 development sources (dev); eight are new and held out (test). ``rename`` maps the source's
column names to the names the card and CSV use.
"""
from __future__ import annotations

DATASETS = {
    # ---------------- dev (the A4S-3 sources) ----------------
    "concrete": {
        "split": "dev", "uci": 165, "title": "Concrete Compressive Strength (UCI 165, Yeh 1998)",
        "describe": "Mixture proportions of concrete samples, their age, and measured compressive strength.",
        "rename": {"Cement": "cement_kg_m3", "Blast Furnace Slag": "slag_kg_m3", "Fly Ash": "fly_ash_kg_m3",
                   "Water": "water_kg_m3", "Superplasticizer": "superplasticizer_kg_m3",
                   "Coarse Aggregate": "coarse_aggregate_kg_m3", "Fine Aggregate": "fine_aggregate_kg_m3",
                   "Age": "age_days", "Concrete compressive strength": "strength_MPa"},
        "units": {"cement_kg_m3": "kg per m^3 of mixture", "slag_kg_m3": "kg per m^3 of mixture",
                  "fly_ash_kg_m3": "kg per m^3 of mixture", "water_kg_m3": "kg per m^3 of mixture",
                  "superplasticizer_kg_m3": "kg per m^3 of mixture",
                  "coarse_aggregate_kg_m3": "kg per m^3 of mixture",
                  "fine_aggregate_kg_m3": "kg per m^3 of mixture", "age_days": "days", "strength_MPa": "MPa"},
        "ranges": {"age_days": (1, 365)}, "target": "strength_MPa",
        "unit_mix": [("cement_kg_m3", 1000.0, 0.0, "g per m^3"), ("strength_MPa", 145.038, 0.0, "psi")],
    },
    "airfoil": {
        "split": "dev", "uci": 291, "title": "Airfoil Self-Noise (UCI 291, NASA)",
        "describe": "NACA 0012 airfoil sections in an anechoic wind tunnel; scaled sound pressure level of self-noise.",
        "rename": {"frequency": "frequency_Hz", "attack-angle": "attack_angle_deg", "chord-length": "chord_length_m",
                   "free-stream-velocity": "velocity_m_s",
                   "suction-side-displacement-thickness": "displacement_thickness_m",
                   "scaled-sound-pressure": "sound_pressure_dB"},
        "units": {"frequency_Hz": "Hz", "attack_angle_deg": "degrees", "chord_length_m": "m",
                  "velocity_m_s": "m/s", "displacement_thickness_m": "m", "sound_pressure_dB": "dB"},
        "ranges": {}, "target": "sound_pressure_dB",
        "unit_mix": [("frequency_Hz", 0.001, 0.0, "kHz"), ("chord_length_m", 1000.0, 0.0, "mm")],
    },
    "ccpp": {
        "split": "dev", "uci": 294, "title": "Combined Cycle Power Plant (UCI 294, Tufekci 2014)",
        "describe": "Hourly averages of ambient variables and net electrical output of a power plant at full load.",
        "rename": {"AT": "AT", "V": "V", "AP": "AP", "RH": "RH", "PE": "PE"},
        "units": {"AT": "degrees C (ambient temperature)", "V": "cm Hg (exhaust vacuum)",
                  "AP": "millibar (ambient pressure)", "RH": "% (relative humidity)",
                  "PE": "MW (net hourly electrical output)"},
        "ranges": {"AT": (1.81, 37.11), "V": (25.36, 81.56), "AP": (992.89, 1033.30), "RH": (25.56, 100.16),
                   "PE": (420.26, 495.76)}, "target": "PE",
        "unit_mix": [("AT", 1.0, 273.15, "kelvin"), ("AP", 0.1, 0.0, "kPa"), ("PE", 1000.0, 0.0, "kW")],
    },
    "supercond": {
        "split": "dev", "uci": 464, "title": "Superconductivity Data (UCI 464, Hamidieh 2018), selected columns",
        "describe": "Features of superconducting compounds derived from elemental properties, and their critical temperature.",
        "rename": {"number_of_elements": "number_of_elements", "mean_atomic_mass": "mean_atomic_mass",
                   "mean_fie": "mean_fie", "mean_atomic_radius": "mean_atomic_radius",
                   "mean_Density": "mean_Density", "mean_ThermalConductivity": "mean_ThermalConductivity",
                   "mean_Valence": "mean_Valence", "critical_temp": "critical_temp"},
        "units": {"number_of_elements": "count", "mean_atomic_mass": "atomic mass units (mean)",
                  "mean_fie": "kJ/mol (mean first ionization energy)", "mean_atomic_radius": "pm (mean)",
                  "mean_Density": "kg/m^3 (mean)", "mean_ThermalConductivity": "W/(m K) (mean)",
                  "mean_Valence": "no units (mean)", "critical_temp": "K"},
        "ranges": {}, "target": "critical_temp",
        "unit_mix": [("critical_temp", 1.0, -273.15, "degrees C"), ("mean_Density", 0.001, 0.0, "g/cm^3")],
    },
    # ---------------- test (held out, new) ----------------
    "gasturbine": {
        "split": "test", "uci": 551, "title": "Gas Turbine CO and NOx Emission (UCI 551, Kaya et al. 2019)",
        "describe": "Hourly sensor measurements of a gas turbine in Turkey, with CO and NOx emissions.",
        "rename": {"AT": "AT", "AP": "AP", "AH": "AH", "AFDP": "AFDP", "GTEP": "GTEP", "TIT": "TIT", "TAT": "TAT",
                   "CDP": "CDP", "TEY": "TEY", "CO": "CO", "NOX": "NOX"},
        "units": {"AT": "degrees C (ambient temperature)", "AP": "mbar (ambient pressure)",
                  "AH": "% (ambient humidity)", "AFDP": "mbar (air filter difference pressure)",
                  "GTEP": "mbar (exhaust pressure)", "TIT": "degrees C (turbine inlet temperature)",
                  "TAT": "degrees C (turbine after temperature)", "CDP": "mbar (compressor discharge pressure)",
                  "TEY": "MWh (turbine energy yield)", "CO": "mg/m^3", "NOX": "mg/m^3"},
        "ranges": {"AT": (-6.23, 37.10), "AP": (985.85, 1036.56), "AH": (24.08, 100.20), "AFDP": (2.09, 7.61),
                   "GTEP": (17.70, 40.72), "TIT": (1000.85, 1100.89), "TAT": (511.04, 550.61),
                   "CDP": (9.85, 15.16), "TEY": (100.02, 179.50), "CO": (0.00, 44.10), "NOX": (25.90, 119.91)},
        "target": "NOX",
        "unit_mix": [("TIT", 1.0, 273.15, "kelvin"), ("AP", 0.1, 0.0, "kPa"), ("NOX", 1000.0, 0.0, "microg/m^3")],
    },
    "steel": {
        "split": "test", "uci": 851, "title": "Steel Industry Energy Consumption (UCI 851, DAEWOO Steel)",
        "describe": "Fifteen-minute electricity measurements of a steel plant in Korea.",
        "rename": {"Usage_kWh": "usage_kWh", "Lagging_Current_Reactive.Power_kVarh": "lagging_reactive_kVarh",
                   "Leading_Current_Reactive_Power_kVarh": "leading_reactive_kVarh", "CO2(tCO2)": "CO2_ppm",
                   "Lagging_Current_Power_Factor": "lagging_power_factor_pct",
                   "Leading_Current_Power_Factor": "leading_power_factor_pct", "NSM": "seconds_from_midnight"},
        "units": {"usage_kWh": "kWh", "lagging_reactive_kVarh": "kVarh", "leading_reactive_kVarh": "kVarh",
                  "CO2_ppm": "ppm", "lagging_power_factor_pct": "%", "leading_power_factor_pct": "%",
                  "seconds_from_midnight": "s"},
        "ranges": {"lagging_power_factor_pct": (0, 100), "leading_power_factor_pct": (0, 100),
                   "seconds_from_midnight": (0, 86400)}, "target": "usage_kWh",
        "unit_mix": [("usage_kWh", 1000.0, 0.0, "Wh"), ("lagging_power_factor_pct", 0.01, 0.0, "fraction")],
    },
    "appliances": {
        "split": "test", "uci": 374, "title": "Appliances Energy Prediction (UCI 374, Candanedo et al. 2017)",
        "describe": "Ten-minute house energy use with indoor and weather-station conditions, Belgium.",
        "rename": {"Appliances": "appliances_Wh", "lights": "lights_Wh", "T1": "T1", "RH_1": "RH_1", "T2": "T2",
                   "RH_2": "RH_2", "T_out": "T_out", "Press_mm_hg": "press_mm_hg", "RH_out": "RH_out",
                   "Windspeed": "windspeed", "Visibility": "visibility", "Tdewpoint": "Tdewpoint"},
        "units": {"appliances_Wh": "Wh", "lights_Wh": "Wh", "T1": "degrees C (kitchen)", "RH_1": "% (kitchen)",
                  "T2": "degrees C (living room)", "RH_2": "% (living room)", "T_out": "degrees C (outside)",
                  "press_mm_hg": "mm Hg", "RH_out": "% (outside)", "windspeed": "m/s", "visibility": "km",
                  "Tdewpoint": "degrees C"},
        "ranges": {"RH_1": (0, 100), "RH_2": (0, 100), "RH_out": (0, 100)}, "target": "appliances_Wh",
        "unit_mix": [("T_out", 1.8, 32.0, "degrees F"), ("press_mm_hg", 1.33322, 0.0, "hPa")],
    },
    "household": {
        "split": "test", "uci": 235, "title": "Individual Household Electric Power Consumption (UCI 235, EDF)",
        "describe": "Minute-averaged electrical measurements of one household near Paris.",
        "rename": {"Global_active_power": "global_active_power_kW", "Global_reactive_power": "global_reactive_power_kW",
                   "Voltage": "voltage_V", "Global_intensity": "global_intensity_A",
                   "Sub_metering_1": "sub_metering_1_Wh", "Sub_metering_2": "sub_metering_2_Wh",
                   "Sub_metering_3": "sub_metering_3_Wh"},
        "units": {"global_active_power_kW": "kW (minute-averaged active power)",
                  "global_reactive_power_kW": "kW (minute-averaged reactive power)",
                  "voltage_V": "V (minute-averaged)", "global_intensity_A": "A (minute-averaged current)",
                  "sub_metering_1_Wh": "Wh of active energy (kitchen)",
                  "sub_metering_2_Wh": "Wh of active energy (laundry)",
                  "sub_metering_3_Wh": "Wh of active energy (water heater, air conditioning)"},
        "ranges": {}, "target": "global_active_power_kW",
        "unit_mix": [("global_active_power_kW", 1000.0, 0.0, "W"), ("voltage_V", 0.001, 0.0, "kV")],
    },
    "wine": {
        "split": "test", "uci": 186, "title": "Wine Quality (UCI 186, Cortez et al. 2009)",
        "describe": "Physicochemical tests of Portuguese vinho verde wines and a sensory quality score.",
        "rename": {"fixed_acidity": "fixed_acidity", "volatile_acidity": "volatile_acidity",
                   "citric_acid": "citric_acid", "residual_sugar": "residual_sugar", "chlorides": "chlorides",
                   "free_sulfur_dioxide": "free_sulfur_dioxide", "total_sulfur_dioxide": "total_sulfur_dioxide",
                   "density": "density", "pH": "pH", "sulphates": "sulphates", "alcohol": "alcohol",
                   "quality": "quality"},
        "units": {"fixed_acidity": "g(tartaric acid)/dm^3", "volatile_acidity": "g(acetic acid)/dm^3",
                  "citric_acid": "g/dm^3", "residual_sugar": "g/dm^3", "chlorides": "g(sodium chloride)/dm^3",
                  "free_sulfur_dioxide": "mg/dm^3", "total_sulfur_dioxide": "mg/dm^3", "density": "g/cm^3",
                  "pH": "pH units", "sulphates": "g(potassium sulphate)/dm^3", "alcohol": "% vol",
                  "quality": "score 0-10"},
        "ranges": {"quality": (0, 10), "pH": (0, 14)}, "target": "quality",
        "unit_mix": [("density", 1000.0, 0.0, "kg/m^3"), ("total_sulfur_dioxide", 0.001, 0.0, "g/dm^3")],
    },
    "abalone": {
        "split": "test", "uci": 1, "title": "Abalone (UCI 1, Nash et al. 1994)",
        "describe": "Physical measurements of abalone and the number of shell rings.",
        "rename": {"Length": "length_mm", "Diameter": "diameter_mm", "Height": "height_mm",
                   "Whole_weight": "whole_weight_g", "Shucked_weight": "shucked_weight_g",
                   "Viscera_weight": "viscera_weight_g", "Shell_weight": "shell_weight_g", "Rings": "rings"},
        "units": {"length_mm": "mm/200 (longest shell; the source divides by 200)",
                  "diameter_mm": "mm/200", "height_mm": "mm/200", "whole_weight_g": "grams/200",
                  "shucked_weight_g": "grams/200", "viscera_weight_g": "grams/200", "shell_weight_g": "grams/200",
                  "rings": "count (+1.5 gives age in years)"},
        "ranges": {}, "target": "rings",
        "unit_mix": [("length_mm", 200.0, 0.0, "mm, unscaled"), ("whole_weight_g", 200.0, 0.0, "grams, unscaled")],
    },
    "gridstab": {
        "split": "test", "uci": 471, "title": "Electrical Grid Stability Simulated Data (UCI 471, Arzamasov 2018)",
        "describe": "Simulated four-node star electrical grid: reaction times, power, price elasticity, stability.",
        "rename": {"tau1": "tau1", "tau2": "tau2", "tau3": "tau3", "tau4": "tau4", "p1": "p1", "p2": "p2",
                   "p3": "p3", "p4": "p4", "g1": "g1", "g2": "g2", "g3": "g3", "g4": "g4", "stab": "stab"},
        "units": {"tau1": "s (reaction time, producer)", "tau2": "s", "tau3": "s", "tau4": "s",
                  "p1": "s^-2 (nominal power produced)", "p2": "s^-2 (consumed, negative)", "p3": "s^-2 (negative)",
                  "p4": "s^-2 (negative)", "g1": "s^-1 (price elasticity coefficient)", "g2": "s^-1",
                  "g3": "s^-1", "g4": "s^-1", "stab": "s^-1 (max real part of characteristic root)"},
        "ranges": {"tau1": (0.5, 10), "tau2": (0.5, 10), "tau3": (0.5, 10), "tau4": (0.5, 10),
                   "p2": (-2, -0.5), "p3": (-2, -0.5), "p4": (-2, -0.5), "g1": (0.05, 1), "g2": (0.05, 1),
                   "g3": (0.05, 1), "g4": (0.05, 1)}, "target": "stab",
        "unit_mix": [("tau1", 1000.0, 0.0, "ms"), ("g2", 60.0, 0.0, "min^-1")],
    },
    "airquality": {
        "split": "test", "uci": 360, "title": "Air Quality (UCI 360, De Vito et al. 2008), reference analysers",
        "describe": "Hourly reference-analyser concentrations and weather at an Italian city road site.",
        "rename": {"CO(GT)": "CO_mg_m3", "C6H6(GT)": "benzene_ug_m3", "NOx(GT)": "NOx_ppb", "NO2(GT)": "NO2_ug_m3",
                   "T": "T", "RH": "RH", "AH": "AH"},
        "units": {"CO_mg_m3": "mg/m^3", "benzene_ug_m3": "microg/m^3", "NOx_ppb": "ppb", "NO2_ug_m3": "microg/m^3",
                  "T": "degrees C", "RH": "%", "AH": "absolute humidity"},
        "ranges": {"RH": (0, 100)}, "target": "NO2_ug_m3",
        "missing_marker": -200.0,
        "unit_mix": [("CO_mg_m3", 1000.0, 0.0, "microg/m^3"), ("T", 1.8, 32.0, "degrees F")],
    },
}

FAULTS = ["F1", "F2", "F3", "F4", "F5", "F6", "F7"]
FAULT_NAMES = {"F1": "mixed_units", "F2": "negated_values", "F3": "duplicated_rows", "F4": "shuffled_target",
               "F5": "swapped_columns", "F6": "sentinel_values", "F7": "rounding"}
SENTINELS = {-999.0, -9999.0, 9999.0}
SIZES = (120, 1200, 12000)


def columns(name: str) -> list[str]:
    return list(DATASETS[name]["rename"].values())


def nonneg(name: str) -> list[str]:
    """Columns whose physical quantity cannot be negative, judged from the card's units alone."""
    d = DATASETS[name]
    out = []
    for c in columns(name):
        u = d["units"].get(c, "").lower()
        if "degrees c" in u or "negative" in u or c in ("stab", "p1", "AT", "T_out", "Tdewpoint", "T") or "s^-2" in u:
            continue
        out.append(c)
    return out


def card(name: str) -> str:
    d = DATASETS[name]
    lines = [f"# {d['title']}", "", d["describe"], "", "Source licence: CC BY 4.0.", "",
             "| column | unit | stated range |", "|---|---|---|"]
    for c in columns(name):
        r = d["ranges"].get(c)
        lines.append(f"| {c} | {d['units'].get(c, '')} | {f'{r[0]} to {r[1]}' if r else ''} |")
    lines += ["", f"Target column: {d['target']}.", "",
              "Each row is one independent observation; rows are in arbitrary order.", ""]
    return "\n".join(lines)
