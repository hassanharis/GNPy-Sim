"""
GNPy Network Visualization and Analysis Tool
Streamlit application for optical network simulation
"""

import json
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, List
import pandas
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from numpy import mean
import numpy as np
import networkx as nx
import sys

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
OOPT_GNPY_DIR = BASE_DIR / "oopt-gnpy"
if OOPT_GNPY_DIR.exists() and str(OOPT_GNPY_DIR) not in sys.path:
    sys.path.insert(0, str(OOPT_GNPY_DIR))

# GNPy imports (after path fix)
from gnpy.core.elements import Transceiver, Roadm, Fiber, RamanFiber, Edfa, Fused
from gnpy.tools.json_io import (load_equipment,
    load_equipments_and_configs,
    load_network,
    load_json,
    load_requests,
    save_network,
    save_json,
    requests_from_json,
)
from gnpy.tools.worker_utils import designed_network, transmission_simulation, planning
from gnpy.topology.request import (PathRequest, ResultElement, compute_path_dsjctn, compute_constrained_path,
    propagate, propagate_and_optimize_mode, compute_spectrum_slot_vs_bandwidth, correct_json_route_list)
from gnpy.topology.spectrum_assignment import (build_oms_list, build_path_oms_id_list,
    aggregate_oms_bitmap, spectrum_selection, FIRST_FIT, LAST_FIT, BitmapValue)
from gnpy.core import exceptions
from gnpy.core.utils import watt2dbm, dbm2watt, automatic_nch

sys.path.append(r"C:\Users\hahassan\OneDrive - Nokia\Work & Data\Software\My Library")

from my_math import haversine_distance

# Custom Input Generator module
from app_CustomInputGenerator import custom_input_generator_ui, set_base_dir

# Page configuration 
st.set_page_config(
    page_title="GNPy Network Viewer",
    page_icon="🌐",
    layout="wide"
)

# Sidebar configuration
st.sidebar.title("⚙️ Configuration")

# File paths
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
if 'along_path' not in st.session_state:
    st.session_state.along_path = None
if 'power_opt' not in st.session_state:
    st.session_state.power_opt = None
if 'power_opt_error' not in st.session_state:
    st.session_state.power_opt_error = None
if 'batch_rsa' not in st.session_state:
    st.session_state.batch_rsa = None
if 'batch_rsa_error' not in st.session_state:
    st.session_state.batch_rsa_error = None
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


def compute_along_path_snapshots(equipment, network, req):
    """Re-propagate the request element by element along the computed path and record the
    accumulated per-channel spectrum (power, OSNR-ASE, SNR-NLI, GSNR) after each element.

    Returns a dict with the ordered path elements and a list of per-element snapshots, each of
    which holds the channel frequencies (THz) and per-channel metrics (dB / dBm) at that point.
    """
    from gnpy.core.info import create_input_spectral_information, carriers_to_spectral_information
    from gnpy.topology.request import filter_si

    path = compute_constrained_path(network, req)

    if getattr(req, 'initial_spectrum', None) is not None:
        si = carriers_to_spectral_information(initial_spectrum=req.initial_spectrum, power=req.power)
    else:
        si = create_input_spectral_information(
            f_min=req.f_min, f_max=req.f_max, roll_off=req.roll_off, baud_rate=req.baud_rate,
            spacing=req.spacing, tx_osnr=req.tx_osnr, tx_power=req.tx_power, delta_pdb=req.offset_db)
    si = filter_si(path, equipment, si)

    def _arr(values):
        return np.asarray(values, dtype=float).tolist()

    snapshots = []
    cumulative_km = 0.0
    for i, el in enumerate(path):
        if isinstance(el, Roadm):
            si = el(si, degree=path[i + 1].uid, from_degree=path[i - 1].uid)
        else:
            si = el(si)

        if isinstance(el, (Fiber, RamanFiber)):
            cumulative_km += float(getattr(el.params, 'length', 0.0)) / 1000.0

        snapshots.append({
            'index': i,
            'uid': el.uid,
            'type': type(el).__name__,
            'cumulative_km': round(cumulative_km, 3),
            'frequency_thz': _arr(np.asarray(si.frequency) * 1e-12),
            'pch_dbm': _arr(si.pch_dbm),
            'osnr_ase_db': _arr(si.snr_lin_db),
            'snr_nli_db': _arr(si.snr_nli_db),
            'gsnr_db': _arr(si.gsnr_db),
        })

    return {
        'path_elements': [el.uid for el in path],
        'snapshots': snapshots,
    }


def _apply_si_overrides(equipment, baudrate=None, rolloff=None, tx_osnr=None,
                        spacing=None, min_freq=None, max_freq=None, margin=None, power_dbm=None):
    """Override the SI reference channel on a (private, already deep-copied) equipment dict from
    the UI values so the propagation actually uses the configured transceiver/spectral settings.

    Display units: baudrate [GBaud], spacing [GHz], min/max freq [THz], tx_osnr/margin [dB],
    power_dbm [dBm]. The caller MUST pass a deep copy so the cached SI defaults stay untouched.
    """
    si = equipment['SI']['default']

    def _set(attr, value, scale=1.0):
        if value is None:
            return
        try:
            setattr(si, attr, float(value) * scale)
        except (TypeError, ValueError):
            pass

    _set('baud_rate', baudrate, 1e9)
    _set('roll_off', rolloff)
    _set('tx_osnr', tx_osnr)
    _set('spacing', spacing, 1e9)
    _set('f_min', min_freq, 1e12)
    _set('f_max', max_freq, 1e12)
    _set('sys_margins', margin)
    _set('power_dbm', power_dbm)
    return equipment


def _normalized_route_constraints(destination, nodes_l, loose_l):
    """Ensure the include-node list ends with the destination, as compute_constrained_path requires."""
    nl = [n for n in (nodes_l or []) if n]
    ll = list(loose_l or [])[:len(nl)]
    if destination and (not nl or nl[-1] != destination):
        nl = nl + [destination]
        ll = ll + ['STRICT']
    return nl, ll


