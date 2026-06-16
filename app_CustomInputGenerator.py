"""
Custom Input Generator for GNPy Network Simulation
Provides forms to build topology, equipment, and request JSON files.
"""

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

# Module-level BASE_DIR - defaults to this file's directory, 
# but can be overridden by calling set_base_dir()
_BASE_DIR = Path(__file__).resolve().parent


def set_base_dir(base_dir: Path):
    """Set the base directory for file operations."""
    global _BASE_DIR
    _BASE_DIR = base_dir


def get_base_dir() -> Path:
    """Get the current base directory."""
    return _BASE_DIR


def _resolve_path(file_path):
    """Resolve input path to an absolute Path under BASE_DIR when relative."""
    if file_path is None or str(file_path).strip() == "":
        raise ValueError("Input file path is empty.")

    resolved = Path(str(file_path)).expanduser()
    if not resolved.is_absolute():
        resolved = (_BASE_DIR / resolved).resolve()
    else:
        resolved = resolved.resolve()
    return resolved


def _default_custom_topology():
    return {
        "network_name": "Custom Network",
        "elements": [],
        "connections": []
    }


def _default_custom_equipment():
    return {
        "Edfa": [],
        "Fiber": [],
        "RamanFiber": [],
        "Span": [
            {
                "power_mode": True,
                "delta_power_range_db": [-2, 3, 0.5],
                "max_fiber_lineic_loss_for_raman": 0.25,
                "target_extended_gain": 2.5,
                "max_length": 150,
                "length_units": "km",
                "max_loss": 28,
                "padding": 10,
                "EOL": 0,
                "con_in": 0,
                "con_out": 0
            }
        ],
        "Roadm": [
            {
                "target_pch_out_db": -20,
                "add_drop_osnr": 38,
                "pmd": 0,
                "pdl": 0,
                "restrictions": {
                    "preamp_variety_list": [],
                    "booster_variety_list": []
                }
            }
        ],
        "SI": [
            {
                "f_min": 191.3e12,
                "baud_rate": 32e9,
                "f_max": 196.1e12,
                "spacing": 50e9,
                "power_dbm": 0,
                "power_range_db": [0, 0, 1],
                "tx_power_dbm": 0,
                "roll_off": 0.15,
                "tx_osnr": 40,
                "sys_margins": 2,
                "use_si_channel_count_for_design": True
            }
        ],
        "Transceiver": []
    }


def _default_custom_requests():
    return {
        "path-request": [],
        "synchronization": []
    }


def _init_custom_input_state():
    if "custom_topology_json" not in st.session_state:
        st.session_state.custom_topology_json = _default_custom_topology()
    if "custom_equipment_json" not in st.session_state:
        st.session_state.custom_equipment_json = _default_custom_equipment()
    if "custom_requests_json" not in st.session_state:
        st.session_state.custom_requests_json = _default_custom_requests()


def _parse_csv_list(value):
    if value is None:
        return []
    return [v.strip() for v in str(value).split(",") if v.strip()]


def _coerce_optional_float(value):
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    return float(text)


def _validate_custom_topology(payload):
    errors = []
    if not isinstance(payload, dict):
        errors.append("Topology root must be a JSON object.")
        return errors

    elements = payload.get("elements")
    connections = payload.get("connections")

    if not isinstance(elements, list):
        errors.append("Topology must include an 'elements' array.")
    if not isinstance(connections, list):
        errors.append("Topology must include a 'connections' array.")

    if isinstance(elements, list):
        for idx, element in enumerate(elements):
            if not isinstance(element, dict):
                errors.append(f"elements[{idx}] must be an object.")
                continue
            if "uid" not in element:
                errors.append(f"elements[{idx}] is missing 'uid'.")
            if "type" not in element:
                errors.append(f"elements[{idx}] is missing 'type'.")

    if isinstance(connections, list):
        for idx, connection in enumerate(connections):
            if not isinstance(connection, dict):
                errors.append(f"connections[{idx}] must be an object.")
                continue
            if "from_node" not in connection:
                errors.append(f"connections[{idx}] is missing 'from_node'.")
            if "to_node" not in connection:
                errors.append(f"connections[{idx}] is missing 'to_node'.")

    return errors


def _validate_custom_equipment(payload):
    errors = []
    required_keys = ["Edfa", "Fiber", "Span", "Roadm", "SI", "Transceiver"]

    if not isinstance(payload, dict):
        errors.append("Equipment root must be a JSON object.")
        return errors

    for key in required_keys:
        if key not in payload:
            errors.append(f"Equipment JSON is missing top-level key: {key}")

    if "SI" in payload and isinstance(payload.get("SI"), list) and payload["SI"]:
        si0 = payload["SI"][0]
        for key in ["f_min", "f_max", "spacing", "baud_rate", "roll_off", "tx_osnr"]:
            if key not in si0:
                errors.append(f"Equipment SI[0] is missing '{key}'.")
    return errors


def _validate_custom_requests(payload):
    errors = []
    if not isinstance(payload, dict):
        errors.append("Requests root must be a JSON object.")
        return errors

    requests = payload.get("path-request")
    if not isinstance(requests, list):
        errors.append("Requests must include a 'path-request' array.")
        return errors

    for idx, req in enumerate(requests):
        if not isinstance(req, dict):
            errors.append(f"path-request[{idx}] must be an object.")
            continue
        for key in ["request-id", "source", "destination", "src-tp-id", "dst-tp-id", "path-constraints"]:
            if key not in req:
                errors.append(f"path-request[{idx}] is missing '{key}'.")
    return errors


def _validate_custom_bundle(topology_payload, equipment_payload, requests_payload):
    errors = []
    errors.extend(_validate_custom_topology(topology_payload))
    errors.extend(_validate_custom_equipment(equipment_payload))
    errors.extend(_validate_custom_requests(requests_payload))
    return errors


def _save_custom_bundle(bundle_name, topology_payload, equipment_payload, requests_payload):
    target_dir = _BASE_DIR / "inputs" / "custom"
    target_dir.mkdir(parents=True, exist_ok=True)

    topology_file = target_dir / f"{bundle_name}_topology.json"
    equipment_file = target_dir / f"{bundle_name}_equipment.json"
    requests_file = target_dir / f"{bundle_name}_requests.json"

    topology_file.write_text(json.dumps(topology_payload, indent=2), encoding="utf-8")
    equipment_file.write_text(json.dumps(equipment_payload, indent=2), encoding="utf-8")
    requests_file.write_text(json.dumps(requests_payload, indent=2), encoding="utf-8")

    return topology_file, equipment_file, requests_file


