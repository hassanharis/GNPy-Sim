"""
GNPy Custom Input Generator v2
A workflow-oriented tool for building GNPy simulation inputs.

Tabs:
1. Component Library - Create/manage reusable components (EDFAs, Fibers, Transceivers, ROADMs, SI presets)
2. Topology Builder - Build network topology with Excel paste support
3. Project Assembler - Select topology + pick components from library → generate equipment.json
4. Services Generator - Create path requests with validation that src/dst exist in topology
"""

import importlib
import json
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import streamlit as st

import gnpy_schema as schema

# Streamlit keeps imported submodules cached in sys.modules across reruns and
# does not always re-import them when the file changes in a long-running
# session. Force a reload so the app never runs against a stale schema. The
# module is tiny (pure functions/constants), so the cost is negligible.
importlib.reload(schema)

# =============================================================================
# Configuration
# =============================================================================
BASE_DIR = Path(__file__).resolve().parent
LIBRARY_DIR = BASE_DIR / "inputs" / "library"
TOPOLOGIES_DIR = BASE_DIR / "inputs" / "topologies"
PROJECTS_DIR = BASE_DIR / "inputs" / "projects"

# Ensure directories exist
LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
(LIBRARY_DIR / "amplifiers").mkdir(exist_ok=True)
(LIBRARY_DIR / "fibers").mkdir(exist_ok=True)
(LIBRARY_DIR / "raman_fibers").mkdir(exist_ok=True)
(LIBRARY_DIR / "transceivers").mkdir(exist_ok=True)
(LIBRARY_DIR / "roadms").mkdir(exist_ok=True)
(LIBRARY_DIR / "simulation_params").mkdir(exist_ok=True)
TOPOLOGIES_DIR.mkdir(parents=True, exist_ok=True)
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# Utility Functions
# =============================================================================
def list_json_files(folder: Path) -> list[str]:
    """List all JSON files in a folder (without extension)."""
    if not folder.exists():
        return []
    return sorted([f.stem for f in folder.glob("*.json")])


