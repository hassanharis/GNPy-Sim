"""
GNPy Network Visualization and Analysis Tool
Streamlit application for optical network simulation
"""

import json
from pathlib import Path
import pandas
import streamlit as st
import plotly.graph_objects as go
from numpy import mean
import networkx as nx
import sys

import pandas as pd

# GNPy imports (after path fix)
from gnpy.core.elements import Transceiver, Roadm, Fiber, RamanFiber, Edfa, Fused
from gnpy.tools.json_io import (load_equipment,
    load_equipments_and_configs,
    load_network,
    load_json,
    load_requests,
    save_network,
    save_json,
)
from gnpy.tools.worker_utils import designed_network, transmission_simulation, planning
from gnpy.topology.request import PathRequest, ResultElement, compute_path_dsjctn,compute_constrained_path
from gnpy.core import exceptions
from gnpy.core.utils import watt2dbm, dbm2watt

sys.path.append(r"C:\Users\hahassan\OneDrive - Nokia\Work & Data\Software\My Library")

from my_math import haversine_distance

# Page configuration 
st.set_page_config(
    page_title="GNPy Network Viewer",
    page_icon="🌐",
    layout="wide"
)

# Sidebar configuration
st.sidebar.title("⚙️ Configuration")

# File paths
BASE_DIR = Path(__file__).resolve().parent
input_topology = str(BASE_DIR / "inputs" / "topology.json")
input_equipment = str(BASE_DIR / "inputs" / "eqpt_config.json")
input_requests = str(BASE_DIR / "inputs" / "requests.json")

topology_path = st.sidebar.text_input("Topology JSON Path", input_topology)
equipment_path = st.sidebar.text_input("Equipment JSON Path", input_equipment)
requests_path = st.sidebar.text_input("Requests JSON Path", input_requests)


def _resolve_path(file_path):
    """Resolve input path to an absolute Path under BASE_DIR when relative."""
    if file_path is None or str(file_path).strip() == "":
        raise ValueError("Input file path is empty.")

    resolved = Path(str(file_path)).expanduser()
    if not resolved.is_absolute():
        resolved = (BASE_DIR / resolved).resolve()
    else:
        resolved = resolved.resolve()
    return resolved



# Main title
st.title("🌐 GNPy Network Visualization & Analysis")

# Initialize session state
if 'highlighted_path' not in st.session_state:
    st.session_state.highlighted_path = None
if 'source_node' not in st.session_state:
    st.session_state.source_node = None
if 'destination_node' not in st.session_state:
    st.session_state.destination_node = None
if 'source_select' not in st.session_state:
    st.session_state.source_select = ""
if 'dest_select' not in st.session_state:
    st.session_state.dest_select = ""
if 'simulation_results' not in st.session_state:
    st.session_state.simulation_results = None
if 'transmission_results' not in st.session_state:
    st.session_state.transmission_results = None
if 'simulation_error' not in st.session_state:
    st.session_state.simulation_error = None
   
                        
def remove_type_from_nodeUid(node_uid):
    for type_name in ['Node', 'Transceiver', 'Amplifier', 'ROADM', 'Fiber']:
        if type_name in node_uid:
            return node_uid.replace(type_name, '').strip()
    return node_uid


def _to_python_value(v):
    if hasattr(v, "tolist"):
        return v.tolist()
    return v

def safe_summary_stats(v):
    if v is None:
        return (None, None, None, "None")
    if not isinstance(v, (list, tuple)):
        try:
            fv = float(v)
            return (fv, fv, fv, "scalar")
        except (TypeError, ValueError):
            return (None, None, None, "scalar-non-numeric")
    if len(v) == 0:
        return (None, None, None, "empty")
    numeric_vals = []
    for val in v:
        try:
            numeric_vals.append(float(val))
        except (TypeError, ValueError):
            pass
    if not numeric_vals:
        return (None, None, None, "non-numeric")
    status = f"mixed ({len(numeric_vals)}/{len(v)})" if len(numeric_vals) < len(v) else "numeric"
    return (min(numeric_vals), sum(numeric_vals) / len(numeric_vals), max(numeric_vals), status)

def transmission_results_to_dfs(results_dict=st.session_state.transmission_results):
    if not results_dict:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    clean = {k: _to_python_value(v) for k, v in results_dict.items() if k != "success"}

    vector_cols = {k: v for k, v in clean.items() if isinstance(v, (list, tuple))}
    scalar_cols = {k: v for k, v in clean.items() if not isinstance(v, (list, tuple))}

    summary_rows = []
    for k, v in clean.items():
        mn, avg, mx, status = safe_summary_stats(v)
        is_vec = isinstance(v, (list, tuple))
        summary_rows.append({
            "parameter": k,
            "kind": "vector" if is_vec else "scalar",
            "length": len(v) if is_vec else 1,
            "status": status,
            "Min": mn,
            "Mean": avg,
            "Max": mx,
        })
    summary_df = pd.DataFrame(summary_rows)

    channel_df = pd.DataFrame()
    if vector_cols:
        max_len = max(len(v) for v in vector_cols.values())
        padded = {k: list(v) + [None] * (max_len - len(v)) for k, v in vector_cols.items()}
        channel_df = pd.DataFrame(padded)
        channel_df.insert(0, "channel_index", range(max_len))

    scalar_df = pd.DataFrame([scalar_cols]) if scalar_cols else pd.DataFrame()

    return summary_df, scalar_df, channel_df