def run_transmission(equipment, network, source, destination, launch_power, trx_type, bidir, margin, baudrate, rolloff, tx_osnr, spacing, min_freq, max_freq, pwr_start, pwr_stop, pwr_step, nodes_l=None, loose_l=None):

    try:
        from copy import deepcopy as _deepcopy
        # Private copies so the cached SI defaults / network are never mutated by a run.
        equipment = _deepcopy(equipment)
        network = _deepcopy(network)
        _apply_si_overrides(equipment, baudrate=baudrate, rolloff=rolloff, tx_osnr=tx_osnr,
                            spacing=spacing, min_freq=min_freq, max_freq=max_freq,
                            margin=margin, power_dbm=launch_power)
        nl, ll = _normalized_route_constraints(destination, nodes_l, loose_l)

        network, req, ref_req = designed_network(
            equipment, network, source, destination,
            nodes_list=nl, loose_list=ll,
            args_power=launch_power, no_insert_edfas=False,
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

        try:
            st.session_state.along_path = compute_along_path_snapshots(equipment, network, req)
        except Exception as e:
            st.session_state.along_path = None
            st.session_state.along_path_error = f"Along-path capture failed: {e}"
        else:
            st.session_state.along_path_error = None
    except Exception as e:
        st.session_state.simulation_results = {'success': False}
        st.session_state.along_path = None
        st.session_state.simulation_error = str(e)


def run_power_optimization(equipment, network, source, destination, launch_power, trx_type, bidir,
                           margin, baudrate, rolloff, tx_osnr, spacing, min_freq, max_freq,
                           pwr_start, pwr_stop, pwr_step, nodes_l=None, loose_l=None):
    """Sweep the per-channel launch power (span input power) across [start, stop] dBm using GNPy's
    native power-mode sweep, compute the mean GSNR at the destination for each power, and pick the
    power that maximises GSNR. This is XLRON's launch-power optimisation done with GNPy.

    The network is redesigned by GNPy at each swept power, so the GSNR-vs-power curve reflects a
    realistic operating point for every candidate launch power.
    """
    try:
        from copy import deepcopy as _deepcopy

        if pwr_start is None or pwr_stop is None or pwr_step is None:
            raise ValueError("Provide Start, Stop and Step values in 'Reference Power and Sweep'.")
        p_start, p_stop, p_step = float(pwr_start), float(pwr_stop), float(pwr_step)
        if p_step == 0:
            raise ValueError("Sweep Step must be non-zero.")
        p_step = abs(p_step)
        if p_stop < p_start:
            p_start, p_stop = p_stop, p_start
        if p_stop - p_start < p_step / 2:
            raise ValueError(
                f"Sweep range is a single point ({p_start:.2f} dBm). Set a wider Start/Stop range "
                "in the '⚡ Reference Power and Sweep' expander (e.g. Start -2, Stop 4, Step 0.5)."
            )

        if not equipment['Span']['default'].power_mode:
            raise ValueError("Power sweep requires power mode (Span.power_mode = true); "
                             "network is configured in gain mode.")

        # Work on private copies so the cached network/equipment are not mutated by the redesign loop.
        equipment = _deepcopy(equipment)
        network = _deepcopy(network)

        # Apply the configured transceiver/spectral settings to the swept reference channel.
        _apply_si_overrides(equipment, baudrate=baudrate, rolloff=rolloff, tx_osnr=tx_osnr,
                            spacing=spacing, min_freq=min_freq, max_freq=max_freq, margin=margin)
        nl, ll = _normalized_route_constraints(destination, nodes_l, loose_l)

        # Configure GNPy power sweep: design reference at p_start, deltas span up to (p_stop - p_start).
        # NOTE: designed_network expects args_power in dBm (it converts to watt internally).
        equipment['SI']['default'].power_range_db = [0.0, p_stop - p_start, p_step]

        network, req, ref_req = designed_network(
            equipment, network, source, destination,
            nodes_list=nl, loose_list=ll,
            args_power=p_start, no_insert_edfas=False,
        )

        path, propagations, powers_dbm, infos = transmission_simulation(equipment, network, req, ref_req)

        if not propagations:
            raise ValueError("Power sweep produced no propagation results.")

        def _mean_metric(trx, attr):
            vals = getattr(trx, attr, None)
            if vals is None:
                return None
            arr = np.asarray(vals, dtype=float)
            arr = arr[np.isfinite(arr)]
            return float(arr.mean()) if arr.size else None

        powers = [round(float(p), 4) for p in powers_dbm]
        gsnr_curve = [_mean_metric(prop[-1], 'snr') for prop in propagations]
        gsnr01_curve = [_mean_metric(prop[-1], 'snr_01nm') for prop in propagations]

        valid = [(p, g, g01) for p, g, g01 in zip(powers, gsnr_curve, gsnr01_curve) if g is not None]
        if not valid:
            raise ValueError("Could not compute GSNR for any swept power.")
        opt_power, opt_gsnr, opt_gsnr01 = max(valid, key=lambda t: t[1])

        path_elements = [getattr(e, "uid", str(e)) for e in path] if path is not None else []

        st.session_state.power_opt = {
            'powers_dbm': powers,
            'gsnr_db': gsnr_curve,
            'gsnr_01nm_db': gsnr01_curve,
            'opt_power_dbm': opt_power,
            'opt_gsnr_db': opt_gsnr,
            'opt_gsnr_01nm_db': opt_gsnr01,
            'n_points': len(powers),
            'source': source,
            'destination': destination,
            'path_elements': path_elements,
        }
        st.session_state.power_opt_error = None
    except Exception as e:
        st.session_state.power_opt = None
        st.session_state.power_opt_error = str(e)


# ---------------------------------------------------------------------------
# Batch RSA pipeline
# ---------------------------------------------------------------------------
# The engine is decomposed into independent stages, each with an explicit
# input/output contract (the dataclasses below). The orchestrator
# `run_batch_rsa` simply wires the stages together. This keeps the workflow
# easy to reason about and lets future features (cost/SE, k-paths, protection,
# regeneration) plug into a single stage without touching the others.
#
#   prepare  -> RsaContext            (design network, build per-link slot grid)
#   parse    -> list[PathRequest]     (requests JSON -> demand objects)
#   offer    -> list[PathRequest]     (replicate to traffic load, normalize)
#   route    -> RouteResult           (per demand: constrained path)
#   feasible -> FeasibilityResult     (per demand: GNPy GSNR vs required OSNR)
#   assign   -> SpectrumResult        (per demand: first/last-fit slot search)
#   commit   -> mutates oms_list      (occupy slots, record the service)
#   aggregate-> BatchResult dict      (blocking, capacity, curves, utilization)
# ---------------------------------------------------------------------------


@dataclass
class RsaContext:
    """Prepared, immutable environment shared by every stage of one batch run."""
    equipment: Any
    network: Any
    oms_list: list
    sys_margins: float
    policy: str
    trx_uids: List[str]


@dataclass
class RouteResult:
    """Output of the routing stage."""
    path: list                       # ordered network elements (empty => no route)
    reason: Optional[str] = None     # e.g. 'NO_PATH'


@dataclass
class FeasibilityResult:
    """Output of the GSNR feasibility stage."""
    feasible: bool
    margin_db: Optional[float] = None
    mean_gsnr_db: Optional[float] = None
    reason: Optional[str] = None     # None, 'GSNR', 'NO_MODE', 'GSNR_ERROR'


@dataclass
class SpectrumResult:
    """Output of the spectrum-assignment stage (search only; commit is separate)."""
    assigned: bool
    center_n: Optional[int] = None
    m: Optional[int] = None
    nb_wl: Optional[int] = None
    path_oms: list = field(default_factory=list)
    slots: Optional[int] = None      # number of occupied 6.25 GHz grid slots
    reason: Optional[str] = None     # None or 'NO_SPECTRUM'


@dataclass
class DemandOutcome:
    """Per-demand result row produced by the orchestrator."""
    request_id: str
    source: str
    destination: str
    mode: str
    bitrate_gbps: float
    path_bw_gbps: float
    gsnr_mean_db: Optional[float]
    gsnr_margin_db: Optional[float]
    slots: Optional[int]
    status: str                      # 'PROVISIONED' or 'BLOCKED'
    reason: str
    offered_bits: float
    provisioned_bits: float


def rsa_prepare(equipment, network, requests_data) -> RsaContext:
    """Stage 1 - Prepare. Validate inputs, design the network (insert amps/set gains)
    and build the per-link OMS slot grid.

    In:  equipment, network, requests_data (parsed JSON dict)
    Out: RsaContext (deep-copied, designed network + oms_list + run settings)
    """
    if not requests_data or not requests_data.get('path-request'):
        raise ValueError("No 'path-request' entries found in the requests JSON.")

    equipment = deepcopy(equipment)
    network = deepcopy(network)

    trx_uids = [n.uid for n in network.nodes() if isinstance(n, Transceiver)]
    if len(trx_uids) < 2:
        raise ValueError("Network needs at least two transceivers for batch RSA.")

    designed_network(equipment, network, trx_uids[0], trx_uids[1], nodes_list=[], loose_list=[],
                     args_power=None, no_insert_edfas=False)
    oms_list = build_oms_list(network, equipment)
    sys_margins = float(getattr(equipment['SI']['default'], 'sys_margins', 0.0) or 0.0)

    return RsaContext(equipment=equipment, network=network, oms_list=oms_list,
                      sys_margins=sys_margins, policy=FIRST_FIT, trx_uids=trx_uids)


def rsa_parse_demands(requests_data, ctx: RsaContext) -> list:
    """Stage 2 - Parse. Turn the requests JSON into GNPy PathRequest objects and
    resolve/validate their route node names.

    In:  requests_data, ctx
    Out: list[PathRequest] (the base demand catalogue)
    """
    base_rqs = requests_from_json(requests_data, ctx.equipment)
    try:
        base_rqs = correct_json_route_list(ctx.network, base_rqs)
    except Exception:
        pass  # fall back to raw names; routing will flag NO_PATH per demand
    return base_rqs


def rsa_build_offered(base_rqs, n_requests, shuffle_seed) -> list:
    """Stage 3 - Offer. Build the offered traffic sequence by replicating the base
    demands cyclically up to the requested load, normalizing each for routing.

    In:  base_rqs, n_requests (offered load), shuffle_seed (or None)
    Out: list[PathRequest] in arrival order
    """
    import random as _random

    n_base = len(base_rqs)
    n_requests = max(1, int(n_requests))
    offered = []
    for k in range(n_requests):
        rq = deepcopy(base_rqs[k % n_base])
        rq.request_id = f"{base_rqs[k % n_base].request_id}#{k + 1}"
        if hasattr(rq, 'blocking_reason'):
            delattr(rq, 'blocking_reason')
        # compute_constrained_path requires nodes_list to end with the destination
        if not rq.nodes_list or rq.nodes_list[-1] != rq.destination:
            rq.nodes_list = list(rq.nodes_list) + [rq.destination]
            rq.loose_list = list(rq.loose_list) + ['STRICT']
        offered.append(rq)
    if shuffle_seed is not None:
        _random.Random(int(shuffle_seed)).shuffle(offered)
    return offered


def rsa_route(ctx: RsaContext, demand) -> RouteResult:
    """Stage 4 - Route. Compute the constrained shortest path for one demand.

    In:  ctx, demand (PathRequest)
    Out: RouteResult
    """
    try:
        path = compute_constrained_path(ctx.network, demand)
    except Exception:
        path = []
    if not path:
        return RouteResult(path=[], reason='NO_PATH')
    return RouteResult(path=path)


def rsa_feasibility(ctx: RsaContext, demand, path, gsnr_cache: dict) -> FeasibilityResult:
    """Stage 5 - Feasibility. Propagate the demand with GNPy and compare the worst-case
    GSNR (0.1 nm, minus penalties) to the required OSNR + system margin. Results are
    cached per (OD, mode) since GSNR depends on the path, not on slot occupancy.

    In:  ctx, demand, path, gsnr_cache (mutated)
    Out: FeasibilityResult (also resolves the transponder mode onto `demand`)
    """
    def _apply(c):
        if c.get('bit_rate') is not None:
            demand.bit_rate = c['bit_rate']
        if c.get('baud_rate') is not None:
            demand.baud_rate = c['baud_rate']
        if c.get('OSNR') is not None:
            demand.OSNR = c['OSNR']
        return FeasibilityResult(feasible=c['feasible'], margin_db=c['margin'],
                                 mean_gsnr_db=c['mean_gsnr'], reason=c['reason'])

    key = (demand.source, demand.destination, demand.baud_rate,
           round(float(demand.spacing), 3), tuple(demand.nodes_list))
    if key in gsnr_cache:
        return _apply(gsnr_cache[key])

    pp = deepcopy(path)
    try:
        if demand.baud_rate is not None:
            propagate(pp, demand, ctx.equipment)
        else:
            pp, mode = propagate_and_optimize_mode(pp, demand, ctx.equipment)
            if mode is None:
                gsnr_cache[key] = dict(feasible=False, margin=None, mean_gsnr=None, reason='NO_MODE',
                                       bit_rate=None, baud_rate=None, OSNR=None)
                return _apply(gsnr_cache[key])
            demand.baud_rate, demand.OSNR, demand.bit_rate = mode['baud_rate'], mode['OSNR'], mode['bit_rate']
        snr01 = np.asarray(pp[-1].snr_01nm, dtype=float)
        pen = np.asarray(getattr(pp[-1], 'total_penalty', 0.0), dtype=float)
        margin = float(np.min(snr01 - pen)) - (float(demand.OSNR or 0.0) + ctx.sys_margins)
        gsnr_cache[key] = dict(feasible=margin >= 0, margin=margin, mean_gsnr=float(np.mean(snr01)),
                               reason=None if margin >= 0 else 'GSNR',
                               bit_rate=demand.bit_rate, baud_rate=demand.baud_rate, OSNR=demand.OSNR)
    except Exception:
        gsnr_cache[key] = dict(feasible=False, margin=None, mean_gsnr=None, reason='GSNR_ERROR',
                               bit_rate=None, baud_rate=None, OSNR=None)
    return _apply(gsnr_cache[key])


def rsa_assign_spectrum(ctx: RsaContext, demand, path) -> SpectrumResult:
    """Stage 6 - Assign. Find a free contiguous slot block on the union of the path's
    OMS using the configured first/last-fit policy. Does NOT commit (see rsa_commit).

    In:  ctx, demand, path
    Out: SpectrumResult
    """
    pb = float(demand.path_bandwidth or demand.bit_rate or 0.0)
    nb_wl, required_m = compute_spectrum_slot_vs_bandwidth(pb or demand.bit_rate, demand.spacing, demand.bit_rate)
    path_oms = build_path_oms_id_list(path)
    if not path_oms:
        return SpectrumResult(assigned=False, reason='NO_PATH')
    agg = aggregate_oms_bitmap(path_oms, ctx.oms_list)
    center_n, _startn, _stopn = spectrum_selection(agg, required_m, None, ctx.policy)
    if center_n is None:
        return SpectrumResult(assigned=False, path_oms=path_oms, reason='NO_SPECTRUM')
    return SpectrumResult(assigned=True, center_n=int(center_n), m=int(required_m), nb_wl=nb_wl,
                          path_oms=path_oms, slots=2 * int(required_m))


def rsa_commit(ctx: RsaContext, demand, spectrum: SpectrumResult) -> None:
    """Stage 7 - Commit. Mark the selected slots occupied on every OMS of the path and
    record the demand as a service (mutates ctx.oms_list).
    """
    for oms_id in spectrum.path_oms:
        ctx.oms_list[oms_id].assign_spectrum(spectrum.center_n, spectrum.m)
        ctx.oms_list[oms_id].add_service(demand.request_id, spectrum.nb_wl)


def rsa_process_demand(ctx: RsaContext, demand, gsnr_cache: dict) -> DemandOutcome:
    """Run one demand through route -> feasibility -> assign -> commit and return its outcome."""
    offered_bits = float(demand.path_bandwidth or demand.bit_rate or 0.0)
    status, reason, slots = 'PROVISIONED', None, None
    margin = mean_gsnr = None

    route = rsa_route(ctx, demand)
    if not route.path:
        status, reason = 'BLOCKED', route.reason or 'NO_PATH'
    else:
        feas = rsa_feasibility(ctx, demand, route.path, gsnr_cache)
        margin, mean_gsnr = feas.margin_db, feas.mean_gsnr_db
        if not feas.feasible:
            status, reason = 'BLOCKED', feas.reason or 'GSNR'
        else:
            spec = rsa_assign_spectrum(ctx, demand, route.path)
            if not spec.assigned:
                status, reason = 'BLOCKED', spec.reason or 'NO_SPECTRUM'
            else:
                rsa_commit(ctx, demand, spec)
                slots = spec.slots

    # recompute offered bits after feasibility may have resolved a mode
    offered_bits = float(demand.path_bandwidth or demand.bit_rate or offered_bits or 0.0)
    provisioned_bits = offered_bits if status == 'PROVISIONED' else 0.0

    return DemandOutcome(
        request_id=demand.request_id,
        source=remove_type_from_nodeUid(str(demand.source)),
        destination=remove_type_from_nodeUid(str(demand.destination)),
        mode=f"{demand.tsp or ''} {demand.tsp_mode or ''}".strip(),
        bitrate_gbps=round(float(demand.bit_rate or 0.0) * 1e-9, 1),
        path_bw_gbps=round(offered_bits * 1e-9, 1),
        gsnr_mean_db=round(mean_gsnr, 2) if mean_gsnr is not None else None,
        gsnr_margin_db=round(margin, 2) if margin is not None else None,
        slots=slots,
        status=status,
        reason=reason or '',
        offered_bits=offered_bits,
        provisioned_bits=provisioned_bits,
    )


def rsa_aggregate(ctx: RsaContext, outcomes: List[DemandOutcome], n_base: int,
                  unique_gsnr_evals: int) -> dict:
    """Stage 8 - Aggregate. Roll up per-demand outcomes and per-link occupancy into the
    reporting payload (blocking probability, capacity, growth curves, utilization).

    In:  ctx, outcomes (ordered by arrival), n_base, unique_gsnr_evals
    Out: BatchResult dict (stored in session_state and consumed by render_batch_rsa)
    """
    cum_offered = cum_blocked = 0
    cum_capacity = offered_capacity = 0.0
    curve_load, curve_block, curve_capacity = [], [], []
    causes = {'NO_PATH': 0, 'GSNR': 0, 'NO_SPECTRUM': 0, 'NO_MODE': 0, 'GSNR_ERROR': 0}
    records = []

    for o in outcomes:
        cum_offered += 1
        offered_capacity += o.offered_bits
        if o.status == 'BLOCKED':
            cum_blocked += 1
            causes[o.reason] = causes.get(o.reason, 0) + 1
        else:
            cum_capacity += o.provisioned_bits
        curve_load.append(cum_offered)
        curve_block.append(cum_blocked / cum_offered)
        curve_capacity.append(cum_capacity * 1e-12)
        records.append({
            'request_id': o.request_id, 'source': o.source, 'destination': o.destination,
            'mode': o.mode, 'bitrate_gbps': o.bitrate_gbps, 'path_bw_gbps': o.path_bw_gbps,
            'GSNR_mean_db': o.gsnr_mean_db, 'GSNR_margin_db': o.gsnr_margin_db,
            'slots_6p25GHz': o.slots, 'status': o.status, 'reason': o.reason,
        })

    oms_util = []
    for om in ctx.oms_list:
        bm = om.spectrum_bitmap.bitmap
        usable = sum(1 for b in bm if b != BitmapValue.UNUSABLE)
        occupied = sum(1 for b in bm if b == BitmapValue.OCCUPIED)
        oms_util.append({
            'oms_id': om.oms_id,
            'link': f"{remove_type_from_nodeUid(om.el_id_list[0])} → {remove_type_from_nodeUid(om.el_id_list[-1])}",
            'utilization': (occupied / usable) if usable else 0.0,
            'services': len(om.service_list),
        })

    return {
        'policy': ctx.policy,
        'n_base': n_base,
        'n_offered': cum_offered,
        'n_provisioned': cum_offered - cum_blocked,
        'n_blocked': cum_blocked,
        'blocking_prob': (cum_blocked / cum_offered) if cum_offered else 0.0,
        'provisioned_tbps': cum_capacity * 1e-12,
        'offered_tbps': offered_capacity * 1e-12,
        'causes': {k: v for k, v in causes.items()},
        'curve_load': curve_load,
        'curve_block': curve_block,
        'curve_capacity': curve_capacity,
        'records': records,
        'oms_util': oms_util,
        'unique_gsnr_evals': unique_gsnr_evals,
    }


def run_batch_rsa(equipment, network, requests_data, n_requests, shuffle_seed, policy_label):
    """Batch multi-request RSA orchestrator (XLRON-style, using GNPy GSNR for feasibility).

    Wires the pipeline stages: prepare -> parse -> offer -> (route -> feasibility ->
    assign -> commit per demand) -> aggregate. Demands arrive one-by-one so the growth
    curves describe blocking probability and provisioned capacity vs offered load.
    Results are written to st.session_state.batch_rsa (or batch_rsa_error on failure).
    """
    try:
        ctx = rsa_prepare(equipment, network, requests_data)
        ctx.policy = LAST_FIT if str(policy_label).lower().startswith('last') else FIRST_FIT

        base_rqs = rsa_parse_demands(requests_data, ctx)
        offered = rsa_build_offered(base_rqs, n_requests, shuffle_seed)

        gsnr_cache = {}
        outcomes = [rsa_process_demand(ctx, demand, gsnr_cache) for demand in offered]

        st.session_state.batch_rsa = rsa_aggregate(ctx, outcomes, len(base_rqs), len(gsnr_cache))
        st.session_state.batch_rsa_error = None
    except Exception as e:
        st.session_state.batch_rsa = None
        st.session_state.batch_rsa_error = str(e)


def _summary_band(values):
    """Return (mean, min, max) of a per-channel metric list, ignoring non-finite entries."""
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return None, None, None
    return float(arr.mean()), float(arr.min()), float(arr.max())


def render_along_path_plots(along_path):
    """Render the per-link spectrum and GSNR-along-path Plotly charts from captured snapshots."""
    snapshots = (along_path or {}).get('snapshots') or []
    if not snapshots:
        st.info("No along-path data captured. Run a transmission to populate per-link plots.")
        return

    def _node_label(snap):
        clean = remove_type_from_nodeUid(snap['uid'])
        return f"{snap['index']:02d} · {snap['type']} · {clean}"

    x_km = [s['cumulative_km'] for s in snapshots]
    labels = [_node_label(s) for s in snapshots]

    gsnr_mean, gsnr_lo, gsnr_hi = zip(*[_summary_band(s['gsnr_db']) for s in snapshots])
    osnr_mean = [_summary_band(s['osnr_ase_db'])[0] for s in snapshots]
    nli_mean = [_summary_band(s['snr_nli_db'])[0] for s in snapshots]
    pch_mean = [_summary_band(s['pch_dbm'])[0] for s in snapshots]

    customdata = list(zip(labels, [s['type'] for s in snapshots]))

    # ---- GSNR / OSNR / power along the path ----
    st.markdown("**GSNR / OSNR along the path**")
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # min-max GSNR band across channels (only over points with a finite spread)
    finite = [j for j in range(len(x_km)) if gsnr_lo[j] is not None and gsnr_hi[j] is not None]
    if finite:
        fx = [x_km[j] for j in finite]
        band_x = fx + fx[::-1]
        band_y = [gsnr_hi[j] for j in finite] + [gsnr_lo[j] for j in finite][::-1]
        fig.add_trace(go.Scatter(
            x=band_x, y=band_y, fill='toself', fillcolor='rgba(31,119,180,0.12)',
            line=dict(width=0), hoverinfo='skip', showlegend=True, name='GSNR ch. spread'
        ), secondary_y=False)

    fig.add_trace(go.Scatter(
        x=x_km, y=gsnr_mean, mode='lines+markers', name='GSNR (mean)',
        line=dict(color='#1f77b4', width=3), customdata=customdata,
        hovertemplate='%{customdata[0]}<br>%{x:.1f} km<br>GSNR: %{y:.2f} dB<extra></extra>'
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=x_km, y=osnr_mean, mode='lines+markers', name='OSNR ASE (mean)',
        line=dict(color='#2ca02c', width=2, dash='dash'), customdata=customdata,
        hovertemplate='%{customdata[0]}<br>%{x:.1f} km<br>OSNR ASE: %{y:.2f} dB<extra></extra>'
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=x_km, y=nli_mean, mode='lines+markers', name='SNR NLI (mean)',
        line=dict(color='#9467bd', width=2, dash='dot'), customdata=customdata,
        hovertemplate='%{customdata[0]}<br>%{x:.1f} km<br>SNR NLI: %{y:.2f} dB<extra></extra>'
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=x_km, y=pch_mean, mode='lines+markers', name='Ch. power (mean)',
        line=dict(color='#ff7f0e', width=2), customdata=customdata,
        hovertemplate='%{customdata[0]}<br>%{x:.1f} km<br>Power: %{y:.2f} dBm<extra></extra>'
    ), secondary_y=True)

    fig.update_xaxes(title_text="Cumulative distance along path (km)")
    fig.update_yaxes(title_text="SNR (dB)", secondary_y=False)
    fig.update_yaxes(title_text="Channel power (dBm)", secondary_y=True)
    fig.update_layout(
        height=480, hovermode='x unified', margin=dict(t=30, b=0, l=0, r=0),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0)
    )
    st.plotly_chart(fig, use_container_width=True, key="along_path_gsnr")

    # ---- Per-link spectrum at a selected element ----
    st.markdown("**Per-link spectrum**")
    sel_label = st.selectbox(
        "Inspect spectrum at element:",
        options=labels,
        index=len(labels) - 1,
        key="along_path_element_select",
        help="Per-channel power and GSNR of the WDM comb at the output of the selected element."
    )
    snap = snapshots[labels.index(sel_label)]
    freqs = snap['frequency_thz']

    metric = st.radio(
        "Spectrum metric",
        options=["Channel power (dBm)", "GSNR (dB)", "OSNR ASE (dB)"],
        horizontal=True,
        key="along_path_spectrum_metric"
    )
    metric_map = {
        "Channel power (dBm)": ('pch_dbm', '#ff7f0e', 'Power (dBm)'),
        "GSNR (dB)": ('gsnr_db', '#1f77b4', 'GSNR (dB)'),
        "OSNR ASE (dB)": ('osnr_ase_db', '#2ca02c', 'OSNR ASE (dB)'),
    }
    key_name, color, y_title = metric_map[metric]
    y_vals = [v if np.isfinite(v) else None for v in snap[key_name]]

    spec_fig = go.Figure()
    spec_fig.add_trace(go.Bar(
        x=freqs, y=y_vals, marker_color=color, name=y_title,
        hovertemplate='%{x:.4f} THz<br>%{y:.2f}<extra></extra>'
    ))
    spec_fig.update_layout(
        height=420,
        xaxis_title="Frequency (THz)",
        yaxis_title=y_title,
        bargap=0.15,
        margin=dict(t=40, b=0, l=0, r=0),
        title=f"{snap['type']} · {remove_type_from_nodeUid(snap['uid'])}  ({snap['cumulative_km']:.1f} km)"
    )
    st.plotly_chart(spec_fig, use_container_width=True, key="along_path_spectrum")

    mn, lo, hi = _summary_band(y_vals)
    if mn is not None:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Channels", len([v for v in y_vals if v is not None]))
        c2.metric(f"Mean", f"{mn:.2f}")
        c3.metric("Min", f"{lo:.2f}")
        c4.metric("Max", f"{hi:.2f}")