def load_json_file(filepath: Path) -> Optional[dict]:
    """Load a JSON file."""
    if not filepath.exists():
        return None
    try:
        return json.loads(filepath.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_json_file(filepath: Path, data: dict) -> bool:
    """Save data to a JSON file."""
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def delete_json_file(filepath: Path) -> bool:
    """Delete a JSON file."""
    try:
        if filepath.exists():
            filepath.unlink()
        return True
    except Exception:
        return False


def unwrap_component(data: Optional[dict]) -> dict:
    """Return the GNPy-native (flat) component dict.

    Some legacy files wrap the payload as ``{"uid": ..., "params": {...}}``.
    The canonical on-disk shape is flat, so unwrap when needed.
    """
    if isinstance(data, dict) and isinstance(data.get("params"), dict) and "type_variety" in data["params"]:
        return data["params"]
    return data or {}


def _strict_transceiver(data: dict) -> dict:
    """Normalize a transceiver to the strict GNPy schema (drops vendor extras)."""
    data = unwrap_component(data)
    modes = []
    for m in data.get("mode", []):
        modes.append(schema.build_transceiver_mode(m, m.get("penalties")))
    freq = data.get("frequency", {})
    return schema.build_transceiver(
        data.get("type_variety", ""),
        freq.get("min", schema.DEFAULT_F_MIN_HZ),
        freq.get("max", schema.DEFAULT_F_MAX_HZ),
        modes,
    )


def list_amplifier_varieties(folder: Path, exclude: Optional[str] = None) -> list[str]:
    """Collect the type_variety names of all amplifiers in a folder."""
    out: list[str] = []
    for name in list_json_files(folder):
        if exclude and name == exclude:
            continue
        data = unwrap_component(load_json_file(folder / f"{name}.json"))
        tv = str(data.get("type_variety", "")).strip()
        if tv:
            out.append(tv)
    return sorted(set(out))


# =============================================================================
# Generic schema-driven form renderer
# =============================================================================
def _parse_float_list(text: str) -> list[float]:
    out: list[float] = []
    for part in str(text).replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(float(part))
        except ValueError:
            pass
    return out


def render_schema_fields(
    specs: list[dict],
    values: dict,
    key_prefix: str,
    ref_options: Optional[list[str]] = None,
) -> dict:
    """Render Streamlit widgets from field specs and return collected values.

    Fields tagged with ``optional_group`` are tucked into expanders so the
    common path stays clean. ``ref_options`` populates reference selectors.
    """
    ref_options = ref_options or []
    result: dict[str, Any] = {}

    def render_one(spec: dict) -> None:
        key = spec["key"]
        wkey = f"{key_prefix}_{key}"
        cur = values.get(key, spec["default"])
        ftype = spec["type"]
        label = spec["label"]
        help_ = spec.get("help") or None

        if ftype == schema.TEXT:
            result[key] = st.text_input(label, value=str(cur or ""), help=help_, key=wkey)
        elif ftype == schema.BOOL:
            result[key] = st.checkbox(label, value=bool(cur), help=help_, key=wkey)
        elif ftype == schema.INT:
            try:
                ival = int(cur)
            except (TypeError, ValueError):
                ival = 0
            result[key] = int(st.number_input(label, value=ival, step=1, help=help_, key=wkey))
        elif ftype in (schema.FLOAT, schema.FLOAT_SCI):
            try:
                fval = float(cur)
            except (TypeError, ValueError):
                fval = 0.0
            result[key] = st.number_input(label, value=fval, format=spec.get("format"), help=help_, key=wkey)
        elif ftype == schema.SELECT:
            opts = spec.get("options", [])
            idx = opts.index(cur) if cur in opts else 0
            result[key] = st.selectbox(label, options=opts, index=idx, help=help_, key=wkey)
        elif ftype == schema.LIST_FLOAT:
            cur_text = ", ".join(str(x) for x in (cur or []))
            txt = st.text_input(label, value=cur_text, help=help_, key=wkey)
            result[key] = _parse_float_list(txt)
        elif ftype == schema.REF_SELECT:
            opts = [""] + [o for o in ref_options if o]
            idx = opts.index(cur) if cur in opts else 0
            result[key] = st.selectbox(label, options=opts, index=idx, help=help_, key=wkey)
        elif ftype == schema.REF_MULTISELECT:
            default = [c for c in (cur or []) if c in ref_options]
            result[key] = st.multiselect(label, options=ref_options, default=default, help=help_, key=wkey)
        else:
            result[key] = st.text_input(label, value=str(cur or ""), help=help_, key=wkey)

    main = [s for s in specs if not s.get("optional_group")]
    groups: dict[str, list[dict]] = {}
    for s in specs:
        g = s.get("optional_group")
        if g:
            groups.setdefault(g, []).append(s)

    for i in range(0, len(main), 2):
        cols = st.columns(2)
        for col, spec in zip(cols, main[i:i + 2]):
            with col:
                render_one(spec)

    for gname, gspecs in groups.items():
        with st.expander(gname, expanded=False):
            for i in range(0, len(gspecs), 2):
                cols = st.columns(2)
                for col, spec in zip(cols, gspecs[i:i + 2]):
                    with col:
                        render_one(spec)

    return result


_PENALTY_IMPAIRMENTS = ["chromatic_dispersion", "pmd", "pdl"]


def _render_penalties_editor(penalties: list, key_prefix: str) -> list:
    """Edit a transceiver mode's penalty list and return the GNPy-shaped list.

    Each GNPy penalty is a dict with one impairment key plus ``penalty_value``,
    e.g. ``{"chromatic_dispersion": 360000, "penalty_value": 0.5}``.
    """
    rows = []
    for p in penalties or []:
        imp = next((k for k in _PENALTY_IMPAIRMENTS if k in p), "chromatic_dispersion")
        rows.append({"impairment": imp, "value": p.get(imp, 0.0), "penalty_value": p.get("penalty_value", 0.0)})
    if not rows:
        rows = [{"impairment": "chromatic_dispersion", "value": 0.0, "penalty_value": 0.0}]

    with st.expander("Penalties (optional)", expanded=False):
        edited = st.data_editor(
            pd.DataFrame(rows),
            num_rows="dynamic",
            use_container_width=True,
            key=f"{key_prefix}_editor",
            column_config={
                "impairment": st.column_config.SelectboxColumn("Impairment", options=_PENALTY_IMPAIRMENTS),
                "value": st.column_config.NumberColumn("Value (ps/nm | ps | dB)"),
                "penalty_value": st.column_config.NumberColumn("Penalty (dB)"),
            },
        )

    out = []
    for _, r in edited.iterrows():
        imp = str(r.get("impairment", "")).strip()
        if imp not in _PENALTY_IMPAIRMENTS:
            continue
        val = r.get("value")
        pen = r.get("penalty_value")
        if pd.isna(val) and pd.isna(pen):
            continue
        out.append({imp: float(val or 0.0), "penalty_value": float(pen or 0.0)})
    return out


# =============================================================================
# Component Library Functions
# =============================================================================
def get_default_amplifier() -> dict:
    return schema.default_edfa("variable_gain")


def get_default_fiber() -> dict:
    return schema.default_fiber("scalar")


def get_default_transceiver() -> dict:
    return {
        "type_variety": "",
        "frequency": {"min": 191.35e12, "max": 196.1e12},
        "mode": []
    }


def get_default_transceiver_mode() -> dict:
    return schema.default_transceiver_mode()


def get_default_roadm() -> dict:
    return schema.default_roadm("target_pch_out_db")


def get_default_si_params() -> dict:
    return schema.default_si()


def get_default_span() -> dict:
    return {
        "power_mode": True,  # True=power mode, False=gain mode
        "delta_power_range_db": [-2, 3, 0.5],  # [min, max, step] relative power excursion
        "max_fiber_lineic_loss_for_raman": 0.25,  # dB/km max for Raman
        "target_extended_gain": 2.5,  # dB
        "max_length": 150,  # km - split fibers longer than this
        "length_units": "km",
        "max_loss": 28,  # dB
        "padding": 10,  # dB - min span loss before padding attenuator
        "EOL": 0,  # dB - end-of-life fiber ageing margin
        "con_in": 0,  # dB - default input connector loss
        "con_out": 0,  # dB - default output connector loss
        # Advanced auto-design options:
        "span_loss_ref": 20,  # dB - reference span loss for delta_p calculation (optional)
        "power_slope": 0.3,  # ratio for delta_p deviation calculation (optional)
        "voa_margin": 1.0,  # dB - safety margin for VOA (optional)
        "voa_step": 0.5,  # dB - VOA rounding step size (optional)
    }


# =============================================================================
# Tab 1: Component Library
# =============================================================================
def render_component_library():
    st.header("📚 Component Library")
    st.caption("Create and manage reusable components. These are saved in `inputs/library/` and can be used across projects.")

    component_type = st.selectbox(
        "Component Type",
        ["Amplifiers (EDFA)", "Fiber Types", "Transceivers", "ROADMs", "Simulation Parameters"],
        key="lib_component_type"
    )

    if component_type == "Amplifiers (EDFA)":
        render_amplifier_library()
    elif component_type == "Fiber Types":
        render_fiber_library()
    elif component_type == "Transceivers":
        render_transceiver_library()
    elif component_type == "ROADMs":
        render_roadm_library()
    elif component_type == "Simulation Parameters":
        render_si_params_library()


def render_amplifier_library():
    st.subheader("EDFA Library")
    st.caption(
        "Fields adapt to the selected `type_def` (GNPy noise/gain model). "
        "Only parameters valid for that model are shown and saved."
    )
    folder = LIBRARY_DIR / "amplifiers"
    existing = list_json_files(folder)

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("**Saved Amplifiers**")
        if existing:
            for name in existing:
                c1, c2 = st.columns([3, 1])
                with c1:
                    if st.button(f"📄 {name}", key=f"load_amp_{name}", use_container_width=True):
                        st.session_state.lib_amp_data = unwrap_component(load_json_file(folder / f"{name}.json"))
                        st.session_state.lib_amp_name = name
                        st.rerun()
                with c2:
                    if st.button("🗑️", key=f"del_amp_{name}"):
                        delete_json_file(folder / f"{name}.json")
                        st.rerun()
        else:
            st.info("No saved amplifiers")

    with col2:
        st.markdown("**Editor**")

        if "lib_amp_data" not in st.session_state:
            st.session_state.lib_amp_data = get_default_amplifier()
        if "lib_amp_name" not in st.session_state:
            st.session_state.lib_amp_name = ""

        amp = st.session_state.lib_amp_data

        name = st.text_input("Name (filename)", value=st.session_state.lib_amp_name, key="amp_name_input")

        # Discriminator: choosing a type_def re-renders the valid field set.
        current_def = amp.get("type_def", "variable_gain")
        type_def = st.selectbox(
            "type_def (noise/gain model)",
            schema.EDFA_TYPE_DEFS,
            index=schema.EDFA_TYPE_DEFS.index(current_def) if current_def in schema.EDFA_TYPE_DEFS else 0,
            key="amp_type_def",
            help="Determines which parameters are required for this amplifier.",
        )

        # dual_stage / multi_band reference other single-band amplifiers.
        ref_varieties = list_amplifier_varieties(folder)

        specs = schema.edfa_field_specs(type_def, known_varieties=ref_varieties)
        values = render_schema_fields(specs, amp, key_prefix="amp", ref_options=ref_varieties)

        built = schema.build_edfa(values, type_def)
        errors, warnings = schema.validate_edfa(built, known_varieties=ref_varieties)

        for w in warnings:
            st.warning(w)

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("💾 Save", type="primary", use_container_width=True, key="save_amp"):
                if not name.strip():
                    st.error("Name (filename) is required")
                elif errors:
                    for e in errors:
                        st.error(e)
                else:
                    if save_json_file(folder / f"{name.strip()}.json", built):
                        st.session_state.lib_amp_data = built
                        st.session_state.lib_amp_name = name.strip()
                        st.success(f"Saved: {name}")
                        st.rerun()
        with c2:
            if st.button("🆕 New", use_container_width=True, key="new_amp"):
                st.session_state.lib_amp_data = get_default_amplifier()
                st.session_state.lib_amp_name = ""
                st.rerun()
        with c3:
            if st.button("📋 Preview JSON", use_container_width=True, key="preview_amp"):
                st.json(built)


def render_fiber_library():
    st.subheader("Fiber Types Library")
    st.caption(
        "Define Fiber or RamanFiber types. The dispersion model switches the "
        "available fields (scalar coefficient vs per-frequency table)."
    )

    kind = st.radio(
        "Component kind",
        ["Fiber", "RamanFiber"],
        horizontal=True,
        key="fib_kind",
        help="RamanFiber library types share the same parameters as Fiber. Raman "
             "pumps are defined per topology instance, not in the library.",
    )
    folder = LIBRARY_DIR / ("raman_fibers" if kind == "RamanFiber" else "fibers")
    existing = list_json_files(folder)

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown(f"**Saved {kind} Types**")
        if existing:
            for name in existing:
                c1, c2 = st.columns([3, 1])
                with c1:
                    if st.button(f"📄 {name}", key=f"load_fib_{kind}_{name}", use_container_width=True):
                        st.session_state.lib_fib_data = unwrap_component(load_json_file(folder / f"{name}.json"))
                        st.session_state.lib_fib_name = name
                        st.rerun()
                with c2:
                    if st.button("🗑️", key=f"del_fib_{kind}_{name}"):
                        delete_json_file(folder / f"{name}.json")
                        st.rerun()
        else:
            st.info(f"No saved {kind.lower()} types")

    with col2:
        st.markdown("**Editor**")

        if "lib_fib_data" not in st.session_state:
            st.session_state.lib_fib_data = get_default_fiber()
        if "lib_fib_name" not in st.session_state:
            st.session_state.lib_fib_name = ""

        fib = st.session_state.lib_fib_data

        name = st.text_input("Name (filename)", value=st.session_state.lib_fib_name, key="fib_name_input")

        current_mode = schema.detect_fiber_dispersion_mode(fib)
        dispersion_mode = st.selectbox(
            "Dispersion model",
            schema.FIBER_DISPERSION_MODES,
            index=schema.FIBER_DISPERSION_MODES.index(current_mode),
            key="fib_disp_mode",
            help="scalar: single dispersion coefficient. per_frequency: dispersion "
                 "table evaluated at multiple frequencies.",
        )

        # Hydrate per-frequency list fields from a loaded dispersion_per_frequency dict.
        seed = dict(fib)
        if dispersion_mode == "per_frequency" and "dispersion_per_frequency" in fib:
            dp = fib["dispersion_per_frequency"]
            seed["dp_value"] = dp.get("value", [])
            seed["dp_frequency"] = dp.get("frequency", [])

        specs = schema.fiber_field_specs(dispersion_mode)
        values = render_schema_fields(specs, seed, key_prefix="fib")

        built = schema.build_fiber(values, dispersion_mode)
        errors, warnings = schema.validate_fiber(built)
        for w in warnings:
            st.warning(w)

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("💾 Save", type="primary", use_container_width=True, key="save_fib"):
                if not name.strip():
                    st.error("Name (filename) is required")
                elif errors:
                    for e in errors:
                        st.error(e)
                else:
                    if save_json_file(folder / f"{name.strip()}.json", built):
                        st.session_state.lib_fib_data = built
                        st.session_state.lib_fib_name = name.strip()
                        st.success(f"Saved {kind}: {name}")
                        st.rerun()
        with c2:
            if st.button("🆕 New", use_container_width=True, key="new_fib"):
                st.session_state.lib_fib_data = get_default_fiber()
                st.session_state.lib_fib_name = ""
                st.rerun()
        with c3:
            if st.button("📋 Preview JSON", use_container_width=True, key="preview_fib"):
                st.json(built)


def render_transceiver_library():
    st.subheader("Transceivers Library")
    folder = LIBRARY_DIR / "transceivers"
    existing = list_json_files(folder)

    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown("**Saved Transceivers**")
        if existing:
            for name in existing:
                c1, c2 = st.columns([3, 1])
                with c1:
                    if st.button(f"📄 {name}", key=f"load_trx_{name}", use_container_width=True):
                        loaded = unwrap_component(load_json_file(folder / f"{name}.json"))
                        st.session_state.lib_trx_data = loaded
                        st.session_state.lib_trx_name = name
                        st.session_state.lib_trx_modes = list(loaded.get("mode", []))
                        st.rerun()
                with c2:
                    if st.button("🗑️", key=f"del_trx_{name}"):
                        delete_json_file(folder / f"{name}.json")
                        st.rerun()
        else:
            st.info("No saved transceivers")

    with col2:
        st.markdown("**Editor**")
        st.caption("Strict GNPy schema. Non-standard vendor fields are not exported.")

        if "lib_trx_data" not in st.session_state:
            st.session_state.lib_trx_data = get_default_transceiver()
        if "lib_trx_name" not in st.session_state:
            st.session_state.lib_trx_name = ""
        if "lib_trx_modes" not in st.session_state:
            st.session_state.lib_trx_modes = list(st.session_state.lib_trx_data.get("mode", []))

        trx = st.session_state.lib_trx_data

        name = st.text_input("Name (filename)", value=st.session_state.lib_trx_name, key="trx_name_input")
        type_variety = st.text_input("type_variety *", value=trx.get("type_variety", ""), key="trx_variety")

        c1, c2 = st.columns(2)
        with c1:
            freq_min = st.number_input("frequency.min (Hz)", value=float(trx.get("frequency", {}).get("min", 191.35e12)), format="%.4e", key="trx_freq_min")
        with c2:
            freq_max = st.number_input("frequency.max (Hz)", value=float(trx.get("frequency", {}).get("max", 196.1e12)), format="%.4e", key="trx_freq_max")

        # Modes editor
        st.markdown("**Modes**")
        for i, mode in enumerate(st.session_state.lib_trx_modes):
            with st.expander(f"Mode: {mode.get('format', 'unnamed')}", expanded=False):
                mvals = render_schema_fields(schema.transceiver_mode_specs(), mode, key_prefix=f"trxmode_{i}")
                penalties = _render_penalties_editor(mode.get("penalties", []), key_prefix=f"trxpen_{i}")
                st.session_state.lib_trx_modes[i] = schema.build_transceiver_mode(mvals, penalties)
                if st.button("🗑️ Remove Mode", key=f"remove_mode_{i}"):
                    st.session_state.lib_trx_modes.pop(i)
                    st.rerun()

        if st.button("➕ Add Mode", key="add_trx_mode"):
            st.session_state.lib_trx_modes.append(get_default_transceiver_mode())
            st.rerun()

        built = schema.build_transceiver(type_variety, freq_min, freq_max, st.session_state.lib_trx_modes)
        errors, warnings = schema.validate_transceiver(built)
        for w in warnings:
            st.warning(w)

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("💾 Save", type="primary", use_container_width=True, key="save_trx"):
                if not name.strip():
                    st.error("Name (filename) is required")
                elif errors:
                    for e in errors:
                        st.error(e)
                else:
                    if save_json_file(folder / f"{name.strip()}.json", built):
                        st.session_state.lib_trx_data = built
                        st.session_state.lib_trx_name = name.strip()
                        st.success(f"Saved: {name}")
                        st.rerun()
        with c2:
            if st.button("🆕 New", use_container_width=True, key="new_trx"):
                st.session_state.lib_trx_data = get_default_transceiver()
                st.session_state.lib_trx_name = ""
                st.session_state.lib_trx_modes = []
                st.rerun()
        with c3:
            if st.button("📋 Preview JSON", use_container_width=True, key="preview_trx"):
                st.json(built)


def render_roadm_library():
    st.subheader("ROADM Library")
    folder = LIBRARY_DIR / "roadms"
    existing = list_json_files(folder)

    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown("**Saved ROADMs**")
        if existing:
            for name in existing:
                c1, c2 = st.columns([3, 1])
                with c1:
                    if st.button(f"📄 {name}", key=f"load_roadm_{name}", use_container_width=True):
                        st.session_state.lib_roadm_data = load_json_file(folder / f"{name}.json")
                        st.session_state.lib_roadm_name = name
                with c2:
                    if st.button("🗑️", key=f"del_roadm_{name}"):
                        delete_json_file(folder / f"{name}.json")
                        st.rerun()
        else:
            st.info("No saved ROADMs")

    with col2:
        st.markdown("**Editor**")

        if "lib_roadm_data" not in st.session_state:
            st.session_state.lib_roadm_data = get_default_roadm()
        if "lib_roadm_name" not in st.session_state:
            st.session_state.lib_roadm_name = ""

        roadm = st.session_state.lib_roadm_data

        name = st.text_input("Name (filename)", value=st.session_state.lib_roadm_name, key="roadm_name_input")

        # Discriminator: equalization strategies are mutually exclusive.
        current_eq = schema.detect_roadm_equalization(roadm)
        equalization = st.selectbox(
            "Equalization strategy",
            schema.ROADM_EQUALIZATION_STRATEGIES,
            index=schema.ROADM_EQUALIZATION_STRATEGIES.index(current_eq),
            key="roadm_eq",
            help="Exactly one target is written: per-channel power (pch), power "
                 "spectral density (psd), or power per slot width (psw).",
        )

        # Restriction selectors reference amplifiers from the library.
        amp_varieties = list_amplifier_varieties(LIBRARY_DIR / "amplifiers")

        # Seed restriction list fields from the nested restrictions dict.
        seed = dict(roadm)
        restr = roadm.get("restrictions", {})
        seed["preamp_variety_list"] = restr.get("preamp_variety_list", [])
        seed["booster_variety_list"] = restr.get("booster_variety_list", [])

        specs = schema.roadm_field_specs(equalization, amp_varieties=amp_varieties)
        values = render_schema_fields(specs, seed, key_prefix="roadm", ref_options=amp_varieties)

        # Preserve advanced structures (impairments/design bands) from loaded data.
        built = schema.build_roadm(values, equalization, preserve=roadm)
        errors, warnings = schema.validate_roadm(built, amp_varieties=amp_varieties)
        for w in warnings:
            st.warning(w)
        if roadm.get("roadm-path-impairments"):
            st.caption("ℹ️ Existing `roadm-path-impairments` are preserved on save (edit via JSON).")

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("💾 Save", type="primary", use_container_width=True, key="save_roadm"):
                if not name.strip():
                    st.error("Name (filename) is required")
                elif errors:
                    for e in errors:
                        st.error(e)
                else:
                    if save_json_file(folder / f"{name.strip()}.json", built):
                        st.session_state.lib_roadm_data = built
                        st.session_state.lib_roadm_name = name.strip()
                        st.success(f"Saved: {name}")
                        st.rerun()
        with c2:
            if st.button("🆕 New", use_container_width=True, key="new_roadm"):
                st.session_state.lib_roadm_data = get_default_roadm()
                st.session_state.lib_roadm_name = ""
                st.rerun()
        with c3:
            if st.button("📋 Preview JSON", use_container_width=True, key="preview_roadm"):
                st.json(built)


def render_si_params_library():
    st.subheader("Simulation Parameters Library")
    folder = LIBRARY_DIR / "simulation_params"
    existing = list_json_files(folder)

    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown("**Saved Presets**")
        if existing:
            for name in existing:
                c1, c2 = st.columns([3, 1])
                with c1:
                    if st.button(f"📄 {name}", key=f"load_si_{name}", use_container_width=True):
                        st.session_state.lib_si_data = unwrap_component(load_json_file(folder / f"{name}.json"))
                        st.session_state.lib_si_name = name
                        st.rerun()
                with c2:
                    if st.button("🗑️", key=f"del_si_{name}"):
                        delete_json_file(folder / f"{name}.json")
                        st.rerun()
        else:
            st.info("No saved presets")

    with col2:
        st.markdown("**Editor**")
        st.caption(
            "SI defines the **design reference channel** + spectrum bounds. It "
            "overlaps with transceiver modes on baud_rate / roll_off / tx_osnr / "
            "spacing — use the prefill below to keep them coherent."
        )

        if "lib_si_data" not in st.session_state:
            st.session_state.lib_si_data = get_default_si_params()
        if "lib_si_name" not in st.session_state:
            st.session_state.lib_si_name = ""

        si = st.session_state.lib_si_data

        name = st.text_input("Name (filename)", value=st.session_state.lib_si_name, key="si_name_input")

        # --- Overlap helper: prefill SI design channel from a transceiver mode ---
        trx_folder = LIBRARY_DIR / "transceivers"
        trx_files = list_json_files(trx_folder)
        trx_lookup: dict[str, dict] = {}
        for tname in trx_files:
            tdata = unwrap_component(load_json_file(trx_folder / f"{tname}.json"))
            if tdata:
                trx_lookup[tname] = tdata

        with st.expander("↪ Prefill from a transceiver mode (coherence helper)", expanded=False):
            pc1, pc2 = st.columns(2)
            with pc1:
                sel_trx = st.selectbox("Transceiver", options=[""] + list(trx_lookup.keys()), key="si_prefill_trx")
            modes_for_trx = trx_lookup.get(sel_trx, {}).get("mode", []) if sel_trx else []
            mode_formats = [m.get("format", "") for m in modes_for_trx]
            with pc2:
                sel_mode = st.selectbox("Mode", options=[""] + mode_formats, key="si_prefill_mode")
            if sel_trx and sel_mode and st.button("Apply prefill", key="si_apply_prefill"):
                mode = next((m for m in modes_for_trx if m.get("format") == sel_mode), None)
                if mode:
                    updated = dict(si)
                    updated["baud_rate"] = mode.get("baud_rate", si.get("baud_rate"))
                    updated["roll_off"] = mode.get("roll_off", si.get("roll_off"))
                    updated["tx_osnr"] = mode.get("tx_osnr", si.get("tx_osnr"))
                    # spacing must be at least the mode's min slot size.
                    updated["spacing"] = max(float(mode.get("min_spacing", 0) or 0), float(si.get("spacing", 0) or 0))
                    freq = trx_lookup[sel_trx].get("frequency", {})
                    if freq:
                        updated["f_min"] = freq.get("min", si.get("f_min"))
                        updated["f_max"] = freq.get("max", si.get("f_max"))
                    st.session_state.lib_si_data = updated
                    st.success(f"Prefilled from {sel_trx} / {sel_mode}")
                    st.rerun()

        specs = schema.si_field_specs()
        values = render_schema_fields(specs, si, key_prefix="si")
        built = schema.build_si(values)

        errors, warnings = schema.validate_si(built)
        for w in warnings:
            st.warning(w)

        # Live coherence check against the currently selected transceiver mode.
        if st.session_state.get("si_prefill_trx") and st.session_state.get("si_prefill_mode"):
            sel_trx = st.session_state["si_prefill_trx"]
            sel_mode = st.session_state["si_prefill_mode"]
            tdata = trx_lookup.get(sel_trx, {})
            mode = next((m for m in tdata.get("mode", []) if m.get("format") == sel_mode), None)
            if mode:
                for w in schema.si_transceiver_coherence(built, mode, tdata.get("frequency")):
                    st.warning(f"Coherence: {w}")

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("💾 Save", type="primary", use_container_width=True, key="save_si"):
                if not name.strip():
                    st.error("Name (filename) is required")
                elif errors:
                    for e in errors:
                        st.error(e)
                else:
                    if save_json_file(folder / f"{name.strip()}.json", built):
                        st.session_state.lib_si_data = built
                        st.session_state.lib_si_name = name.strip()
                        st.success(f"Saved: {name}")
                        st.rerun()
        with c2:
            if st.button("🆕 New", use_container_width=True, key="new_si"):
                st.session_state.lib_si_data = get_default_si_params()
                st.session_state.lib_si_name = ""
                st.rerun()
        with c3:
            if st.button("📋 Preview JSON", use_container_width=True, key="preview_si"):
                st.json(built)


# =============================================================================
# Tab 2: Topology Builder
# =============================================================================
def render_topology_builder():
    st.header("🗺️ Topology Builder")
    st.caption("Build network topology with Excel paste support. Save topologies to `inputs/topologies/`.")

    # Initialize topology name in session state
    if "topo_name_value" not in st.session_state:
        st.session_state.topo_name_value = "my_network"

    # Topology name and file selection
    col1, col2 = st.columns([2, 1])
    with col1:
        topo_name = st.text_input("Topology Name", value=st.session_state.topo_name_value, key="topo_name")
    with col2:
        existing_topos = list_json_files(TOPOLOGIES_DIR)
        load_topo = st.selectbox("Load Existing", options=[""] + existing_topos, key="load_topo_select")
        if load_topo and st.button("Load", key="load_topo_btn"):
            data = load_json_file(TOPOLOGIES_DIR / f"{load_topo}.json")
            if data:
                st.session_state.topo_data = data
                st.session_state.topo_name_value = load_topo  # Update topology name to loaded file
                st.success(f"Loaded: {load_topo}")
                st.rerun()

    # Initialize topology data
    if "topo_data" not in st.session_state:
        st.session_state.topo_data = {"network_name": "", "elements": [], "connections": []}

    topo = st.session_state.topo_data

    # === NODES TABLE ===
    st.markdown("#### Nodes (Transceiver, Roadm, Edfa, Fused)")
    st.caption("Paste from Excel: uid, type, city, region, latitude, longitude, type_variety")
    
    existing_nodes = [e for e in topo.get("elements", []) if e.get("type") in ["Transceiver", "Roadm", "Edfa", "Fused"]]
    nodes_data = []
    for node in existing_nodes:
        loc = node.get("metadata", {}).get("location", {})
        nodes_data.append({
            "uid": node.get("uid", ""),
            "type": node.get("type", "Transceiver"),
            "city": loc.get("city", ""),
            "region": loc.get("region", ""),
            "latitude": loc.get("latitude", None),
            "longitude": loc.get("longitude", None),
            "type_variety": node.get("type_variety", ""),
        })
    
    if not nodes_data:
        nodes_data = [{"uid": "", "type": "Transceiver", "city": "", "region": "", "latitude": None, "longitude": None, "type_variety": ""}]
    
    nodes_df = pd.DataFrame(nodes_data)
    
    edited_nodes = st.data_editor(
        nodes_df,
        num_rows="dynamic",
        use_container_width=True,
        key="topo_nodes_editor",
        column_config={
            "uid": st.column_config.TextColumn("UID *"),
            "type": st.column_config.TextColumn("Type * (Transceiver/Roadm/Edfa/Fused)"),
            "city": st.column_config.TextColumn("City"),
            "region": st.column_config.TextColumn("Region"),
            "latitude": st.column_config.NumberColumn("Latitude", format="%.6f"),
            "longitude": st.column_config.NumberColumn("Longitude", format="%.6f"),
            "type_variety": st.column_config.TextColumn("Type Variety"),
        }
    )

    # Get list of node UIDs for validation
    node_uids = set()
    node_types = {}  # uid -> type
    for _, row in edited_nodes.iterrows():
        uid = str(row.get("uid", "")).strip()
        ntype = str(row.get("type", "")).strip()
        if uid:
            node_uids.add(uid)
            node_types[uid] = ntype

    # === HELPER: Create ROADMs for Transceivers ===
    transceivers = [uid for uid, t in node_types.items() if t.lower() == "transceiver"]
    existing_roadms = set(uid for uid, t in node_types.items() if t.lower() == "roadm")
    
    # Check which transceivers don't have matching roadms
    transceivers_without_roadm = []
    for trx_uid in transceivers:
        expected_roadm = f"roadm {trx_uid}"
        if expected_roadm not in existing_roadms:
            transceivers_without_roadm.append(trx_uid)
    
    if transceivers_without_roadm:
        st.info(f"💡 **{len(transceivers_without_roadm)} Transceiver(s) without matching ROADM:** {', '.join(transceivers_without_roadm[:5])}{'...' if len(transceivers_without_roadm) > 5 else ''}")
        if st.button("🔧 Create ROADMs for All Transceivers", key="create_roadms_btn"):
            # Get existing elements
            new_elements = list(topo.get("elements", []))
            added_count = 0
            
            for trx_uid in transceivers_without_roadm:
                # Find the transceiver to get its metadata
                trx_data = None
                for _, row in edited_nodes.iterrows():
                    if str(row.get("uid", "")).strip() == trx_uid:
                        trx_data = row
                        break
                
                if trx_data is not None:
                    roadm_element = {
                        "uid": f"roadm {trx_uid}",
                        "type": "Roadm",
                    }
                    # Copy location metadata if available
                    loc = {}
                    if pd.notna(trx_data.get("city")) and str(trx_data.get("city")).strip():
                        loc["city"] = str(trx_data.get("city")).strip()
                    if pd.notna(trx_data.get("region")) and str(trx_data.get("region")).strip():
                        loc["region"] = str(trx_data.get("region")).strip()
                    if pd.notna(trx_data.get("latitude")):
                        loc["latitude"] = float(trx_data["latitude"])
                    if pd.notna(trx_data.get("longitude")):
                        loc["longitude"] = float(trx_data["longitude"])
                    if loc:
                        roadm_element["metadata"] = {"location": loc}
                    
                    new_elements.append(roadm_element)
                    added_count += 1
            
            st.session_state.topo_data["elements"] = new_elements
            st.success(f"✅ Created {added_count} ROADM element(s)")
            st.rerun()

    # === FIBERS TABLE ===
    st.markdown("#### Fibers")
    st.caption("Paste from Excel: start_node, end_node, type, type_variety, length_km, loss_coef, att_in, con_in, con_out")
    st.caption("UID is auto-generated as: fiber (start_node → end_node)")
    
    existing_fibers = [e for e in topo.get("elements", []) if e.get("type") in ["Fiber", "RamanFiber"]]
    fibers_data = []
    for fiber in existing_fibers:
        params = fiber.get("params", {})
        uid = fiber.get("uid", "")
        # Parse UID to extract start/end nodes: "fiber (A → B)" or "Fiber (A → B)"
        start_node = ""
        end_node = ""
        if "(" in uid and "→" in uid:
            try:
                inner = uid.split("(")[1].split(")")[0]
                parts = inner.split("→")
                if len(parts) == 2:
                    start_node = parts[0].strip()
                    end_node = parts[1].strip()
            except:
                pass
        fibers_data.append({
            "start_node": start_node,
            "end_node": end_node,
            "uid": f"fiber ({start_node} → {end_node})" if start_node and end_node else "",
            "type": fiber.get("type", "Fiber"),
            "type_variety": fiber.get("type_variety", "SSMF"),
            "length_km": params.get("length", 80.0),
            "loss_coef": params.get("loss_coef", 0.2),
            "att_in": params.get("att_in", 0.0),
            "con_in": params.get("con_in", 0.0),
            "con_out": params.get("con_out", 0.0),
        })
    
    if not fibers_data:
        fibers_data = [{"start_node": "", "end_node": "", "uid": "", "type": "Fiber", "type_variety": "SSMF", "length_km": 80.0, "loss_coef": 0.2, "att_in": 0.0, "con_in": 0.0, "con_out": 0.0}]
    
    fibers_df = pd.DataFrame(fibers_data)
    
    # Recompute UID column based on start_node and end_node for display
    def compute_fiber_uid(row):
        s = str(row.get("start_node", "")).strip() if pd.notna(row.get("start_node")) else ""
        e = str(row.get("end_node", "")).strip() if pd.notna(row.get("end_node")) else ""
        return f"fiber ({s} → {e})" if s and e else ""
    
    fibers_df["uid"] = fibers_df.apply(compute_fiber_uid, axis=1)
    
    # Reorder columns to put uid first
    cols = ["uid", "start_node", "end_node", "type", "type_variety", "length_km", "loss_coef", "att_in", "con_in", "con_out"]
    fibers_df = fibers_df[cols]
    
    edited_fibers = st.data_editor(
        fibers_df,
        num_rows="dynamic",
        use_container_width=True,
        key="topo_fibers_editor",
        disabled=["uid"],  # Make UID column read-only
        column_config={
            "uid": st.column_config.TextColumn("UID (auto)"),
            "start_node": st.column_config.TextColumn("Start Node *"),
            "end_node": st.column_config.TextColumn("End Node *"),
            "type": st.column_config.TextColumn("Type * (Fiber/RamanFiber)"),
            "type_variety": st.column_config.TextColumn("Type Variety"),
            "length_km": st.column_config.NumberColumn("Length (km) *", format="%.3f"),
            "loss_coef": st.column_config.NumberColumn("Loss Coef (dB/km) *", format="%.3f"),
            "att_in": st.column_config.NumberColumn("Att In (dB)", format="%.2f"),
            "con_in": st.column_config.NumberColumn("Con In (dB)", format="%.2f"),
            "con_out": st.column_config.NumberColumn("Con Out (dB)", format="%.2f"),
        }
    )

    # Validate fiber start/end nodes against node UIDs
    fiber_validation_errors = []
    for idx, row in edited_fibers.iterrows():
        start = str(row.get("start_node", "")).strip() if pd.notna(row.get("start_node")) else ""
        end = str(row.get("end_node", "")).strip() if pd.notna(row.get("end_node")) else ""
        if start or end:  # Only validate if there's data
            if start and start not in node_uids:
                fiber_validation_errors.append(f"Row {idx + 1}: Start node '{start}' not found in Nodes table")
            if end and end not in node_uids:
                fiber_validation_errors.append(f"Row {idx + 1}: End node '{end}' not found in Nodes table")
    
    if fiber_validation_errors:
        st.warning("**Fiber Node Validation Issues:**")
        for err in fiber_validation_errors:
            st.caption(f"⚠️ {err}")

    # === CONNECTIONS TABLE ===
    st.markdown("#### Connections")
    st.caption("Paste from Excel: from_node, to_node — OR auto-generate from fibers")
    
    # Build fiber UIDs set for validation
    fiber_uids_for_validation = set()
    for _, row in edited_fibers.iterrows():
        start = str(row.get("start_node", "")).strip() if pd.notna(row.get("start_node")) else ""
        end = str(row.get("end_node", "")).strip() if pd.notna(row.get("end_node")) else ""
        if start and end:
            fiber_uids_for_validation.add(f"fiber ({start} → {end})")
    
    # Button to auto-generate connections from fibers
    col_conn1, col_conn2 = st.columns([1, 2])
    with col_conn1:
        if st.button("⚡ Auto-Generate from Fibers", key="auto_gen_connections_btn"):
            auto_connections = []
            for _, row in edited_fibers.iterrows():
                start_node = str(row.get("start_node", "")).strip() if pd.notna(row.get("start_node")) else ""
                end_node = str(row.get("end_node", "")).strip() if pd.notna(row.get("end_node")) else ""
                if start_node and end_node:
                    fiber_uid = f"fiber ({start_node} → {end_node})"
                    
                    # If start/end is a Transceiver, connect to its ROADM instead
                    conn_start = start_node
                    conn_end = end_node
                    if node_types.get(start_node, "").lower() == "transceiver":
                        conn_start = f"roadm {start_node}"
                    if node_types.get(end_node, "").lower() == "transceiver":
                        conn_end = f"roadm {end_node}"
                    
                    auto_connections.append({"from_node": conn_start, "to_node": fiber_uid})
                    auto_connections.append({"from_node": fiber_uid, "to_node": conn_end})
            
            if auto_connections:
                st.session_state.topo_data["connections"] = auto_connections
                st.success(f"Generated {len(auto_connections)} connections from {len(auto_connections)//2} fiber(s)")
                st.rerun()
            else:
                st.warning("No fibers to generate connections from")
    with col_conn2:
        st.caption("Connects fibers to ROADMs (not Transceivers)")
    
    existing_connections = topo.get("connections", [])
    connections_data = [{"from_node": c.get("from_node", ""), "to_node": c.get("to_node", "")} for c in existing_connections]
    
    if not connections_data:
        connections_data = [{"from_node": "", "to_node": ""}]
    
    connections_df = pd.DataFrame(connections_data)
    
    edited_connections = st.data_editor(
        connections_df,
        num_rows="dynamic",
        use_container_width=True,
        key="topo_connections_editor",
        column_config={
            "from_node": st.column_config.TextColumn("From Node *"),
            "to_node": st.column_config.TextColumn("To Node *"),
        }
    )

    # Check for duplicate connections
    seen_connections = set()
    duplicate_rows = []
    for idx, row in edited_connections.iterrows():
        from_n = str(row.get("from_node", "")).strip() if pd.notna(row.get("from_node")) else ""
        to_n = str(row.get("to_node", "")).strip() if pd.notna(row.get("to_node")) else ""
        if from_n and to_n:
            conn_key = (from_n, to_n)
            if conn_key in seen_connections:
                duplicate_rows.append(idx + 1)
            else:
                seen_connections.add(conn_key)
    
    # Validate connections against node UIDs AND fiber UIDs
    valid_connection_uids = node_uids | fiber_uids_for_validation
    connection_validation_errors = []
    for idx, row in edited_connections.iterrows():
        from_n = str(row.get("from_node", "")).strip() if pd.notna(row.get("from_node")) else ""
        to_n = str(row.get("to_node", "")).strip() if pd.notna(row.get("to_node")) else ""
        if from_n or to_n:  # Only validate if there's data
            if from_n and from_n not in valid_connection_uids:
                connection_validation_errors.append(f"Row {idx + 1}: From node '{from_n}' not found in Nodes or Fibers")
            if to_n and to_n not in valid_connection_uids:
                connection_validation_errors.append(f"Row {idx + 1}: To node '{to_n}' not found in Nodes or Fibers")
    
    if connection_validation_errors:
        st.warning("**Connection Validation Issues:**")
        for err in connection_validation_errors:
            st.caption(f"⚠️ {err}")
    
    if duplicate_rows:
        st.info(f"**Duplicate connections found in rows:** {', '.join(map(str, duplicate_rows))}")
        if st.button("🗑️ Remove Duplicate Connections", key="remove_dup_connections"):
            # Deduplicate and update topo_data
            seen = set()
            unique_connections = []
            for _, row in edited_connections.iterrows():
                from_n = str(row.get("from_node", "")).strip() if pd.notna(row.get("from_node")) else ""
                to_n = str(row.get("to_node", "")).strip() if pd.notna(row.get("to_node")) else ""
                if from_n and to_n:
                    conn_key = (from_n, to_n)
                    if conn_key not in seen:
                        seen.add(conn_key)
                        unique_connections.append({"from_node": from_n, "to_node": to_n})
            st.session_state.topo_data["connections"] = unique_connections
            st.success(f"Removed {len(duplicate_rows)} duplicate connection(s)")
            st.rerun()

    # === TOPOLOGY VALIDATION (GNPy Structure) ===
    st.markdown("---")
    st.markdown("#### 🔍 Topology Validation")
    
    # Build lookup structures from current editor state
    trx_nodes = set()
    roadm_nodes = set()
    edfa_nodes = set()
    fused_nodes = set()
    all_node_uids = set()
    
    for _, row in edited_nodes.iterrows():
        uid = str(row.get("uid", "")).strip()
        ntype = str(row.get("type", "")).strip().lower()
        if uid:
            all_node_uids.add(uid)
            if ntype == "transceiver":
                trx_nodes.add(uid)
            elif ntype == "roadm":
                roadm_nodes.add(uid)
            elif ntype == "edfa":
                edfa_nodes.add(uid)
            elif ntype == "fused":
                fused_nodes.add(uid)
    
    fiber_uids = set()
    fiber_endpoints = {}  # fiber_uid -> (start, end)
    for _, row in edited_fibers.iterrows():
        start = str(row.get("start_node", "")).strip() if pd.notna(row.get("start_node")) else ""
        end = str(row.get("end_node", "")).strip() if pd.notna(row.get("end_node")) else ""
        if start and end:
            fiber_uid = f"fiber ({start} → {end})"
            fiber_uids.add(fiber_uid)
            fiber_endpoints[fiber_uid] = (start, end)
    
    # Parse connections
    conn_from = {}  # from_node -> list of to_nodes
    conn_to = {}    # to_node -> list of from_nodes
    for _, row in edited_connections.iterrows():
        from_n = str(row.get("from_node", "")).strip() if pd.notna(row.get("from_node")) else ""
        to_n = str(row.get("to_node", "")).strip() if pd.notna(row.get("to_node")) else ""
        if from_n and to_n:
            conn_from.setdefault(from_n, []).append(to_n)
            conn_to.setdefault(to_n, []).append(from_n)
    
    # Validation checks
    validation_errors = []
    validation_warnings = []
    validation_info = []
    
    # 1. Check: Transceivers should have matching ROADMs
    for trx in trx_nodes:
        expected_roadm = f"roadm {trx}"
        if expected_roadm not in roadm_nodes:
            validation_errors.append(f"Transceiver '{trx}' has no matching ROADM (expected 'roadm {trx}')")
    
    # 2. Check: Fibers should connect to Roadm or Edfa, NOT Transceivers
    for fiber_uid, (start, end) in fiber_endpoints.items():
        if start in trx_nodes:
            validation_errors.append(f"Fiber '{fiber_uid}' starts at Transceiver '{start}' - fibers must connect to Roadm/Edfa")
        if end in trx_nodes:
            validation_errors.append(f"Fiber '{fiber_uid}' ends at Transceiver '{end}' - fibers must connect to Roadm/Edfa")
    
    # 3. Check: Each fiber should have exactly 2 connections (in and out)
    for fiber_uid in fiber_uids:
        incoming = len(conn_to.get(fiber_uid, []))
        outgoing = len(conn_from.get(fiber_uid, []))
        if incoming != 1:
            validation_warnings.append(f"Fiber '{fiber_uid}' has {incoming} incoming connection(s) (expected 1)")
        if outgoing != 1:
            validation_warnings.append(f"Fiber '{fiber_uid}' has {outgoing} outgoing connection(s) (expected 1)")
    
    # 4. Check: Connection references exist
    all_element_uids = all_node_uids | fiber_uids
    for from_n in conn_from.keys():
        if from_n not in all_element_uids:
            validation_errors.append(f"Connection from_node '{from_n}' not found in elements")
    for to_n in conn_to.keys():
        if to_n not in all_element_uids:
            validation_errors.append(f"Connection to_node '{to_n}' not found in elements")
    
    # 5. Info: Summary
    validation_info.append(f"Transceivers: {len(trx_nodes)}, ROADMs: {len(roadm_nodes)}, EDFAs: {len(edfa_nodes)}, Fibers: {len(fiber_uids)}, Connections: {len(list(conn_from.keys()))}")
    
    # Display validation results
    with st.expander("View Validation Results", expanded=bool(validation_errors)):
        for info in validation_info:
            st.info(f"📊 {info}")
        
        if validation_errors:
            st.error(f"**{len(validation_errors)} Error(s) Found:**")
            for err in validation_errors[:10]:  # Show first 10
                st.caption(f"❌ {err}")
            if len(validation_errors) > 10:
                st.caption(f"... and {len(validation_errors) - 10} more errors")
        else:
            st.success("✅ No critical errors found")
        
        if validation_warnings:
            st.warning(f"**{len(validation_warnings)} Warning(s):**")
            for warn in validation_warnings[:10]:
                st.caption(f"⚠️ {warn}")
            if len(validation_warnings) > 10:
                st.caption(f"... and {len(validation_warnings) - 10} more warnings")

    # === ACTIONS ===
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        if st.button("💾 Save Topology", type="primary", use_container_width=True, key="save_topo"):
            # Valid types for validation
            VALID_NODE_TYPES = ["Transceiver", "Roadm", "Edfa", "Fused"]
            VALID_FIBER_TYPES = ["Fiber", "RamanFiber"]
            
            # Build elements list
            elements = []
            warnings = []
            
            # Add nodes
            for idx, row in edited_nodes.iterrows():
                uid = str(row.get("uid", "")).strip()
                if not uid:
                    continue
                
                # Normalize type (case-insensitive match)
                raw_type = str(row.get("type", "Transceiver")).strip()
                node_type = "Transceiver"  # default
                for vt in VALID_NODE_TYPES:
                    if raw_type.lower() == vt.lower():
                        node_type = vt
                        break
                else:
                    warnings.append(f"Node '{uid}': Unknown type '{raw_type}', defaulted to 'Transceiver'")
                
                node: dict[str, Any] = {"uid": uid, "type": node_type}
                location: dict[str, Any] = {}
                if pd.notna(row.get("city")) and str(row.get("city")).strip():
                    location["city"] = str(row.get("city")).strip()
                if pd.notna(row.get("region")) and str(row.get("region")).strip():
                    location["region"] = str(row.get("region")).strip()
                if pd.notna(row.get("latitude")):
                    location["latitude"] = float(row["latitude"])
                if pd.notna(row.get("longitude")):
                    location["longitude"] = float(row["longitude"])
                if location:
                    node["metadata"] = {"location": location}
                if pd.notna(row.get("type_variety")) and str(row.get("type_variety")).strip():
                    node["type_variety"] = str(row.get("type_variety")).strip()
                elements.append(node)
            
            # Collect node UIDs for fiber validation
            node_uids_for_save = set(e["uid"] for e in elements if e.get("type") in VALID_NODE_TYPES)
            
            # Add fibers
            for idx, row in edited_fibers.iterrows():
                start_node = str(row.get("start_node", "")).strip() if pd.notna(row.get("start_node")) else ""
                end_node = str(row.get("end_node", "")).strip() if pd.notna(row.get("end_node")) else ""
                
                if not start_node or not end_node:
                    continue
                
                # Generate UID from start and end nodes
                uid = f"fiber ({start_node} → {end_node})"
                
                # Normalize type (case-insensitive match)
                raw_type = str(row.get("type", "Fiber")).strip()
                fiber_type = "Fiber"  # default
                for vt in VALID_FIBER_TYPES:
                    if raw_type.lower() == vt.lower():
                        fiber_type = vt
                        break
                else:
                    warnings.append(f"Fiber '{uid}': Unknown type '{raw_type}', defaulted to 'Fiber'")
                
                # Validate nodes exist
                if start_node not in node_uids_for_save:
                    warnings.append(f"Fiber '{uid}': Start node '{start_node}' not found in Nodes")
                if end_node not in node_uids_for_save:
                    warnings.append(f"Fiber '{uid}': End node '{end_node}' not found in Nodes")
                
                fiber: dict[str, Any] = {
                    "uid": uid,
                    "type": fiber_type,
                    "type_variety": str(row.get("type_variety", "SSMF")).strip() or "SSMF",
                    "params": {
                        "length": float(row.get("length_km", 80.0)),
                        "length_units": "km",
                        "loss_coef": float(row.get("loss_coef", 0.2)),
                        "att_in": float(row.get("att_in", 0.0)) if pd.notna(row.get("att_in")) else 0.0,
                        "con_in": float(row.get("con_in", 0.0)) if pd.notna(row.get("con_in")) else 0.0,
                        "con_out": float(row.get("con_out", 0.0)) if pd.notna(row.get("con_out")) else 0.0,
                    }
                }
                elements.append(fiber)
            
            # Build connections
            connections = []
            for _, row in edited_connections.iterrows():
                from_node = str(row.get("from_node", "")).strip()
                to_node = str(row.get("to_node", "")).strip()
                if from_node and to_node:
                    connections.append({"from_node": from_node, "to_node": to_node})
            
            # Save
            topology_data = {
                "network_name": topo_name.strip(),
                "elements": elements,
                "connections": connections
            }
            
            if save_json_file(TOPOLOGIES_DIR / f"{topo_name.strip()}.json", topology_data):
                st.session_state.topo_data = topology_data
                st.success(f"Saved topology: {topo_name}")
                if warnings:
                    for w in warnings:
                        st.warning(w)
    
    with c2:
        if st.button("🆕 New Topology", use_container_width=True, key="new_topo"):
            st.session_state.topo_data = {"network_name": "", "elements": [], "connections": []}
            st.rerun()
    
    with c3:
        if st.button("📋 Preview JSON", use_container_width=True, key="preview_topo"):
            st.json(topo)


# =============================================================================
# Tab 3: Project Assembler
# =============================================================================
def render_project_assembler():
    st.header("🔧 Project Assembler")
    st.caption("Select a topology and pick components from library to generate equipment.json")

    # Project name
    project_name = st.text_input("Project Name", value="my_project", key="proj_name")

    # Load existing project
    existing_projects = [d.name for d in PROJECTS_DIR.iterdir() if d.is_dir()] if PROJECTS_DIR.exists() else []
    col1, col2 = st.columns([3, 1])
    with col2:
        load_proj = st.selectbox("Load Project", options=[""] + existing_projects, key="load_proj_select")
        if load_proj and st.button("Load", key="load_proj_btn"):
            proj_dir = PROJECTS_DIR / load_proj
            if (proj_dir / "equipment.json").exists():
                st.session_state.proj_equipment = load_json_file(proj_dir / "equipment.json")
            st.success(f"Loaded: {load_proj}")

    st.markdown("---")

    # Step 1: Select Topology
    st.subheader("1️⃣ Select Topology")
    topos = list_json_files(TOPOLOGIES_DIR)
    selected_topo = st.selectbox("Topology File", options=[""] + topos, key="proj_topo_select")
    
    if selected_topo:
        topo_data = load_json_file(TOPOLOGIES_DIR / f"{selected_topo}.json")
        if topo_data:
            elements = topo_data.get("elements", [])
            node_count = len([e for e in elements if e.get("type") in ["Transceiver", "Roadm", "Edfa", "Fused"]])
            fiber_count = len([e for e in elements if e.get("type") in ["Fiber", "RamanFiber"]])
            conn_count = len(topo_data.get("connections", []))
            st.info(f"📊 {node_count} nodes, {fiber_count} fibers, {conn_count} connections")
    
    st.markdown("---")

    # Step 2: Select Components
    st.subheader("2️⃣ Select Components from Library")

    col1, col2 = st.columns(2)
    
    with col1:
        # Amplifiers
        st.markdown("**Amplifiers (EDFA)**")
        amp_options = list_json_files(LIBRARY_DIR / "amplifiers")
        selected_amps = st.multiselect("Select amplifier types", options=amp_options, key="proj_amps")
        
        # Fibers
        st.markdown("**Fiber Types**")
        fiber_options = list_json_files(LIBRARY_DIR / "fibers")
        selected_fibers = st.multiselect("Select fiber types", options=fiber_options, key="proj_fibers")
        
        # ROADMs
        st.markdown("**ROADMs**")
        roadm_options = list_json_files(LIBRARY_DIR / "roadms")
        selected_roadms = st.multiselect("Select ROADM types", options=roadm_options, key="proj_roadms")

    with col2:
        # Transceivers
        st.markdown("**Transceivers**")
        trx_options = list_json_files(LIBRARY_DIR / "transceivers")
        selected_trx = st.multiselect("Select transceiver types", options=trx_options, key="proj_trx")
        
        # SI Parameters
        st.markdown("**Simulation Parameters**")
        si_options = list_json_files(LIBRARY_DIR / "simulation_params")
        selected_si = st.selectbox("Select SI preset", options=["(default)"] + si_options, key="proj_si")

    st.markdown("---")

    # Step 3: Span Configuration
    st.subheader("3️⃣ Span Configuration")
    
    span = get_default_span()
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        span_power_mode = st.checkbox("power_mode", value=span["power_mode"], key="span_pwr_mode")
        span_max_length = st.number_input("max_length (km)", value=float(span["max_length"]), key="span_max_len")
        span_loss_ref = st.number_input("span_loss_ref (dB) [optional]", value=float(span.get("span_loss_ref", 20)), key="span_loss_ref")
    with c2:
        span_max_loss = st.number_input("max_loss (dB)", value=float(span["max_loss"]), key="span_max_loss")
        span_padding = st.number_input("padding", value=float(span["padding"]), key="span_padding")
        span_power_slope = st.number_input("power_slope [optional]", value=float(span.get("power_slope", 0.3)), key="span_power_slope")
    with c3:
        span_eol = st.number_input("EOL", value=float(span["EOL"]), key="span_eol")
        span_con_in = st.number_input("con_in", value=float(span["con_in"]), key="span_con_in")
        span_voa_margin = st.number_input("voa_margin (dB) [optional]", value=float(span.get("voa_margin", 1.0)), key="span_voa_margin")
    with c4:
        span_con_out = st.number_input("con_out", value=float(span["con_out"]), key="span_con_out")
        span_target_ext = st.number_input("target_extended_gain", value=float(span["target_extended_gain"]), key="span_target_ext")
        span_voa_step = st.number_input("voa_step (dB) [optional]", value=float(span.get("voa_step", 0.5)), key="span_voa_step")

    st.markdown("---")

    # Generate & Save
    c1, c2 = st.columns(2)
    
    with c1:
        if st.button("🔨 Generate Equipment JSON", type="primary", use_container_width=True, key="gen_equipment"):
            if not selected_topo:
                st.error("Please select a topology first")
            else:
                equipment = {"Edfa": [], "Fiber": [], "RamanFiber": [], "Span": [], "Roadm": [], "SI": [], "Transceiver": []}
                
                # Add amplifiers (flattened to GNPy-native shape)
                for amp_name in selected_amps:
                    amp_data = unwrap_component(load_json_file(LIBRARY_DIR / "amplifiers" / f"{amp_name}.json"))
                    if amp_data:
                        equipment["Edfa"].append(amp_data)
                
                # Add fiber types
                for fib_name in selected_fibers:
                    fib_data = unwrap_component(load_json_file(LIBRARY_DIR / "fibers" / f"{fib_name}.json"))
                    if fib_data:
                        equipment["Fiber"].append(fib_data)
                
                # Add ROADMs
                for roadm_name in selected_roadms:
                    roadm_data = unwrap_component(load_json_file(LIBRARY_DIR / "roadms" / f"{roadm_name}.json"))
                    if roadm_data:
                        equipment["Roadm"].append(roadm_data)
                
                # Add transceivers (normalized to strict GNPy schema on export)
                for trx_name in selected_trx:
                    trx_data = unwrap_component(load_json_file(LIBRARY_DIR / "transceivers" / f"{trx_name}.json"))
                    if trx_data:
                        equipment["Transceiver"].append(_strict_transceiver(trx_data))
                
                # Add SI parameters
                if selected_si and selected_si != "(default)":
                    si_data = unwrap_component(load_json_file(LIBRARY_DIR / "simulation_params" / f"{selected_si}.json"))
                    if si_data:
                        equipment["SI"].append(si_data)
                else:
                    equipment["SI"].append(get_default_si_params())
                
                # Add Span
                equipment["Span"].append({
                    "power_mode": span_power_mode,
                    "delta_power_range_db": [-2, 3, 0.5],
                    "max_fiber_lineic_loss_for_raman": 0.25,
                    "target_extended_gain": span_target_ext,
                    "max_length": span_max_length,
                    "length_units": "km",
                    "max_loss": span_max_loss,
                    "padding": span_padding,
                    "EOL": span_eol,
                    "con_in": span_con_in,
                    "con_out": span_con_out,
                    "span_loss_ref": span_loss_ref,
                    "power_slope": span_power_slope,
                    "voa_margin": span_voa_margin,
                    "voa_step": span_voa_step,
                })
                
                # Default ROADM if none selected
                if not equipment["Roadm"]:
                    equipment["Roadm"].append(get_default_roadm())
                
                st.session_state.proj_equipment = equipment
                st.success("Generated equipment.json!")
                st.json(equipment)

    with c2:
        if st.button("💾 Save Project", use_container_width=True, key="save_project"):
            if not project_name.strip():
                st.error("Project name is required")
            elif not selected_topo:
                st.error("Please select a topology")
            elif "proj_equipment" not in st.session_state:
                st.error("Generate equipment first")
            else:
                proj_dir = PROJECTS_DIR / project_name.strip()
                proj_dir.mkdir(parents=True, exist_ok=True)
                
                # Copy topology
                topo_data = load_json_file(TOPOLOGIES_DIR / f"{selected_topo}.json")
                save_json_file(proj_dir / "topology.json", topo_data)
                
                # Save equipment
                save_json_file(proj_dir / "equipment.json", st.session_state.proj_equipment)
                
                st.success(f"Project saved to: {proj_dir}")


# =============================================================================
# Tab 4: Services Generator
# =============================================================================
def render_services_generator():
    st.header("📡 Services Generator")
    st.caption("Create path requests with validation that source/destination exist in the topology")

    # Select project or topology
    col1, col2 = st.columns(2)
    
    with col1:
        projects = [d.name for d in PROJECTS_DIR.iterdir() if d.is_dir()] if PROJECTS_DIR.exists() else []
        selected_project = st.selectbox("Select Project", options=[""] + projects, key="svc_project")
    
    with col2:
        topos = list_json_files(TOPOLOGIES_DIR)
        selected_topo = st.selectbox("Or Select Topology", options=[""] + topos, key="svc_topo")

    # Load topology and get valid nodes
    valid_nodes = []
    topo_data = None
    
    if selected_project:
        topo_data = load_json_file(PROJECTS_DIR / selected_project / "topology.json")
    elif selected_topo:
        topo_data = load_json_file(TOPOLOGIES_DIR / f"{selected_topo}.json")
    
    if topo_data:
        elements = topo_data.get("elements", [])
        # Only Transceivers and ROADMs can be endpoints
        valid_nodes = sorted([e.get("uid") for e in elements if e.get("type") in ["Transceiver", "Roadm"] and e.get("uid")])
        st.success(f"✅ Loaded topology with {len(valid_nodes)} valid endpoint nodes")
    else:
        st.warning("⚠️ Select a project or topology to enable node validation")

    st.markdown("---")

    # Services editor
    st.subheader("Path Requests")
    
    # Initialize services
    if "svc_requests" not in st.session_state:
        st.session_state.svc_requests = []

    # Get available transceivers for mode selection
    trx_options = list_json_files(LIBRARY_DIR / "transceivers")
    trx_modes: dict[str, list[str]] = {}
    for trx_name in trx_options:
        trx_data = load_json_file(LIBRARY_DIR / "transceivers" / f"{trx_name}.json")
        if trx_data:
            trx_modes[trx_data.get("type_variety", trx_name)] = [m.get("format", "") for m in trx_data.get("mode", [])]

    # Add new request form
    with st.expander("➕ Add New Request", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            req_id = st.text_input("Request ID *", value=f"request_{len(st.session_state.svc_requests) + 1}", key="new_req_id")
            if valid_nodes:
                source = st.selectbox("Source Node *", options=[""] + valid_nodes, key="new_req_source")
            else:
                source = st.text_input("Source Node *", key="new_req_source_txt")
        with c2:
            if valid_nodes:
                destination = st.selectbox("Destination Node *", options=[""] + valid_nodes, key="new_req_dest")
            else:
                destination = st.text_input("Destination Node *", key="new_req_dest_txt")
            bidir = st.checkbox("Bidirectional", value=False, key="new_req_bidir")
        with c3:
            trx_type = st.selectbox("Transceiver Type", options=[""] + list(trx_modes.keys()), key="new_req_trx")
            available_modes = trx_modes.get(trx_type, ["mode 1"]) if trx_type else ["mode 1"]
            trx_mode = st.selectbox("Transceiver Mode", options=available_modes if available_modes else ["mode 1"], key="new_req_mode")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            spacing = st.number_input("Spacing (GHz)", value=50.0, key="new_req_spacing")
        with c2:
            path_bw = st.number_input("Path Bandwidth (Gbps)", value=100.0, key="new_req_bw")
        with c3:
            max_nb_channel = st.number_input("Max Channels [optional, 0=auto]", value=0, min_value=0, key="new_req_max_ch")
        
        # Optional advanced parameters
        with st.expander("Advanced Options", expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                output_power = st.number_input("Output Power (W) [0=default]", value=0.0, min_value=0.0, format="%.6f", key="new_req_output_power")
                tx_power = st.number_input("TX Power (W) [0=default]", value=0.0, min_value=0.0, format="%.6f", key="new_req_tx_power")
            with c2:
                include_nodes = st.text_input("Include Nodes (comma-separated UIDs) [optional]", key="new_req_include_nodes")

        if st.button("Add Request", type="primary", key="add_request"):
            # Validation
            errors = []
            if not req_id.strip():
                errors.append("Request ID is required")
            if not source:
                errors.append("Source node is required")
            if not destination:
                errors.append("Destination node is required")
            if source == destination and source:
                errors.append("Source and destination must be different")
            if valid_nodes:
                if source and source not in valid_nodes:
                    errors.append(f"Source '{source}' not found in topology")
                if destination and destination not in valid_nodes:
                    errors.append(f"Destination '{destination}' not found in topology")
            
            if errors:
                for err in errors:
                    st.error(err)
            else:
                request_data: dict[str, Any] = {
                    "request-id": req_id.strip(),
                    "source": source,
                    "destination": destination,
                    "src-tp-id": source,
                    "dst-tp-id": destination,
                    "bidirectional": bidir,
                    "path-constraints": {
                        "te-bandwidth": {
                            "technology": "flexi-grid",
                            "trx_type": trx_type or "Voyager",
                            "trx_mode": trx_mode or "mode 1",
                            "spacing": spacing * 1e9,
                            "path_bandwidth": path_bw * 1e9
                        }
                    }
                }
                
                # Add optional fields if specified
                if max_nb_channel > 0:
                    request_data["path-constraints"]["te-bandwidth"]["max-nb-of-channel"] = max_nb_channel
                if output_power > 0:
                    request_data["path-constraints"]["te-bandwidth"]["output-power"] = output_power
                if tx_power > 0:
                    request_data["path-constraints"]["te-bandwidth"]["tx_power"] = tx_power
                
                # Add route include constraints if specified
                if include_nodes.strip():
                    node_uids = [n.strip() for n in include_nodes.split(",") if n.strip()]
                    if node_uids:
                        request_data["path-constraints"]["te-bandwidth"]["route-object-include-exclude"] = [
                            {
                                "explicit-route-usage": "route-include-ero",
                                "index": idx,
                                "num-unnum-hop": {"node-id": uid, "hop-type": "STRICT"}
                            }
                            for idx, uid in enumerate(node_uids)
                        ]
                
                st.session_state.svc_requests.append(request_data)
                st.success(f"Added request: {req_id}")
                st.rerun()

    # Display existing requests
    st.markdown("---")
    st.subheader(f"Current Requests ({len(st.session_state.svc_requests)})")
    
    for i, req in enumerate(st.session_state.svc_requests):
        col1, col2, col3 = st.columns([3, 3, 1])
        with col1:
            st.write(f"**{req['request-id']}**")
        with col2:
            bidir_icon = "↔️" if req.get("bidirectional") else "→"
            st.write(f"{req['source']} {bidir_icon} {req['destination']}")
        with col3:
            if st.button("🗑️", key=f"del_req_{i}"):
                st.session_state.svc_requests.pop(i)
                st.rerun()

    # Save services
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        if st.button("💾 Save Services", type="primary", use_container_width=True, key="save_services"):
            if not st.session_state.svc_requests:
                st.error("No requests to save")
            elif not selected_project and not selected_topo:
                st.error("Select a project or topology first")
            else:
                services = {
                    "path-request": st.session_state.svc_requests,
                    "synchronization": []
                }
                
                if selected_project:
                    save_path = PROJECTS_DIR / selected_project / "services.json"
                else:
                    save_path = TOPOLOGIES_DIR / f"{selected_topo}_services.json"
                
                if save_json_file(save_path, services):
                    st.success(f"Saved to: {save_path}")
    
    with c2:
        if st.button("🆕 Clear All", use_container_width=True, key="clear_services"):
            st.session_state.svc_requests = []
            st.rerun()
    
    with c3:
        if st.button("📋 Preview JSON", use_container_width=True, key="preview_services"):
            st.json({
                "path-request": st.session_state.svc_requests,
                "synchronization": []
            })


# =============================================================================
# Tab 5: Common Tools
# =============================================================================
def render_common_tools():
    st.header("🧰 Common Tools")
    st.caption("Utility tools for network planning and data conversion")

    tool_type = st.selectbox(
        "Select Tool",
        ["Coordinate Converter (DMS → Decimal)"],
        key="tool_type_select"
    )

    if tool_type == "Coordinate Converter (DMS → Decimal)":
        render_coordinate_converter()


def render_coordinate_converter():
    st.subheader("📍 Coordinate Converter")
    st.caption("Convert Degrees, Minutes, Seconds (DMS) to Decimal Degrees. Paste from Excel.")

    st.markdown("#### Coordinates Table")
    st.caption("Paste from Excel: name, lat_deg, lat_min, lat_sec, lon_deg, lon_min, lon_sec (use negative degrees for S/W)")
    
    coord_default = [{
        "name": "", 
        "lat_deg": 0, "lat_min": 0, "lat_sec": 0.0,
        "lon_deg": 0, "lon_min": 0, "lon_sec": 0.0
    }]
    coord_df = pd.DataFrame(coord_default)
    
    edited_coords = st.data_editor(
        coord_df,
        num_rows="dynamic",
        use_container_width=True,
        key="coord_combined_editor",
        column_config={
            "name": st.column_config.TextColumn("Name/ID"),
            "lat_deg": st.column_config.NumberColumn("Lat°"),
            "lat_min": st.column_config.NumberColumn("Lat'"),
            "lat_sec": st.column_config.NumberColumn("Lat\"", format="%.6f"),
            "lon_deg": st.column_config.NumberColumn("Lon°"),
            "lon_min": st.column_config.NumberColumn("Lon'"),
            "lon_sec": st.column_config.NumberColumn("Lon\"", format="%.6f"),
        }
    )

    st.markdown("---")
    
    if st.button("🔄 Convert to Decimal", type="primary", use_container_width=True, key="convert_coords"):
        results = []
        
        for idx, row in edited_coords.iterrows():
            name = str(row.get("name", "")).strip() if pd.notna(row.get("name")) else ""
            
            # Check if row has any meaningful data
            lat_deg = row.get("lat_deg", 0)
            lat_min = row.get("lat_min", 0)
            lat_sec = row.get("lat_sec", 0.0)
            lon_deg = row.get("lon_deg", 0)
            lon_min = row.get("lon_min", 0)
            lon_sec = row.get("lon_sec", 0.0)
            
            has_lat = (pd.notna(lat_deg) and lat_deg != 0) or \
                      (pd.notna(lat_min) and lat_min != 0) or \
                      (pd.notna(lat_sec) and lat_sec != 0.0)
            has_lon = (pd.notna(lon_deg) and lon_deg != 0) or \
                      (pd.notna(lon_min) and lon_min != 0) or \
                      (pd.notna(lon_sec) and lon_sec != 0.0)
            
            if not has_lat and not has_lon and not name:
                continue
            
            # Parse latitude (sign of degrees determines N/S)
            lat_d = float(lat_deg) if pd.notna(lat_deg) else 0.0
            lat_m = float(lat_min) if pd.notna(lat_min) else 0.0
            lat_s = float(lat_sec) if pd.notna(lat_sec) else 0.0
            
            # Calculate latitude decimal (preserve sign from degrees)
            sign = -1 if lat_d < 0 else 1
            lat_decimal = sign * (abs(lat_d) + (abs(lat_m) / 60) + (abs(lat_s) / 3600))
            
            # Parse longitude (sign of degrees determines E/W)
            lon_d = float(lon_deg) if pd.notna(lon_deg) else 0.0
            lon_m = float(lon_min) if pd.notna(lon_min) else 0.0
            lon_s = float(lon_sec) if pd.notna(lon_sec) else 0.0
            
            # Calculate longitude decimal (preserve sign from degrees)
            sign = -1 if lon_d < 0 else 1
            lon_decimal = sign * (abs(lon_d) + (abs(lon_m) / 60) + (abs(lon_s) / 3600))
            
            results.append({
                "name": name or f"Point {idx + 1}",
                "latitude": round(lat_decimal, 8),
                "longitude": round(lon_decimal, 8),
            })
        
        # Display results
        if results:
            st.markdown("---")
            st.subheader("📊 Conversion Results")
            
            result_df = pd.DataFrame(results)
            st.dataframe(result_df, use_container_width=True, hide_index=True)
        else:
            st.info("No data to convert. Enter coordinates in the table above.")
    
    # Clear button
    if st.button("🆕 Clear All", use_container_width=True, key="clear_coords"):
        st.rerun()
    
    # Help section
    with st.expander("ℹ️ How to use"):
        st.markdown("""
        **DMS to Decimal Conversion Formula:**
        ```
        Decimal = Degrees + (Minutes / 60) + (Seconds / 3600)
        ```
        
        **Sign Convention:**
        - **Negative latitude** = South
        - **Positive latitude** = North  
        - **Negative longitude** = West
        - **Positive longitude** = East
        
        **Example:**
        - 40° 26' 46" (North) → lat_deg=40, lat_min=26, lat_sec=46 → 40.44611111
        - 79° 58' 21" (West) → lon_deg=-79, lon_min=58, lon_sec=21 → -79.97250000
        
        **Columns:**
        - `name`: Site/point identifier
        - `lat_deg`, `lat_min`, `lat_sec`: Latitude degrees, minutes, seconds
        - `lon_deg`, `lon_min`, `lon_sec`: Longitude degrees, minutes, seconds
        
        **Tips:**
        - Use negative degrees for South latitudes and West longitudes
        - Paste data directly from Excel with columns in the same order
        - Add rows by clicking + or pressing Enter in the last row
        """)


# =============================================================================
# Main App
# =============================================================================
def main():
    st.set_page_config(
        page_title="GNPy Input Generator v2",
        page_icon="🛠️",
        layout="wide"
    )

    st.title("🛠️ GNPy Input Generator v2")
    st.caption("Workflow-oriented tool for building GNPy simulation inputs")

    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📚 Component Library",
        "🗺️ Topology Builder",
        "🔧 Project Assembler",
        "📡 Services Generator",
        "🧰 Common Tools"
    ])

    with tab1:
        render_component_library()

    with tab2:
        render_topology_builder()

    with tab3:
        render_project_assembler()

    with tab4:
        render_services_generator()

    with tab5:
        render_common_tools()

    # Sidebar info
    st.sidebar.title("📁 Workspace")
    st.sidebar.markdown(f"""
    **Library:** `inputs/library/`
    - Amplifiers: {len(list_json_files(LIBRARY_DIR / 'amplifiers'))}
    - Fibers: {len(list_json_files(LIBRARY_DIR / 'fibers'))}
    - Transceivers: {len(list_json_files(LIBRARY_DIR / 'transceivers'))}
    - ROADMs: {len(list_json_files(LIBRARY_DIR / 'roadms'))}
    - SI Presets: {len(list_json_files(LIBRARY_DIR / 'simulation_params'))}
    
    **Topologies:** {len(list_json_files(TOPOLOGIES_DIR))}
    
    **Projects:** {len([d for d in PROJECTS_DIR.iterdir() if d.is_dir()] if PROJECTS_DIR.exists() else [])}
    """)


if __name__ == "__main__":
    main()