def run_transmission(equipment, network, source, destination, launch_power, trx_type, bidir, margin, baudrate, rolloff, tx_osnr, min_osnr, spacing, min_freq, max_freq, roadm_osnr, pwr_start, pwr_stop, pwr_step, nodes_l=None, loose_l=None):

    try:
        network, req, ref_req = designed_network(
            equipment, network, source, destination,
            nodes_list=[], loose_list=[],
            args_power=dbm2watt(launch_power), no_insert_edfas=False,
        )

        path, propagations, powers_dbm, infos = transmission_simulation(equipment, network, req, ref_req)


        ase = getattr(infos, "ase", None)
        ase_dbm = getattr(infos, "ase_dbm", None)
        baud_rate = getattr(infos, "baud_rate", None)
        carriers = getattr(infos, "carriers", None)
        channel_number = getattr(infos, "channel_number", None)
        chromatic_dispersion = getattr(infos, "chromatic_dispersion", None)
        delta_pdb_per_channel = getattr(infos, "delta_pdb_per_channel", None)
        df = getattr(infos, "df", None)
        frequency = getattr(infos, "frequency", None)
        gsnr_db = getattr(infos, "gsnr_db", None)
        label = getattr(infos, "label", None)
        latency = getattr(infos, "latency", None)
        nli = getattr(infos, "nli", None)
        nli_dbm = getattr(infos, "nli_dbm", None)
        number_of_channels = getattr(infos, "number_of_channels", None)
        opt_gsnr_db = getattr(infos, "opt_gsnr_db", None)
        opt_snr_lin_db = getattr(infos, "opt_snr_lin_db", None)
        pch = getattr(infos, "pch", None)
        pch_dbm = getattr(infos, "pch_dbm", None)
        pdl = getattr(infos, "pdl", None)
        pmd = getattr(infos, "pmd", None)
        ptot = getattr(infos, "ptot", None)
        ptot_dbm = getattr(infos, "ptot_dbm", None)
        roll_off = getattr(infos, "roll_off", None)
        signal = getattr(infos, "signal", None)
        signal_dbm = getattr(infos, "signal_dbm", None)
        slot_width = getattr(infos, "slot_width", None)
        snr = getattr(infos, "gsnr", None)
        snr_lin = getattr(infos, "snr_lin", None)
        snr_lin_db = getattr(infos, "snr_lin_db", None)
        snr_nli = getattr(infos, "snr_nli", None)
        snr_nli_db = getattr(infos, "snr_nli_db", None)
        tx_osnr = getattr(infos, "tx_osnr", None)
        tx_power = getattr(infos, "tx_power", None)


        final_gsnr = float(snr.mean()) if snr is not None else None

        path_elements = []
        if path is not None:
            for element in path:
                path_elements.append(getattr(element, "uid", str(element)))

        st.session_state.highlighted_path = path_elements if path_elements else None
        st.session_state.simulation_results = {
            'success': True,
            'path_elements': path_elements,
            'path_length': len(path_elements),
            'osnr_ase': final_gsnr if final_gsnr is not None else "N/A",
            'osnr_01nm': final_gsnr if final_gsnr is not None else "N/A",
            'propagations_count': len(propagations) if propagations is not None else 0,
            'channel_count': len(powers_dbm) if powers_dbm is not None else 0
        }

        st.session_state.transmission_results = {
            'success': True,
            'ase': ase,
            'ase_dbm': ase_dbm,
            'baud_rate': baud_rate,
            'carriers': carriers,
            'channel_number': channel_number,
            'chromatic_dispersion': chromatic_dispersion,
            'delta_pdb_per_channel': delta_pdb_per_channel,
            'df': df,
            'frequency': frequency,
            'gsnr_db': gsnr_db,
            'label': label,
            'latency':  latency,
            'nli': nli,
            'nli_dbm': nli_dbm,
            'number_of_channels': number_of_channels,
            'opt_gsnr_db': opt_gsnr_db,
            'opt_snr_lin_db': opt_snr_lin_db,
            'pch': pch,
            'pch_dbm': pch_dbm,
            'pdl': pdl,
            'pmd': pmd,
            'ptot': ptot,
            'ptot_dbm': ptot_dbm,
            'roll_off': roll_off,
            'signal': signal,
            'signal_dbm': signal_dbm,
            'slot_width': slot_width,
            'snr': snr,
            'snr_lin': snr_lin,
            'snr_lin_db': snr_lin_db,
            'snr_nli': snr_nli,
            'snr_nli_db': snr_nli_db,
            'tx_osnr': tx_osnr,
            'tx_power': tx_power,       
        }
        st.session_state.simulation_error = None
    except Exception as e:
        st.session_state.simulation_results = {'success': False}
        st.session_state.simulation_error = str(e)



def run_simulation_callback(network, equipment, source, destination, launch_power, trx_type, bidir, margin, baudrate, rolloff, tx_osnr, min_osnr, spacing, min_freq, max_freq, roadm_osnr, pwr_start, pwr_stop, pwr_step, nodes_list, loose_list):
    """Callback function to run simulation and store results in session state"""
    try:
        from gnpy.core.utils import dbm2watt
        from statistics import mean
        
        # Get spectral info from equipment
        si = equipment['SI']['default']

        def _to_hz(value, scale):
            if value is None:
                return None
            try:
                value_f = float(value)
            except (TypeError, ValueError):
                return None
            if value_f < 1e6:
                return value_f * scale
            return value_f

        def _get_si_attr(name, alt_name=None):
            if hasattr(si, name):
                return getattr(si, name)
            if alt_name and hasattr(si, alt_name):
                return getattr(si, alt_name)
            return None


     
        spacing_hz = _to_hz(spacing, 1e9) or _to_hz(_get_si_attr('spacing'), 1e9) or 50.0e9
        f_min_hz = _to_hz(min_freq, 1e12) or _to_hz(_get_si_attr('f_min'), 1e12) or 191.3e12
        f_max_hz = _to_hz(max_freq, 1e12) or _to_hz(_get_si_attr('f_max'), 1e12) or 196.1e12
        baud_rate_hz = _to_hz(baudrate, 1e9) or _to_hz(_get_si_attr('baud_rate', 'baudrate'), 1e9) or 31.57e9
        roll_off_attr = _get_si_attr('roll_off', 'rolloff')
        roll_off_val = float(rolloff) if rolloff is not None else (float(roll_off_attr) if roll_off_attr is not None else 0.15)
        tx_osnr_val = float(tx_osnr) if tx_osnr is not None else (float(_get_si_attr('tx_osnr')) if _get_si_attr('tx_osnr') is not None else 35.0)

        # Create comprehensive path request with all required parameters
        params = {
            'request_id': 'req1',
            'source': source,
            'destination': destination,
            'bidir': bidir,
            'trx_type': trx_type,
            'trx_mode': None,
            'format': None,
            'spacing': spacing_hz,
            'power': dbm2watt(launch_power),
            'tx_power': dbm2watt(launch_power),
            'nb_channel': 96,
            'f_min': f_min_hz,
            'f_max': f_max_hz,
            'baud_rate': baud_rate_hz,
            'bit_rate': None,
            'roll_off': roll_off_val,
            'OSNR': None,
            'penalties': None,
            'tx_osnr': tx_osnr_val,
            'min_spacing': None,
            'cost':     None,
            'path_bandwidth':   None,
            'effective_freq_slot':  None,
            'equalization_offset_db':   None,
            'nodes_list': nodes_list,
            'loose_list': loose_list
        }
        
        request = PathRequest(**params)
        
        

        # Compute path
        paths = compute_path_dsjctn(network, equipment, [request], [])
        # st.markdown(f"Computed paths: {paths}")
        if paths and len(paths) > 0:
            path = paths[0]
            dest_trx = path[-1]
            path_elements = [e.uid for e in path]
            # Store path in session state for visualization
            st.session_state.highlighted_path = path_elements
            
            # Store results
            osnr_val = mean(dest_trx.osnr_ase) if hasattr(dest_trx, 'osnr_ase') and dest_trx.osnr_ase is not None else "N/A"
            osnr_01nm = mean(dest_trx.osnr_ase_01nm) if hasattr(dest_trx, 'osnr_ase_01nm') and dest_trx.osnr_ase_01nm is not None else "N/A"
            
            st.session_state.simulation_results = {
                'success': True,
                'path_elements': path_elements,
                'path_length': len(path),
                'osnr_ase': osnr_val,
                'osnr_01nm': osnr_01nm
                
            }
            st.session_state.simulation_error = None
        else:
            st.session_state.simulation_results = {'success': False}
            st.session_state.simulation_error = "No path found between source and destination."
        
        


        

    except Exception as e:
        st.session_state.simulation_results = {'success': False}
        st.session_state.simulation_error = str(e)

