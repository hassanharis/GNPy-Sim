"""Headless smoke tests that actually render the Streamlit app.

Uses streamlit.testing.v1.AppTest to execute the real app script (all tabs are
rendered on every run) and asserts that no uncaught exception is raised. It then
switches the Component Library to each category and each EDFA type_def to
exercise the dynamic, schema-driven editors for real.

Run with:  python -m pytest tests/test_app_smoke.py -q
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

APP_PATH = str(ROOT / "app_CustomInputGenerator_v2.py")
COMPONENT_TYPES = [
    "Amplifiers (EDFA)",
    "Fiber Types",
    "Transceivers",
    "ROADMs",
    "Simulation Parameters",
]
EDFA_TYPE_DEFS = [
    "variable_gain", "fixed_gain", "openroadm", "openroadm_preamp",
    "openroadm_booster", "advanced_model", "dual_stage", "multi_band",
]


def _run():
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    return at


def test_app_renders_without_exception():
    at = _run()
    assert not at.exception, at.exception


def test_each_component_category_renders():
    at = _run()
    for ctype in COMPONENT_TYPES:
        at.selectbox(key="lib_component_type").set_value(ctype).run()
        assert not at.exception, f"{ctype} raised: {at.exception}"


def test_every_edfa_type_def_renders():
    at = _run()
    at.selectbox(key="lib_component_type").set_value("Amplifiers (EDFA)").run()
    for td in EDFA_TYPE_DEFS:
        at.selectbox(key="amp_type_def").set_value(td).run()
        assert not at.exception, f"EDFA type_def {td} raised: {at.exception}"


def test_fiber_dispersion_modes_render():
    at = _run()
    at.selectbox(key="lib_component_type").set_value("Fiber Types").run()
    for mode in ["scalar", "per_frequency"]:
        at.selectbox(key="fib_disp_mode").set_value(mode).run()
        assert not at.exception, f"Fiber dispersion mode {mode} raised: {at.exception}"


def test_roadm_equalization_strategies_render():
    at = _run()
    at.selectbox(key="lib_component_type").set_value("ROADMs").run()
    for strat in ["target_pch_out_db", "target_psd_out_mWperGHz", "target_out_mWperSlotWidth"]:
        at.selectbox(key="roadm_eq").set_value(strat).run()
        assert not at.exception, f"ROADM equalization {strat} raised: {at.exception}"