def render_power_optimization(power_opt):
    """Render the GSNR-vs-launch-power sweep curve with the optimum highlighted."""
    powers = power_opt.get('powers_dbm') or []
    gsnr = power_opt.get('gsnr_db') or []
    gsnr01 = power_opt.get('gsnr_01nm_db') or []
    if not powers:
        st.info("No power sweep data. Run 'Optimize Launch Power' to populate the curve.")
        return

    opt_p = power_opt.get('opt_power_dbm')
    opt_g = power_opt.get('opt_gsnr_db')
    opt_g01 = power_opt.get('opt_gsnr_01nm_db')

    c1, c2, c3 = st.columns(3)
    c1.metric("Optimum launch power", f"{opt_p:.2f} dBm" if opt_p is not None else "N/A")
    c2.metric("GSNR @ optimum (signal bw)", f"{opt_g:.2f} dB" if opt_g is not None else "N/A")
    c3.metric("GSNR @ optimum (0.1 nm)", f"{opt_g01:.2f} dB" if opt_g01 is not None else "N/A")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=powers, y=gsnr, mode='lines+markers', name='GSNR (signal bw)',
        line=dict(color='#1f77b4', width=3),
        hovertemplate='Pch %{x:.2f} dBm<br>GSNR %{y:.2f} dB<extra></extra>'
    ))
    if any(v is not None for v in gsnr01):
        fig.add_trace(go.Scatter(
            x=powers, y=gsnr01, mode='lines+markers', name='GSNR (0.1 nm)',
            line=dict(color='#2ca02c', width=2, dash='dash'),
            hovertemplate='Pch %{x:.2f} dBm<br>GSNR %{y:.2f} dB<extra></extra>'
        ))
    if opt_p is not None and opt_g is not None:
        fig.add_trace(go.Scatter(
            x=[opt_p], y=[opt_g], mode='markers', name='Optimum',
            marker=dict(color='#d62728', size=15, symbol='star'),
            hovertemplate='Optimum<br>Pch %{x:.2f} dBm<br>GSNR %{y:.2f} dB<extra></extra>'
        ))
        fig.add_vline(x=opt_p, line=dict(color='#d62728', width=1, dash='dot'))
    fig.update_layout(
        height=460,
        xaxis_title="Per-channel launch power (span input, dBm)",
        yaxis_title="Mean GSNR over channels (dB)",
        hovermode='x unified',
        margin=dict(t=30, b=0, l=0, r=0),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0)
    )
    st.plotly_chart(fig, use_container_width=True, key="power_opt_curve")

    table = pd.DataFrame({
        'Launch power (dBm)': powers,
        'GSNR signal bw (dB)': gsnr,
        'GSNR 0.1nm (dB)': gsnr01,
    })
    with st.expander("View GSNR-vs-power table"):
        st.dataframe(table, use_container_width=True, hide_index=True)


