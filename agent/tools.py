"""
Agent tools for the GNPy Simulator.

Every tool here is a thin wrapper around existing, UI-free logic:
  * ``gnpy_schema`` builders/validators/defaults (the single source of truth)
  * the on-disk ``inputs/`` layout used by the manual apps

No business logic is duplicated and the manual apps are never imported, so the
two manual Streamlit apps remain fully independent of this package.

Tools return JSON strings (best for tool-calling models). Writes are isolated
to two explicit tools (``save_component``, ``save_topology``) so the agent can
follow a preview -> confirm -> save flow.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional, Union

# Make the repo root importable so we can reuse gnpy_schema regardless of the
# working directory the Streamlit app is launched from.
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import gnpy_schema as schema  # noqa: E402

try:
    from langchain_core.tools import tool
except ImportError as exc:  # pragma: no cover - environment dependent
    raise ImportError(
        "langchain-core is not installed. Run `pip install -r requirements-agent.txt`."
    ) from exc


# =============================================================================
# Paths (mirror app_CustomInputGenerator_v2.py layout)
# =============================================================================
LIBRARY_DIR = BASE_DIR / "inputs" / "library"
TOPOLOGIES_DIR = BASE_DIR / "inputs" / "topologies"
INPUTS_DIR = BASE_DIR / "inputs"
DOCS_DIR = BASE_DIR / "docs"

# category -> on-disk library folder
CATEGORY_FOLDERS = {
    "edfa": "amplifiers",
    "fiber": "fibers",
    "raman_fiber": "raman_fibers",
    "roadm": "roadms",
    "transceiver": "transceivers",
    "si": "simulation_params",
}

# Discriminator hints shown to the agent so it can pick a valid variant.
CATEGORY_DISCRIMINATORS = {
    "edfa": {"name": "type_def", "options": schema.EDFA_TYPE_DEFS},
    "fiber": {"name": "dispersion_mode", "options": schema.FIBER_DISPERSION_MODES},
    "raman_fiber": {"name": "dispersion_mode", "options": schema.FIBER_DISPERSION_MODES},
    "roadm": {"name": "equalization", "options": schema.ROADM_EQUALIZATION_STRATEGIES},
    "transceiver": {"name": None, "options": []},
    "si": {"name": None, "options": []},
}


def _as_dict(params: Union[dict, str, None]) -> dict:
    """Accept either a dict or a JSON string for tool params."""
    if params is None:
        return {}
    if isinstance(params, dict):
        return params
    if isinstance(params, str):
        params = params.strip()
        if not params:
            return {}
        try:
            loaded = json.loads(params)
            return loaded if isinstance(loaded, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _ok(payload: dict) -> str:
    return json.dumps(payload, indent=2, default=str)


# =============================================================================
# Core build/validate routing (shared by tools)
# =============================================================================
def _build_and_validate(category: str, params: dict, discriminator: Optional[str]):
    """Return (component_dict, errors, warnings) for any category."""
    cat = category.lower().strip()

    if cat == "edfa":
        type_def = discriminator or params.get("type_def") or "variable_gain"
        built = schema.build_edfa(params, type_def)
        errors, warnings = schema.validate_edfa(built)
        return built, errors, warnings

    if cat in ("fiber", "raman_fiber"):
        mode = discriminator or schema.detect_fiber_dispersion_mode(params) or "scalar"
        built = schema.build_fiber(params, mode)
        errors, warnings = schema.validate_fiber(built)
        return built, errors, warnings

    if cat == "roadm":
        eq = discriminator or schema.detect_roadm_equalization(params) or "target_pch_out_db"
        built = schema.build_roadm(params, eq, preserve=params)
        errors, warnings = schema.validate_roadm(built)
        return built, errors, warnings

    if cat == "si":
        built = schema.build_si(params)
        errors, warnings = schema.validate_si(built)
        return built, errors, warnings

    if cat == "transceiver":
        modes_in = params.get("mode") or params.get("modes") or []
        modes = [schema.build_transceiver_mode(m, m.get("penalties")) for m in modes_in]
        freq = params.get("frequency", {})
        freq_min = freq.get("min", params.get("frequency_min", schema.DEFAULT_F_MIN_HZ))
        freq_max = freq.get("max", params.get("frequency_max", schema.DEFAULT_F_MAX_HZ))
        built = schema.build_transceiver(params.get("type_variety", ""), freq_min, freq_max, modes)
        errors, warnings = schema.validate_transceiver(built)
        return built, errors, warnings

    raise ValueError(
        f"Unknown category '{category}'. Valid: {sorted(CATEGORY_FOLDERS)}"
    )


# =============================================================================
# Schema discovery tools (for guided generation)
# =============================================================================
@tool
def list_component_categories() -> str:
    """List the GNPy component categories the agent can create, with their
    discriminator field (the choice that decides which parameters are valid)."""
    out = {}
    for cat, disc in CATEGORY_DISCRIMINATORS.items():
        out[cat] = {
            "library_folder": CATEGORY_FOLDERS[cat],
            "discriminator": disc["name"],
            "discriminator_options": disc["options"],
        }
    return _ok(out)


@tool
def describe_component_schema(category: str, discriminator: str = "") -> str:
    """Return the field specification for a component category so you can guide
    the user and build valid JSON.

    Args:
        category: one of edfa, fiber, raman_fiber, roadm, transceiver, si.
        discriminator: required for edfa (type_def), fiber/raman_fiber
            (dispersion_mode) and roadm (equalization). Ignored otherwise.

    Returns a JSON list of fields with key, label, type, default, required and
    help text. Use these exact keys when building params.
    """
    cat = category.lower().strip()
    disc = discriminator.strip() or None
    try:
        if cat == "edfa":
            specs = schema.edfa_field_specs(disc or "variable_gain")
        elif cat in ("fiber", "raman_fiber"):
            specs = schema.fiber_field_specs(disc or "scalar")
        elif cat == "roadm":
            specs = schema.roadm_field_specs(disc or "target_pch_out_db")
        elif cat == "transceiver":
            specs = schema.transceiver_mode_specs()
        elif cat == "si":
            specs = schema.si_field_specs()
        else:
            return _ok({"error": f"Unknown category '{category}'."})
    except Exception as e:  # noqa: BLE001
        return _ok({"error": str(e)})

    fields = [
        {
            "key": s["key"],
            "label": s["label"],
            "type": s["type"],
            "default": s["default"],
            "required": s.get("required", False),
            "help": s.get("help", ""),
        }
        for s in specs
    ]
    note = ""
    if cat == "transceiver":
        note = ("Transceiver params: {type_variety, frequency_min, frequency_max, "
                "mode:[{...mode fields...}]}. Fields above describe one mode.")
    return _ok({"category": cat, "discriminator": disc, "fields": fields, "note": note})


@tool
def get_component_defaults(category: str, discriminator: str = "") -> str:
    """Return a ready-to-edit default component object for a category. Good
    starting point before applying user- or datasheet-provided values."""
    cat = category.lower().strip()
    disc = discriminator.strip() or None
    try:
        if cat == "edfa":
            data = schema.default_edfa(disc or "variable_gain")
        elif cat in ("fiber", "raman_fiber"):
            data = schema.default_fiber(disc or "scalar")
        elif cat == "roadm":
            data = schema.default_roadm(disc or "target_pch_out_db")
        elif cat == "si":
            data = schema.default_si()
        elif cat == "transceiver":
            data = {
                "type_variety": "",
                "frequency_min": schema.DEFAULT_F_MIN_HZ,
                "frequency_max": schema.DEFAULT_F_MAX_HZ,
                "mode": [schema.default_transceiver_mode()],
            }
        else:
            return _ok({"error": f"Unknown category '{category}'."})
    except Exception as e:  # noqa: BLE001
        return _ok({"error": str(e)})
    return _ok({"category": cat, "discriminator": disc, "defaults": data})


# =============================================================================
# Build / validate (no disk writes)
# =============================================================================
@tool
def preview_component(category: str, params: Union[dict, str], discriminator: str = "") -> str:
    """Build a GNPy component from params and validate it WITHOUT saving.

    Always call this before save_component and show the user the resulting JSON
    plus any errors/warnings. Only valid (no-error) components should be saved.

    Args:
        category: edfa, fiber, raman_fiber, roadm, transceiver or si.
        params: dict (or JSON string) of field key -> value, using the keys from
            describe_component_schema.
        discriminator: type_def / dispersion_mode / equalization where required.
    """
    try:
        built, errors, warnings = _build_and_validate(
            category, _as_dict(params), discriminator.strip() or None
        )
    except Exception as e:  # noqa: BLE001
        return _ok({"error": str(e)})
    return _ok({
        "category": category.lower().strip(),
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "component": built,
    })


# =============================================================================
# Library read tools
# =============================================================================
@tool
def list_library(category: str = "") -> str:
    """List saved component files in the library. With no category, list all
    categories and their saved component names."""
    cat = category.lower().strip()
    if cat:
        if cat not in CATEGORY_FOLDERS:
            return _ok({"error": f"Unknown category '{category}'."})
        folder = LIBRARY_DIR / CATEGORY_FOLDERS[cat]
        names = sorted(f.stem for f in folder.glob("*.json")) if folder.exists() else []
        return _ok({cat: names})
    out = {}
    for c, sub in CATEGORY_FOLDERS.items():
        folder = LIBRARY_DIR / sub
        out[c] = sorted(f.stem for f in folder.glob("*.json")) if folder.exists() else []
    return _ok(out)


@tool
def read_library_component(category: str, name: str) -> str:
    """Read a saved component's JSON from the library by category and file name."""
    cat = category.lower().strip()
    if cat not in CATEGORY_FOLDERS:
        return _ok({"error": f"Unknown category '{category}'."})
    path = LIBRARY_DIR / CATEGORY_FOLDERS[cat] / f"{name}.json"
    if not path.exists():
        return _ok({"error": f"No '{name}' found in {cat}."})
    try:
        return _ok({"component": json.loads(path.read_text(encoding="utf-8"))})
    except Exception as e:  # noqa: BLE001
        return _ok({"error": str(e)})