def flatten_dict(d, parent_key='', sep='_'):
    """Flatten nested dictionary into single-level dict with compound keys"""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)
# Helper functions for dynamic dataframe usage
def find_column_by_keywords(df, keywords):
    for col in df.columns:
        col_lower = str(col).lower()
        if any(keyword in col_lower for keyword in keywords):
            return col
    return None

def get_label_column(df):
    return find_column_by_keywords(df, ["city", "name", "label"]) or "uid"

def get_coord_columns(df):
    lon_col = find_column_by_keywords(df, ["longitude", "lon"])
    lat_col = find_column_by_keywords(df, ["latitude", "lat"])
    return lon_col, lat_col

def get_edge_columns(df):
    columns = [str(col) for col in df.columns]

    def find_exact_or_contains(options):
        for option in options:
            for col in columns:
                if col.lower() == option:
                    return col
        for option in options:
            for col in columns:
                if option in col.lower():
                    return col
        return None

    from_col = find_exact_or_contains(["from_node", "from"])
    to_col = find_exact_or_contains(["to_node", "to"])
    return from_col, to_col

# Load data

# Load data
@st.cache_data
def load_network_data(topo_path, eqpt_path, reqs_path):
    """Load network and equipment data"""
    topo = _resolve_path(topo_path)
    eqpt = _resolve_path(eqpt_path)
    reqs = _resolve_path(reqs_path)

    for label, required_file in (("Topology", topo), ("Equipment", eqpt), ("Requests", reqs)):
        if not required_file.exists():
            raise FileNotFoundError(f"{label} file not found: {required_file}")

    try:
        equipment = load_equipment(eqpt)
    except Exception as e:
        st.error(f"Failed to load equipment: {e}")
        raise
    
    try:
        network = load_network(topo, equipment)
    except Exception as e:
        st.error(f"Failed to load network topology: {e}")
        raise
    

    return equipment, network


def load_json_file(file_path):
    """Load network and equipment data"""
    file = _resolve_path(file_path)
    if not file.exists():
        raise FileNotFoundError(f"Input file not found: {file}")
    return load_json(file)

@st.cache_data
def load_json_files(topo_path, eqpt_path, reqs_path):
    """Load network and equipment data"""

    return load_json_file(topo_path), load_json_file(eqpt_path), load_json_file(reqs_path)
    


def input_viewer(input_json, type_name: str):
    st.subheader(type_name + " Configuration")

    with st.expander("View Input JSON"):
        st.json(input_json)

    if not isinstance(input_json, dict):
        st.info(f"{type_name} JSON root is not an object. Raw preview shown above.")
        return

    st.markdown("View Components:")
    for key, value in input_json.items():
        with st.expander(f"{key}"):
            data = input_json.get(key)
            if isinstance(data, list):
                st.dataframe(pandas.json_normalize(data), use_container_width=True)
                st.json(pandas.json_normalize(data).to_dict(orient="records"))
                
            else:
                st.json(data)
    st.download_button(
        label="Download JSON",
        data=json.dumps(input_json, indent=2),
        file_name=type_name +".json",
        mime="application/json"
    )