def render_sim_inputs_preview(source, destination, nodes_list, loose_list, launch_power, trx_type, bidir):
    """Summarize the inputs configured for the single-path simulation (shown once a source and
    destination are selected, before the run). This reflects the values the run will be launched
    with so the user can review them up front."""
    ss = st.session_state
    constraints = ", ".join(
        f"{remove_type_from_nodeUid(str(n))} [{lt}]"
        for n, lt in zip(nodes_list or [], loose_list or [])
    ) or "—"

    def _f(key, default=0.0):
        v = ss.get(key, default)
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    spacing_ghz = _f('sim_spacing')
    fmin_thz = _f('sim_min_freq')
    fmax_thz = _f('sim_max_freq')
    try:
        nch = automatic_nch(fmin_thz * 1e12, fmax_thz * 1e12, spacing_ghz * 1e9)
    except Exception:
        nch = None

    rows = [
        ("Path", "Source", remove_type_from_nodeUid(str(source))),
        ("Path", "Destination", remove_type_from_nodeUid(str(destination))),
        ("Path", "Include-node constraints", constraints),
        ("Transceiver", "Type", str(trx_type)),
        ("Transceiver", "Bidirectional", "Yes" if bidir else "No"),
        ("Transceiver", "Launch power", f"{float(launch_power):.1f} dBm"),
        ("Transceiver", "Baud rate", f"{_f('sim_baudrate'):.2f} GBaud"),
        ("Transceiver", "Roll-off", f"{_f('sim_rolloff'):.2f}"),
        ("Transceiver", "Tx OSNR", f"{_f('sim_tx_osnr'):.1f} dB"),
        ("Transceiver", "System margin", f"{_f('sim_margin'):.1f} dB"),
        ("Spectral load", "Channel spacing", f"{spacing_ghz:.2f} GHz"),
        ("Spectral load", "Frequency range", f"{fmin_thz:.2f} – {fmax_thz:.2f} THz"),
        ("Spectral load", "Channels (auto)", str(nch) if nch is not None else "—"),
    ]
    p_start, p_stop, p_step = _f('sim_pwr_start'), _f('sim_pwr_stop'), _f('sim_pwr_step')
    if p_start is not None and p_stop is not None and p_step:
        rows.append(("Power sweep", "Range (optimization)",
                     f"{p_start:.1f} → {p_stop:.1f} dBm, step {p_step:.2f}"))

    st.dataframe(pd.DataFrame(rows, columns=["Group", "Parameter", "Value"]),
                 use_container_width=True, hide_index=True)