@tool
def list_topologies() -> str:
    """List saved topology file names under inputs/topologies/."""
    names = sorted(f.stem for f in TOPOLOGIES_DIR.glob("*.json")) if TOPOLOGIES_DIR.exists() else []
    return _ok({"topologies": names})


@tool
def read_input_file(filename: str) -> str:
    """Read a JSON input file from the inputs/ folder (e.g. topology.json,
    equipment.json, path_requests.json). Returns its parsed JSON content."""
    # Constrain reads to the inputs/ tree.
    safe = (INPUTS_DIR / filename).resolve()
    if not str(safe).startswith(str(INPUTS_DIR.resolve())):
        return _ok({"error": "Path escapes inputs/ folder."})
    if not safe.exists():
        return _ok({"error": f"File not found: {filename}"})
    try:
        return _ok({"file": filename, "content": json.loads(safe.read_text(encoding="utf-8"))})
    except Exception as e:  # noqa: BLE001
        return _ok({"error": str(e)})


# =============================================================================
# Write tools (call only after the user confirms the previewed JSON)
# =============================================================================
@tool
def save_component(category: str, name: str, params: Union[dict, str], discriminator: str = "") -> str:
    """Save a validated component to the library. ONLY call this after the user
    has reviewed the preview_component output and explicitly approved saving.

    Refuses to write if validation produces errors.
    """
    cat = category.lower().strip()
    if cat not in CATEGORY_FOLDERS:
        return _ok({"error": f"Unknown category '{category}'."})
    name = name.strip()
    if not name:
        return _ok({"error": "A file name is required."})
    try:
        built, errors, warnings = _build_and_validate(
            cat, _as_dict(params), discriminator.strip() or None
        )
    except Exception as e:  # noqa: BLE001
        return _ok({"error": str(e)})
    if errors:
        return _ok({"saved": False, "errors": errors, "message": "Refusing to save invalid component."})

    folder = LIBRARY_DIR / CATEGORY_FOLDERS[cat]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.json"
    try:
        path.write_text(json.dumps(built, indent=2), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        return _ok({"saved": False, "error": str(e)})
    return _ok({
        "saved": True,
        "path": str(path.relative_to(BASE_DIR)),
        "warnings": warnings,
        "component": built,
    })


@tool
def save_topology(name: str, topology: Union[dict, str]) -> str:
    """Save a topology object ({network_name, elements, connections}) to
    inputs/topologies/<name>.json. Call only after user confirmation."""
    name = name.strip()
    if not name:
        return _ok({"error": "A topology name is required."})
    data = _as_dict(topology)
    if "elements" not in data or "connections" not in data:
        return _ok({"error": "Topology must contain 'elements' and 'connections'."})
    TOPOLOGIES_DIR.mkdir(parents=True, exist_ok=True)
    path = TOPOLOGIES_DIR / f"{name}.json"
    try:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        return _ok({"saved": False, "error": str(e)})
    return _ok({
        "saved": True,
        "path": str(path.relative_to(BASE_DIR)),
        "n_elements": len(data.get("elements", [])),
        "n_connections": len(data.get("connections", [])),
    })


# Convenience grouping consumed by agent.py
READ_TOOLS = [
    list_component_categories,
    describe_component_schema,
    get_component_defaults,
    preview_component,
    list_library,
    read_library_component,
    list_topologies,
    read_input_file,
]
WRITE_TOOLS = [save_component, save_topology]
ALL_TOOLS = READ_TOOLS + WRITE_TOOLS
