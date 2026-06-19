"""Real unit tests for gnpy_schema builders and validators.

Run with:  python -m pytest tests/test_gnpy_schema.py -q
These tests exercise the actual schema logic (no mocking/stubbing) and assert
GNPy-standard output shapes and interdependency validation.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gnpy_schema as s  # noqa: E402


# ---------------------------------------------------------------------------
# EDFA
# ---------------------------------------------------------------------------
def test_edfa_variable_gain_fields_and_build():
    keys = [f["key"] for f in s.edfa_field_specs("variable_gain")]
    assert "nf_min" in keys and "nf_max" in keys
    assert "nf0" not in keys and "nf_coef" not in keys
    built = s.build_edfa(
        {"type_variety": "amp1", "gain_flatmax": 26, "gain_min": 15, "p_max": 23,
         "nf_min": 6, "nf_max": 10, "out_voa_auto": False, "allowed_for_design": True},
        "variable_gain",
    )
    assert built["type_def"] == "variable_gain"
    assert "nf0" not in built and "nf_coef" not in built
    assert s.validate_edfa(built) == ([], [])


def test_edfa_fixed_gain_uses_nf0_only():
    built = s.build_edfa(
        {"type_variety": "fg", "gain_flatmax": 21, "gain_min": 20, "p_max": 21, "nf0": 5.5},
        "fixed_gain",
    )
    assert built["nf0"] == 5.5
    assert "nf_min" not in built and "nf_max" not in built


def test_edfa_openroadm_requires_four_coeffs():
    bad = s.build_edfa({"type_variety": "o", "nf_coef": [1, 2, 3]}, "openroadm")
    errors, _ = s.validate_edfa(bad)
    assert any("nf_coef" in e for e in errors)
    good = s.build_edfa({"type_variety": "o", "nf_coef": [1, 2, 3, 4]}, "openroadm")
    assert s.validate_edfa(good)[0] == []


def test_edfa_dual_stage_reference_validation():
    built = s.build_edfa(
        {"type_variety": "ds", "gain_min": 25, "preamp_variety": "preA", "booster_variety": "boostB"},
        "dual_stage",
    )
    # Unknown references -> warnings (not in library)
    _, warnings = s.validate_edfa(built, known_varieties=["other"])
    assert any("preamp_variety" in w for w in warnings)
    # Known references -> no warnings
    _, warnings_ok = s.validate_edfa(built, known_varieties=["preA", "boostB"])
    assert warnings_ok == []


def test_edfa_multiband_requires_amplifiers():
    built = s.build_edfa({"type_variety": "mb", "amplifiers": []}, "multi_band")
    errors, _ = s.validate_edfa(built)
    assert any("multi_band" in e for e in errors)


def test_edfa_gain_min_must_not_exceed_flatmax():
    built = s.build_edfa(
        {"type_variety": "x", "gain_flatmax": 10, "gain_min": 20, "p_max": 21, "nf_min": 6, "nf_max": 10},
        "variable_gain",
    )
    errors, _ = s.validate_edfa(built)
    assert any("gain_min" in e for e in errors)


def test_edfa_empty_optional_config_dropped():
    built = s.build_edfa(
        {"type_variety": "x", "gain_flatmax": 26, "gain_min": 15, "p_max": 23,
         "nf_min": 6, "nf_max": 10, "default_config_from_json": ""},
        "variable_gain",
    )
    assert "default_config_from_json" not in built


# ---------------------------------------------------------------------------
# Fiber
# ---------------------------------------------------------------------------
def test_fiber_scalar_build_and_drop_zero_optionals():
    built = s.build_fiber(
        {"type_variety": "SSMF", "dispersion": 1.67e-05, "dispersion_slope": 0.0,
         "effective_area": 83e-12, "pmd_coef": 1.265e-15, "gamma": 0.0},
        "scalar",
    )
    assert built["dispersion"] == 1.67e-05
    assert "dispersion_slope" not in built  # zero dropped
    assert "gamma" not in built  # zero dropped
    assert s.validate_fiber(built)[0] == []


def test_fiber_per_frequency_requires_equal_length_lists():
    built = s.build_fiber(
        {"type_variety": "F", "dp_value": [0.18, 0.20], "dp_frequency": [191e12]},
        "per_frequency",
    )
    errors, _ = s.validate_fiber(built)
    assert any("dispersion_per_frequency" in e for e in errors)
    built_ok = s.build_fiber(
        {"type_variety": "F", "dp_value": [0.18, 0.20], "dp_frequency": [191e12, 196e12]},
        "per_frequency",
    )
    assert s.validate_fiber(built_ok)[0] == []


def test_fiber_effective_area_positive():
    built = s.build_fiber({"type_variety": "F", "dispersion": 1e-5, "effective_area": 0}, "scalar")
    assert any("effective_area" in e for e in s.validate_fiber(built)[0])


def test_detect_fiber_dispersion_mode():
    assert s.detect_fiber_dispersion_mode({"dispersion": 1e-5}) == "scalar"
    assert s.detect_fiber_dispersion_mode({"dispersion_per_frequency": {}}) == "per_frequency"


# ---------------------------------------------------------------------------
# ROADM
# ---------------------------------------------------------------------------
def test_roadm_single_equalization_key():
    built = s.build_roadm({"type_variety": "r", "target_pch_out_db": -20}, "target_pch_out_db")
    present = [k for k in s.ROADM_EQUALIZATION_STRATEGIES if k in built]
    assert present == ["target_pch_out_db"]
    assert s.validate_roadm(built)[0] == []


def test_roadm_detects_psd_equalization():
    assert s.detect_roadm_equalization({"target_psd_out_mWperGHz": 3e-4}) == "target_psd_out_mWperGHz"


def test_roadm_mutually_exclusive_violation():
    data = {"type_variety": "r", "target_pch_out_db": -20, "target_psd_out_mWperGHz": 3e-4,
            "restrictions": {"preamp_variety_list": [], "booster_variety_list": []}}
    errors, _ = s.validate_roadm(data)
    assert any("mutually exclusive" in e for e in errors)


def test_roadm_restrictions_reference_warning():
    built = s.build_roadm(
        {"type_variety": "r", "target_pch_out_db": -20, "preamp_variety_list": ["ampX"]},
        "target_pch_out_db",
    )
    _, warnings = s.validate_roadm(built, amp_varieties=["ampY"])
    assert any("ampX" in w for w in warnings)


def test_roadm_preserves_advanced_keys():
    preserve = {"roadm-path-impairments": [{"roadm-path-impairments-id": 0}]}
    built = s.build_roadm({"type_variety": "r", "target_pch_out_db": -20}, "target_pch_out_db", preserve=preserve)
    assert built["roadm-path-impairments"] == preserve["roadm-path-impairments"]


# ---------------------------------------------------------------------------
# Transceiver
# ---------------------------------------------------------------------------
def test_transceiver_strict_mode_drops_nonstandard():
    mode_in = {"format": "16QAM", "baud_rate": 64e9, "OSNR": 24, "bit_rate": 400e9,
               "roll_off": 0.1, "tx_osnr": 37, "min_spacing": 75e9, "cost": 1,
               "modulation": "16qam", "rx_min_power": -6, "rx_max_power": 6}
    built = s.build_transceiver_mode(mode_in)
    assert "modulation" not in built and "rx_min_power" not in built
    assert built["baud_rate"] == 64e9


def test_transceiver_duplicate_format_error():
    trx = s.build_transceiver("T", 191.35e12, 196.1e12, [
        s.build_transceiver_mode({"format": "m1", "baud_rate": 32e9, "min_spacing": 50e9}),
        s.build_transceiver_mode({"format": "m1", "baud_rate": 32e9, "min_spacing": 50e9}),
    ])
    errors, _ = s.validate_transceiver(trx)
    assert any("Duplicate" in e for e in errors)


def test_transceiver_frequency_order():
    trx = s.build_transceiver("T", 196e12, 191e12, [])
    assert any("frequency.min" in e for e in s.validate_transceiver(trx)[0])


# ---------------------------------------------------------------------------
# SI + SI/transceiver coherence
# ---------------------------------------------------------------------------
def test_si_build_and_validate():
    built = s.build_si({"f_min": 191.3e12, "f_max": 196.1e12, "baud_rate": 32e9,
                        "spacing": 50e9, "power_dbm": 0})
    assert built["type_variety"] == "default"
    assert s.validate_si(built)[0] == []


def test_si_spacing_below_baud_warns():
    built = s.build_si({"f_min": 191.3e12, "f_max": 196.1e12, "baud_rate": 64e9, "spacing": 50e9})
    _, warnings = s.validate_si(built)
    assert any("overlap" in w for w in warnings)


def test_si_power_range_must_be_three():
    built = s.build_si({"f_min": 191.3e12, "f_max": 196.1e12, "baud_rate": 32e9,
                        "spacing": 50e9, "power_range_db": [0, 0]})
    assert any("power_range_db" in e for e in s.validate_si(built)[0])


def test_si_transceiver_coherence_min_spacing():
    si = {"spacing": 50e9, "baud_rate": 32e9, "f_min": 191.3e12, "f_max": 196.1e12}
    mode = {"min_spacing": 75e9, "baud_rate": 64e9}
    warns = s.si_transceiver_coherence(si, mode, {"min": 191.35e12, "max": 196.1e12})
    assert any("min_spacing" in w for w in warns)
    assert any("baud_rate" in w for w in warns)
