"""
GNPy universal schema definitions.

This module is the single source of truth for:
  * Enumerated options (constants) used across the input generator.
  * Field specifications (incl. conditional/interdependent fields) for each
    GNPy equipment category, so editors can be rendered dynamically.
  * Builders that emit clean, GNPy-standard objects (only the fields that are
    valid for the chosen discriminator, e.g. EDFA ``type_def``).
  * Validators that check interdependencies and frequency coherence.

It is intentionally free of any UI framework imports so it stays easy to test
and reuse. The Streamlit app consumes these specs through a generic renderer.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

# =============================================================================
# Field type tokens (consumed by the renderer in the app)
# =============================================================================
TEXT = "text"
FLOAT = "float"
FLOAT_SCI = "float_sci"  # rendered with scientific format, e.g. frequencies in Hz
INT = "int"
BOOL = "bool"
SELECT = "select"
LIST_FLOAT = "list_float"  # comma-separated list of floats (e.g. nf_coef)
REF_SELECT = "ref_select"  # single choice from known type_variety names
REF_MULTISELECT = "ref_multiselect"  # multiple choices from known type_variety names


def field(
    key: str,
    label: str,
    ftype: str,
    default: Any,
    *,
    help: str = "",
    required: bool = False,
    fmt: Optional[str] = None,
    options: Optional[list] = None,
    optional_group: Optional[str] = None,
) -> dict:
    """Build a single field specification.

    ``optional_group`` lets the renderer tuck non-mandatory fields behind an
    expander so the common path stays clean.
    """
    spec: dict[str, Any] = {
        "key": key,
        "label": label,
        "type": ftype,
        "default": default,
        "help": help,
        "required": required,
    }
    if fmt is not None:
        spec["format"] = fmt
    if options is not None:
        spec["options"] = options
    if optional_group is not None:
        spec["optional_group"] = optional_group
    return spec


# =============================================================================
# Enumerated options (constants)
# =============================================================================
# EDFA noise/gain models. The chosen value decides which fields are valid.
EDFA_TYPE_DEFS: list[str] = [
    "variable_gain",
    "fixed_gain",
    "openroadm",
    "openroadm_preamp",
    "openroadm_booster",
    "advanced_model",
    "dual_stage",
    "multi_band",
]

# Single-band models that can be combined inside a multi_band / dual_stage.
EDFA_SINGLE_BAND_TYPE_DEFS: list[str] = [
    "variable_gain",
    "fixed_gain",
    "openroadm",
    "openroadm_preamp",
    "openroadm_booster",
    "advanced_model",
]

# Topology element types.
NODE_TYPES: list[str] = ["Transceiver", "Roadm", "Edfa", "Multiband_amplifier", "Fused"]
FIBER_ELEMENT_TYPES: list[str] = ["Fiber", "RamanFiber"]
ALL_ELEMENT_TYPES: list[str] = NODE_TYPES + FIBER_ELEMENT_TYPES

LENGTH_UNITS: list[str] = ["km", "m"]

# ROADM equalization strategies are mutually exclusive.
ROADM_EQUALIZATION_STRATEGIES: list[str] = [
    "target_pch_out_db",
    "target_psd_out_mWperGHz",
    "target_out_mWperSlotWidth",
]

# Raman pump propagation directions.
PROPAGATION_DIRECTIONS: list[str] = ["coprop", "counterprop"]

# sim_params.json choices.
RAMAN_METHODS: list[str] = ["perturbative", "numerical"]
NLI_METHODS: list[str] = [
    "gn_model_analytic",
    "ggn_spectrally_separated",
    "ggn_approx",
]

# Service path-constraint choices.
TECHNOLOGY_CHOICES: list[str] = ["flexi-grid"]
HOP_TYPES: list[str] = ["STRICT", "LOOSE"]

# Reference C-band spectrum boundaries (GNPy defaults). Used only as starting
# values / coherence hints; frequencies remain user-editable.
DEFAULT_F_MIN_HZ: float = 191.3e12
DEFAULT_F_MAX_HZ: float = 196.1e12
# Amplifier bandwidth default (slightly wider than the SI default per GNPy docs).
DEFAULT_AMP_F_MIN_HZ: float = 191.275e12
DEFAULT_AMP_F_MAX_HZ: float = 196.125e12


# =============================================================================
# EDFA (Edfa) field specifications — conditional on type_def
# =============================================================================
def _edfa_freq_fields() -> list[dict]:
    """Optional amplifier bandwidth bounds, shared by single-band models."""
    return [
        field(
            "f_min", "f_min (Hz)", FLOAT_SCI, DEFAULT_AMP_F_MIN_HZ,
            help="Optional. Amplifier bandwidth lower bound. The entire channel "
                 "(center frequency + spectrum width) must fit within [f_min, f_max].",
            fmt="%.4e", optional_group="Frequency range (optional)",
        ),
        field(
            "f_max", "f_max (Hz)", FLOAT_SCI, DEFAULT_AMP_F_MAX_HZ,
            help="Optional. Amplifier bandwidth upper bound.",
            fmt="%.4e", optional_group="Frequency range (optional)",
        ),
    ]


def _edfa_gain_power_fields() -> list[dict]:
    return [
        field("gain_flatmax", "gain_flatmax (dB)", FLOAT, 26.0,
              help="Maximum flat gain.", required=True),
        field("gain_min", "gain_min (dB)", FLOAT, 15.0,
              help="Minimum gain.", required=True),
        field("p_max", "p_max (dBm)", FLOAT, 23.0,
              help="Maximum total output power.", required=True),
    ]


def edfa_field_specs(type_def: str, *, known_varieties: Optional[list[str]] = None) -> list[dict]:
    """Return ordered field specs valid for the given EDFA ``type_def``.

    ``known_varieties`` populates reference selectors for dual_stage / multi_band.
    """
    known_varieties = known_varieties or []
    type_variety = field(
        "type_variety", "type_variety *", TEXT, "",
        help="Unique name used to reference this amplifier in the topology.",
        required=True,
    )
    allowed = field(
        "allowed_for_design", "allowed_for_design", BOOL, True,
        help="If false, auto-design will not pick this amplifier, but it can "
             "still be used as a manual input in topology files.",
    )

    if type_def == "variable_gain":
        return [
            type_variety,
            *_edfa_gain_power_fields(),
            field("nf_min", "nf_min (dB)", FLOAT, 6.0, help="Min noise figure (used for 2-stage NF calc).", required=True),
            field("nf_max", "nf_max (dB)", FLOAT, 10.0, help="Max noise figure (used for 2-stage NF calc).", required=True),
            field("out_voa_auto", "out_voa_auto", BOOL, False,
                  help="Auto-design optimizes output VOA to push gain to max within EOL margins."),
            *_edfa_freq_fields(),
            field("default_config_from_json", "default_config_from_json", TEXT, "",
                  help="Optional. Filename of a config providing DGT, NF ripple and gain ripple.",
                  optional_group="Advanced (optional)"),
            allowed,
        ]

    if type_def == "fixed_gain":
        return [
            type_variety,
            *_edfa_gain_power_fields(),
            field("nf0", "nf0 (dB)", FLOAT, 6.0,
                  help="Constant noise figure: NF == nf0 when gain_min < gain < gain_flatmax.", required=True),
            *_edfa_freq_fields(),
            field("default_config_from_json", "default_config_from_json", TEXT, "",
                  help="Optional. Filename of a config providing DGT, NF ripple and gain ripple.",
                  optional_group="Advanced (optional)"),
            allowed,
        ]

    if type_def == "openroadm":
        return [
            type_variety,
            *_edfa_gain_power_fields(),
            field("nf_coef", "nf_coef [4 coefficients]", LIST_FLOAT, [-8.104e-4, -6.221e-2, -5.889e-1, 37.62],
                  help="Coefficients of the 3rd-degree polynomial modelling incremental OSNR vs input power.",
                  required=True),
            *_edfa_freq_fields(),
            allowed,
        ]

    if type_def in ("openroadm_preamp", "openroadm_booster"):
        return [
            type_variety,
            *_edfa_gain_power_fields(),
            field("pmd", "pmd (s)", FLOAT, 0.0, help="Polarization mode dispersion.",
                  optional_group="Impairments (optional)"),
            field("pdl", "pdl (dB)", FLOAT, 0.0, help="Polarization dependent loss.",
                  optional_group="Impairments (optional)"),
            *_edfa_freq_fields(),
            allowed,
        ]

    if type_def == "advanced_model":
        return [
            type_variety,
            *_edfa_gain_power_fields(),
            field("advanced_config_from_json", "advanced_config_from_json *", TEXT, "",
                  help="Filename of the detailed JSON config (NF = f(gain), NF/gain ripple, DGT). "
                       "Required for advanced_model.", required=True),
            field("out_voa_auto", "out_voa_auto", BOOL, False,
                  help="Auto-design optimizes output VOA."),
            *_edfa_freq_fields(),
            allowed,
        ]

    if type_def == "dual_stage":
        return [
            type_variety,
            field("gain_min", "gain_min (dB)", FLOAT, 25.0,
                  help="Minimum total gain across the two cascaded stages.", required=True),
            field("preamp_variety", "preamp_variety *", REF_SELECT, "",
                  help="type_variety of the first stage (must already exist in the library).",
                  options=known_varieties, required=True),
            field("booster_variety", "booster_variety *", REF_SELECT, "",
                  help="type_variety of the second stage (must already exist in the library).",
                  options=known_varieties, required=True),
            field("raman", "raman", BOOL, False,
                  help="Mark this dual-stage as a Raman-EDFA hybrid (informational).",
                  optional_group="Advanced (optional)"),
            allowed,
        ]

    if type_def == "multi_band":
        return [
            type_variety,
            field("amplifiers", "amplifiers *", REF_MULTISELECT, [],
                  help="List of single-band amplifier type_varieties that compose this multiband site.",
                  options=known_varieties, required=True),
            allowed,
        ]

    # Fallback: just the identifier so the UI never breaks on an unknown value.
    return [type_variety, allowed]


def default_edfa(type_def: str = "variable_gain") -> dict:
    """Return a clean default EDFA object for the given type_def."""
    data: dict[str, Any] = {"type_variety": "", "type_def": type_def}
    for spec in edfa_field_specs(type_def):
        if spec["key"] == "type_variety":
            continue
        data[spec["key"]] = spec["default"]
    return data


def build_edfa(values: dict, type_def: str) -> dict:
    """Assemble a GNPy-standard EDFA object containing ONLY valid fields.

    Empty optional strings are dropped so the output stays clean.
    """
    out: dict[str, Any] = {
        "type_variety": str(values.get("type_variety", "")).strip(),
        "type_def": type_def,
    }
    for spec in edfa_field_specs(type_def):
        key = spec["key"]
        if key == "type_variety":
            continue
        val = values.get(key, spec["default"])
        # Drop empty optional text fields (e.g. unset *_config_from_json).
        if spec["type"] == TEXT and not spec.get("required") and not str(val).strip():
            continue
        out[key] = val
    return out


def validate_edfa(data: dict, known_varieties: Optional[list[str]] = None) -> tuple[list[str], list[str]]:
    """Validate one EDFA object. Returns (errors, warnings)."""
    known_varieties = known_varieties or []
    errors: list[str] = []
    warnings: list[str] = []

    type_def = data.get("type_def")
    if not str(data.get("type_variety", "")).strip():
        errors.append("type_variety is required.")
    if type_def not in EDFA_TYPE_DEFS:
        errors.append(f"Unknown type_def '{type_def}'.")
        return errors, warnings

    # Gain sanity for single-band models that expose both bounds.
    if {"gain_min", "gain_flatmax"} <= data.keys():
        try:
            if float(data["gain_min"]) > float(data["gain_flatmax"]):
                errors.append("gain_min must be <= gain_flatmax.")
        except (TypeError, ValueError):
            pass

    # Frequency coherence.
    if {"f_min", "f_max"} <= data.keys():
        try:
            if float(data["f_min"]) >= float(data["f_max"]):
                errors.append("f_min must be < f_max.")
        except (TypeError, ValueError):
            pass

    # Cross-references.
    if type_def == "dual_stage":
        for ref_key in ("preamp_variety", "booster_variety"):
            ref = str(data.get(ref_key, "")).strip()
            if not ref:
                errors.append(f"{ref_key} is required for dual_stage.")
            elif known_varieties and ref not in known_varieties:
                warnings.append(f"{ref_key} '{ref}' is not in the current library.")
    if type_def == "multi_band":
        amps = data.get("amplifiers") or []
        if not amps:
            errors.append("multi_band requires at least one amplifier variety.")
        for ref in amps:
            if known_varieties and ref not in known_varieties:
                warnings.append(f"multi_band references '{ref}' which is not in the current library.")
    if type_def == "openroadm":
        coef = data.get("nf_coef") or []
        if len(coef) != 4:
            errors.append("openroadm nf_coef must contain exactly 4 coefficients.")

    return errors, warnings


# =============================================================================
# Fiber / RamanFiber field specifications
# =============================================================================
# The chromatic-dispersion description can be a single scalar coefficient or a
# table evaluated per frequency. This is the conditional structure for fibers.
FIBER_DISPERSION_MODES: list[str] = ["scalar", "per_frequency"]


def fiber_field_specs(dispersion_mode: str = "scalar") -> list[dict]:
    """Return field specs for a Fiber/RamanFiber library type."""
    specs: list[dict] = [
        field("type_variety", "type_variety *", TEXT, "", required=True,
              help="Unique name used to reference this fiber in the topology."),
    ]
    if dispersion_mode == "per_frequency":
        specs += [
            field("dp_value", "dispersion values [s/m²]", LIST_FLOAT, [],
                  help="dispersion_per_frequency.value list (s·m⁻²).", required=True),
            field("dp_frequency", "dispersion frequencies [Hz]", LIST_FLOAT, [],
                  help="dispersion_per_frequency.frequency list (Hz). Same length as values.",
                  required=True),
        ]
    else:
        specs += [
            field("dispersion", "dispersion (s/m²)", FLOAT_SCI, 1.67e-05, required=True,
                  fmt="%.4e", help="Chromatic dispersion D coefficient."),
            field("dispersion_slope", "dispersion_slope (s/m³)", FLOAT_SCI, 0.0, fmt="%.4e",
                  help="Optional dispersion slope S.", optional_group="Optional"),
        ]
    specs += [
        field("effective_area", "effective_area (m²)", FLOAT_SCI, 83e-12, required=True,
              fmt="%.4e", help="Effective area A_eff of the fiber."),
        field("pmd_coef", "pmd_coef (s/√m)", FLOAT_SCI, 1.265e-15, required=True,
              fmt="%.4e", help="Polarization mode dispersion coefficient."),
        field("gamma", "gamma (1/W/m)", FLOAT_SCI, 0.0, fmt="%.4e",
              help="Optional. Nonlinear coefficient; derived from effective_area when 0/omitted.",
              optional_group="Optional"),
    ]
    return specs


def default_fiber(dispersion_mode: str = "scalar") -> dict:
    data: dict[str, Any] = {"type_variety": ""}
    for spec in fiber_field_specs(dispersion_mode):
        if spec["key"] == "type_variety":
            continue
        data[spec["key"]] = spec["default"]
    return data


def detect_fiber_dispersion_mode(data: dict) -> str:
    return "per_frequency" if "dispersion_per_frequency" in (data or {}) else "scalar"


def build_fiber(values: dict, dispersion_mode: str = "scalar") -> dict:
    """Assemble a GNPy-standard Fiber object. Empty optionals are dropped."""
    out: dict[str, Any] = {"type_variety": str(values.get("type_variety", "")).strip()}
    if dispersion_mode == "per_frequency":
        out["dispersion_per_frequency"] = {
            "value": values.get("dp_value") or [],
            "frequency": values.get("dp_frequency") or [],
        }
    else:
        out["dispersion"] = values.get("dispersion", 1.67e-05)
        slope = values.get("dispersion_slope", 0.0)
        if slope:
            out["dispersion_slope"] = slope
    out["effective_area"] = values.get("effective_area", 83e-12)
    out["pmd_coef"] = values.get("pmd_coef", 1.265e-15)
    gamma = values.get("gamma", 0.0)
    if gamma:
        out["gamma"] = gamma
    return out


def validate_fiber(data: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not str(data.get("type_variety", "")).strip():
        errors.append("type_variety is required.")
    if "dispersion_per_frequency" in data:
        dp = data["dispersion_per_frequency"]
        values = dp.get("value") or []
        freqs = dp.get("frequency") or []
        if not values or len(values) != len(freqs):
            errors.append("dispersion_per_frequency value/frequency lists must be non-empty and equal length.")
    elif "dispersion" not in data:
        errors.append("dispersion is required.")
    try:
        if float(data.get("effective_area", 0) or 0) <= 0:
            errors.append("effective_area must be > 0.")
    except (TypeError, ValueError):
        errors.append("effective_area must be numeric.")
    try:
        if float(data.get("pmd_coef", 0) or 0) < 0:
            errors.append("pmd_coef must be >= 0.")
    except (TypeError, ValueError):
        errors.append("pmd_coef must be numeric.")
    return errors, warnings


# =============================================================================
# ROADM field specifications — conditional on equalization strategy
# =============================================================================
_ROADM_EQ_LABELS = {
    "target_pch_out_db": ("target_pch_out_db (dBm)", FLOAT, -20.0,
                          "Per-channel output power target."),
    "target_psd_out_mWperGHz": ("target_psd_out_mWperGHz (mW/GHz)", FLOAT_SCI, 3.125e-4,
                                "Power spectral density target."),
    "target_out_mWperSlotWidth": ("target_out_mWperSlotWidth (mW/slot)", FLOAT_SCI, 2.0e-4,
                                  "Power per slot-width target."),
}


def roadm_field_specs(equalization: str, amp_varieties: Optional[list[str]] = None) -> list[dict]:
    amp_varieties = amp_varieties or []
    if equalization not in _ROADM_EQ_LABELS:
        equalization = "target_pch_out_db"
    label, ftype, default, helptext = _ROADM_EQ_LABELS[equalization]
    return [
        field("type_variety", "type_variety", TEXT, "default",
              help="Unique ROADM variety name. 'default' is used when blank."),
        field(equalization, label, ftype, default, required=True, help=helptext,
              fmt="%.4e" if ftype == FLOAT_SCI else None),
        field("add_drop_osnr", "add_drop_osnr (dB)", FLOAT, 38.0,
              help="OSNR contribution from the add/drop ports."),
        field("pmd", "pmd (s)", FLOAT, 0.0, help="Polarization mode dispersion."),
        field("pdl", "pdl (dB)", FLOAT, 0.0, help="Polarization dependent loss."),
        field("preamp_variety_list", "restrictions.preamp_variety_list", REF_MULTISELECT, [],
              options=amp_varieties, help="Allowed preamp amplifier varieties (empty = no restriction).",
              optional_group="Restrictions (optional)"),
        field("booster_variety_list", "restrictions.booster_variety_list", REF_MULTISELECT, [],
              options=amp_varieties, help="Allowed booster amplifier varieties (empty = no restriction).",
              optional_group="Restrictions (optional)"),
    ]


def detect_roadm_equalization(data: dict) -> str:
    for strat in ROADM_EQUALIZATION_STRATEGIES:
        if strat in (data or {}):
            return strat
    return "target_pch_out_db"


def default_roadm(equalization: str = "target_pch_out_db") -> dict:
    data: dict[str, Any] = {"type_variety": "default"}
    for spec in roadm_field_specs(equalization):
        if spec["key"] == "type_variety":
            continue
        if spec["key"] in ("preamp_variety_list", "booster_variety_list"):
            continue
        data[spec["key"]] = spec["default"]
    data["restrictions"] = {"preamp_variety_list": [], "booster_variety_list": []}
    return data


def build_roadm(values: dict, equalization: str, preserve: Optional[dict] = None) -> dict:
    """Assemble a GNPy-standard ROADM object with exactly one equalization key."""
    tv = str(values.get("type_variety", "")).strip() or "default"
    out: dict[str, Any] = {"type_variety": tv}
    out[equalization] = values.get(equalization, _ROADM_EQ_LABELS[equalization][2])
    out["add_drop_osnr"] = values.get("add_drop_osnr", 38.0)
    out["pmd"] = values.get("pmd", 0.0)
    out["pdl"] = values.get("pdl", 0.0)
    out["restrictions"] = {
        "preamp_variety_list": values.get("preamp_variety_list") or [],
        "booster_variety_list": values.get("booster_variety_list") or [],
    }
    # Preserve advanced structures that the basic editor does not expose.
    if preserve:
        for key in ("roadm-path-impairments", "design_bands", "per_degree_impairments"):
            if key in preserve:
                out[key] = preserve[key]
    return out


def validate_roadm(data: dict, amp_varieties: Optional[list[str]] = None) -> tuple[list[str], list[str]]:
    amp_varieties = amp_varieties or []
    errors: list[str] = []
    warnings: list[str] = []
    present = [s for s in ROADM_EQUALIZATION_STRATEGIES if s in data]
    if len(present) == 0:
        errors.append("A ROADM must define one equalization target.")
    elif len(present) > 1:
        errors.append(f"Equalization strategies are mutually exclusive; found {present}.")
    restrictions = data.get("restrictions", {})
    for ref_key in ("preamp_variety_list", "booster_variety_list"):
        for ref in restrictions.get(ref_key, []) or []:
            if amp_varieties and ref not in amp_varieties:
                warnings.append(f"restrictions.{ref_key} references '{ref}' not in the current library.")
    return errors, warnings


# =============================================================================
# Transceiver field specifications (strict GNPy)
# =============================================================================
def transceiver_mode_specs() -> list[dict]:
    return [
        field("format", "format *", TEXT, "mode 1", required=True, help="Unique mode name."),
        field("baud_rate", "baud_rate (Hz)", FLOAT_SCI, 32e9, required=True, fmt="%.4e"),
        field("OSNR", "OSNR (dB)", FLOAT, 11.0, required=True,
              help="Min required OSNR in 0.1 nm (receiver threshold)."),
        field("bit_rate", "bit_rate (bit/s)", FLOAT_SCI, 100e9, required=True, fmt="%.4e"),
        field("roll_off", "roll_off", FLOAT, 0.15, required=True, help="TX signal roll-off (0..1)."),
        field("tx_osnr", "tx_osnr (dB)", FLOAT, 40.0, required=True, help="OSNR out from transponder."),
        field("min_spacing", "min_spacing (Hz)", FLOAT_SCI, 37.5e9, required=True, fmt="%.4e",
              help="Minimum slot size required for this mode."),
        field("cost", "cost", FLOAT, 1.0, help="Arbitrary unit."),
        field("equalization_offset_db", "equalization_offset_db (dB)", FLOAT, 0.0,
              help="Optional deviation from per-channel equalization target.",
              optional_group="Optional"),
    ]


def default_transceiver_mode() -> dict:
    return {spec["key"]: spec["default"] for spec in transceiver_mode_specs()}


def build_transceiver_mode(values: dict, penalties: Optional[list] = None) -> dict:
    out: dict[str, Any] = {}
    for spec in transceiver_mode_specs():
        key = spec["key"]
        val = values.get(key, spec["default"])
        if key == "equalization_offset_db" and not val:
            continue
        out[key] = val
    if penalties:
        out["penalties"] = penalties
    return out


def build_transceiver(type_variety: str, freq_min: float, freq_max: float, modes: list) -> dict:
    return {
        "type_variety": str(type_variety).strip(),
        "frequency": {"min": freq_min, "max": freq_max},
        "mode": modes,
    }


def validate_transceiver(data: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not str(data.get("type_variety", "")).strip():
        errors.append("type_variety is required.")
    freq = data.get("frequency", {})
    try:
        if float(freq.get("min", 0)) >= float(freq.get("max", 0)):
            errors.append("frequency.min must be < frequency.max.")
    except (TypeError, ValueError):
        errors.append("frequency.min/max must be numeric.")
    modes = data.get("mode", [])
    if not modes:
        warnings.append("Transceiver has no modes defined.")
    seen_formats = set()
    for i, m in enumerate(modes):
        fmt = str(m.get("format", "")).strip()
        if not fmt:
            errors.append(f"Mode #{i + 1}: format is required.")
        elif fmt in seen_formats:
            errors.append(f"Duplicate mode format '{fmt}'.")
        else:
            seen_formats.add(fmt)
        try:
            if float(m.get("baud_rate", 0)) <= 0:
                errors.append(f"Mode '{fmt or i + 1}': baud_rate must be > 0.")
            if float(m.get("min_spacing", 0)) < float(m.get("baud_rate", 0)):
                warnings.append(f"Mode '{fmt or i + 1}': min_spacing < baud_rate (carriers may not fit).")
        except (TypeError, ValueError):
            errors.append(f"Mode '{fmt or i + 1}': numeric fields invalid.")
    return errors, warnings


# =============================================================================
# Spectral Information (SI) field specifications
# =============================================================================
def si_field_specs() -> list[dict]:
    return [
        field("type_variety", "type_variety", TEXT, "default",
              help="Optional. Band identifier (used for multiband SI)."),
        field("f_min", "f_min (Hz)", FLOAT_SCI, DEFAULT_F_MIN_HZ, required=True, fmt="%.4e",
              help="Spectrum lower bound. First carrier is placed at f_min + spacing."),
        field("f_max", "f_max (Hz)", FLOAT_SCI, DEFAULT_F_MAX_HZ, required=True, fmt="%.4e",
              help="Spectrum upper bound (last carrier center)."),
        field("baud_rate", "baud_rate (Hz)", FLOAT_SCI, 32e9, required=True, fmt="%.4e"),
        field("spacing", "spacing (Hz)", FLOAT_SCI, 50e9, required=True, fmt="%.4e",
              help="Carrier spacing."),
        field("power_dbm", "power_dbm (dBm)", FLOAT, 0.0, required=True,
              help="Reference target input power in spans used for design."),
        field("roll_off", "roll_off", FLOAT, 0.15, required=True),
        field("tx_osnr", "tx_osnr (dB)", FLOAT, 40.0, required=True),
        field("sys_margins", "sys_margins (dB)", FLOAT, 2.0,
              help="Added margin on min required transceiver OSNR."),
        field("power_range_db", "power_range_db [min,max,step]", LIST_FLOAT, [0.0, 0.0, 1.0],
              help="Power sweep excursion around power_dbm.", optional_group="Optional"),
        field("tx_power_dbm", "tx_power_dbm (dBm)", FLOAT, 0.0,
              help="Optional. Power out from transceiver (defaults to power_dbm).",
              optional_group="Optional"),
        field("use_si_channel_count_for_design", "use_si_channel_count_for_design", BOOL, False,
              help="Use SI definition for channel count instead of amplifier bandwidth.",
              optional_group="Optional"),
    ]


def default_si() -> dict:
    return {spec["key"]: spec["default"] for spec in si_field_specs()}


def build_si(values: dict) -> dict:
    out: dict[str, Any] = {}
    for spec in si_field_specs():
        key = spec["key"]
        val = values.get(key, spec["default"])
        if key == "type_variety":
            out[key] = str(val).strip() or "default"
        elif key == "power_range_db":
            out[key] = val or [0.0, 0.0, 1.0]
        else:
            out[key] = val
    return out


def validate_si(data: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        if float(data.get("f_min", 0)) >= float(data.get("f_max", 0)):
            errors.append("f_min must be < f_max.")
    except (TypeError, ValueError):
        errors.append("f_min/f_max must be numeric.")
    try:
        if float(data.get("spacing", 0)) < float(data.get("baud_rate", 0)):
            warnings.append("spacing < baud_rate: carriers may overlap.")
    except (TypeError, ValueError):
        errors.append("spacing/baud_rate must be numeric.")
    prd = data.get("power_range_db")
    if prd is not None and len(prd) != 3:
        errors.append("power_range_db must have exactly 3 values [min, max, step].")
    return errors, warnings


def si_transceiver_coherence(si: dict, mode: dict, trx_frequency: Optional[dict] = None) -> list[str]:
    """Coherence warnings between an SI band and a transceiver mode.

    SI defines the design reference channel/spectrum; the transceiver mode is
    the physical transponder. They overlap on baud_rate, roll_off, tx_osnr and
    spacing/min_spacing. Returns human-readable warning strings (no exceptions).
    """
    warnings: list[str] = []
    try:
        if float(mode.get("min_spacing", 0)) > float(si.get("spacing", 0)):
            warnings.append(
                f"Mode min_spacing ({mode.get('min_spacing')} Hz) > SI spacing "
                f"({si.get('spacing')} Hz): carriers will not fit at this spacing."
            )
        if float(mode.get("baud_rate", 0)) != float(si.get("baud_rate", 0)):
            warnings.append(
                f"baud_rate differs: transceiver mode {mode.get('baud_rate')} Hz vs "
                f"SI {si.get('baud_rate')} Hz."
            )
    except (TypeError, ValueError):
        pass
    if trx_frequency:
        try:
            if float(si.get("f_min", 0)) < float(trx_frequency.get("min", 0)) or \
               float(si.get("f_max", 0)) > float(trx_frequency.get("max", 0)):
                warnings.append(
                    "SI spectrum [f_min, f_max] extends beyond the transceiver frequency range."
                )
        except (TypeError, ValueError):
            pass
    return warnings