def documentation_view():
    st.subheader("Documentation")
    st.markdown("Reference notes for optical spectrum planning.")

    with st.expander("Spectrum Standard"):
        spectrum_df = pd.DataFrame(
            {
                "Band": ["S-band", "C-band", "L-band"],
                "Wavelength Range": ["1486-1530 nm", "1530-1568 nm", "1568-1621 nm"],
                "Channels": ["116 channels", "96 channels", "125 channels"],
            }
        )
        st.table(spectrum_df)

    with st.expander("Inputs"):
        inputs_df = pd.DataFrame(
            {
                "Input": [
                    "Network topology (JSON/YANG)",
                    "Equipment library (eqpt_config.json)",
                    "Service/path requests",
                    "Simulation parameters",
                ],
                "Description": [
                    "Node list: fiber spans, EDFAs, ROADMs, transceivers, fused nodes; link connectivity and physical parameters",
                    "Fiber types, amplifier models, ROADM specs, transceiver catalog",
                    "Source & destination nodes; requested modulation format and bitrate; spectrum assignment (fixed or flexible grid)",
                    "Power mode or gain mode; frequency range, channel count, baud rate; EGN model on/off",
                ],
            }
        )
        st.table(inputs_df)

    with st.expander("Key Variables"):
        st.markdown("**Fiber Span**")
        fiber_span_df = pd.DataFrame(
            {
                "Variable": ["length", "loss_coef", "dispersion", "gamma", "pmd_coef"],
                "Description": [
                    "Span length (km)",
                    "Attenuation coefficient (dB/km)",
                    "Chromatic dispersion (ps/nm/km)",
                    "Nonlinear coefficient (1/W/km)",
                    "PMD coefficient (ps/sqrt(km))",
                ],
            }
        )
        st.table(fiber_span_df)

        st.markdown("**Signal / Spectral Information**")
        signal_df = pd.DataFrame(
            {
                "Variable": [
                    "f_min, f_max",
                    "baud_rate",
                    "roll_off",
                    "tx_power",
                    "channel_spacing",
                    "nb_channel",
                ],
                "Description": [
                    "Frequency band boundaries (Hz)",
                    "Symbol rate per channel (Bd)",
                    "Nyquist filter roll-off factor",
                    "Transmitter launch power (dBm)",
                    "Grid spacing (Hz)",
                    "Number of WDM channels",
                ],
            }
        )
        st.table(signal_df)

        st.markdown("**Amplifier**")
        amplifier_df = pd.DataFrame(
            {
                "Variable": ["gain_target", "tilt_target", "nf_min, nf_max", "p_max"],
                "Description": [
                    "Target gain (dB)",
                    "Gain tilt (dB)",
                    "Noise figure range (dB)",
                    "Maximum output power (dBm)",
                ],
            }
        )
        st.table(amplifier_df)

    with st.expander("Configuration Options"):
        st.markdown("**Simulation Modes**")
        simulation_modes_df = pd.DataFrame(
            {
                "Option": [
                    "power_mode",
                    "spectral_information",
                    "Roadm target power",
                    "EGN model",
                    "verbose",
                ],
                "Description": [
                    "Optimize/fix per-channel launch power",
                    "Define the full WDM comb",
                    "Set per-ROADM output power or loss",
                    "Enable enhanced GN correction terms",
                    "Debug output level",
                ],
            }
        )
        st.table(simulation_modes_df)

        st.markdown("**Equipment Library Options**")
        st.markdown("- Fiber: type, loss coefficient, dispersion, gamma, PMD")
        st.markdown("- Amplifier (EDFA): gain range, NF model (polynomial/multiband), tilt, VOA")
        st.markdown("- ROADM: target power, add/drop loss, passthrough loss, per-degree settings")
        st.markdown("- Transceiver: baudrate, modulation format, TX power, required OSNR, FEC threshold")
        st.markdown("- RamanAmplifier: Raman pump configuration (if enabled)")

    with st.expander("Outputs"):
        outputs_df = pd.DataFrame(
            {
                "Output": [
                    "OSNR (linear & dB)",
                    "GSNR",
                    "NLI noise",
                    "ASE noise",
                    "Per-node signal power",
                    "Gain & tilt per EDFA",
                    "Feasibility verdict",
                    "Path computation result",
                    "JSON report",
                ],
                "Description": [
                    "Optical signal-to-noise ratio per channel along path",
                    "Generalized SNR (includes NLI + ASE)",
                    "Nonlinear interference power per channel",
                    "Amplified spontaneous emission per amplifier/path",
                    "Channel power at each network element",
                    "Operating point of each amplifier",
                    "Pass/fail vs. transceiver OSNR/GSNR threshold",
                    "Chosen route with spectrum assignment",
                    "Full propagation data exportable for further analysis",
                ],
            }
        )
        st.table(outputs_df)


# Create tabs
tab1, tab2, tab3 = st.tabs(["📄 Inputs", "📊 Network Visualization", "📘 Documentation"])

topology_json, equipment_json, requests_json = load_json_files(topology_path, equipment_path, requests_path)
equipment, network = load_network_data(topology_path, equipment_path, requests_path)

                     

# TAB 2: JSON Viewer
with tab1:    
    input_viewer(topology_json, "Topology")
    input_viewer(equipment_json, "Equipment")
    input_viewer(requests_json, "Requests")

with tab3:
    documentation_view()

network_df = pandas.json_normalize(topology_json.get("elements"))
edges_df = pandas.json_normalize(topology_json.get("connections"))