def render_batch_rsa(result):
    """Render batch RSA results: blocking probability, provisioned capacity, blocking-vs-load and
    capacity-vs-load curves, per-link spectral utilization, and a per-request outcome table."""
    if not result:
        st.info("No batch results. Configure the load and run the batch RSA engine.")
        return

    bp = result['blocking_prob']
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Blocking probability", f"{bp * 100:.2f} %")
    c2.metric("Provisioned", f"{result['n_provisioned']} / {result['n_offered']}")
    c3.metric("Provisioned capacity", f"{result['provisioned_tbps']:.2f} Tb/s")
    c4.metric("Offered capacity", f"{result['offered_tbps']:.2f} Tb/s")

    causes = {k: v for k, v in result['causes'].items() if v}
    if causes:
        st.caption("Blocking causes: " + ", ".join(f"{k}: {v}" for k, v in causes.items())
                   + f"  ·  policy: {result['policy']}  ·  unique GSNR evaluations: {result['unique_gsnr_evals']}")

    # ---- blocking probability & provisioned capacity vs offered load ----
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(
        x=result['curve_load'], y=[b * 100 for b in result['curve_block']],
        mode='lines', name='Blocking probability', line=dict(color='#d62728', width=3),
        hovertemplate='After %{x} demands<br>Blocking %{y:.2f}%<extra></extra>'
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=result['curve_load'], y=result['curve_capacity'],
        mode='lines', name='Provisioned capacity', line=dict(color='#1f77b4', width=2, dash='dash'),
        hovertemplate='After %{x} demands<br>%{y:.2f} Tb/s<extra></extra>'
    ), secondary_y=True)
    fig.update_xaxes(title_text="Offered demands (cumulative arrivals)")
    fig.update_yaxes(title_text="Blocking probability (%)", secondary_y=False)
    fig.update_yaxes(title_text="Provisioned capacity (Tb/s)", secondary_y=True)
    fig.update_layout(height=420, hovermode='x unified', margin=dict(t=30, b=0, l=0, r=0),
                      legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0))
    st.plotly_chart(fig, use_container_width=True, key="batch_rsa_curve")

    # ---- per-link spectral utilization (top links) ----
    util_rows = [u for u in result['oms_util'] if u['services'] > 0]
    util_rows.sort(key=lambda u: u['utilization'], reverse=True)
    top = util_rows[:20]
    if top:
        st.markdown("**Per-link spectral utilization (busiest links)**")
        ufig = go.Figure(go.Bar(
            x=[u['utilization'] * 100 for u in top][::-1],
            y=[u['link'] for u in top][::-1],
            orientation='h',
            marker_color=[u['utilization'] * 100 for u in top][::-1],
            marker=dict(colorscale='YlOrRd', cmin=0, cmax=100),
            hovertemplate='%{y}<br>%{x:.1f}% used<extra></extra>',
        ))
        ufig.update_layout(height=max(280, 22 * len(top)), xaxis_title="Slot utilization (%)",
                           margin=dict(t=10, b=0, l=0, r=0), xaxis=dict(range=[0, 100]))
        st.plotly_chart(ufig, use_container_width=True, key="batch_rsa_util")

    # ---- per-request outcomes ----
    with st.expander("Per-request outcomes"):
        st.dataframe(pd.DataFrame(result['records']), use_container_width=True, hide_index=True)


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
                "Variable": ["type_def","gain_target", "tilt_target", "nf_min, nf_max", "p_max"],
                "Description": [
                    "Noise models",
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
tab1, tab2, tab3, tab4 = st.tabs([
    "📄 Inputs",
    "🛠️ Custom Input Generator",
    "📊 Network Visualization",
    "📘 Documentation"
])

topology_json, equipment_json, requests_json = load_json_files(topology_path, equipment_path, requests_path)
equipment, network = load_network_data(topology_path, equipment_path, requests_path)

                     

# TAB 1: JSON Viewer
with tab1:
    input_viewer(topology_json, "Topology")
    input_viewer(equipment_json, "Equipment")
    input_viewer(requests_json, "Requests")

with tab2:
    # Set base directory for the custom input generator
    set_base_dir(BASE_DIR)
    
    # Define callback to clear caches when custom inputs are applied
    def _clear_caches():
        load_json_files.clear()
        load_network_data.clear()
    
    custom_input_generator_ui(topology_path, equipment_path, requests_path, on_apply_callback=_clear_caches)

with tab4:
    documentation_view()

network_df = pandas.json_normalize(topology_json.get("elements"))
edges_df = pandas.json_normalize(topology_json.get("connections"))

# TAB 3: Network Visualization
with tab3:
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

                    # Per-link spectrum / GSNR-along-path
                    if st.session_state.get('along_path'):
                        st.subheader("📡 Per-Link Spectrum & GSNR Along Path")
                        render_along_path_plots(st.session_state.along_path)
                    elif st.session_state.get('along_path_error'):
                        st.warning(st.session_state.along_path_error)


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

            # Launch-power optimization (GSNR-vs-power sweep)
            if st.session_state.get('power_opt'):
                st.subheader("⚡ Launch Power Optimization")
                render_power_optimization(st.session_state.power_opt)
            elif st.session_state.get('power_opt_error'):
                st.error(f"❌ Power optimization failed: {st.session_state.power_opt_error}")

            # Batch RSA / blocking-probability study
            if st.session_state.get('batch_rsa'):
                st.subheader("📦 Batch RSA — Blocking & Provisioned Capacity")
                render_batch_rsa(st.session_state.batch_rsa)
            elif st.session_state.get('batch_rsa_error'):
                st.error(f"❌ Batch RSA failed: {st.session_state.batch_rsa_error}")

    with col2:
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

                # Workflow tabs (controls only; outputs render in col1 as before)
                wf_single, wf_batch = st.tabs([
                    "🔬 Single-Path Analysis",
                    "📦 Batch RSA / Blocking",
                ])

                with wf_single:
                    source_options = [""] + nodes
                    dest_options = [""] + nodes

                    # Calculate selectbox indices based on current session state
                    source_index = 0
                    if st.session_state.source_select and st.session_state.source_select in source_options:
                        source_index = source_options.index(st.session_state.source_select)

                    dest_index = 0
                    if st.session_state.dest_select and st.session_state.dest_select in dest_options:
                        dest_index = dest_options.index(st.session_state.dest_select)

                    sp_col1, sp_col2 = st.columns(2)

                    with sp_col1:
                        source_node = st.selectbox(
                            "Source node:",
                            options=source_options,
                            index=source_index,
                            key='source_select'
                        )
                        st.session_state.source_node = source_node if source_node else None

                    with sp_col2:
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

                    def _si_default(attr, fallback, scale=1.0):
                        """Read an SI reference attribute (Hz/dB) and convert to display units."""
                        v = getattr(si, attr, None)
                        try:
                            return float(v) * scale if v is not None else fallback
                        except (TypeError, ValueError):
                            return fallback

                    # Seed simulation parameters from the equipment SI reference channel (defaults).
                    # These are display-unit copies; editing them never changes the SI library.
                    if 'sim_margin' not in st.session_state:
                        st.session_state.sim_margin = _si_default('sys_margins', 0.0)
                    if 'sim_baudrate' not in st.session_state:
                        st.session_state.sim_baudrate = _si_default('baud_rate', 31.57, 1e-9)
                    if 'sim_rolloff' not in st.session_state:
                        st.session_state.sim_rolloff = _si_default('roll_off', 0.15)
                    if 'sim_tx_osnr' not in st.session_state:
                        st.session_state.sim_tx_osnr = _si_default('tx_osnr', 40.0)
                    if 'sim_spacing' not in st.session_state:
                        st.session_state.sim_spacing = _si_default('spacing', 50.0, 1e-9)
                    if 'sim_min_freq' not in st.session_state:
                        st.session_state.sim_min_freq = _si_default('f_min', 191.30, 1e-12)
                    if 'sim_max_freq' not in st.session_state:
                        st.session_state.sim_max_freq = _si_default('f_max', 196.10, 1e-12)
                    if 'sim_pwr_start' not in st.session_state:
                        st.session_state.sim_pwr_start = -2.0
                    if 'sim_pwr_stop' not in st.session_state:
                        st.session_state.sim_pwr_stop = 4.0
                    if 'sim_pwr_step' not in st.session_state:
                        st.session_state.sim_pwr_step = 0.5

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
                                value=float(st.session_state.sim_pwr_stop) if st.session_state.sim_pwr_stop is not None else 4.0,
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

                    if can_run_simulation:
                        st.subheader("🧾 Simulation inputs to be used")
                        render_sim_inputs_preview(source, destination, nodes_list, loose_list,
                                                  launch_power, trx_type, bidir)
                        st.caption(
                            "These values are applied to the propagated reference channel — editing them "
                            "changes the simulation. The equipment SI library defaults are left unchanged."
                        )

                    if st.button(
                        "🚀 Run Transmission",
                        type="primary",
                        disabled=not can_run_simulation,
                        on_click=run_transmission,
                        args=(
                            equipment, network, source, destination, launch_power, trx_type, bidir, st.session_state.sim_margin, st.session_state.sim_baudrate, st.session_state.sim_rolloff, st.session_state.sim_tx_osnr, st.session_state.sim_spacing, st.session_state.sim_min_freq, st.session_state.sim_max_freq, st.session_state.sim_pwr_start, st.session_state.sim_pwr_stop, st.session_state.sim_pwr_step, nodes_list, loose_list
                        )
                    ):
                        pass  # Callback handles everything

                    st.caption(
                        "Optimization sweeps span input power from Start to Stop (Step) in the "
                        "'⚡ Reference Power and Sweep' expander and picks the GSNR-maximising power."
                    )
                    if st.button(
                        "⚡ Optimize Launch Power",
                        type="secondary",
                        disabled=not can_run_simulation,
                        on_click=run_power_optimization,
                        args=(
                            equipment, network, source, destination, launch_power, trx_type, bidir,
                            st.session_state.sim_margin, st.session_state.sim_baudrate, st.session_state.sim_rolloff,
                            st.session_state.sim_tx_osnr, st.session_state.sim_spacing,
                            st.session_state.sim_min_freq, st.session_state.sim_max_freq,
                            st.session_state.sim_pwr_start, st.session_state.sim_pwr_stop, st.session_state.sim_pwr_step,
                            nodes_list, loose_list,
                        )
                    ):
                        pass  # Callback handles everything

                with wf_batch:
                    st.subheader("📦 Batch RSA / Blocking")
                    n_base_req = len(requests_json.get('path-request', [])) if isinstance(requests_json, dict) else 0
                    if n_base_req == 0:
                        st.info("Load a requests JSON with 'path-request' entries to run the batch engine.")
                    else:
                        st.caption(
                            f"{n_base_req} base demand(s) in the requests file. Demands are offered one-by-one "
                            "(cumulative load); each is routed, GSNR-checked, then first/last-fit assigned on the "
                            "per-link slot grid. Blocking = no path / GSNR fail / no spectrum."
                        )
                        bcol1, bcol2 = st.columns(2)
                        with bcol1:
                            n_offered = st.number_input(
                                "Demands to offer (load)", min_value=1, max_value=100000,
                                value=int(max(n_base_req, 50)), step=10, key='rsa_n_offered',
                                help="Base demands are replicated cyclically to reach this offered load."
                            )
                        with bcol2:
                            rsa_policy = st.selectbox("Spectrum policy", ["first_fit", "last_fit"], key='rsa_policy')
                        rsa_shuffle = st.checkbox("Shuffle demand order", value=False, key='rsa_shuffle')
                        rsa_seed = None
                        if rsa_shuffle:
                            rsa_seed = st.number_input("Shuffle seed", value=0, step=1, key='rsa_seed')

                        if st.button(
                            "📦 Run Batch RSA",
                            type="secondary",
                            on_click=run_batch_rsa,
                            args=(equipment, network, requests_json, n_offered, rsa_seed, rsa_policy),
                        ):
                            pass  # Callback handles everything


# Footer
st.sidebar.markdown("---")
st.sidebar.info("""
**GNPy Network Viewer**  
Version 1.0  
Built with Streamlit & Plotly
""")