def _load_custom_bundle(bundle_name):
    target_dir = _BASE_DIR / "inputs" / "custom"
    topology_file = target_dir / f"{bundle_name}_topology.json"
    equipment_file = target_dir / f"{bundle_name}_equipment.json"
    requests_file = target_dir / f"{bundle_name}_requests.json"

    if not topology_file.exists() or not equipment_file.exists() or not requests_file.exists():
        raise FileNotFoundError("Selected custom bundle is incomplete. Expected topology/equipment/requests files.")

    topology_payload = json.loads(topology_file.read_text(encoding="utf-8"))
    equipment_payload = json.loads(equipment_file.read_text(encoding="utf-8"))
    requests_payload = json.loads(requests_file.read_text(encoding="utf-8"))
    return topology_payload, equipment_payload, requests_payload


def custom_input_generator_ui(topology_path: str, equipment_path: str, requests_path: str, 
                               on_apply_callback=None):
    """
    Render the Custom Input Generator UI.
    
    Args:
        topology_path: Path to topology JSON file
        equipment_path: Path to equipment JSON file
        requests_path: Path to requests JSON file
        on_apply_callback: Optional callback function to call after applying changes
                          (e.g., to clear caches)
    """
    _init_custom_input_state()

    custom_topology = st.session_state.custom_topology_json
    custom_equipment = st.session_state.custom_equipment_json
    custom_requests = st.session_state.custom_requests_json

    generator_col, preview_col = st.columns([3, 2])

    with generator_col:
        with st.expander("Custom Input Generator", expanded=True):
            st.caption("Build topology, equipment, and request JSON from forms and export in simulator-compatible schema.")

            with st.container():
                section = st.selectbox(
                    "Builder Section *",
                    ["Topology", "Equipment", "Requests"],
                    key="gen_builder_section"
                )

            if section == "Topology":
                st.markdown("### Topology Components")
                st.caption("Paste data from Excel into the tables below. Each table can be edited directly.")

                topology_name = st.text_input("Network name (opt)", value=str(custom_topology.get("network_name", "Custom Network")), key="gen_topology_network_name")
                if topology_name.strip():
                    custom_topology["network_name"] = topology_name.strip()

                # === NODES TABLE ===
                st.markdown("#### Nodes (Transceiver, Roadm, Edfa, Fused)")
                
                # Initialize nodes dataframe from existing elements
                existing_nodes = [e for e in custom_topology.get("elements", []) if e.get("type") in ["Transceiver", "Roadm", "Edfa", "Fused"]]
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
                        "gain_target": node.get("operational", {}).get("gain_target", None),
                        "loss": node.get("params", {}).get("loss", None),
                    })
                
                if not nodes_data:
                    nodes_data = [{"uid": "", "type": "Transceiver", "city": "", "region": "", "latitude": None, "longitude": None, "type_variety": "", "gain_target": None, "loss": None}]
                
                nodes_df = pd.DataFrame(nodes_data)
                
                edited_nodes = st.data_editor(
                    nodes_df,
                    num_rows="dynamic",
                    use_container_width=True,
                    key="gen_nodes_editor",
                    column_config={
                        "uid": st.column_config.TextColumn("UID *", help="Unique identifier for the node"),
                        "type": st.column_config.SelectboxColumn("Type *", options=["Transceiver", "Roadm", "Edfa", "Fused"], required=True),
                        "city": st.column_config.TextColumn("City"),
                        "region": st.column_config.TextColumn("Region"),
                        "latitude": st.column_config.NumberColumn("Latitude", format="%.6f"),
                        "longitude": st.column_config.NumberColumn("Longitude", format="%.6f"),
                        "type_variety": st.column_config.TextColumn("Type Variety"),
                        "gain_target": st.column_config.NumberColumn("Gain Target (Edfa)", format="%.2f"),
                        "loss": st.column_config.NumberColumn("Loss (Fused)", format="%.2f"),
                    }
                )

                # === FIBERS TABLE ===
                st.markdown("#### Fibers")
                
                existing_fibers = [e for e in custom_topology.get("elements", []) if e.get("type") in ["Fiber", "RamanFiber"]]
                fibers_data = []
                for fiber in existing_fibers:
                    params = fiber.get("params", {})
                    fibers_data.append({
                        "uid": fiber.get("uid", ""),
                        "type": fiber.get("type", "Fiber"),
                        "type_variety": fiber.get("type_variety", "SSMF"),
                        "length_km": params.get("length", 80.0),
                        "loss_coef": params.get("loss_coef", 0.2),
                        "con_in": params.get("con_in", None),
                        "con_out": params.get("con_out", None),
                    })
                
                if not fibers_data:
                    fibers_data = [{"uid": "", "type": "Fiber", "type_variety": "SSMF", "length_km": 80.0, "loss_coef": 0.2, "con_in": None, "con_out": None}]
                
                fibers_df = pd.DataFrame(fibers_data)
                
                edited_fibers = st.data_editor(
                    fibers_df,
                    num_rows="dynamic",
                    use_container_width=True,
                    key="gen_fibers_editor",
                    column_config={
                        "uid": st.column_config.TextColumn("UID *", help="Unique identifier"),
                        "type": st.column_config.SelectboxColumn("Type *", options=["Fiber", "RamanFiber"], required=True),
                        "type_variety": st.column_config.TextColumn("Type Variety", default="SSMF"),
                        "length_km": st.column_config.NumberColumn("Length (km) *", min_value=0.001, format="%.3f"),
                        "loss_coef": st.column_config.NumberColumn("Loss Coef (dB/km) *", min_value=0.0, format="%.3f"),
                        "con_in": st.column_config.NumberColumn("Connector In"),
                        "con_out": st.column_config.NumberColumn("Connector Out"),
                    }
                )

                # === CONNECTIONS TABLE ===
                st.markdown("#### Connections")
                
                existing_connections = custom_topology.get("connections", [])
                connections_data = []
                for conn in existing_connections:
                    connections_data.append({
                        "from_node": conn.get("from_node", ""),
                        "to_node": conn.get("to_node", ""),
                    })
                
                if not connections_data:
                    connections_data = [{"from_node": "", "to_node": ""}]
                
                connections_df = pd.DataFrame(connections_data)
                
                edited_connections = st.data_editor(
                    connections_df,
                    num_rows="dynamic",
                    use_container_width=True,
                    key="gen_connections_editor",
                    column_config={
                        "from_node": st.column_config.TextColumn("From Node *", help="Source node UID"),
                        "to_node": st.column_config.TextColumn("To Node *", help="Target node UID"),
                    }
                )

                # === APPLY BUTTON ===
                if st.button("Apply Topology Changes", type="primary", use_container_width=True, key="gen_apply_topology"):
                    # Build nodes
                    new_elements = []
                    for _, row in edited_nodes.iterrows():
                        uid = str(row.get("uid", "")).strip()
                        if not uid:
                            continue
                        node: dict[str, Any] = {
                            "uid": uid,
                            "type": row.get("type", "Transceiver")
                        }
                        location: dict[str, Any] = {}
                        if pd.notna(row.get("city")) and str(row.get("city")).strip():
                            location["city"] = str(row.get("city")).strip()
                        if pd.notna(row.get("region")) and str(row.get("region")).strip():
                            location["region"] = str(row.get("region")).strip()
                        if pd.notna(row.get("latitude")):
                            location["latitude"] = float(row.get("latitude"))
                        if pd.notna(row.get("longitude")):
                            location["longitude"] = float(row.get("longitude"))
                        if location:
                            node["metadata"] = {"location": location}
                        if pd.notna(row.get("type_variety")) and str(row.get("type_variety")).strip():
                            node["type_variety"] = str(row.get("type_variety")).strip()
                        if row.get("type") == "Edfa" and pd.notna(row.get("gain_target")):
                            node["operational"] = {"gain_target": float(row.get("gain_target"))}
                        if row.get("type") == "Fused" and pd.notna(row.get("loss")):
                            node["params"] = {"loss": float(row.get("loss"))}
                        new_elements.append(node)
                    
                    # Build fibers
                    for _, row in edited_fibers.iterrows():
                        uid = str(row.get("uid", "")).strip()
                        if not uid:
                            continue
                        fiber: dict[str, Any] = {
                            "uid": uid,
                            "type": row.get("type", "Fiber"),
                            "type_variety": str(row.get("type_variety", "SSMF")).strip() or "SSMF",
                            "params": {
                                "length": float(row.get("length_km", 80.0)),
                                "length_units": "km",
                                "loss_coef": float(row.get("loss_coef", 0.2)),
                            }
                        }
                        if pd.notna(row.get("con_in")):
                            fiber["params"]["con_in"] = float(row.get("con_in"))
                        if pd.notna(row.get("con_out")):
                            fiber["params"]["con_out"] = float(row.get("con_out"))
                        new_elements.append(fiber)
                    
                    # Build connections
                    new_connections = []
                    for _, row in edited_connections.iterrows():
                        from_node = str(row.get("from_node", "")).strip()
                        to_node = str(row.get("to_node", "")).strip()
                        if from_node and to_node:
                            new_connections.append({"from_node": from_node, "to_node": to_node})
                    
                    # Update topology
                    custom_topology["elements"] = new_elements
                    custom_topology["connections"] = new_connections
                    st.success(f"Applied: {len(new_elements)} elements, {len(new_connections)} connections")

            elif section == "Equipment":
                st.markdown("### Equipment Components")
                st.markdown("##### EDFA")

                with st.form("add_equipment_edfa_form", clear_on_submit=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        edfa_type_variety = st.text_input("Type variety *", key="gen_eqpt_edfa_type_variety", help="Unique name for this EDFA type (e.g. 'MyCustomEDFA'). Required.")
                    with c2:
                        edfa_type_def = st.selectbox("Type def *", ["variable_gain", "fixed_gain", "openroadm", "advanced_model", "dual_stage"], key="gen_eqpt_edfa_type_def", help="Predefined behavior models. 'variable_gain' and 'fixed_gain' are simple models with basic parameters. 'openroadm' follows OpenROADM specifications. 'advanced_model' allows more detailed parameters. 'dual_stage' represents a two-stage amplifier with separate parameters for each stage.")
                    
                    c3, c4, c5 = st.columns(3)
                    with c3:
                        gain_flatmax = st.number_input("gain_flatmax *", value=26.0, step=0.1, key="gen_eqpt_edfa_gain_flatmax", help="Maximum gain in dB that this EDFA can provide while maintaining a flat gain profile. For 'fixed_gain' type, this is the target gain. For 'variable_gain', this is the maximum achievable gain.")
                    with c4:
                        gain_min = st.number_input("gain_min *", value=15.0, step=0.1, key="gen_eqpt_edfa_gain_min", help="Minimum gain in dB that this EDFA can provide.")
                    with c5:
                        p_max = st.number_input("p_max *", value=23.0, step=0.1, key="gen_eqpt_edfa_p_max", help="Maximum output power in dBm that this EDFA can provide.")
                    
                    c6, c7 = st.columns(2)
                    with c6:
                        nf_min = st.text_input("nf_min (opt)", value="", key="gen_eqpt_edfa_nf_min", help="Minimum noise figure in dB for this EDFA type. Optional parameter that can be used for more detailed modeling, especially with 'advanced_model' type. If left empty, noise figure will not be considered in simulations.")
                    with c7:
                        nf_max = st.text_input("nf_max (opt)", value="", key="gen_eqpt_edfa_nf_max", help="Maximum noise figure in dB for this EDFA type. Optional parameter that can be used for more detailed modeling, especially with 'advanced_model' type. If left empty, noise figure will not be considered in simulations.")
                    
                    c8, c9 = st.columns(2)
                    with c8:
                        out_voa_auto = st.checkbox("out_voa_auto", value=False, key="gen_eqpt_edfa_out_voa")
                        st.caption("If checked, this EDFA type will automatically add a Variable optical attenuator at output during design phase to meet gain targets. If unchecked, no VOA will be added and gain targets must be met by adjusting launch power or using different EDFA types.")
                    with c9:
                        allowed_for_design = st.checkbox("allowed_for_design", value=True, key="gen_eqpt_edfa_allowed")
                        st.caption("If unchecked, this EDFA type will not be considered during design phase but can be used in simulations.")

                    edfa_extra_json = st.text_area("extra fields json (opt)", value="", key="gen_eqpt_edfa_extra_json", help="Optional JSON object for advanced keys like nf0, nf_coef, f_min, f_max, default_config_from_json, advanced_config_from_json, amplifiers, preamp_variety, booster_variety, raman.")

                    add_edfa = st.form_submit_button("Add EDFA Type")
                    if add_edfa:
                        if not edfa_type_variety.strip():
                            st.error("EDFA type_variety is required.")
                        else:
                            valid_edfa = True
                            edfa_entry = {
                                "type_variety": edfa_type_variety.strip(),
                                "type_def": edfa_type_def,
                                "gain_flatmax": float(gain_flatmax),
                                "gain_min": float(gain_min),
                                "p_max": float(p_max),
                                "out_voa_auto": out_voa_auto,
                                "allowed_for_design": allowed_for_design
                            }
                            if nf_min.strip():
                                edfa_entry["nf_min"] = float(nf_min)
                            if nf_max.strip():
                                edfa_entry["nf_max"] = float(nf_max)
                            if edfa_extra_json.strip():
                                try:
                                    parsed_edfa_extra = json.loads(edfa_extra_json)
                                    if isinstance(parsed_edfa_extra, dict):
                                        edfa_entry.update(parsed_edfa_extra)
                                    else:
                                        st.error("extra fields json must be a JSON object.")
                                        valid_edfa = False
                                except Exception as exc:
                                    st.error(f"Invalid extra fields json: {exc}")
                                    valid_edfa = False
                            if valid_edfa:
                                custom_equipment["Edfa"].append(edfa_entry)
                                st.success(f"Added EDFA type: {edfa_type_variety}")
                st.markdown("##### Fiber")

                with st.form("add_equipment_fiber_form", clear_on_submit=True):
                    c1, c2, c3, c4 = st.columns(4)
                    with c1:
                        fiber_variety = st.text_input("Type variety *", value="SSMF", key="gen_eqpt_fiber_variety", help="Unique name for this fiber type (e.g. 'SSMF'). Required.")
                    with c2:
                        dispersion = st.number_input("dispersion *", value=1.67e-05, format="%.8f", key="gen_eqpt_fiber_dispersion", help="Chromatic dispersion coefficient in s/m^2. For standard single-mode fiber (SSMF), this is typically around 1.67e-05 s/m^2 at 1550 nm.")
                    with c3:
                        effective_area = st.number_input("effective_area *", value=83e-12, format="%.12f", key="gen_eqpt_fiber_effective_area", help="Effective area of the fiber in m^2. For SSMF, this is typically around 83e-12 m^2.")
                    with c4:
                        pmd_coef = st.number_input("pmd_coef *", value=1.265e-15, format="%.15f", key="gen_eqpt_fiber_pmd", help="Polarization mode dispersion coefficient in s/m^0.5. For SSMF, this is typically around 1.265e-15 s/m^0.5.")

                    c5, c6 = st.columns(2)
                    with c5:
                        fiber_gamma_opt = st.text_input("gamma (opt)", value="", key="gen_eqpt_fiber_gamma", help="Optional nonlinear coefficient in 1/W/m. If omitted, GNPy computes it from effective_area.")
                    with c6:
                        dispersion_slope_opt = st.text_input("dispersion_slope (opt)", value="", key="gen_eqpt_fiber_dispersion_slope", help="Optional dispersion slope in s/m^3.")

                    c7, c8, c9 = st.columns(3)
                    with c7:
                        fiber_raman_g0_csv = st.text_input("raman g0 csv (opt)", value="", key="gen_eqpt_fiber_raman_g0", help="Comma-separated Raman g0 values.")
                    with c8:
                        fiber_raman_offset_csv = st.text_input("raman freq offset csv (opt)", value="", key="gen_eqpt_fiber_raman_offset", help="Comma-separated Raman frequency offsets in Hz.")
                    with c9:
                        fiber_raman_ref_freq = st.text_input("raman ref freq (opt)", value="", key="gen_eqpt_fiber_raman_ref_freq", help="Optional Raman reference frequency in Hz.")

                    add_eq_fiber = st.form_submit_button("Add Fiber Type")
                    if add_eq_fiber:
                        valid_raman = True
                        fiber_entry = {
                            "type_variety": fiber_variety.strip(),
                            "dispersion": float(dispersion),
                            "effective_area": float(effective_area),
                            "pmd_coef": float(pmd_coef)
                        }
                        gamma_val = _coerce_optional_float(fiber_gamma_opt)
                        if gamma_val is not None:
                            fiber_entry["gamma"] = gamma_val

                        dispersion_slope_val = _coerce_optional_float(dispersion_slope_opt)
                        if dispersion_slope_val is not None:
                            fiber_entry["dispersion_slope"] = dispersion_slope_val

                        g0_values = [float(v) for v in _parse_csv_list(fiber_raman_g0_csv)]
                        offset_values = [float(v) for v in _parse_csv_list(fiber_raman_offset_csv)]
                        if g0_values or offset_values:
                            if len(g0_values) != len(offset_values):
                                st.error("Raman g0 and frequency_offset lists must have the same number of values.")
                                valid_raman = False
                            else:
                                raman_coeff: dict[str, Any] = {
                                    "g0": g0_values,
                                    "frequency_offset": offset_values
                                }
                                raman_ref = _coerce_optional_float(fiber_raman_ref_freq)
                                if raman_ref is not None:
                                    raman_coeff["reference_frequency"] = raman_ref
                                fiber_entry["raman_coefficient"] = raman_coeff
                        if valid_raman:
                            custom_equipment["Fiber"].append(fiber_entry)
                            st.success(f"Added fiber type: {fiber_variety}")

                with st.form("add_equipment_ramanfiber_form", clear_on_submit=True):
                    st.markdown("##### RamanFiber Type")
                    c1, c2, c3, c4 = st.columns(4)
                    with c1:
                        raman_variety = st.text_input("Type variety *", value="SSMF", key="gen_eqpt_raman_variety")
                    with c2:
                        raman_dispersion = st.number_input("dispersion *", value=1.67e-05, format="%.8f", key="gen_eqpt_raman_dispersion")
                    with c3:
                        raman_effective_area = st.number_input("effective_area *", value=83e-12, format="%.12f", key="gen_eqpt_raman_effective_area")
                    with c4:
                        raman_pmd = st.number_input("pmd_coef *", value=1.265e-15, format="%.15f", key="gen_eqpt_raman_pmd")

                    add_raman_fiber = st.form_submit_button("Add RamanFiber Type")
                    if add_raman_fiber:
                        if not raman_variety.strip():
                            st.error("RamanFiber type_variety is required.")
                        else:
                            custom_equipment["RamanFiber"].append({
                                "type_variety": raman_variety.strip(),
                                "dispersion": float(raman_dispersion),
                                "effective_area": float(raman_effective_area),
                                "pmd_coef": float(raman_pmd)
                            })
                            st.success(f"Added RamanFiber type: {raman_variety}")

                with st.form("set_equipment_span_form", clear_on_submit=False):
                    st.markdown("##### Span Parameters")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        span_power_mode = st.checkbox("power_mode *", value=bool(custom_equipment.get("Span", [{}])[0].get("power_mode", True)), key="gen_eqpt_span_power_mode")
                    with c2:
                        span_max_length = st.number_input("max_length *", min_value=1.0, value=float(custom_equipment.get("Span", [{}])[0].get("max_length", 150.0)), step=1.0, key="gen_eqpt_span_max_length")
                    with c3:
                        span_length_units = st.selectbox("length_units *", ["km", "m"], index=0 if str(custom_equipment.get("Span", [{}])[0].get("length_units", "km")) == "km" else 1, key="gen_eqpt_span_length_units")

                    c4, c5, c6 = st.columns(3)
                    with c4:
                        span_delta_min = st.number_input("delta_p min *", value=float(custom_equipment.get("Span", [{}])[0].get("delta_power_range_db", [0, 0, 0.5])[0]), key="gen_eqpt_span_delta_min")
                    with c5:
                        span_delta_max = st.number_input("delta_p max *", value=float(custom_equipment.get("Span", [{}])[0].get("delta_power_range_db", [0, 0, 0.5])[1]), key="gen_eqpt_span_delta_max")
                    with c6:
                        span_delta_step = st.number_input("delta_p step *", min_value=0.0, value=float(custom_equipment.get("Span", [{}])[0].get("delta_power_range_db", [0, 0, 0.5])[2]), key="gen_eqpt_span_delta_step")

                    c7, c8, c9, c10 = st.columns(4)
                    with c7:
                        span_padding = st.number_input("padding *", value=float(custom_equipment.get("Span", [{}])[0].get("padding", 10.0)), key="gen_eqpt_span_padding")
                    with c8:
                        span_eol = st.number_input("EOL *", value=float(custom_equipment.get("Span", [{}])[0].get("EOL", 0.0)), key="gen_eqpt_span_eol")
                    with c9:
                        span_con_in = st.number_input("con_in *", value=float(custom_equipment.get("Span", [{}])[0].get("con_in", 0.0)), key="gen_eqpt_span_con_in")
                    with c10:
                        span_con_out = st.number_input("con_out *", value=float(custom_equipment.get("Span", [{}])[0].get("con_out", 0.0)), key="gen_eqpt_span_con_out")

                    c11, c12, c13 = st.columns(3)
                    with c11:
                        span_max_loss = st.number_input("max_loss *", value=float(custom_equipment.get("Span", [{}])[0].get("max_loss", 28.0)), key="gen_eqpt_span_max_loss")
                    with c12:
                        span_max_lineic = st.number_input("max_fiber_lineic_loss_for_raman *", value=float(custom_equipment.get("Span", [{}])[0].get("max_fiber_lineic_loss_for_raman", 0.25)), key="gen_eqpt_span_max_lineic")
                    with c13:
                        span_target_ext = st.number_input("target_extended_gain *", value=float(custom_equipment.get("Span", [{}])[0].get("target_extended_gain", 2.5)), key="gen_eqpt_span_target_ext")

                    set_span = st.form_submit_button("Set Span Parameters")
                    if set_span:
                        custom_equipment["Span"] = [{
                            "power_mode": bool(span_power_mode),
                            "delta_power_range_db": [float(span_delta_min), float(span_delta_max), float(span_delta_step)],
                            "max_fiber_lineic_loss_for_raman": float(span_max_lineic),
                            "target_extended_gain": float(span_target_ext),
                            "max_length": float(span_max_length),
                            "length_units": span_length_units,
                            "max_loss": float(span_max_loss),
                            "padding": float(span_padding),
                            "EOL": float(span_eol),
                            "con_in": float(span_con_in),
                            "con_out": float(span_con_out)
                        }]
                        st.success("Span parameters updated.")

                with st.form("set_equipment_si_form", clear_on_submit=False):
                    st.markdown("##### SI Parameters")
                    si0 = custom_equipment.get("SI", [{}])[0]
                    c1, c2, c3, c4 = st.columns(4)
                    with c1:
                        si_f_min = st.number_input("f_min *", value=float(si0.get("f_min", 191.3e12)), format="%.1f", key="gen_eqpt_si_f_min")
                    with c2:
                        si_f_max = st.number_input("f_max *", value=float(si0.get("f_max", 196.1e12)), format="%.1f", key="gen_eqpt_si_f_max")
                    with c3:
                        si_baud = st.number_input("baud_rate *", value=float(si0.get("baud_rate", 32e9)), format="%.1f", key="gen_eqpt_si_baud")
                    with c4:
                        si_spacing = st.number_input("spacing *", value=float(si0.get("spacing", 50e9)), format="%.1f", key="gen_eqpt_si_spacing")

                    c5, c6, c7, c8 = st.columns(4)
                    with c5:
                        si_power_dbm = st.number_input("power_dbm *", value=float(si0.get("power_dbm", 0.0)), key="gen_eqpt_si_power_dbm")
                    with c6:
                        si_tx_power_dbm = st.number_input("tx_power_dbm *", value=float(si0.get("tx_power_dbm", 0.0)), key="gen_eqpt_si_tx_power_dbm")
                    with c7:
                        si_rolloff = st.number_input("roll_off *", value=float(si0.get("roll_off", 0.15)), key="gen_eqpt_si_rolloff")
                    with c8:
                        si_tx_osnr = st.number_input("tx_osnr *", value=float(si0.get("tx_osnr", 40.0)), key="gen_eqpt_si_tx_osnr")

                    c9, c10, c11, c12 = st.columns(4)
                    with c9:
                        si_margin = st.number_input("sys_margins *", value=float(si0.get("sys_margins", 2.0)), key="gen_eqpt_si_margins")
                    with c10:
                        si_pr_min = st.number_input("power_range min *", value=float(si0.get("power_range_db", [0, 0, 1])[0]), key="gen_eqpt_si_pr_min")
                    with c11:
                        si_pr_max = st.number_input("power_range max *", value=float(si0.get("power_range_db", [0, 0, 1])[1]), key="gen_eqpt_si_pr_max")
                    with c12:
                        si_pr_step = st.number_input("power_range step *", value=float(si0.get("power_range_db", [0, 0, 1])[2]), min_value=0.0, key="gen_eqpt_si_pr_step")

                    si_ch_count = st.checkbox("use_si_channel_count_for_design", value=bool(si0.get("use_si_channel_count_for_design", True)), key="gen_eqpt_si_channel_count")
                    set_si = st.form_submit_button("Set SI Parameters")
                    if set_si:
                        custom_equipment["SI"] = [{
                            "f_min": float(si_f_min),
                            "baud_rate": float(si_baud),
                            "f_max": float(si_f_max),
                            "spacing": float(si_spacing),
                            "power_dbm": float(si_power_dbm),
                            "power_range_db": [float(si_pr_min), float(si_pr_max), float(si_pr_step)],
                            "tx_power_dbm": float(si_tx_power_dbm),
                            "roll_off": float(si_rolloff),
                            "tx_osnr": float(si_tx_osnr),
                            "sys_margins": float(si_margin),
                            "use_si_channel_count_for_design": bool(si_ch_count)
                        }]
                        st.success("SI parameters updated.")

                with st.form("add_equipment_roadm_form", clear_on_submit=True):
                    st.markdown("##### ROADM Type")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        roadm_variety = st.text_input("type_variety (opt)", value="", key="gen_eqpt_roadm_variety")
                    with c2:
                        roadm_target = st.number_input("target_pch_out_db *", value=-20.0, step=0.1, key="gen_eqpt_roadm_target")
                    with c3:
                        roadm_add_drop_osnr = st.number_input("add_drop_osnr *", value=38.0, step=0.1, key="gen_eqpt_roadm_add_drop_osnr")

                    c4, c5 = st.columns(2)
                    with c4:
                        roadm_pmd = st.number_input("pmd *", value=0.0, step=0.1, key="gen_eqpt_roadm_pmd")
                    with c5:
                        roadm_pdl = st.number_input("pdl *", value=0.0, step=0.1, key="gen_eqpt_roadm_pdl")

                    c6, c7 = st.columns(2)
                    with c6:
                        preamps_csv = st.text_input("preamp_variety_list csv (opt)", value="", key="gen_eqpt_roadm_preamps")
                    with c7:
                        boosters_csv = st.text_input("booster_variety_list csv (opt)", value="", key="gen_eqpt_roadm_boosters")

                    roadm_impairments_json = st.text_area("roadm-path-impairments json (opt)", value="", key="gen_eqpt_roadm_impairments")
                    add_roadm = st.form_submit_button("Add ROADM Type")
                    if add_roadm:
                        valid_roadm = True
                        roadm_entry: dict[str, Any] = {
                            "target_pch_out_db": float(roadm_target),
                            "add_drop_osnr": float(roadm_add_drop_osnr),
                            "pmd": float(roadm_pmd),
                            "pdl": float(roadm_pdl),
                            "restrictions": {
                                "preamp_variety_list": _parse_csv_list(preamps_csv),
                                "booster_variety_list": _parse_csv_list(boosters_csv)
                            }
                        }
                        if roadm_variety.strip():
                            roadm_entry["type_variety"] = roadm_variety.strip()
                        if roadm_impairments_json.strip():
                            try:
                                parsed_imp = json.loads(roadm_impairments_json)
                                if isinstance(parsed_imp, list):
                                    roadm_entry["roadm-path-impairments"] = parsed_imp
                                else:
                                    st.error("roadm-path-impairments json must be a JSON list.")
                                    valid_roadm = False
                            except Exception as exc:
                                st.error(f"Invalid roadm-path-impairments json: {exc}")
                                valid_roadm = False
                        if valid_roadm:
                            custom_equipment["Roadm"].append(roadm_entry)
                            st.success("Added ROADM type.")

                with st.expander("Transceiver", expanded=True):
                    with st.form("add_equipment_transceiver_form", clear_on_submit=True):
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            trx_type_variety = st.text_input("Type variety *", key="gen_eqpt_trx_type_variety", help="Unique name for this transceiver type. Required.")
                        with c2:
                            freq_min = st.number_input("Freq min (Hz) *", value=191.35e12, format="%.1f", key="gen_eqpt_trx_fmin", help="Minimum operating frequency in Hz for this transceiver type.")
                        with c3:
                            freq_max = st.number_input("Freq max (Hz) *", value=196.1e12, format="%.1f", key="gen_eqpt_trx_fmax", help="Maximum operating frequency in Hz for this transceiver type.")

                        add_trx = st.form_submit_button("Add Transceiver Type")
                        if add_trx:
                            if not trx_type_variety.strip():
                                st.error("Transceiver type_variety is required.")
                            else:
                                existing_varieties = {
                                    str(t.get("type_variety", "")).strip()
                                    for t in custom_equipment.get("Transceiver", [])
                                    if isinstance(t, dict)
                                }
                                if trx_type_variety.strip() in existing_varieties:
                                    st.error("Transceiver type_variety already exists. Use it from dropdown to add modes.")
                                else:
                                    custom_equipment["Transceiver"].append({
                                        "type_variety": trx_type_variety.strip(),
                                        "frequency": {
                                            "min": float(freq_min),
                                            "max": float(freq_max)
                                        },
                                        "mode": []
                                    })
                                    st.success(f"Added transceiver type: {trx_type_variety}")

                    with st.expander("Modes", expanded=True):
                        transceivers = [t for t in custom_equipment.get("Transceiver", []) if isinstance(t, dict)]
                        transceiver_options = [str(t.get("type_variety", "")).strip() for t in transceivers if str(t.get("type_variety", "")).strip()]

                        if not transceiver_options:
                            st.info("Create a transceiver first, then add modes to it.")
                        else:
                            selected_trx = st.selectbox("Select existing transceiver *", transceiver_options, key="gen_eqpt_trx_selected")

                            with st.form("add_equipment_transceiver_mode_form", clear_on_submit=True):
                                c1, c2, c3 = st.columns(3)
                                with c1:
                                    mode_format = st.text_input("Mode *", value="mode 1", key="gen_eqpt_trx_mode_format", help="Modulation format for this transceiver mode.")
                                with c2:
                                    mode_baud = st.number_input("Baud rate *", value=32e9, format="%.1f", key="gen_eqpt_trx_mode_baud", help="Baud rate in Hz for this transceiver mode.")
                                with c3:
                                    mode_osnr = st.number_input("OSNR *", value=12.0, step=0.1, key="gen_eqpt_trx_mode_osnr", help="Optical Signal-to-Noise Ratio in dB for this transceiver mode.")

                                c4, c5, c6 = st.columns(3)
                                with c4:
                                    mode_bitrate = st.number_input("Bit rate *", value=100e9, format="%.1f", key="gen_eqpt_trx_mode_bitrate", help="Bit rate in Hz for this transceiver mode.")
                                with c5:
                                    mode_rolloff = st.number_input("Roll off *", value=0.15, step=0.01, key="gen_eqpt_trx_mode_rolloff", help="Roll-off factor for this transceiver mode.")
                                with c6:
                                    mode_tx_osnr = st.number_input("TX OSNR *", value=40.0, step=0.1, key="gen_eqpt_trx_mode_txosnr", help="Transmitter Optical Signal-to-Noise Ratio in dB for this transceiver mode.")

                                c7, c8 = st.columns(2)
                                with c7:
                                    mode_min_spacing = st.number_input("Min spacing *", value=50e9, format="%.1f", key="gen_eqpt_trx_mode_spacing", help="Minimum spacing in Hz for this transceiver mode.")
                                with c8:
                                    mode_cost = st.number_input("Cost *", value=1.0, step=0.1, key="gen_eqpt_trx_mode_cost", help="Cost for this transceiver mode.")

                                c9, c10 = st.columns(2)
                                with c9:
                                    mode_eq_offset = st.text_input("equalization_offset_db (opt)", value="", key="gen_eqpt_trx_mode_eq_offset")
                                with c10:
                                    mode_penalties_json = st.text_area("penalties json (opt)", value="", key="gen_eqpt_trx_mode_penalties", help="Example: [{\"chromatic_dispersion\": 360000, \"penalty_value\": 0.5}]")

                                add_mode = st.form_submit_button("Add Mode To Selected Transceiver")
                                if add_mode:
                                    if not mode_format.strip():
                                        st.error("Mode format is required.")
                                    else:
                                        valid_mode = True
                                        mode_entry: dict[str, Any] = {
                                            "format": mode_format.strip(),
                                            "baud_rate": float(mode_baud),
                                            "OSNR": float(mode_osnr),
                                            "bit_rate": float(mode_bitrate),
                                            "roll_off": float(mode_rolloff),
                                            "tx_osnr": float(mode_tx_osnr),
                                            "min_spacing": float(mode_min_spacing),
                                            "cost": float(mode_cost)
                                        }
                                        eq_offset_val = _coerce_optional_float(mode_eq_offset)
                                        if eq_offset_val is not None:
                                            mode_entry["equalization_offset_db"] = eq_offset_val
                                        if mode_penalties_json.strip():
                                            try:
                                                penalties_val = json.loads(mode_penalties_json)
                                                if isinstance(penalties_val, list):
                                                    mode_entry["penalties"] = penalties_val
                                                else:
                                                    st.error("penalties json must be a JSON list.")
                                                    valid_mode = False
                                            except Exception as exc:
                                                st.error(f"Invalid penalties json: {exc}")
                                                valid_mode = False

                                        if valid_mode:
                                            target_trx = next((t for t in transceivers if str(t.get("type_variety", "")).strip() == selected_trx), None)
                                            if target_trx is None:
                                                st.error("Selected transceiver was not found.")
                                            else:
                                                if not isinstance(target_trx.get("mode"), list):
                                                    target_trx["mode"] = []
                                                target_trx["mode"].append(mode_entry)
                                                st.success(f"Added mode to transceiver: {selected_trx}")

                            selected_entry = next((t for t in transceivers if str(t.get("type_variety", "")).strip() == selected_trx), None)
                            selected_modes = selected_entry.get("mode", []) if isinstance(selected_entry, dict) else []
                            if selected_modes:
                                st.caption(f"Modes for {selected_trx}: {len(selected_modes)}")
                                for idx, mode in enumerate(selected_modes, start=1):
                                    row1, row2 = st.columns([5, 1])
                                    with row1:
                                        st.write(
                                            f"{idx}. {mode.get('format', '')} | baud={mode.get('baud_rate', 0):.3g} | "
                                            f"bit_rate={mode.get('bit_rate', 0):.3g} | OSNR={mode.get('OSNR', 0):.3g}"
                                        )
                                    with row2:
                                        if st.button("Remove", key=f"gen_eqpt_trx_mode_remove_{selected_trx}_{idx}"):
                                            selected_modes.pop(idx - 1)
                                            st.rerun()
                                if selected_entry is not None and st.button("Clear Modes", key=f"gen_eqpt_trx_mode_clear_{selected_trx}"):
                                    selected_entry["mode"] = []
                                    st.rerun()

            else:
                st.markdown("### Request Components")

                with st.form("add_request_form", clear_on_submit=True):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        request_id = st.text_input("Request ID *", value="request_1", key="gen_req_id")
                    with c2:
                        source = st.text_input("Source *", key="gen_req_source")
                    with c3:
                        destination = st.text_input("Destination *", key="gen_req_destination")
                    
                    c4, c5, c6, c7 = st.columns(4)
                    with c4:
                        trx_type = st.text_input("TRX type *", value="Voyager", key="gen_req_trx_type")
                    with c5:
                        trx_mode = st.text_input("TRX mode", value="mode 1", key="gen_req_trx_mode")
                    with c6:
                        spacing = st.number_input("Spacing *", value=50e9, format="%.1f", key="gen_req_spacing")
                    with c7:
                        path_bandwidth = st.number_input("Path BW *", value=100e9, format="%.1f", key="gen_req_path_bw")

                    c8, c9, c10 = st.columns(3)
                    with c8:
                        req_max_channels = st.text_input("max-nb-of-channel (opt)", value="", key="gen_req_max_channels")
                    with c9:
                        req_output_power = st.text_input("output-power W (opt)", value="", key="gen_req_output_power")
                    with c10:
                        req_tx_power = st.text_input("tx_power W (opt)", value="", key="gen_req_tx_power")

                    c11, c12, c13 = st.columns(3)
                    with c11:
                        req_slot_n = st.text_input("effective slot N (opt)", value="", key="gen_req_slot_n")
                    with c12:
                        req_slot_m = st.text_input("effective slot M (opt)", value="", key="gen_req_slot_m")
                    with c13:
                        req_include_nodes_csv = st.text_input("include nodes csv (opt)", value="", key="gen_req_include_nodes")

                    req_include_hops_csv = st.text_input("include hop types csv (opt)", value="", key="gen_req_include_hops", help="LOOSE or STRICT per node, same count as include nodes")
                    
                    bidirectional = st.checkbox("Bidirectional *", value=False, key="gen_req_bidir")
                    add_request = st.form_submit_button("Add Path Request")
                    if add_request:
                        if not source.strip() or not destination.strip():
                            st.error("source and destination are required.")
                        else:
                            valid_request = True
                            custom_equipment_types = [e.get("type_variety") for e in custom_equipment.get("Transceiver", []) if isinstance(e, dict)]
                            request = {
                                "request-id": request_id.strip(),
                                "source": source.strip(),
                                "destination": destination.strip(),
                                "src-tp-id": source.strip(),
                                "dst-tp-id": destination.strip(),
                                "bidirectional": bidirectional,
                                "path-constraints": {
                                    "te-bandwidth": {
                                        "technology": "flexi-grid",
                                        "trx_type": trx_type.strip() if trx_type.strip() else (custom_equipment_types[0] if custom_equipment_types else "Voyager"),
                                        "trx_mode": trx_mode.strip() or "mode 1",
                                        "spacing": float(spacing),
                                        "path_bandwidth": float(path_bandwidth)
                                    }
                                }
                            }

                            te_bw = request["path-constraints"]["te-bandwidth"]
                            max_ch_val = _coerce_optional_float(req_max_channels)
                            if max_ch_val is not None:
                                te_bw["max-nb-of-channel"] = int(max_ch_val)
                            out_pwr_val = _coerce_optional_float(req_output_power)
                            if out_pwr_val is not None:
                                te_bw["output-power"] = out_pwr_val
                            tx_pwr_val = _coerce_optional_float(req_tx_power)
                            if tx_pwr_val is not None:
                                te_bw["tx_power"] = tx_pwr_val
                            if req_slot_n.strip() and req_slot_m.strip():
                                te_bw["effective-freq-slot"] = [{
                                    "N": req_slot_n.strip(),
                                    "M": req_slot_m.strip()
                                }]

                            include_nodes = _parse_csv_list(req_include_nodes_csv)
                            include_hops = [h.strip().upper() for h in _parse_csv_list(req_include_hops_csv)]
                            if include_nodes:
                                if include_hops and len(include_hops) != len(include_nodes):
                                    st.error("include hop types count must match include nodes count.")
                                    valid_request = False
                                else:
                                    if not include_hops:
                                        include_hops = ["LOOSE"] * len(include_nodes)
                                    route_constraints = []
                                    valid_hops = True
                                    for idx, (node_id, hop_type) in enumerate(zip(include_nodes, include_hops), start=1):
                                        if hop_type not in {"LOOSE", "STRICT"}:
                                            st.error("Hop types must be LOOSE or STRICT.")
                                            valid_hops = False
                                            break
                                        route_constraints.append({
                                            "explicit-route-usage": "route-include-ero",
                                            "index": idx - 1,
                                            "num-unnum-hop": {
                                                "node-id": node_id,
                                                "link-tp-id": "link-tp-id is not used",
                                                "hop-type": hop_type
                                            }
                                        })
                                    if valid_hops:
                                        request["explicit-route-objects"] = {
                                            "route-object-include-exclude": route_constraints
                                        }
                                    else:
                                        valid_request = False
                            if valid_request:
                                custom_requests["path-request"].append(request)
                                st.success(f"Added request: {request_id}")

                with st.form("add_synchronization_form", clear_on_submit=True):
                    st.markdown("##### Synchronization")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        sync_id = st.text_input("synchronization-id *", value="1", key="gen_sync_id")
                    with c2:
                        sync_relaxable = st.checkbox("relaxable", value=False, key="gen_sync_relaxable")
                    with c3:
                        sync_disjointness = st.selectbox("disjointness *", ["node link"], key="gen_sync_disjointness")

                    sync_req_ids_csv = st.text_input("request-id-number csv *", value="", key="gen_sync_req_ids")
                    add_sync = st.form_submit_button("Add Synchronization")
                    if add_sync:
                        req_ids = _parse_csv_list(sync_req_ids_csv)
                        if not sync_id.strip():
                            st.error("synchronization-id is required.")
                        elif not req_ids:
                            st.error("At least one request-id-number is required.")
                        else:
                            custom_requests.setdefault("synchronization", []).append({
                                "synchronization-id": sync_id.strip(),
                                "svec": {
                                    "relaxable": bool(sync_relaxable),
                                    "disjointness": sync_disjointness,
                                    "request-id-number": req_ids
                                }
                            })
                            st.success(f"Added synchronization: {sync_id}")

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric("Topology Elements", len(custom_topology.get("elements", [])))
    with col_b:
        st.metric("Topology Connections", len(custom_topology.get("connections", [])))
    with col_c:
        st.metric("Path Requests", len(custom_requests.get("path-request", [])))

    with preview_col:
        with st.expander("Preview Generated JSON", expanded=True):
            preview_tab1, preview_tab2, preview_tab3 = st.tabs(["Topology", "Equipment", "Requests"])
            with preview_tab1:
                st.json(custom_topology)
            with preview_tab2:
                st.json(custom_equipment)
            with preview_tab3:
                st.json(custom_requests)

    validation_errors = _validate_custom_bundle(custom_topology, custom_equipment, custom_requests)
    if validation_errors:
        st.warning("Validation warnings/errors found. Fix before applying to simulator paths.")
        for err in validation_errors[:20]:
            st.write(f"- {err}")
    else:
        st.success("Schema validation passed for topology, equipment, and requests JSON.")

    st.markdown("### Save / Load Bundle")
    custom_dir = _BASE_DIR / "inputs" / "custom"
    custom_dir.mkdir(parents=True, exist_ok=True)
    existing_topologies = sorted(custom_dir.glob("*_topology.json"))
    existing_bundle_names = [f.name.replace("_topology.json", "") for f in existing_topologies]

    col_save, col_load, col_apply, col_reset = st.columns([2, 2, 2, 1])
    with col_save:
        bundle_name = st.text_input("Bundle name", value="custom_input", key="gen_bundle_name")
        if st.button("Save Bundle", use_container_width=True):
            if validation_errors:
                st.error("Cannot save bundle until validation errors are resolved.")
            else:
                top_file, eq_file, req_file = _save_custom_bundle(bundle_name, custom_topology, custom_equipment, custom_requests)
                st.success(f"Saved: {top_file.name}, {eq_file.name}, {req_file.name}")

    with col_load:
        selected_bundle = st.selectbox("Load existing", options=[""] + existing_bundle_names, key="gen_selected_bundle")
        if st.button("Load Bundle", use_container_width=True):
            if not selected_bundle:
                st.warning("Select a bundle to load.")
            else:
                topo_payload, eq_payload, req_payload = _load_custom_bundle(selected_bundle)
                st.session_state.custom_topology_json = topo_payload
                st.session_state.custom_equipment_json = eq_payload
                st.session_state.custom_requests_json = req_payload
                st.success(f"Loaded bundle: {selected_bundle}")
                st.rerun()

    with col_apply:
        if st.button("Apply To Active Input Paths", use_container_width=True):
            if validation_errors:
                st.error("Cannot apply custom inputs until validation errors are resolved.")
            else:
                topo_target = _resolve_path(topology_path)
                eqpt_target = _resolve_path(equipment_path)
                req_target = _resolve_path(requests_path)
                topo_target.write_text(json.dumps(custom_topology, indent=2), encoding="utf-8")
                eqpt_target.write_text(json.dumps(custom_equipment, indent=2), encoding="utf-8")
                req_target.write_text(json.dumps(custom_requests, indent=2), encoding="utf-8")

                # Call the callback to clear caches if provided
                if on_apply_callback:
                    on_apply_callback()
                    
                st.success("Custom JSON applied to active input paths. App will reload using these files.")
                st.rerun()

    with col_reset:
        if st.button("Reset", use_container_width=True):
            st.session_state.custom_topology_json = _default_custom_topology()
            st.session_state.custom_equipment_json = _default_custom_equipment()
            st.session_state.custom_requests_json = _default_custom_requests()
            st.success("Custom generator state has been reset.")
            st.rerun()


# ============================================================================
# Standalone App Entry Point
# ============================================================================
if __name__ == "__main__":
    # Page configuration
    st.set_page_config(
        page_title="GNPy Custom Input Generator",
        page_icon="🛠️",
        layout="wide"
    )

    # Sidebar configuration
    st.sidebar.title("⚙️ Configuration")

    # File paths
    BASE_DIR = Path(__file__).resolve().parent
    set_base_dir(BASE_DIR)
    
    input_topology = str(BASE_DIR / "inputs" / "topology.json")
    input_equipment = str(BASE_DIR / "inputs" / "eqpt_config.json")
    input_requests = str(BASE_DIR / "inputs" / "requests.json")

    topology_path = st.sidebar.text_input("Topology JSON Path", input_topology)
    equipment_path = st.sidebar.text_input("Equipment JSON Path", input_equipment)
    requests_path = st.sidebar.text_input("Requests JSON Path", input_requests)

    # Main title
    st.title("🛠️ GNPy Custom Input Generator")

    # Run the Custom Input Generator UI
    custom_input_generator_ui(topology_path, equipment_path, requests_path)

    # Footer
    st.sidebar.markdown("---")
    st.sidebar.info("""
    **GNPy Custom Input Generator**  
    Build topology, equipment, and request JSON files.
    """)