# TAB 1: Network Visualization
with tab2:    
    if network is None:
        st.error("Network failed to load. Check the error message above.")
    else:
        label_col = get_label_column(network_df)
        type_col = find_column_by_keywords(network_df, ["type"])

        transceiver_mask = network_df['uid'].str.contains('trx', case=False, na=False)
        if "type" in network_df.columns:
            transceiver_mask = transceiver_mask | (network_df["type"] == "Transceiver")

        transceivers = network_df[transceiver_mask]['uid'].dropna().tolist()
        if label_col in network_df.columns:
            transceivers_labels = network_df.loc[transceiver_mask, label_col].fillna("").tolist()
        else:
            transceivers_labels = transceivers

        col1, col2 = st.columns([3, 1])
        
        with col2:
            with st.expander("Visualization Settings"):
            
    
                # Node customization
                node_size = st.slider("Node Size", 5, 50, 15)
                node_color = st.color_picker("Node Color", "#1f77b4")
                
                # Edge customization
                edge_width = st.slider("Edge Width", 1, 10, 2)
                edge_color = st.color_picker("Edge Color", "#888888")
                
                # Show labels
                show_labels = st.checkbox("Show Node Labels", value=True)
                show_node_info = st.checkbox("Show Node Info on Hover", value=True)
                
                # Layout options
                layout_type = st.selectbox("Layout Type", 
                                        ["Geographic (lat/lon)", "haversine_distance"])
                
            # Path highlighting control
            if st.session_state.highlighted_path:
                st.info(f"Path highlighted with {len(st.session_state.highlighted_path)} nodes")
                if st.button("Clear Path Highlighting"):
                    st.session_state.highlighted_path = None
                    st.rerun()
                
        

        with col1:
            # Build nodes and edges from dataframes
            nodes_data = network_df.to_dict("records")

            from_col, to_col = get_edge_columns(edges_df)
            if from_col and to_col:
                edges_df_clean = edges_df.rename(columns={from_col: "source", to_col: "target"})
                edges_df_clean = edges_df_clean[
                    pandas.notna(edges_df_clean["source"]) & pandas.notna(edges_df_clean["target"])
                ]
                edges_data = edges_df_clean.to_dict("records")
            else:
                edges_data = []

            # Create plotly figure
            fig = go.Figure()

            # Determine node positions based on layout type and available data
            lon_col, lat_col = get_coord_columns(network_df)
            use_map = layout_type == "Geographic (lat/lon)" and lon_col and lat_col
            
            if use_map:
                node_lon = network_df[lon_col].tolist()
                node_lat = network_df[lat_col].tolist()
                node_x = node_lon
                node_y = node_lat
            else:
                # Fallback to spring layout
                G_simple = nx.DiGraph()
                if "uid" in network_df.columns:
                    uid_list = network_df["uid"].dropna().tolist()
                    G_simple.add_nodes_from(uid_list)
                if from_col and to_col:
                    edge_pairs = list(zip(edges_df[from_col], edges_df[to_col]))
                    G_simple.add_edges_from(edge_pairs)
                pos = nx.spring_layout(G_simple, k=0.3, iterations=50)
                uid_series = network_df["uid"].tolist() if "uid" in network_df.columns else []
                node_x = [pos.get(uid, (0, 0))[0] if pandas.notna(uid) else 0 for uid in uid_series]
                node_y = [pos.get(uid, (0, 0))[1] if pandas.notna(uid) else 0 for uid in uid_series]
                node_lon = node_x
                node_lat = node_y

            # Create position mapping
            pos_map = {}
            if "uid" in network_df.columns:
                uid_series = network_df["uid"].tolist()
                for i, uid in enumerate(uid_series):
                    if isinstance(uid, str) and uid and i < len(node_x) and i < len(node_y):
                        x_val = node_x[i]
                        y_val = node_y[i]
                        if pandas.notna(x_val) and pandas.notna(y_val):
                            pos_map[uid] = (x_val, y_val)
            
            # Get highlighted path from session state
            highlighted_nodes = set()
            highlighted_edges = set()
            if st.session_state.highlighted_path:
                highlighted_nodes = set(st.session_state.highlighted_path)
                # Create edge pairs from path
                for i in range(len(st.session_state.highlighted_path) - 1):
                    highlighted_edges.add((st.session_state.highlighted_path[i], st.session_state.highlighted_path[i+1]))
            
            # Add regular edges (not in path)
            edge_x = []
            edge_y = []
            for edge in edges_data:
                if edge['source'] in pos_map and edge['target'] in pos_map:
                    if (edge['source'], edge['target']) not in highlighted_edges:
                        x0, y0 = pos_map[edge['source']]
                        x1, y1 = pos_map[edge['target']]
                        edge_x.extend([x0, x1, None])
                        edge_y.extend([y0, y1, None])
            
            if edge_x:  # Only add if there are non-path edges
                if use_map:
                    fig.add_trace(go.Scattermapbox(
                        lon=edge_x, lat=edge_y,
                        mode='lines',
                        line=dict(width=edge_width, color=edge_color),
                        hoverinfo='none',
                        showlegend=False,
                        name='Edges'
                    ))
                else:
                    fig.add_trace(go.Scatter(
                        x=edge_x, y=edge_y,
                        mode='lines',
                        line=dict(width=edge_width, color=edge_color),
                        hoverinfo='none',
                        showlegend=False,
                        name='Edges'
                    ))
            
            # Add highlighted path edges on top
            if highlighted_edges:
                path_edge_x = []
                path_edge_y = []
                for edge in edges_data:
                    if (edge['source'], edge['target']) in highlighted_edges:
                        if edge['source'] in pos_map and edge['target'] in pos_map:
                            x0, y0 = pos_map[edge['source']]
                            x1, y1 = pos_map[edge['target']]
                            path_edge_x.extend([x0, x1, None])
                            path_edge_y.extend([y0, y1, None])
                
                if use_map:
                    fig.add_trace(go.Scattermapbox(
                        lon=path_edge_x, lat=path_edge_y,
                        mode='lines',
                        line=dict(width=edge_width*2, color='#FF4444'),
                        hoverinfo='none',
                        showlegend=False,
                        name='Path'
                    ))
                else:
                    fig.add_trace(go.Scatter(
                        x=path_edge_x, y=path_edge_y,
                        mode='lines',
                        line=dict(width=edge_width*2, color='#FF4444'),
                        hoverinfo='none',
                        showlegend=False,
                        name='Path'
                    ))
            
            # Add nodes with highlighting
            node_text = []
            if show_node_info:
                for node in nodes_data:
                    uid_value = node.get("uid", "N/A")
                    hover_parts = [f"UID: {uid_value}"]
                    if type_col and type_col in node and pandas.notna(node[type_col]) and node[type_col] != "":
                        hover_parts.append(f"Type: {node[type_col]}")
                    if label_col in node and label_col not in ("uid", type_col):
                        label_value = node.get(label_col)
                        if pandas.notna(label_value) and label_value != "":
                            hover_parts.append(f"Label: {label_value}")
                    node_text.append("<br>".join(hover_parts))

            # Build type-based color mapping
            type_values = []
            if type_col and type_col in network_df.columns:
                type_values = [node.get(type_col) for node in nodes_data]
            unique_types = sorted({
                str(t) for t in type_values
                if pandas.notna(t) and t != ""
            })
            palette = [
                "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
                "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
                "#bcbd22", "#17becf"
            ]
            if len(unique_types) <= 1:
                type_color_map = {t: node_color for t in unique_types}
            else:
                type_color_map = {
                    t: palette[i % len(palette)]
                    for i, t in enumerate(unique_types)
                }
            
            # Separate nodes by type for legend
            nodes_by_type = {}
            for node_type in unique_types:
                nodes_by_type[node_type] = {
                    'x': [], 'y': [], 'text': [], 'hover': [], 'uid': [],
                    'color': type_color_map.get(node_type, node_color)
                }
            
            path_x, path_y, path_text, path_hover, path_uid, path_color, path_type = [], [], [], [], [], [], []
            
            for i, node in enumerate(nodes_data):
                node_type_value = None
                if type_col and type_col in node:
                    node_type_value = node.get(type_col)
                
                # Don't show labels for Fiber nodes
                is_fiber = node_type_value and str(node_type_value).lower() == "fiber"
                
                if show_labels and not is_fiber:
                    label_value = node.get(label_col) if label_col in node else None
                    if label_value is None or not pandas.notna(label_value) or label_value == "":
                        label_value = node.get("uid", "")
                    label = str(label_value)
                else:
                    label = ""
                hover = node_text[i] if show_node_info and i < len(node_text) else ""

                if node_type_value is not None and pandas.notna(node_type_value) and node_type_value != "":
                    node_color_value = type_color_map.get(str(node_type_value), node_color)
                    node_type_str = str(node_type_value)
                else:
                    node_color_value = node_color
                    node_type_str = "Unknown"
                
                if node['uid'] in highlighted_nodes:
                    path_x.append(node_x[i])
                    path_y.append(node_y[i])
                    path_uid.append(node['uid'])
                    path_color.append(node_color_value)
                    path_type.append(node_type_str)
                    if show_labels:
                        path_text.append(label)
                    if show_node_info:
                        path_hover.append(hover)
                else:
                    if node_type_str in nodes_by_type:
                        nodes_by_type[node_type_str]['x'].append(node_x[i])
                        nodes_by_type[node_type_str]['y'].append(node_y[i])
                        nodes_by_type[node_type_str]['uid'].append(node['uid'])
                        if show_labels:
                            nodes_by_type[node_type_str]['text'].append(label)
                        if show_node_info:
                            nodes_by_type[node_type_str]['hover'].append(hover)
            
            # Add regular nodes grouped by type
            for node_type, data in nodes_by_type.items():
                if data['x']:  # Only add if there are nodes of this type
                    if use_map:
                        fig.add_trace(go.Scattermapbox(
                            lon=data['x'], lat=data['y'],
                            mode='markers+text' if show_labels else 'markers',
                            marker=dict(
                                size=node_size,
                                color=data['color']
                            ),
                            text=data['text'] if show_labels else None,
                            textposition="top center",
                            hovertext=data['hover'] if show_node_info else None,
                            hoverinfo='text' if show_node_info else 'none',
                            customdata=[[uid] for uid in data['uid']],
                            showlegend=True,
                            name=node_type,
                            legendgroup=node_type
                        ))
                    else:
                        fig.add_trace(go.Scatter(
                            x=data['x'], y=data['y'],
                            mode='markers+text' if show_labels else 'markers',
                            marker=dict(
                                size=node_size,
                                color=data['color'],
                                line=dict(width=2, color='white')
                            ),
                            text=data['text'] if show_labels else None,
                            textposition="top center",
                            hovertext=data['hover'] if show_node_info else None,
                            hoverinfo='text' if show_node_info else 'none',
                            customdata=[[uid] for uid in data['uid']],
                            showlegend=True,
                            name=node_type,
                            legendgroup=node_type
                        ))
            
            # Add path nodes on top
            if path_x:
                if use_map:
                    fig.add_trace(go.Scattermapbox(
                        lon=path_x, lat=path_y,
                        mode='markers+text' if show_labels else 'markers',
                        marker=dict(
                            size=node_size*1.5,
                            color=path_color
                        ),
                        text=path_text if show_labels else None,
                        textposition="top center",
                        hovertext=path_hover if show_node_info else None,
                        hoverinfo='text' if show_node_info else 'none',
                        customdata=[[uid] for uid in path_uid],
                        showlegend=False,
                        name='Path Nodes'
                    ))
                else:
                    fig.add_trace(go.Scatter(
                        x=path_x, y=path_y,
                        mode='markers+text' if show_labels else 'markers',
                        marker=dict(
                            size=node_size*1.5,
                            color=path_color,
                            line=dict(width=3, color='#FF4444')
                        ),
                        text=path_text if show_labels else None,
                        textposition="top center",
                        hovertext=path_hover if show_node_info else None,
                        hoverinfo='text' if show_node_info else 'none',
                        customdata=[[uid] for uid in path_uid],
                        showlegend=False,
                        name='Path Nodes'
                    ))
            
            # Update layout
            if use_map:
                # Calculate center coordinates for better initial view
                center_lat = network_df[lat_col].mean() if lat_col and lat_col in network_df.columns else 0
                center_lon = network_df[lon_col].mean() if lon_col and lon_col in network_df.columns else 0
                
                fig.update_layout(
                    title="Network Topology",
                    showlegend=True,
                    legend=dict(
                        yanchor="top",
                        y=0.99,
                        xanchor="left",
                        x=0.01,
                        bgcolor="rgba(255, 255, 255, 0.8)"
                    ),
                    mapbox=dict(
                        style="open-street-map",
                        center=dict(lat=center_lat, lon=center_lon),
                        zoom=4
                    ),
                    hovermode='closest',
                    margin=dict(b=0, l=0, r=0, t=40),
                    height=800
                )
            else:
                fig.update_layout(
                    title="Network Topology",
                    showlegend=True,
                    legend=dict(
                        yanchor="top",
                        y=0.99,
                        xanchor="left",
                        x=0.01,
                        bgcolor="rgba(255, 255, 255, 0.8)"
                    ),
                    hovermode='closest',
                    margin=dict(b=0, l=0, r=0, t=40),
                    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    height=800,
                    plot_bgcolor='rgba(240,240,240,0.5)'
                )
            
            selection = st.plotly_chart(
                fig,
                use_container_width=True,
                key="network_topology_graph",
                on_select="rerun",
                selection_mode="points"
            )

            if selection and "selection" in selection and "points" in selection["selection"]:
                selected_points = selection["selection"]["points"]
                
                # Only process if there are selected points
                if selected_points and len(selected_points) > 0:
                    selected_uids = []
                    
                    for point in selected_points:
                        customdata = point.get("customdata")
                        if customdata and len(customdata) > 0:
                            node_uid = customdata[0]
                            if isinstance(node_uid, str) and node_uid in transceivers:
                                selected_uids.append(node_uid)

                    selected_uids = list(dict.fromkeys(selected_uids))
                    
                    if selected_uids and len(selected_uids) > 0:
                        selected_uid = selected_uids[0]
                        
                        # First click: set source
                        if st.session_state.source_node is None:
                            st.session_state.source_node = selected_uid
                            st.session_state.source_select = selected_uid
                        # Second click: set destination (only if different from source)
                        elif st.session_state.destination_node is None:
                            if selected_uid != st.session_state.source_node:
                                st.session_state.destination_node = selected_uid
                                st.session_state.dest_select = selected_uid
                        # Subsequent clicks: update destination (only if different from source and current destination)
                        else:
                            if selected_uid != st.session_state.source_node and selected_uid != st.session_state.destination_node:
                                st.session_state.destination_node = selected_uid
                                st.session_state.dest_select = selected_uid

            # Network statistics
            st.subheader("📈 Network Statistics")
            col_a, col_b, col_c = st.columns(3)
            edge_pairs = {
                (edge.get("source"), edge.get("target"))
                for edge in edges_data
                if edge.get("source") and edge.get("target")
            }
            is_directed = True
            if edge_pairs:
                is_directed = any((b, a) not in edge_pairs for (a, b) in edge_pairs)
            with col_a:
                st.metric("Total Nodes", len(nodes_data))
            with col_b:
                st.metric("Total Edges", len(edges_data))
            with col_c:
                st.metric("Is Directed", "Yes" if is_directed else "No")
            
            # Display simulation results if available
            if st.session_state.simulation_results is not None:
                results = st.session_state.simulation_results
                results_2 = st.session_state.transmission_results
                
                if results.get('success'):
                    st.success("✅ Simulation completed successfully!")
                    
                    # Results
                    st.subheader("📊 Results")
                    
                    col_1, col_2, col_3, col_4 = st.columns(4)
                    with col_1:
                        osnr_val = results['osnr_ase']
                        st.metric("Avg OSNR (ASE)", f"{osnr_val:.2f} dB" if isinstance(osnr_val, (int, float)) else osnr_val)
                    with col_2:
                        osnr_01nm = results['osnr_01nm']
                        st.metric("Avg OSNR @ 0.1nm", f"{osnr_01nm:.2f} dB" if isinstance(osnr_01nm, (int, float)) else osnr_01nm)
                    with col_3:
                        st.metric("Path Found", "Yes")
                    with col_4:
                        st.metric("Number of Hops", results['path_length'])
                    
                    #propagations_count = results['propagations_count']
                    #st.metric("Number of Propagations", f"{propagations_count}" if isinstance(propagations_count, (int, float)) else propagations_count)

                    #channel_count = results['channel_count']
                    #st.metric("Number of Channels", f"{channel_count}" if isinstance(channel_count, (int, float)) else channel_count)
                    

                    summary_df, scalar_df, channel_df = transmission_results_to_dfs(results_2)

                    st.subheader("Transmission Summary")
                    with st.expander("View Transmission Summary"):
                        st.dataframe(summary_df, use_container_width=True, hide_index=True)

                    if not scalar_df.empty:
                        st.subheader("Scalar Parameters")
                        with st.expander("View all Scalar Parameters"):
                            st.dataframe(scalar_df, use_container_width=True, hide_index=True)

                    if not channel_df.empty:
                        st.subheader("Per-Channel Parameters")
                        with st.expander("View all Per-Channel Parameters"):
                            st.dataframe(channel_df, use_container_width=True, hide_index=True)


                    # Display all results_2 parameters
                    st.subheader("📋 All Transmission Results Parameters")
                    with st.expander("View all Transmission parameters"):
                        for key, value in results_2.items():
                            if isinstance(value, (int, float)):
                                st.write(f"**{key}:** {value:.4f}")
                            elif isinstance(value, (list, tuple)):
                                st.write(f"**{key}:** {type(value).__name__} (length: {len(value)})")
                                try:
                                    st.write(f"  Value: {value}")
                                except Exception as e:
                                    st.write(f"  Unable to display: {str(e)}")
                            else:
                                st.write(f"**{key}:** {value}")

                    # Path details
                    st.subheader("🛤️ Path Details")
                    st.write(f"**Number of hops:** {len(results['path_elements'])}")
                    st.write("**Path elements:**")
                    st.code(" → ".join(results['path_elements']))
                else:
                    st.error("❌ No path found between source and destination.")
            
            # Display errors if any
            if st.session_state.simulation_error is not None:
                st.error(f"❌ Simulation failed: {st.session_state.simulation_error}")

    with col2:
        st.subheader("Optical Path Simulation")
        if network is None or equipment is None:
            st.error("Network or equipment failed to load. Check the error messages above.")
        else:
            # Get list of transceiver nodes
            if len(transceivers) < 2:
                st.warning("Not enough transceiver nodes found in the network for path simulation.")
            else:
                def get_available_nodes():
                    return sorted(transceivers)

                # Get available nodes
                nodes = get_available_nodes()
                source_options = [""] + nodes
                dest_options = [""] + nodes

                # Calculate selectbox indices based on current session state
                source_index = 0
                if st.session_state.source_select and st.session_state.source_select in source_options:
                    source_index = source_options.index(st.session_state.source_select)
                
                dest_index = 0
                if st.session_state.dest_select and st.session_state.dest_select in dest_options:
                    dest_index = dest_options.index(st.session_state.dest_select)

                col1, col2 = st.columns(2)

                with col1:
                    source_node = st.selectbox(
                        "Source node:",
                        options=source_options,
                        index=source_index,
                        key='source_select'
                    )
                    st.session_state.source_node = source_node if source_node else None

                with col2:
                    destination_node = st.selectbox(
                        "Destination node:",
                        options=dest_options,
                        index=dest_index,
                        key='dest_select'
                    )
                    st.session_state.destination_node = destination_node if destination_node else None

                st.subheader("Path Constraints")
                nodes_list = st.multiselect(
                    "nodes_list:",
                    options=nodes,
                    default=st.session_state.get("constraint_nodes_list", []),
                    key="constraint_nodes_list",
                    help="Ordered list of nodes that the path should traverse."
                )

                loose_list = []
                if nodes_list:
                    st.markdown("loose_list:")
                    for constrained_node in nodes_list:
                        loose_key = f"constraint_type_{str(constrained_node).replace(' ', '_')}"
                        hop_type = st.selectbox(
                            f"{constrained_node} hop type",
                            options=["LOOSE", "STRICT"],
                            index=0,
                            key=loose_key,
                            help="STRICT enforces this hop; LOOSE allows alternate optimization."
                        )
                        loose_list.append(hop_type)

                source = st.session_state.source_node
                destination = st.session_state.destination_node

                if source and destination and source == destination:
                    st.warning("Source and destination must be different nodes.")

                # Basic simulation settings
                st.subheader("Simulation Configuration")
                col_a, col_b, col_c = st.columns(3)
                
                with col_a:
                    launch_power = st.slider("Launch Power (dBm)", -5, 5, 0)
                with col_b:
                    trx_type = st.text_input("Transceiver Type", "Voyager")
                with col_c:
                    bidir = st.checkbox("Bidirectional", value=False)
                

                si = equipment['SI']['default']
                # Initialize session state for simulation parameters
                if 'sim_margin' not in st.session_state:
                    st.session_state.sim_margin = 0.0
                if 'sim_baudrate' not in st.session_state:
                    st.session_state.sim_baudrate = float(si.baudrate) if hasattr(si, 'baudrate') and si.baudrate is not None else 31.57
                if 'sim_rolloff' not in st.session_state:
                    st.session_state.sim_rolloff = float(si.rolloff) if hasattr(si, 'rolloff') and si.rolloff is not None else 0.15
                if 'sim_tx_osnr' not in st.session_state:
                    st.session_state.sim_tx_osnr = float(si.tx_osnr) if hasattr(si, 'tx_osnr') and si.tx_osnr is not None else 35.0
                if 'sim_min_osnr' not in st.session_state:
                    st.session_state.sim_min_osnr = float(si.min_osnr) if hasattr(si, 'min_osnr') and si.min_osnr is not None else 0.0
                if 'sim_spacing' not in st.session_state:
                    st.session_state.sim_spacing = float(si.spacing) if hasattr(si, 'spacing') and si.spacing is not None else 50.00
                if 'sim_min_freq' not in st.session_state:
                    st.session_state.sim_min_freq = 191.30
                if 'sim_max_freq' not in st.session_state:
                    st.session_state.sim_max_freq = 196.10
                if 'sim_roadm_osnr' not in st.session_state:
                    st.session_state.sim_roadm_osnr = 33.0
                if 'sim_pwr_start' not in st.session_state:
                    st.session_state.sim_pwr_start = 2.0
                if 'sim_pwr_stop' not in st.session_state:
                    st.session_state.sim_pwr_stop = None
                if 'sim_pwr_step' not in st.session_state:
                    st.session_state.sim_pwr_step = None
                
                # Set Transceiver Parameters
                with st.expander("Set Transceiver Parameters"):
                    col_t1, col_t2 = st.columns(2)
                    with col_t1:
                        st.session_state.sim_margin = st.number_input(
                            "Margin [dB]",
                            value=float(st.session_state.sim_margin),
                            step=0.1,
                            key='trx_margin'
                        )
                        st.session_state.sim_baudrate = st.number_input(
                            "Baudrate [Gbaud]",
                            value=float(st.session_state.sim_baudrate),
                            step=0.01,
                            key='trx_baudrate'
                        )
                        st.session_state.sim_rolloff = st.number_input(
                            "Roll-off",
                            value=float(st.session_state.sim_rolloff),
                            min_value=0.0,
                            max_value=1.0,
                            step=0.01,
                            key='trx_rolloff'
                        )
                    with col_t2:
                        st.session_state.sim_tx_osnr = st.number_input(
                            "Tx OSNR [dB]",
                            value=float(st.session_state.sim_tx_osnr),
                            step=0.1,
                            key='trx_tx_osnr'
                        )
                        st.session_state.sim_min_osnr = st.number_input(
                            "Min OSNR [dB]",
                            value=float(st.session_state.sim_min_osnr),
                            step=0.1,
                            key='trx_min_osnr'
                        )
                
                # Spectral Load Parameters
                with st.expander("📡 Spectral Load Parameters"):
                    col_s1, col_s2, col_s3 = st.columns(3)
                    with col_s1:
                        st.session_state.sim_spacing = st.number_input(
                            "Spacing [GHz]",
                            value=float(st.session_state.sim_spacing),
                            step=0.01,
                            key='spec_spacing'
                        )
                    with col_s2:
                        st.session_state.sim_min_freq = st.number_input(
                            "Minimum Frequency [THz]",
                            value=float(st.session_state.sim_min_freq),
                            step=0.01,
                            format="%.2f",
                            key='spec_min_freq'
                        )
                    with col_s3:
                        st.session_state.sim_max_freq = st.number_input(
                            "Maximum Frequency [THz]",
                            value=float(st.session_state.sim_max_freq),
                            step=0.01,
                            format="%.2f",
                            key='spec_max_freq'
                        )
                
                # ROADM Parameters
                with st.expander("🛣️ ROADM Parameters"):
                    st.session_state.sim_roadm_osnr = st.number_input(
                        "Add/Drop OSNR [dB]",
                        value=float(st.session_state.sim_roadm_osnr),
                        step=0.1,
                        key='roadm_osnr'
                    )
                
                # Reference Power and Sweep
                with st.expander("⚡ Reference Power and Sweep"):
                    col_p1, col_p2, col_p3 = st.columns(3)
                    with col_p1:
                        st.session_state.sim_pwr_start = st.number_input(
                            "Start [dBm]",
                            value=float(st.session_state.sim_pwr_start),
                            step=0.1,
                            key='pwr_start'
                        )
                    with col_p2:
                        st.session_state.sim_pwr_stop = st.number_input(
                            "Stop [dBm]",
                            value=float(st.session_state.sim_pwr_stop) if st.session_state.sim_pwr_stop is not None else 2.0,
                            step=0.1,
                            key='pwr_stop'
                        )
                    with col_p3:
                        st.session_state.sim_pwr_step = st.number_input(
                            "Step [dBm]",
                            value=float(st.session_state.sim_pwr_step) if st.session_state.sim_pwr_step is not None else 0.1,
                            step=0.01,
                            key='pwr_step'
                        )
                
                can_run_simulation = bool(source and destination and source != destination)
                if st.button(
                    "🚀 Run Simulation", 
                    type="primary", 
                    disabled=not can_run_simulation,
                    on_click=run_simulation_callback,
                    args=(
                        network,
                        equipment,
                        source,
                        destination,
                        launch_power,
                        trx_type,
                        bidir,
                        st.session_state.sim_margin,
                        st.session_state.sim_baudrate,
                        st.session_state.sim_rolloff,
                        st.session_state.sim_tx_osnr,
                        st.session_state.sim_min_osnr,
                        st.session_state.sim_spacing,
                        st.session_state.sim_min_freq,
                        st.session_state.sim_max_freq,
                        st.session_state.sim_roadm_osnr,
                        st.session_state.sim_pwr_start,
                        st.session_state.sim_pwr_stop,
                        st.session_state.sim_pwr_step,
                        nodes_list,
                        loose_list,
                    )
                ):
                    pass  # Callback handles everything


                if st.button(
                    "🚀 Run Transmission", 
                    type="primary", 
                    disabled=not can_run_simulation,
                    on_click=run_transmission,
                    args=(
                        equipment, network, source, destination, launch_power, trx_type, bidir, st.session_state.sim_margin, st.session_state.sim_baudrate, st.session_state.sim_rolloff, st.session_state.sim_tx_osnr, st.session_state.sim_min_osnr, st.session_state.sim_spacing, st.session_state.sim_min_freq, st.session_state.sim_max_freq, st.session_state.sim_roadm_osnr, st.session_state.sim_pwr_start, st.session_state.sim_pwr_stop, st.session_state.sim_pwr_step
                    )
                ):
                    pass  # Callback handles everything

                # path, propagations, powers_dbm, infos, final_gsnr = run_transmission(equipment, network, source, destination, launch_power, trx_type, bidir, st.session_state.sim_margin, st.session_state.sim_baudrate, st.session_state.sim_rolloff, st.session_state.sim_tx_osnr, st.session_state.sim_min_osnr, st.session_state.sim_spacing, st.session_state.sim_min_freq, st.session_state.sim_max_freq, st.session_state.sim_roadm_osnr, st.session_state.sim_pwr_start, st.session_state.sim_pwr_stop, st.session_state.sim_pwr_step)


# Footer
st.sidebar.markdown("---")
st.sidebar.info("""
**GNPy Network Viewer**  
Version 1.0  
Built with Streamlit & Plotly
""")
