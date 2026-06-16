"""
GNPy Single Span Transmission Simulator
Streamlit application for optical single-span simulation
Based on transmission_script.py workflow
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Prefer vendored GNPy in this repo so imports match (e.g. gnpy.core.info); see app_2.py
BASE_DIR = Path(__file__).resolve().parent
OOPT_GNPY_DIR = BASE_DIR / "oopt-gnpy"
if OOPT_GNPY_DIR.exists() and str(OOPT_GNPY_DIR) not in sys.path:
    sys.path.insert(0, str(OOPT_GNPY_DIR))

# GNPy imports
from gnpy.core.info import SpectralInformation, Carrier, create_input_spectral_information
from gnpy.core.elements import Fiber, RamanFiber, Edfa
from gnpy.core.parameters import FiberParams, EdfaParams, SimParams
from gnpy.tools.json_io import load_json, Model_fg, Model_vg
from gnpy.core.utils import watt2dbm, dbm2watt, lin2db, db2lin

# Page configuration
st.set_page_config(
    page_title="GNPy Single Span Simulator",
    page_icon="🔬",
    layout="wide"
)

# Base directory (BASE_DIR set above before gnpy imports)
INPUTS_DIR = BASE_DIR / "inputs"

# Component library paths
LIBRARY_DIR = INPUTS_DIR / "library"
TRANSCEIVERS_DIR = LIBRARY_DIR / "transceivers"
FIBERS_DIR = LIBRARY_DIR / "fibers"
AMPLIFIERS_DIR = LIBRARY_DIR / "amplifiers"
SIM_PARAMS_DIR = LIBRARY_DIR / "simulation_params"
ROADMS_DIR = LIBRARY_DIR / "roadms"

# Spectrum paths
SPECTRUM_DIR = INPUTS_DIR / "spectrum"
FREQUENCY_RANGE_DIR = SPECTRUM_DIR / "frequency_range"
SPECTRA_DIR = SPECTRUM_DIR / "spectra" / "fixed_grid"

# -----------------------------------------------------------------------------
# Helper functions for loading component files
# -----------------------------------------------------------------------------

def list_json_files(folder: Path) -> List[str]:
    """List all JSON files in a folder (without extension)."""
    if not folder.exists():
        return []
    return sorted([f.stem for f in folder.glob("*.json")])


def load_component_json(folder: Path, name: str) -> Dict[str, Any]:
    """Load a JSON component file."""
    file_path = folder / f"{name}.json"
    if not file_path.exists():
        raise FileNotFoundError(f"Component file not found: {file_path}")
    with open(file_path, 'r') as f:
        return json.load(f)


def get_transceivers() -> List[str]:
    """Get list of available transceivers."""
    return list_json_files(TRANSCEIVERS_DIR)


def get_fibers() -> List[str]:
    """Get list of available fiber types."""
    return list_json_files(FIBERS_DIR)


def get_amplifiers() -> List[str]:
    """Get list of available amplifier types."""
    return list_json_files(AMPLIFIERS_DIR)


def get_sim_params() -> List[str]:
    """Get list of available simulation parameter configs."""
    return list_json_files(SIM_PARAMS_DIR)


def get_frequency_bands() -> List[str]:
    """Get list of available frequency bands."""
    return list_json_files(FREQUENCY_RANGE_DIR)


def get_spectra_bands() -> List[str]:
    """Get list of available spectra band folders."""
    if not SPECTRA_DIR.exists():
        return []
    return sorted([d.name for d in SPECTRA_DIR.iterdir() if d.is_dir()])


def get_spectra_files(band: str) -> List[str]:
    """Get list of spectrum files for a given band."""
    spectra_band_dir = SPECTRA_DIR / band
    if not spectra_band_dir.exists():
        return []
    return sorted([f.stem for f in spectra_band_dir.glob("*.json")])


# -----------------------------------------------------------------------------
# Spectrum creation functions
# -----------------------------------------------------------------------------

def create_spectrum_from_params(
    f_min: float,
    f_max: float,
    spacing: float,
    baud_rate: float,
    roll_off: float,
    signal_power_dbm: float,
    tx_osnr: float = 40.0
) -> SpectralInformation:
    """Create a spectral information object from parameters."""
    signal_power_w = dbm2watt(signal_power_dbm)
    
    # Create the spectral information
    spectral_info = create_input_spectral_information(
        f_min=f_min,
        f_max=f_max,
        roll_off=roll_off,
        baud_rate=baud_rate,
        tx_power=signal_power_w,
        spacing=spacing,
        tx_osnr=tx_osnr
    )
    return spectral_info


def load_spectrum_from_file(file_path: Path, signal_power_dbm: float, tx_osnr: float = 40.0) -> SpectralInformation:
    """Load spectrum configuration from a JSON file."""
    with open(file_path, 'r') as f:
        spec_data = json.load(f)
    
    # Extract arrays
    frequencies = np.array(spec_data.get('frequency', []))
    slot_widths = np.array(spec_data.get('slot_width', []))
    baud_rates = np.array(spec_data.get('baud_rate', []))
    roll_offs = np.array(spec_data.get('roll_off', []))
    
    if len(frequencies) == 0:
        raise ValueError("Spectrum file has no frequency data")
    
    signal_power_w = dbm2watt(signal_power_dbm)
    
    # Create carriers
    carriers = tuple(
        Carrier(
            delta_pdb=0.0,
            baud_rate=baud_rates[i] if i < len(baud_rates) else baud_rates[0],
            slot_width=slot_widths[i] if i < len(slot_widths) else slot_widths[0],
            roll_off=roll_offs[i] if i < len(roll_offs) else roll_offs[0],
            tx_osnr=tx_osnr,
            tx_power=signal_power_w
        )
        for i in range(len(frequencies))
    )
    
    spectral_info = SpectralInformation(
        frequency=frequencies,
        baud_rate=baud_rates if len(baud_rates) == len(frequencies) else np.full(len(frequencies), baud_rates[0]),
        slot_width=slot_widths if len(slot_widths) == len(frequencies) else np.full(len(frequencies), slot_widths[0]),
        signal=np.full(len(frequencies), signal_power_w),
        nli=np.zeros(len(frequencies)),
        ase=np.zeros(len(frequencies)),
        roll_off=roll_offs if len(roll_offs) == len(frequencies) else np.full(len(frequencies), roll_offs[0]),
        chromatic_dispersion=np.zeros(len(frequencies)),
        pmd=np.zeros(len(frequencies)),
        pdl=np.zeros(len(frequencies)),
        latency=np.zeros(len(frequencies)),
        tx_osnr=np.full(len(frequencies), tx_osnr)
    )
    
    return spectral_info


# -----------------------------------------------------------------------------
# Component creation functions
# -----------------------------------------------------------------------------

def create_fiber_element(
    fiber_config: Dict[str, Any],
    length_km: float,
    use_raman: bool = False,
    sim_params: Dict[str, Any] = None
) -> Fiber:
    """Create a fiber element from configuration."""
    # Get fiber params
    if "Regular" in fiber_config:
        fiber_data = fiber_config["Regular"]
    elif "Extended" in fiber_config:
        fiber_data = fiber_config["Extended"]
    else:
        fiber_data = fiber_config
    
    params = fiber_data.get("params", fiber_data)
    
    fiber_params = {
        "uid": fiber_data.get("uid", "fiber_span"),
        "type_variety": fiber_data.get("type_variety", "SSMF"),
        "params": {
            "length": length_km,
            "length_units": "km",
            "loss_coef": params.get("loss_coef", 0.2),
            "con_in": params.get("con_in", 0.0),
            "con_out": params.get("con_out", 0.0),
        }
    }
    
    # Add optional parameters
    for key in ["dispersion", "gamma", "effective_area", "pmd_coef", "ref_frequency"]:
        if key in params:
            fiber_params["params"][key] = params[key]
    
    # Set simulation parameters if provided
    if sim_params:
        set_simulation_params(sim_params)
    
    if use_raman:
        # RamanFiber requires operational parameters with raman_pumps and temperature
        # Default Raman pump configuration for counter-propagating pump
        default_raman_pumps = [
            {"power": 200e-3, "frequency": 206e12, "propagation_direction": "counterprop"},
            {"power": 150e-3, "frequency": 207e12, "propagation_direction": "counterprop"},
        ]
        
        # Check if sim_params has raman pump configuration
        raman_pumps = default_raman_pumps
        temperature = 300  # Kelvin
        
        if sim_params and "raman_params" in sim_params:
            raman_cfg = sim_params["raman_params"]
            if "pumps" in raman_cfg:
                raman_pumps = raman_cfg["pumps"]
            if "temperature" in raman_cfg:
                temperature = raman_cfg["temperature"]
        
        fiber_params["operational"] = {
            "raman_pumps": raman_pumps,
            "temperature": temperature
        }
        fiber = RamanFiber(**fiber_params)
    else:
        fiber = Fiber(**fiber_params)
    
    return fiber


def create_amplifier_element(
    amp_config: Dict[str, Any],
    gain_db: float = None,
    target_power_dbm: float = None,
    f_min: float = 191.3e12,
    f_max: float = 196.1e12
) -> Edfa:
    """Create an EDFA element from configuration."""
    # Get params from config - they may be nested under 'params' key
    config_params = amp_config.get("params", amp_config)
    
    # Get NF value and create appropriate nf_model
    nf0_val = config_params.get("nf0", 6.0)
    type_def = config_params.get("type_def", "fixed_gain")
    
    # Create nf_model based on type_def
    if type_def == "fixed_gain":
        nf_model = Model_fg(nf0=nf0_val)
    else:
        # For variable_gain, create Model_vg (but we default to fixed_gain)
        nf_model = Model_fg(nf0=nf0_val)
    
    # Build the params dict for EDFA - must include type_variety and frequency range
    edfa_params_dict = {
        "type_variety": config_params.get("type_variety", "std_fixed_gain"),
        "type_def": type_def,
        "gain_flatmax": config_params.get("gain_flatmax", 26),
        "gain_min": config_params.get("gain_min", 12),
        "p_max": config_params.get("p_max", 24),
        "nf0": nf0_val,
        "allowed_for_design": config_params.get("allowed_for_design", False),
        "f_min": config_params.get("f_min", f_min),
        "f_max": config_params.get("f_max", f_max),
        "f_ripple_ref": None,
        "gain_ripple": [0, 0],  # Must be array with at least 2 elements
        "tilt_ripple": [0, 0],  # Must be array with at least 2 elements
        "nf_ripple": [0, 0],    # Must be array with at least 2 elements
        "nf_model": nf_model,
        "nf_min": config_params.get("nf_min"),
        "nf_max": config_params.get("nf_max"),
        "nf_coef": None,
        "nf_fit_coeff": None,
        "dual_stage_model": None,
        "out_voa_auto": config_params.get("out_voa_auto", False),
        "pmd": 0,
        "pdl": 0,
        "raman": False,
        "dgt": [0, 0],  # Dynamic gain tilt - must be array with at least 2 elements
        "advance_configurations_from_json": None,
    }
    
    # Build operational parameters
    operational = {
        "tilt_target": 0,  # Required - default to 0 for flat gain
        "out_voa": 0,      # Output VOA - default to 0
        "in_voa": 0,       # Input VOA - default to 0
    }
    if gain_db is not None:
        operational["gain_target"] = gain_db
    if target_power_dbm is not None:
        operational["out_target"] = target_power_dbm
    
    edfa = Edfa(
        uid=amp_config.get("uid", "edfa"),
        params=edfa_params_dict,
        operational=operational
    )
    return edfa


def set_simulation_params(sim_config: Dict[str, Any]):
    """Set GNPy simulation parameters."""
    raman_params = sim_config.get("raman_params", {})
    nli_params = sim_config.get("nli_params", {})
    
    # SimParams.set_params() expects specific format
    params = {
        "raman_params": raman_params,
        "nli_params": nli_params
    }
    SimParams.set_params(params)


# -----------------------------------------------------------------------------
# Simulation functions
# -----------------------------------------------------------------------------

def run_single_span_simulation(
    fiber_config: Dict[str, Any],
    fiber_length: float,
    spectrum: SpectralInformation,
    use_raman: bool,
    sim_params: Dict[str, Any],
    amplifier_config: Optional[Dict[str, Any]] = None,
    amp_gain_db: Optional[float] = None
) -> Dict[str, Any]:
    """Run single span transmission simulation."""
    
    results = {
        "input": {},
        "after_fiber": {},
        "after_amplifier": {}
    }
    
    # Store input spectrum
    results["input"] = {
        "frequency": spectrum.frequency.copy(),
        "signal_dbm": watt2dbm(spectrum.signal),
        "signal_w": spectrum.signal.copy(),
    }
    
    # Set simulation parameters
    set_simulation_params(sim_params)
    
    # Create fiber
    fiber = create_fiber_element(fiber_config, fiber_length, use_raman, sim_params)
    
    # Set reference input power (required for fiber element)
    fiber.ref_pch_in_dbm = watt2dbm(np.mean(spectrum.signal))
    
    # Propagate through fiber
    spectrum_after_fiber = fiber(spectrum)
    
    results["after_fiber"] = {
        "frequency": spectrum_after_fiber.frequency.copy(),
        "signal_dbm": watt2dbm(spectrum_after_fiber.signal),
        "signal_w": spectrum_after_fiber.signal.copy(),
        "ase_dbm": watt2dbm(spectrum_after_fiber.ase) if np.any(spectrum_after_fiber.ase > 0) else np.full_like(spectrum_after_fiber.ase, -np.inf),
        "nli_dbm": watt2dbm(spectrum_after_fiber.nli) if np.any(spectrum_after_fiber.nli > 0) else np.full_like(spectrum_after_fiber.nli, -np.inf),
        "chromatic_dispersion": spectrum_after_fiber.chromatic_dispersion.copy(),
    }
    
    # Calculate SNR metrics after fiber
    signal = spectrum_after_fiber.signal
    ase = spectrum_after_fiber.ase
    nli = spectrum_after_fiber.nli
    
    with np.errstate(divide='ignore', invalid='ignore'):
        osnr_db = lin2db(signal / (ase + 1e-30)) if np.any(ase > 0) else np.full_like(signal, np.inf)
        snr_nl_db = lin2db(signal / (nli + 1e-30)) if np.any(nli > 0) else np.full_like(signal, np.inf)
        gsnr_db = lin2db(signal / (ase + nli + 1e-30)) if np.any(ase + nli > 0) else np.full_like(signal, np.inf)
    
    results["after_fiber"]["osnr_db"] = np.nan_to_num(osnr_db, nan=np.inf, posinf=np.inf)
    results["after_fiber"]["snr_nl_db"] = np.nan_to_num(snr_nl_db, nan=np.inf, posinf=np.inf)
    results["after_fiber"]["gsnr_db"] = np.nan_to_num(gsnr_db, nan=np.inf, posinf=np.inf)
    
    # Amplification stage (if configured)
    if amplifier_config is not None:
        # Get frequency range from spectrum
        spec_f_min = float(spectrum_after_fiber.frequency.min())
        spec_f_max = float(spectrum_after_fiber.frequency.max())
        amp = create_amplifier_element(amplifier_config, gain_db=amp_gain_db, f_min=spec_f_min, f_max=spec_f_max)
        spectrum_after_amp = amp(spectrum_after_fiber)
        
        results["after_amplifier"] = {
            "frequency": spectrum_after_amp.frequency.copy(),
            "signal_dbm": watt2dbm(spectrum_after_amp.signal),
            "signal_w": spectrum_after_amp.signal.copy(),
            "ase_dbm": watt2dbm(spectrum_after_amp.ase) if np.any(spectrum_after_amp.ase > 0) else np.full_like(spectrum_after_amp.ase, -np.inf),
            "nli_dbm": watt2dbm(spectrum_after_amp.nli) if np.any(spectrum_after_amp.nli > 0) else np.full_like(spectrum_after_amp.nli, -np.inf),
        }
        
        # Calculate SNR after amplifier
        signal_amp = spectrum_after_amp.signal
        ase_amp = spectrum_after_amp.ase
        nli_amp = spectrum_after_amp.nli
        
        with np.errstate(divide='ignore', invalid='ignore'):
            osnr_amp_db = lin2db(signal_amp / (ase_amp + 1e-30)) if np.any(ase_amp > 0) else np.full_like(signal_amp, np.inf)
            snr_nl_amp_db = lin2db(signal_amp / (nli_amp + 1e-30)) if np.any(nli_amp > 0) else np.full_like(signal_amp, np.inf)
            gsnr_amp_db = lin2db(signal_amp / (ase_amp + nli_amp + 1e-30)) if np.any(ase_amp + nli_amp > 0) else np.full_like(signal_amp, np.inf)
        
        results["after_amplifier"]["osnr_db"] = np.nan_to_num(osnr_amp_db, nan=np.inf, posinf=np.inf)
        results["after_amplifier"]["snr_nl_db"] = np.nan_to_num(snr_nl_amp_db, nan=np.inf, posinf=np.inf)
        results["after_amplifier"]["gsnr_db"] = np.nan_to_num(gsnr_amp_db, nan=np.inf, posinf=np.inf)
    
    return results


# -----------------------------------------------------------------------------
# Plotting functions
# -----------------------------------------------------------------------------

def plot_power_spectrum(results: Dict[str, Any], title: str = "Signal Power vs Frequency") -> go.Figure:
    """Plot signal power spectrum at different stages."""
    fig = go.Figure()
    
    # Input
    if "input" in results and "frequency" in results["input"]:
        freq_thz = results["input"]["frequency"] * 1e-12
        fig.add_trace(go.Scatter(
            x=freq_thz,
            y=results["input"]["signal_dbm"],
            mode='markers',
            name='Input',
            marker=dict(size=6)
        ))
    
    # After fiber
    if "after_fiber" in results and "frequency" in results["after_fiber"]:
        freq_thz = results["after_fiber"]["frequency"] * 1e-12
        fig.add_trace(go.Scatter(
            x=freq_thz,
            y=results["after_fiber"]["signal_dbm"],
            mode='markers',
            name='After Fiber',
            marker=dict(size=6)
        ))
    
    # After amplifier
    if "after_amplifier" in results and "frequency" in results["after_amplifier"]:
        freq_thz = results["after_amplifier"]["frequency"] * 1e-12
        fig.add_trace(go.Scatter(
            x=freq_thz,
            y=results["after_amplifier"]["signal_dbm"],
            mode='markers',
            name='After Amplifier',
            marker=dict(size=6)
        ))
    
    fig.update_layout(
        title=title,
        xaxis_title="Frequency (THz)",
        yaxis_title="Power (dBm)",
        legend=dict(x=0.02, y=0.98),
        hovermode='closest'
    )
    
    return fig


def plot_snr_spectrum(results: Dict[str, Any], stage: str = "after_fiber", title: str = "SNR Metrics") -> go.Figure:
    """Plot SNR metrics for a given stage."""
    fig = go.Figure()
    
    if stage in results and "frequency" in results[stage]:
        data = results[stage]
        freq_thz = data["frequency"] * 1e-12
        
        # OSNR
        if "osnr_db" in data:
            osnr = data["osnr_db"]
            # Filter out infinities for plotting
            mask = np.isfinite(osnr)
            if np.any(mask):
                fig.add_trace(go.Scatter(
                    x=freq_thz[mask],
                    y=osnr[mask],
                    mode='markers',
                    name='OSNR',
                    marker=dict(size=6)
                ))
        
        # SNR_NL
        if "snr_nl_db" in data:
            snr_nl = data["snr_nl_db"]
            mask = np.isfinite(snr_nl)
            if np.any(mask):
                fig.add_trace(go.Scatter(
                    x=freq_thz[mask],
                    y=snr_nl[mask],
                    mode='markers',
                    name='SNR_NL',
                    marker=dict(size=6)
                ))
        
        # GSNR
        if "gsnr_db" in data:
            gsnr = data["gsnr_db"]
            mask = np.isfinite(gsnr)
            if np.any(mask):
                fig.add_trace(go.Scatter(
                    x=freq_thz[mask],
                    y=gsnr[mask],
                    mode='markers',
                    name='GSNR',
                    marker=dict(size=6)
                ))
    
    fig.update_layout(
        title=title,
        xaxis_title="Frequency (THz)",
        yaxis_title="SNR (dB)",
        legend=dict(x=0.02, y=0.02),
        hovermode='closest'
    )
    
    return fig


def plot_comparison(results_raman: Dict, results_no_raman: Dict) -> go.Figure:
    """Plot comparison between Raman and non-Raman simulations."""
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=("Signal Power Comparison", "GSNR Comparison"),
        vertical_spacing=0.15
    )
    
    # Power comparison
    if "after_fiber" in results_raman:
        freq_thz = results_raman["after_fiber"]["frequency"] * 1e-12
        fig.add_trace(go.Scatter(
            x=freq_thz,
            y=results_raman["after_fiber"]["signal_dbm"],
            mode='markers',
            name='With Raman',
            marker=dict(size=5)
        ), row=1, col=1)
    
    if "after_fiber" in results_no_raman:
        freq_thz = results_no_raman["after_fiber"]["frequency"] * 1e-12
        fig.add_trace(go.Scatter(
            x=freq_thz,
            y=results_no_raman["after_fiber"]["signal_dbm"],
            mode='markers',
            name='Without Raman',
            marker=dict(size=5)
        ), row=1, col=1)
    
    # GSNR comparison
    if "after_fiber" in results_raman and "gsnr_db" in results_raman["after_fiber"]:
        freq_thz = results_raman["after_fiber"]["frequency"] * 1e-12
        gsnr = results_raman["after_fiber"]["gsnr_db"]
        mask = np.isfinite(gsnr)
        if np.any(mask):
            fig.add_trace(go.Scatter(
                x=freq_thz[mask],
                y=gsnr[mask],
                mode='markers',
                name='GSNR (Raman)',
                marker=dict(size=5),
                showlegend=False
            ), row=2, col=1)
    
    if "after_fiber" in results_no_raman and "gsnr_db" in results_no_raman["after_fiber"]:
        freq_thz = results_no_raman["after_fiber"]["frequency"] * 1e-12
        gsnr = results_no_raman["after_fiber"]["gsnr_db"]
        mask = np.isfinite(gsnr)
        if np.any(mask):
            fig.add_trace(go.Scatter(
                x=freq_thz[mask],
                y=gsnr[mask],
                mode='markers',
                name='GSNR (No Raman)',
                marker=dict(size=5),
                showlegend=False
            ), row=2, col=1)
    
    fig.update_xaxes(title_text="Frequency (THz)", row=1, col=1)
    fig.update_xaxes(title_text="Frequency (THz)", row=2, col=1)
    fig.update_yaxes(title_text="Power (dBm)", row=1, col=1)
    fig.update_yaxes(title_text="GSNR (dB)", row=2, col=1)
    
    fig.update_layout(height=700, showlegend=True)
    
    return fig


def plot_waterfall(results: Dict[str, Any]) -> go.Figure:
    """Plot waterfall/cascade showing signal evolution: Input → After Fiber → After Amp."""
    # Frequency to wavelength conversion
    c_nm_thz = 299792.458
    
    fig = go.Figure()
    
    stages = []
    if "input" in results and "frequency" in results["input"]:
        stages.append(("Input", results["input"], "rgb(31, 119, 180)"))
    if "after_fiber" in results and "frequency" in results["after_fiber"]:
        stages.append(("After Fiber", results["after_fiber"], "rgb(255, 127, 14)"))
    if "after_amplifier" in results and results["after_amplifier"] and "frequency" in results["after_amplifier"]:
        stages.append(("After Amplifier", results["after_amplifier"], "rgb(44, 160, 44)"))
    
    num_channels = len(results["input"]["signal_dbm"]) if "input" in results else 0
    
    # Create waterfall view - each stage offset
    for i, (name, data, color) in enumerate(stages):
        freq_thz = data["frequency"] * 1e-12
        signal_dbm = data["signal_dbm"]
        wl_nm = c_nm_thz / freq_thz
        
        # Offset each stage for waterfall effect
        y_offset = i * 0
        
        fig.add_trace(go.Scatter(
            x=freq_thz,
            y=signal_dbm + y_offset,
            mode='markers+lines',
            name=name,
            marker=dict(size=5, color=color),
            line=dict(color=color, width=1),
            customdata=np.column_stack([wl_nm, signal_dbm]),
            hovertemplate="<b>%{fullData.name}</b><br>" +
                          "Freq: %{x:.3f} THz<br>" +
                          "λ: %{customdata[0]:.2f} nm<br>" +
                          "Power: %{customdata[1]:.2f} dBm<extra></extra>"
        ))
    
    fig.update_layout(
        title="Signal Evolution - Waterfall View",
        xaxis_title="Frequency (THz)",
        yaxis_title="Power (dBm)",
        height=400,
        legend=dict(x=0.02, y=0.98, bgcolor='rgba(255,255,255,0.8)'),
        hovermode='x unified'
    )
    
    return fig


def plot_power_with_noise(results: Dict[str, Any], stage: str = "after_fiber", 
                          required_osnr: Optional[float] = None) -> go.Figure:
    """Plot power spectrum with NLI and ASE noise floors."""
    c_nm_thz = 299792.458
    fig = go.Figure()
    
    if stage in results and "frequency" in results[stage]:
        data = results[stage]
        freq_thz = data["frequency"] * 1e-12
        wl_nm = c_nm_thz / freq_thz
        
        # Signal power
        fig.add_trace(go.Scatter(
            x=freq_thz,
            y=data["signal_dbm"],
            mode='markers+lines',
            name='Signal',
            marker=dict(size=5, color='rgb(31, 119, 180)'),
            line=dict(color='rgb(31, 119, 180)', width=1),
            customdata=wl_nm,
            hovertemplate="Signal<br>Freq: %{x:.3f} THz<br>λ: %{customdata:.2f} nm<br>Power: %{y:.2f} dBm<extra></extra>"
        ))
        
        # ASE noise floor
        if "ase_dbm" in data:
            ase_dbm = data["ase_dbm"]
            mask = np.isfinite(ase_dbm)
            if np.any(mask):
                fig.add_trace(go.Scatter(
                    x=freq_thz[mask],
                    y=ase_dbm[mask],
                    mode='lines',
                    name='ASE Noise Floor',
                    line=dict(color='rgb(255, 127, 14)', width=2, dash='dash'),
                    fill='tozeroy',
                    fillcolor='rgba(255, 127, 14, 0.1)'
                ))
        
        # NLI noise floor 
        if "nli_dbm" in data:
            nli_dbm = data["nli_dbm"]
            mask = np.isfinite(nli_dbm)
            if np.any(mask):
                fig.add_trace(go.Scatter(
                    x=freq_thz[mask],
                    y=nli_dbm[mask],
                    mode='lines',
                    name='NLI Noise Floor',
                    line=dict(color='rgb(214, 39, 40)', width=2, dash='dot'),
                    fill='tozeroy',
                    fillcolor='rgba(214, 39, 40, 0.1)'
                ))
        
        # Required OSNR threshold line
        if required_osnr is not None and "osnr_db" in data:
            # Calculate signal level at required OSNR margin
            avg_signal = np.mean(data["signal_dbm"])
            threshold_line = avg_signal - required_osnr
            
            fig.add_shape(
                type="line",
                x0=freq_thz.min(), x1=freq_thz.max(),
                y0=threshold_line, y1=threshold_line,
                line=dict(color="red", width=2, dash="dashdot"),
            )
            fig.add_annotation(
                x=freq_thz.max(),
                y=threshold_line,
                text=f"Required OSNR Threshold ({required_osnr:.1f} dB)",
                showarrow=False,
                yshift=10,
                font=dict(color="red", size=10),
                xanchor="right"
            )
    
    stage_title = stage.replace("_", " ").title()
    fig.update_layout(
        title=f"Power Spectrum with Noise Floors ({stage_title})",
        xaxis_title="Frequency (THz)",
        yaxis_title="Power (dBm)",
        height=400,
        legend=dict(x=0.02, y=0.02, bgcolor='rgba(255,255,255,0.8)'),
        hovermode='closest'
    )
    
    return fig


def plot_gsnr_heatmap(results: Dict[str, Any], required_osnr: Optional[float] = None) -> go.Figure:
    """Plot GSNR heatmap for multi-channel visualization."""
    c_nm_thz = 299792.458
    
    fig = go.Figure()
    
    stages = []
    stage_names = []
    
    for stage_name, stage_key in [("After Fiber", "after_fiber"), ("After Amp", "after_amplifier")]:
        if stage_key in results and results[stage_key] and "gsnr_db" in results[stage_key]:
            gsnr = results[stage_key]["gsnr_db"]
            if isinstance(gsnr, (list, np.ndarray)) and len(gsnr) > 0:
                gsnr_arr = np.asarray(gsnr, dtype=float)
                mask = np.isfinite(gsnr_arr)
                if np.any(mask):
                    stages.append(gsnr_arr)
                    stage_names.append(stage_name)
    
    if not stages:
        fig.add_annotation(text="No GSNR data available", x=0.5, y=0.5, showarrow=False)
        return fig
    
    # Ensure all stages have the same length by padding with NaN if needed
    max_len = max(len(s) for s in stages)
    stages_padded = []
    for s in stages:
        if len(s) < max_len:
            padded = np.full(max_len, np.nan)
            padded[:len(s)] = s
            stages_padded.append(padded)
        else:
            stages_padded.append(s)
    
    freq_thz = results["after_fiber"]["frequency"] * 1e-12 if "after_fiber" in results else np.arange(max_len)
    if len(freq_thz) < max_len:
        freq_thz = np.arange(max_len)
    wl_nm = c_nm_thz / freq_thz
    
    # Create heatmap data
    z_data = np.array(stages_padded, dtype=float)
    
    # Create custom hover text
    hover_text = []
    for i, stage_name in enumerate(stage_names):
        row_text = []
        for j, (f, w, g) in enumerate(zip(freq_thz, wl_nm, z_data[i])):
            row_text.append(f"{stage_name}<br>Ch: {j+1}<br>Freq: {f:.3f} THz<br>λ: {w:.2f} nm<br>GSNR: {g:.2f} dB")
        hover_text.append(row_text)
    
    fig.add_trace(go.Heatmap(
        z=z_data,
        x=freq_thz,
        y=stage_names,
        colorscale='RdYlGn',
        colorbar=dict(title="GSNR (dB)"),
        text=hover_text,
        hoverinfo='text',
        zmin=np.nanmin(z_data) if np.any(np.isfinite(z_data)) else 0,
        zmax=np.nanmax(z_data) if np.any(np.isfinite(z_data)) else 40
    ))
    
    # Add required OSNR contour line if available
    if required_osnr is not None:
        for i, stage_name in enumerate(stage_names):
            below_threshold = z_data[i] < required_osnr
            if np.any(below_threshold):
                # Mark channels below threshold
                threshold_freqs = freq_thz[below_threshold]
                for f in threshold_freqs:
                    fig.add_shape(
                        type="rect",
                        x0=f - 0.025, x1=f + 0.025,
                        y0=i - 0.4, y1=i + 0.4,
                        line=dict(color="red", width=2),
                        fillcolor="rgba(255,0,0,0.1)"
                    )
    
    fig.update_layout(
        title="GSNR Heatmap - Multi-Channel View",
        xaxis_title="Frequency (THz)",
        yaxis_title="Stage",
        height=250,
    )
    
    return fig


def plot_margin_to_threshold(results: Dict[str, Any], required_osnr: float, stage: str = "after_fiber") -> go.Figure:
    """Plot margin to required OSNR as bar chart."""
    c_nm_thz = 299792.458
    fig = go.Figure()
    
    if stage in results and "gsnr_db" in results[stage]:
        data = results[stage]
        freq_thz = data["frequency"] * 1e-12
        wl_nm = c_nm_thz / freq_thz
        gsnr = data["gsnr_db"]
        
        # Calculate margin
        margin = gsnr - required_osnr
        mask = np.isfinite(margin)
        
        if np.any(mask):
            colors = ['rgb(44, 160, 44)' if m >= 0 else 'rgb(214, 39, 40)' for m in margin[mask]]
            
            fig.add_trace(go.Bar(
                x=freq_thz[mask],
                y=margin[mask],
                marker_color=colors,
                customdata=np.column_stack([wl_nm[mask], gsnr[mask]]),
                hovertemplate="Freq: %{x:.3f} THz<br>λ: %{customdata[0]:.2f} nm<br>" +
                              "GSNR: %{customdata[1]:.2f} dB<br>Margin: %{y:.2f} dB<extra></extra>"
            ))
            
            # Add zero line (threshold)
            fig.add_hline(y=0, line_dash="dash", line_color="black", 
                         annotation_text=f"Required OSNR: {required_osnr:.1f} dB")
    
    fig.update_layout(
        title="Margin to Required OSNR",
        xaxis_title="Frequency (THz)",
        yaxis_title="Margin (dB)",
        height=300,
        showlegend=False
    )
    
    return fig


def plot_constellation_quality(results: Dict[str, Any], required_osnr: float, stage: str = "after_fiber") -> go.Figure:
    """Plot constellation quality indicator based on GSNR margin."""
    fig = go.Figure()
    
    if stage in results and "gsnr_db" in results[stage]:
        gsnr = results[stage]["gsnr_db"]
        mask = np.isfinite(gsnr)
        
        if np.any(mask):
            valid_gsnr = gsnr[mask]
            
            # Calculate effective SNR and EVM approximation
            # EVM (%) ≈ sqrt(1/SNR_linear) * 100
            snr_linear = 10 ** (valid_gsnr / 10)
            evm_percent = np.sqrt(1 / snr_linear) * 100
            
            # Quality categories
            avg_gsnr = np.mean(valid_gsnr)
            margin = avg_gsnr - required_osnr
            
            # Constellation quality score (0-100)
            quality_score = min(100, max(0, 50 + margin * 5))
            
            # Determine quality level
            if margin >= 3:
                quality = "Excellent"
                color = "rgb(44, 160, 44)"
            elif margin >= 1:
                quality = "Good"
                color = "rgb(148, 201, 84)"
            elif margin >= 0:
                quality = "Marginal"
                color = "rgb(255, 193, 37)"
            else:
                quality = "Poor"
                color = "rgb(214, 39, 40)"
            
            # Create gauge chart
            fig.add_trace(go.Indicator(
                mode="gauge+number+delta",
                value=quality_score,
                delta={'reference': 75, 'position': "bottom"},
                title={'text': f"Constellation Quality<br><span style='font-size:0.7em;color:gray'>GSNR Margin: {margin:.1f} dB</span>"},
                gauge={
                    'axis': {'range': [0, 100], 'tickwidth': 1},
                    'bar': {'color': color},
                    'steps': [
                        {'range': [0, 25], 'color': "rgba(214, 39, 40, 0.3)"},
                        {'range': [25, 50], 'color': "rgba(255, 193, 37, 0.3)"},
                        {'range': [50, 75], 'color': "rgba(148, 201, 84, 0.3)"},
                        {'range': [75, 100], 'color': "rgba(44, 160, 44, 0.3)"}
                    ],
                    'threshold': {
                        'line': {'color': "black", 'width': 2},
                        'thickness': 0.75,
                        'value': 50  # Minimum acceptable
                    }
                }
            ))
            
            # Add quality label annotation
            fig.add_annotation(
                x=0.5, y=-0.15,
                text=f"Quality: {quality} | Avg EVM: {np.mean(evm_percent):.1f}%",
                showarrow=False,
                font=dict(size=12, color=color),
                xref="paper", yref="paper"
            )
    
    fig.update_layout(height=280)
    
    return fig


def plot_delta_power(results_raman: Dict, results_no_raman: Dict) -> go.Figure:
    """Plot delta power (Raman gain = Power_raman - Power_no_raman)."""
    c_nm_thz = 299792.458
    fig = go.Figure()
    
    if "after_fiber" in results_raman and "after_fiber" in results_no_raman:
        freq_thz = results_raman["after_fiber"]["frequency"] * 1e-12
        wl_nm = c_nm_thz / freq_thz
        
        power_raman = results_raman["after_fiber"]["signal_dbm"]
        power_no_raman = results_no_raman["after_fiber"]["signal_dbm"]
        
        delta_power = power_raman - power_no_raman
        
        # Color by sign
        colors = ['rgb(44, 160, 44)' if d >= 0 else 'rgb(214, 39, 40)' for d in delta_power]
        
        fig.add_trace(go.Bar(
            x=freq_thz,
            y=delta_power,
            marker_color=colors,
            name='Raman Gain',
            customdata=np.column_stack([wl_nm, power_raman, power_no_raman]),
            hovertemplate="Freq: %{x:.3f} THz<br>λ: %{customdata[0]:.2f} nm<br>" +
                          "Raman: %{customdata[1]:.2f} dBm<br>" +
                          "No Raman: %{customdata[2]:.2f} dBm<br>" +
                          "Δ: %{y:.2f} dB<extra></extra>"
        ))
        
        # Add zero reference line
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        
        # Add trendline to show tilt
        if len(freq_thz) > 2:
            z = np.polyfit(freq_thz, delta_power, 1)
            p = np.poly1d(z)
            fig.add_trace(go.Scatter(
                x=freq_thz,
                y=p(freq_thz),
                mode='lines',
                name=f'Tilt Trend ({z[0]:.2f} dB/THz)',
                line=dict(color='black', width=2, dash='dot')
            ))
    
    fig.update_layout(
        title="Raman Gain (ΔPower = Raman - No Raman)",
        xaxis_title="Frequency (THz)",
        yaxis_title="ΔPower (dB)",
        height=350,
        legend=dict(x=0.02, y=0.98)
    )
    
    return fig


def plot_tilt_visualization(results_raman: Dict, results_no_raman: Dict) -> go.Figure:
    """Plot tilt visualization across the band."""
    c_nm_thz = 299792.458
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Power Profile", "GSNR Profile"))
    
    for results, name, color in [
        (results_raman, "With Raman", "rgb(31, 119, 180)"),
        (results_no_raman, "Without Raman", "rgb(255, 127, 14)")
    ]:
        if "after_fiber" in results:
            freq_thz = results["after_fiber"]["frequency"] * 1e-12
            signal_dbm = results["after_fiber"]["signal_dbm"]
            
            # Power profile with tilt line
            fig.add_trace(go.Scatter(
                x=freq_thz,
                y=signal_dbm,
                mode='markers',
                name=name,
                marker=dict(size=4, color=color),
                legendgroup=name
            ), row=1, col=1)
            
            # Add linear fit for tilt
            if len(freq_thz) > 2:
                z = np.polyfit(freq_thz, signal_dbm, 1)
                p = np.poly1d(z)
                tilt_db_thz = z[0]
                fig.add_trace(go.Scatter(
                    x=freq_thz,
                    y=p(freq_thz),
                    mode='lines',
                    name=f'{name} Tilt: {tilt_db_thz:.2f} dB/THz',
                    line=dict(color=color, width=2, dash='dash'),
                    legendgroup=name,
                    showlegend=False
                ), row=1, col=1)
            
            # GSNR profile
            if "gsnr_db" in results["after_fiber"]:
                gsnr = results["after_fiber"]["gsnr_db"]
                mask = np.isfinite(gsnr)
                if np.any(mask):
                    fig.add_trace(go.Scatter(
                        x=freq_thz[mask],
                        y=gsnr[mask],
                        mode='markers',
                        marker=dict(size=4, color=color),
                        legendgroup=name,
                        showlegend=False
                    ), row=1, col=2)
                    
                    # GSNR tilt
                    if np.sum(mask) > 2:
                        z_gsnr = np.polyfit(freq_thz[mask], gsnr[mask], 1)
                        p_gsnr = np.poly1d(z_gsnr)
                        fig.add_trace(go.Scatter(
                            x=freq_thz[mask],
                            y=p_gsnr(freq_thz[mask]),
                            mode='lines',
                            line=dict(color=color, width=2, dash='dash'),
                            legendgroup=name,
                            showlegend=False
                        ), row=1, col=2)
    
    fig.update_xaxes(title_text="Frequency (THz)", row=1, col=1)
    fig.update_xaxes(title_text="Frequency (THz)", row=1, col=2)
    fig.update_yaxes(title_text="Power (dBm)", row=1, col=1)
    fig.update_yaxes(title_text="GSNR (dB)", row=1, col=2)
    
    fig.update_layout(height=350, showlegend=True)
    
    return fig


def compute_statistics(data: np.ndarray) -> Dict[str, float]:
    """Compute statistics for an array."""
    valid = data[np.isfinite(data)]
    if len(valid) == 0:
        return {"min": np.nan, "max": np.nan, "mean": np.nan, "std": np.nan, "range": np.nan}
    return {
        "min": float(np.min(valid)),
        "max": float(np.max(valid)),
        "mean": float(np.mean(valid)),
        "std": float(np.std(valid)),
        "range": float(np.max(valid) - np.min(valid))
    }


# -----------------------------------------------------------------------------
# Power Sweep Functions
# -----------------------------------------------------------------------------

def run_power_sweep(
    fiber_config: Dict[str, Any],
    fiber_length: float,
    spectrum_config: Dict[str, Any],
    use_raman: bool,
    sim_params: Dict[str, Any],
    amplifier_config: Optional[Dict[str, Any]],
    amp_gain_db: Optional[float],
    power_min: float,
    power_max: float,
    power_step: float = 1.0,
    tx_osnr: float = 40.0
) -> Dict[str, Any]:
    """Run power sweep simulation across a range of input powers."""
    
    power_levels = np.arange(power_min, power_max + power_step/2, power_step)
    
    sweep_results = {
        "power_levels": power_levels.tolist(),
        "after_fiber": {
            "gsnr_mean": [], "gsnr_min": [], "gsnr_max": [],
            "power_mean": [], "osnr_mean": [], "snr_nl_mean": [],
        },
        "after_amplifier": {
            "gsnr_mean": [], "gsnr_min": [], "gsnr_max": [],
            "power_mean": [], "osnr_mean": [], "snr_nl_mean": [],
        }
    }
    
    for power_dbm in power_levels:
        # Create spectrum for this power level
        if spectrum_config.get("method") == "parameters":
            spectrum = create_spectrum_from_params(
                f_min=spectrum_config["f_min"],
                f_max=spectrum_config["f_max"],
                spacing=spectrum_config["spacing"],
                baud_rate=spectrum_config["baud_rate"],
                roll_off=spectrum_config["roll_off"],
                signal_power_dbm=power_dbm,
                tx_osnr=tx_osnr
            )
        else:
            spectrum = load_spectrum_from_file(
                Path(spectrum_config["file_path"]),
                signal_power_dbm=power_dbm,
                tx_osnr=tx_osnr
            )
        
        # Run simulation
        results = run_single_span_simulation(
            fiber_config=fiber_config,
            fiber_length=fiber_length,
            spectrum=spectrum,
            use_raman=use_raman,
            sim_params=sim_params,
            amplifier_config=amplifier_config,
            amp_gain_db=amp_gain_db
        )
        
        # Extract metrics for after_fiber
        if "after_fiber" in results and results["after_fiber"]:
            af = results["after_fiber"]
            gsnr = af.get("gsnr_db", np.array([]))
            valid_gsnr = gsnr[np.isfinite(gsnr)] if len(gsnr) > 0 else np.array([])
            
            sweep_results["after_fiber"]["gsnr_mean"].append(float(np.mean(valid_gsnr)) if len(valid_gsnr) > 0 else np.nan)
            sweep_results["after_fiber"]["gsnr_min"].append(float(np.min(valid_gsnr)) if len(valid_gsnr) > 0 else np.nan)
            sweep_results["after_fiber"]["gsnr_max"].append(float(np.max(valid_gsnr)) if len(valid_gsnr) > 0 else np.nan)
            sweep_results["after_fiber"]["power_mean"].append(float(np.mean(af["signal_dbm"])))
            
            osnr = af.get("osnr_db", np.array([]))
            valid_osnr = osnr[np.isfinite(osnr)] if len(osnr) > 0 else np.array([])
            sweep_results["after_fiber"]["osnr_mean"].append(float(np.mean(valid_osnr)) if len(valid_osnr) > 0 else np.nan)
            
            snr_nl = af.get("snr_nl_db", np.array([]))
            valid_snr_nl = snr_nl[np.isfinite(snr_nl)] if len(snr_nl) > 0 else np.array([])
            sweep_results["after_fiber"]["snr_nl_mean"].append(float(np.mean(valid_snr_nl)) if len(valid_snr_nl) > 0 else np.nan)
        else:
            for k in sweep_results["after_fiber"]:
                sweep_results["after_fiber"][k].append(np.nan)
        
        # Extract metrics for after_amplifier
        if "after_amplifier" in results and results["after_amplifier"]:
            aa = results["after_amplifier"]
            gsnr = aa.get("gsnr_db", np.array([]))
            valid_gsnr = gsnr[np.isfinite(gsnr)] if len(gsnr) > 0 else np.array([])
            
            sweep_results["after_amplifier"]["gsnr_mean"].append(float(np.mean(valid_gsnr)) if len(valid_gsnr) > 0 else np.nan)
            sweep_results["after_amplifier"]["gsnr_min"].append(float(np.min(valid_gsnr)) if len(valid_gsnr) > 0 else np.nan)
            sweep_results["after_amplifier"]["gsnr_max"].append(float(np.max(valid_gsnr)) if len(valid_gsnr) > 0 else np.nan)
            sweep_results["after_amplifier"]["power_mean"].append(float(np.mean(aa["signal_dbm"])))
            
            osnr = aa.get("osnr_db", np.array([]))
            valid_osnr = osnr[np.isfinite(osnr)] if len(osnr) > 0 else np.array([])
            sweep_results["after_amplifier"]["osnr_mean"].append(float(np.mean(valid_osnr)) if len(valid_osnr) > 0 else np.nan)
            
            snr_nl = aa.get("snr_nl_db", np.array([]))
            valid_snr_nl = snr_nl[np.isfinite(snr_nl)] if len(snr_nl) > 0 else np.array([])
            sweep_results["after_amplifier"]["snr_nl_mean"].append(float(np.mean(valid_snr_nl)) if len(valid_snr_nl) > 0 else np.nan)
        else:
            for k in sweep_results["after_amplifier"]:
                sweep_results["after_amplifier"][k].append(np.nan)
    
    return sweep_results


def plot_power_sweep(sweep_results: Dict[str, Any], required_osnr: float) -> go.Figure:
    """Plot power sweep results showing GSNR vs input power."""
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("GSNR vs Input Power", "SNR Components vs Input Power"),
        horizontal_spacing=0.12
    )
    
    power_levels = sweep_results["power_levels"]
    fiber_color = 'rgb(31, 119, 180)'
    amp_color = 'rgb(255, 127, 14)'
    
    # Left plot: GSNR with min/max bands
    # After Fiber
    gsnr_mean_fiber = sweep_results["after_fiber"]["gsnr_mean"]
    gsnr_min_fiber = sweep_results["after_fiber"]["gsnr_min"]
    gsnr_max_fiber = sweep_results["after_fiber"]["gsnr_max"]
    
    if any(np.isfinite(g) for g in gsnr_mean_fiber):
        # Fill band
        fig.add_trace(go.Scatter(
            x=list(power_levels) + list(power_levels)[::-1],
            y=list(gsnr_max_fiber) + list(gsnr_min_fiber)[::-1],
            fill='toself',
            fillcolor='rgba(31, 119, 180, 0.2)',
            line=dict(color='rgba(255,255,255,0)'),
            name='Fiber (min-max)',
            showlegend=False,
            hoverinfo='skip'
        ), row=1, col=1)
        
        # Mean line
        fig.add_trace(go.Scatter(
            x=power_levels,
            y=gsnr_mean_fiber,
            mode='lines+markers',
            name='After Fiber',
            line=dict(color=fiber_color, width=2),
            marker=dict(size=8),
            hovertemplate="Pin: %{x:.1f} dBm<br>GSNR: %{y:.2f} dB<extra>After Fiber</extra>"
        ), row=1, col=1)
    
    # After Amplifier
    gsnr_mean_amp = sweep_results["after_amplifier"]["gsnr_mean"]
    gsnr_min_amp = sweep_results["after_amplifier"]["gsnr_min"]
    gsnr_max_amp = sweep_results["after_amplifier"]["gsnr_max"]
    
    if any(np.isfinite(g) for g in gsnr_mean_amp if g is not None):
        # Fill band
        fig.add_trace(go.Scatter(
            x=list(power_levels) + list(power_levels)[::-1],
            y=list(gsnr_max_amp) + list(gsnr_min_amp)[::-1],
            fill='toself',
            fillcolor='rgba(255, 127, 14, 0.2)',
            line=dict(color='rgba(255,255,255,0)'),
            name='Amp (min-max)',
            showlegend=False,
            hoverinfo='skip'
        ), row=1, col=1)
        
        # Mean line
        fig.add_trace(go.Scatter(
            x=power_levels,
            y=gsnr_mean_amp,
            mode='lines+markers',
            name='After Amplifier',
            line=dict(color=amp_color, width=2),
            marker=dict(size=8),
            hovertemplate="Pin: %{x:.1f} dBm<br>GSNR: %{y:.2f} dB<extra>After Amp</extra>"
        ), row=1, col=1)
    
    # Required OSNR threshold
    fig.add_hline(y=required_osnr, line_dash="dash", line_color="red",
                  annotation_text=f"Required: {required_osnr:.1f} dB", row=1, col=1)
    
    # Right plot: SNR components
    osnr_fiber = sweep_results["after_fiber"]["osnr_mean"]
    snr_nl_fiber = sweep_results["after_fiber"]["snr_nl_mean"]
    
    if any(np.isfinite(g) for g in osnr_fiber):
        fig.add_trace(go.Scatter(
            x=power_levels,
            y=osnr_fiber,
            mode='lines+markers',
            name='OSNR (Fiber)',
            line=dict(color=fiber_color, dash='dot'),
            marker=dict(size=6, symbol='circle-open'),
            hovertemplate="Pin: %{x:.1f} dBm<br>OSNR: %{y:.2f} dB<extra></extra>"
        ), row=1, col=2)
    
    if any(np.isfinite(g) for g in snr_nl_fiber):
        fig.add_trace(go.Scatter(
            x=power_levels,
            y=snr_nl_fiber,
            mode='lines+markers',
            name='SNR_NL (Fiber)',
            line=dict(color=fiber_color, dash='dash'),
            marker=dict(size=6, symbol='triangle-up'),
            hovertemplate="Pin: %{x:.1f} dBm<br>SNR_NL: %{y:.2f} dB<extra></extra>"
        ), row=1, col=2)
    
    if any(np.isfinite(g) for g in gsnr_mean_fiber):
        fig.add_trace(go.Scatter(
            x=power_levels,
            y=gsnr_mean_fiber,
            mode='lines+markers',
            name='GSNR (Fiber)',
            line=dict(color=fiber_color, width=2),
            marker=dict(size=8),
            hovertemplate="Pin: %{x:.1f} dBm<br>GSNR: %{y:.2f} dB<extra></extra>"
        ), row=1, col=2)
    
    fig.update_xaxes(title_text="Input Power (dBm)", row=1, col=1)
    fig.update_xaxes(title_text="Input Power (dBm)", row=1, col=2)
    fig.update_yaxes(title_text="GSNR (dB)", row=1, col=1)
    fig.update_yaxes(title_text="SNR (dB)", row=1, col=2)
    
    fig.update_layout(
        height=400,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
    )
    
    return fig


def plot_power_sweep_output(sweep_results: Dict[str, Any]) -> go.Figure:
    """Plot output power vs input power for power sweep."""
    fig = go.Figure()
    
    power_levels = sweep_results["power_levels"]
    
    # After Fiber
    power_out_fiber = sweep_results["after_fiber"]["power_mean"]
    if any(np.isfinite(p) for p in power_out_fiber):
        fig.add_trace(go.Scatter(
            x=power_levels,
            y=power_out_fiber,
            mode='lines+markers',
            name='After Fiber',
            line=dict(color='rgb(31, 119, 180)', width=2),
            marker=dict(size=8),
            hovertemplate="Pin: %{x:.1f} dBm<br>Pout: %{y:.2f} dBm<extra>After Fiber</extra>"
        ))
    
    # After Amplifier
    power_out_amp = sweep_results["after_amplifier"]["power_mean"]
    if any(np.isfinite(p) for p in power_out_amp if p is not None):
        fig.add_trace(go.Scatter(
            x=power_levels,
            y=power_out_amp,
            mode='lines+markers',
            name='After Amplifier',
            line=dict(color='rgb(255, 127, 14)', width=2),
            marker=dict(size=8),
            hovertemplate="Pin: %{x:.1f} dBm<br>Pout: %{y:.2f} dBm<extra>After Amp</extra>"
        ))
    
    # Reference line (unity gain)
    fig.add_trace(go.Scatter(
        x=power_levels,
        y=power_levels,
        mode='lines',
        name='Unity (Reference)',
        line=dict(color='gray', dash='dash', width=1),
        hoverinfo='skip'
    ))
    
    fig.update_layout(
        title="Output Power vs Input Power",
        xaxis_title="Input Power (dBm)",
        yaxis_title="Output Power (dBm)",
        height=350,
        showlegend=True
    )
    
    return fig


# -----------------------------------------------------------------------------
# Streamlit UI
# -----------------------------------------------------------------------------

st.title("🔬 GNPy Single Span Transmission Simulator")

st.markdown("""
This tool simulates single-span optical transmission using GNPy.
Select components and configure simulation parameters below.
""")

# =============================================================================
# SECTION 1: Component Selection
# =============================================================================
st.header("⚙️ Component Selection")

col_comp1, col_comp2, col_comp3, col_comp4, col_comp5 = st.columns(5)

# ----- Transceiver Selection -----
with col_comp1:
    st.subheader("📡 Transceiver")
    transceivers = get_transceivers()
    if transceivers:
        selected_transceiver = st.selectbox(
            "Select Transceiver",
            options=transceivers,
            index=transceivers.index("400ZR+") if "400ZR+" in transceivers else 0,
            key="trx_select"
        )
        
        # Load transceiver to get modes
        try:
            trx_config = load_component_json(TRANSCEIVERS_DIR, selected_transceiver)
            modes = trx_config.get("mode", [])
            mode_names = [m.get("format", f"Mode {i}") for i, m in enumerate(modes)]
            if mode_names:
                selected_mode = st.selectbox("Select Mode", options=mode_names, key="mode_select")
                selected_mode_idx = mode_names.index(selected_mode)
                mode_config = modes[selected_mode_idx]
                
                st.caption(f"Baud: {mode_config.get('baud_rate', 0)/1e9:.1f} GBd")
                st.caption(f"Rate: {mode_config.get('bit_rate', 0)/1e9:.1f} Gb/s")
                st.caption(f"OSNR: {mode_config.get('OSNR', 0):.1f} dB")
                st.caption(f"Spacing: {mode_config.get('min_spacing', 0)/1e9:.1f} GHz")
                st.caption(f"Roll-off: {mode_config.get('roll_off', 0):.2f}")
            else:
                selected_mode = None
                mode_config = {}
            with st.expander("Full Config"):
                st.json(trx_config)
        except Exception as e:
            st.error(f"Error: {e}")
            trx_config = {}
            mode_config = {}
    else:
        st.warning("No transceivers found")
        trx_config = {}
        mode_config = {}

# ----- Spectrum Setup -----
with col_comp2:
    st.subheader("📊 Spectrum")
    
    spectrum_method = st.radio(
        "Source",
        options=["Parameters", "File"],
        horizontal=False,
        key="spectrum_method"
    )
    
    if spectrum_method == "Parameters":
        freq_bands = get_frequency_bands()
        if freq_bands:
            selected_band = st.selectbox("Band", options=freq_bands, key="band_select")
            try:
                band_config = load_component_json(FREQUENCY_RANGE_DIR, selected_band)
                if isinstance(band_config, dict):
                    variant_names = list(band_config.keys())
                    selected_variant = st.selectbox("Variant", options=variant_names, key="variant_select")
                    variant_config = band_config[selected_variant]
                    f_min = variant_config.get("f_min", 191.3e12)
                    f_max = variant_config.get("f_max", 196.1e12)
                else:
                    f_min = 191.3e12
                    f_max = 196.1e12
            except Exception:
                f_min = 191.3e12
                f_max = 196.1e12
        else:
            f_min = 191.3e12
            f_max = 196.1e12
        
        st.caption(f"f_min: {f_min / 1e12:.3f} THz")
        st.caption(f"f_max: {f_max / 1e12:.3f} THz")
        
        # Get values from transceiver mode
        baud_rate = mode_config.get("baud_rate", 64e9) if mode_config else 64e9
        spacing = mode_config.get("min_spacing", 75e9) if mode_config else 75e9
        roll_off = mode_config.get("roll_off", 0.1) if mode_config else 0.1
        
        st.caption(f"Spacing: {spacing / 1e9:.1f} GHz")
        st.caption(f"Baud: {baud_rate / 1e9:.1f} GBd")
        st.caption(f"Roll-off: {roll_off:.2f}")
        
        n_channels = int((f_max - f_min) / spacing) + 1
        st.caption(f"Channels: {n_channels}")
        
        spectrum_config = {
            "method": "parameters",
            "f_min": f_min,
            "f_max": f_max,
            "spacing": spacing,
            "baud_rate": baud_rate,
            "roll_off": roll_off
        }
    else:  # From File
        spectra_bands = get_spectra_bands()
        if spectra_bands:
            selected_spectra_band = st.selectbox("Band", options=spectra_bands, key="spectra_band")
            spectra_files = get_spectra_files(selected_spectra_band)
            if spectra_files:
                selected_spectrum_file = st.selectbox("Spectrum", options=spectra_files, key="spectrum_file")
                spectrum_file_path = INPUTS_DIR / "spectrum" / "spectra" / "fixed_grid" / selected_spectra_band / f"{selected_spectrum_file}.json"
                try:
                    spec_preview = load_json(spectrum_file_path)
                    n_channels = len(spec_preview.get("frequency", []))
                    st.caption(f"Channels: {n_channels}")
                except Exception:
                    pass
                spectrum_config = {"method": "file", "file_path": str(spectrum_file_path)}
            else:
                st.warning("No files")
                spectrum_config = {"method": None}
        else:
            st.warning("No spectrum files")
            spectrum_config = {"method": None}

# ----- Fiber Selection -----
with col_comp3:
    st.subheader("🔗 Fiber")
    fibers = get_fibers()
    if fibers:
        selected_fiber = st.selectbox(
            "Select Fiber Type",
            options=fibers,
            index=fibers.index("SSMF") if "SSMF" in fibers else 0,
            key="fiber_select"
        )
        # Load and display fiber config
        try:
            fiber_config = load_component_json(FIBERS_DIR, selected_fiber)
            st.caption(f"Loss: {fiber_config.get('loss_coef', 0)*1e3:.3f} dB/km")
            st.caption(f"D: {fiber_config.get('dispersion', 0)*1e6:.9f} ps/nm/km")
            st.caption(f"γ: {fiber_config.get('gamma', 0)*1e3:.2f} /W/km")
            st.caption(f"Aeff: {fiber_config.get('effective_area', 0)*1e12:.1f} µm²")
            with st.expander("Full Config"):
                st.json(fiber_config)
        except Exception as e:
            st.error(f"Error: {e}")
            fiber_config = {}
    else:
        st.warning("No fiber configs found")
        selected_fiber = None
        fiber_config = {}

# ----- Amplifier Selection -----
with col_comp4:
    st.subheader("📶 Amplifier")
    amplifiers = get_amplifiers()
    use_amplifier = st.checkbox("Include Amplifier", value=True, key="use_amp")
    if amplifiers and use_amplifier:
        selected_amplifier = st.selectbox(
            "Select Amplifier",
            options=amplifiers,
            index=amplifiers.index("C_amp") if "C_amp" in amplifiers else 0,
            key="amp_select"
        )
        # Load and display amplifier config
        try:
            amp_config = load_component_json(AMPLIFIERS_DIR, selected_amplifier)
            st.caption(f"Gain min: {amp_config.get('gain_min', 0):.1f} dB")
            st.caption(f"Gain max: {amp_config.get('gain_flatmax', 0):.1f} dB")
            nf_val = amp_config.get('nf0', amp_config.get('nf_min', 0))
            st.caption(f"NF: {nf_val:.1f} dB")
            st.caption(f"P out: {amp_config.get('p_max', 0):.1f} dBm")
            with st.expander("Full Config"):
                st.json(amp_config)
        except Exception as e:
            st.error(f"Error: {e}")
            amp_config = {}
    else:
        selected_amplifier = None
        amp_config = {}

# ----- Simulation Parameters -----
with col_comp5:
    st.subheader("🔧 Sim Config")
    sim_params_list = get_sim_params()
    if sim_params_list:
        selected_sim_params = st.selectbox(
            "Simulation Config",
            options=sim_params_list,
            index=sim_params_list.index("raman_gn") if "raman_gn" in sim_params_list else 0,
            key="sim_params_select"
        )
        # Load and display sim params
        try:
            sim_config = load_component_json(SIM_PARAMS_DIR, selected_sim_params)
            raman_flag = sim_config.get('raman_params', {}).get('flag', False)
            nli_method = sim_config.get('nli_params', {}).get('method', 'N/A')
            st.caption(f"Raman: {'Yes' if raman_flag else 'No'}")
            st.caption(f"NLI: {nli_method}")
            with st.expander("Full Config"):
                st.json(sim_config)
        except Exception as e:
            st.error(f"Error: {e}")
            sim_config = {}
    else:
        st.warning("No sim parameters found")
        selected_sim_params = None
        sim_config = {}

st.divider()

# =============================================================================
# SECTION 1b: Fiber Characteristics Plots
# =============================================================================
st.header("📉 Fiber Characteristics")

# Speed of light for frequency-wavelength conversion
c_nm_thz = 299792.458  # c in nm*THz

# Helper function to convert frequency (THz) to wavelength (nm)
def freq_to_wavelength(freq_thz):
    return c_nm_thz / freq_thz

if fiber_config:
    # Get band region for shading (if spectrum config exists)
    band_f_min_thz = spectrum_config.get("f_min", 191.3e12) * 1e-12 if spectrum_config.get("method") == "parameters" else None
    band_f_max_thz = spectrum_config.get("f_max", 196.1e12) * 1e-12 if spectrum_config.get("method") == "parameters" else None
    
    col_plot1, col_plot2 = st.columns(2)
    
    with col_plot1:
        # Plot Loss Coefficient vs Frequency
        fig_loss = go.Figure()
        
        # Add band region shading first (so it's behind the data)
        if band_f_min_thz and band_f_max_thz:
            fig_loss.add_vrect(
                x0=band_f_min_thz, x1=band_f_max_thz,
                fillcolor="rgba(0, 255, 0, 0.15)", layer="below",
                line_width=0, annotation_text="Band", annotation_position="top left"
            )
        
        # Regular fiber data
        if "Regular" in fiber_config:
            reg_params = fiber_config["Regular"].get("params", {})
            loss_data = reg_params.get("loss_coef", {})
            if isinstance(loss_data, dict) and "frequency" in loss_data and "value" in loss_data:
                freq_thz = np.array(loss_data["frequency"]) * 1e-12
                loss_values = np.array(loss_data["value"])
                fig_loss.add_trace(go.Scatter(
                    x=freq_thz, y=loss_values,
                    mode='lines', name='Regular',
                    line=dict(color='blue', width=2)
                ))
        
        # Extended fiber data
        if "Extended" in fiber_config:
            ext_params = fiber_config["Extended"].get("params", {})
            loss_data = ext_params.get("loss_coef", {})
            if isinstance(loss_data, dict) and "frequency" in loss_data and "value" in loss_data:
                freq_thz = np.array(loss_data["frequency"]) * 1e-12
                loss_values = np.array(loss_data["value"])
                fig_loss.add_trace(go.Scatter(
                    x=freq_thz, y=loss_values,
                    mode='lines', name='Extended',
                    line=dict(color='orange', dash='dot')
                ))
        
        # Create wavelength tick values for secondary axis
        freq_ticks = [185, 190, 195, 200, 205, 210]
        wl_ticks = [freq_to_wavelength(f) for f in freq_ticks]
        
        fig_loss.update_layout(
            title="Loss Coefficient vs Frequency",
            xaxis=dict(
                title="Frequency (THz)",
                side="bottom"
            ),
            xaxis2=dict(
                title="Wavelength (nm)",
                overlaying="x",
                side="top",
                tickvals=freq_ticks,
                ticktext=[f"{wl:.1f}" for wl in wl_ticks],
                range=[fig_loss.layout.xaxis.range[0] if fig_loss.layout.xaxis.range else 180, 
                       fig_loss.layout.xaxis.range[1] if fig_loss.layout.xaxis.range else 212]
            ),
            yaxis_title="Loss Coefficient (dB/km)",
            legend=dict(x=0.02, y=0.85),
            height=380,
            margin=dict(l=60, r=20, t=60, b=40)
        )
        st.plotly_chart(fig_loss, use_container_width=True)
    
    with col_plot2:
        # Plot Raman Coefficient vs Frequency Offset
        fig_raman = go.Figure()
        
        # Regular fiber data
        if "Regular" in fiber_config:
            reg_params = fiber_config["Regular"].get("params", {})
            raman_data = reg_params.get("raman_coefficient", {})
            if raman_data and "frequency_offset" in raman_data and "g0" in raman_data:
                ref_freq = raman_data.get("reference_frequency", 0)
                freq_offset_thz = np.array(raman_data["frequency_offset"]) * 1e-12
                g0_values = np.array(raman_data["g0"])
                fig_raman.add_trace(go.Scatter(
                    x=freq_offset_thz, y=g0_values,
                    mode='lines', name=f'Regular (ref: {ref_freq*1e-12:.1f} THz)',
                    line=dict(color='blue', width=2)
                ))
        
        # Extended fiber data
        if "Extended" in fiber_config:
            ext_params = fiber_config["Extended"].get("params", {})
            raman_data = ext_params.get("raman_coefficient", {})
            if raman_data and "frequency_offset" in raman_data and "g0" in raman_data:
                ref_freq = raman_data.get("reference_frequency", 0)
                freq_offset_thz = np.array(raman_data["frequency_offset"]) * 1e-12
                g0_values = np.array(raman_data["g0"])
                fig_raman.add_trace(go.Scatter(
                    x=freq_offset_thz, y=g0_values,
                    mode='lines', name=f'Extended (ref: {ref_freq*1e-12:.1f} THz)',
                    line=dict(color='orange', dash='dot')
                ))
        
        fig_raman.update_layout(
            title="Raman Coefficient vs Frequency Offset",
            xaxis_title="Frequency Offset (THz)",
            yaxis_title="Raman Gain (g₀) [1/W/m]",
            legend=dict(x=0.02, y=0.98),
            height=380,
            margin=dict(l=60, r=20, t=60, b=40)
        )
        st.plotly_chart(fig_raman, use_container_width=True)
    
    # Plot Channel Allocation based on spectrum parameters
    if spectrum_config.get("method") == "parameters":
        st.subheader("📡 Channel Allocation")
        
        fig_channels = go.Figure()
        
        # Get spectrum parameters
        ch_f_min = spectrum_config.get("f_min", 191.3e12)
        ch_f_max = spectrum_config.get("f_max", 196.1e12)
        ch_spacing = spectrum_config.get("spacing", 75e9)
        ch_baud = spectrum_config.get("baud_rate", 64e9)
        ch_roll_off = spectrum_config.get("roll_off", 0.1)
        
        # Calculate channel frequencies
        channel_freqs = np.arange(ch_f_min, ch_f_max + ch_spacing/2, ch_spacing)
        n_ch = len(channel_freqs)
        
        # Calculate channel bandwidth (signal bandwidth considering roll-off)
        signal_bw = ch_baud * (1 + ch_roll_off)
        
        # Plot each channel as a filled region
        for i, center_freq in enumerate(channel_freqs):
            freq_start = (center_freq - signal_bw/2) * 1e-12
            freq_end = (center_freq + signal_bw/2) * 1e-12
            center_thz = center_freq * 1e-12
            
            # Channel signal bandwidth (filled)
            fig_channels.add_trace(go.Scatter(
                x=[freq_start, freq_start, freq_end, freq_end, freq_start],
                y=[0, 1, 1, 0, 0],
                fill='toself',
                fillcolor='rgba(0, 100, 255, 0.4)',
                line=dict(color='blue', width=1),
                name=f'Ch {i+1}' if i < 5 else None,
                showlegend=(i < 5),
                hovertemplate=f'Ch {i+1}<br>Center: {center_thz:.4f} THz<br>BW: {signal_bw*1e-9:.1f} GHz<extra></extra>'
            ))
            
            # Channel slot boundary (spacing)
            slot_start = (center_freq - ch_spacing/2) * 1e-12
            slot_end = (center_freq + ch_spacing/2) * 1e-12
            fig_channels.add_trace(go.Scatter(
                x=[slot_start, slot_start, slot_end, slot_end],
                y=[0, 1.1, 1.1, 0],
                mode='lines',
                line=dict(color='gray', width=0.5, dash='dot'),
                showlegend=False,
                hoverinfo='skip'
            ))
        
        # Add frequency range markers
        fig_channels.add_vline(x=ch_f_min * 1e-12, line=dict(color='red', width=2), annotation_text="f_min")
        fig_channels.add_vline(x=ch_f_max * 1e-12, line=dict(color='red', width=2), annotation_text="f_max")
        
        # Key frequency points to highlight (in THz)
        key_freqs_thz = [184.825, 185.525, 190.325, 190.625, 191.3, 195.1, 196.1, 196.725]
        key_wls = [freq_to_wavelength(f) for f in key_freqs_thz]
        
        # Wavelength ticks for secondary axis
        freq_ticks_ch = [184, 186, 188, 190, 192, 194, 196]
        wl_ticks_ch = [freq_to_wavelength(f) for f in freq_ticks_ch]
        
        fig_channels.update_layout(
            title=f"Channel Allocation ({n_ch} channels)",
            xaxis=dict(
                title="Frequency (THz)",
                range=[183, 197],
                tickvals=key_freqs_thz,
                ticktext=[f"<b>{f:.3f}</b>" for f in key_freqs_thz],
                tickfont=dict(size=9)
            ),
            xaxis2=dict(
                title="Wavelength (nm)",
                overlaying="x",
                side="top",
                tickvals=key_freqs_thz,
                ticktext=[f"<b>{wl:.1f}</b>" for wl in key_wls],
                tickfont=dict(size=9),
                range=[183, 197]
            ),
            yaxis_title="",
            yaxis=dict(showticklabels=False, range=[0, 1.3]),
            height=350,
            margin=dict(l=60, r=20, t=40, b=40),
            annotations=[
                dict(x=0.5, y=1.25, xref='paper', yref='y', showarrow=False,
                     text=f"Spacing: {ch_spacing*1e-9:.1f} GHz | Baud: {ch_baud*1e-9:.1f} GBd | Roll-off: {ch_roll_off:.2f} | Signal BW: {signal_bw*1e-9:.1f} GHz",
                     font=dict(size=10))
            ]
        )
        st.plotly_chart(fig_channels, use_container_width=True)
else:
    st.info("Select a fiber to view its characteristics.")

st.divider()

# =============================================================================
# SECTION 2: Configuration
# =============================================================================
st.header("📝 Configuration")

col_cfg1, col_cfg2, col_cfg3 = st.columns(3)

with col_cfg1:
    st.subheader("Fiber Parameters")
    fiber_length = st.number_input(
        "Fiber Length (km)",
        min_value=1.0,
        max_value=500.0,
        value=80.0,
        step=1.0,
        key="fiber_length"
    )
    
    use_raman = st.checkbox("Enable Raman Scattering", value=False, key="use_raman")

with col_cfg2:
    st.subheader("Amplifier Parameters")
    if use_amplifier and selected_amplifier:
        amp_gain = st.number_input(
            "Amplifier Gain (dB)",
            min_value=0.0,
            max_value=40.0,
            value=16.0,
            step=0.5,
            key="amp_gain"
        )
    else:
        amp_gain = 0.0

with col_cfg3:
    st.subheader("Signal Parameters")
    signal_power_dbm = st.number_input(
        "Launch Power (dBm)",
        min_value=-10.0,
        max_value=10.0,
        value=1.0,
        step=0.5,
        key="signal_power"
    )
    
    tx_osnr = st.number_input(
        "TX OSNR (dB)",
        min_value=20.0,
        max_value=50.0,
        value=40.0,
        step=1.0,
        key="tx_osnr"
    )

st.divider()

# =============================================================================
# SECTION 3: Results
# =============================================================================
st.header("📈 Results")

if st.button("▶️ Run Simulation", type="primary", use_container_width=True, key="run_sim"):
    with st.spinner("Running simulation..."):
        try:
            # Load simulation parameters
            if selected_sim_params:
                sim_params = load_component_json(SIM_PARAMS_DIR, selected_sim_params)
            else:
                sim_params = {"raman_params": {"flag": False}, "nli_params": {"method": "gn_model_analytic"}}
            
            # Create spectrum
            if spectrum_config.get("method") == "parameters":
                spectrum = create_spectrum_from_params(
                    f_min=spectrum_config["f_min"],
                    f_max=spectrum_config["f_max"],
                    spacing=spectrum_config["spacing"],
                    baud_rate=spectrum_config["baud_rate"],
                    roll_off=spectrum_config["roll_off"],
                    signal_power_dbm=signal_power_dbm,
                    tx_osnr=tx_osnr
                )
            elif spectrum_config.get("method") == "file" and spectrum_config.get("file_path"):
                spectrum = load_spectrum_from_file(
                    Path(spectrum_config["file_path"]),
                    signal_power_dbm=signal_power_dbm,
                    tx_osnr=tx_osnr
                )
            else:
                st.error("Please configure spectrum first")
                st.stop()
            
            # Run simulation
            results = run_single_span_simulation(
                fiber_config=fiber_config,
                fiber_length=fiber_length,
                spectrum=spectrum,
                use_raman=use_raman,
                sim_params=sim_params,
                amplifier_config=amp_config if use_amplifier else None,
                amp_gain_db=amp_gain if use_amplifier else None
            )
            
            st.session_state.simulation_results = results
            st.success("Simulation completed!")
            
        except Exception as e:
            st.error(f"Simulation error: {e}")
            import traceback
            st.code(traceback.format_exc())

# Display results if available
if "simulation_results" in st.session_state and st.session_state.simulation_results:
    results = st.session_state.simulation_results
    with st.expander("Raw Results Data (JSON)"):
        st.json(results)
    
    # Get required OSNR from transceiver mode
    required_osnr = mode_config.get("OSNR", 24.0) if mode_config else 24.0
    
    # Summary metrics
    col_res1, col_res2, col_res3, col_res4 = st.columns(4)
    
    with col_res1:
        if "input" in results:
            avg_input = np.mean(results["input"]["signal_dbm"])
            st.metric("Input Power (avg)", f"{avg_input:.2f} dBm")
    
    with col_res2:
        if "after_fiber" in results:
            avg_after_fiber = np.mean(results["after_fiber"]["signal_dbm"])
            st.metric("After Fiber (avg)", f"{avg_after_fiber:.2f} dBm")
    
    with col_res3:
        if "after_fiber" in results and "gsnr_db" in results["after_fiber"]:
            gsnr = results["after_fiber"]["gsnr_db"]
            valid_gsnr = gsnr[np.isfinite(gsnr)]
            if len(valid_gsnr) > 0:
                avg_gsnr = np.mean(valid_gsnr)
                margin = avg_gsnr - required_osnr
                st.metric("GSNR after Fiber (avg)", f"{avg_gsnr:.2f} dB", delta=f"{margin:.1f} dB margin")
    
    with col_res4:
        if "after_amplifier" in results and results["after_amplifier"]:
            avg_after_amp = np.mean(results["after_amplifier"]["signal_dbm"])
            st.metric("After Amp (avg)", f"{avg_after_amp:.2f} dBm")
    
    # ----- Waterfall Plot -----
    st.subheader("🌊 Signal Evolution")
    st.plotly_chart(plot_waterfall(results), use_container_width=True)
    
    # ----- Power Spectrum with Noise Floors -----
    st.subheader("📊 Power Spectrum with Noise Floors")
    col_noise1, col_noise2 = st.columns(2)
    with col_noise1:
        st.plotly_chart(
            plot_power_with_noise(results, "after_fiber", required_osnr),
            use_container_width=True
        )
    with col_noise2:
        if "after_amplifier" in results and results["after_amplifier"]:
            st.plotly_chart(
                plot_power_with_noise(results, "after_amplifier", required_osnr),
                use_container_width=True
            )
    
    # ----- GSNR Heatmap -----
    
    # ----- Margin and Quality Indicators -----
    st.subheader("📏 Margin & Quality Analysis")
    col_margin1, col_margin2 = st.columns(2)
    
    with col_margin1:
        st.plotly_chart(
            plot_margin_to_threshold(results, required_osnr, "after_fiber"),
            use_container_width=True
        )
    
    with col_margin2:
        st.plotly_chart(
            plot_constellation_quality(results, required_osnr, "after_fiber"),
            use_container_width=True
        )
    
    # ----- SNR Metrics -----
    st.subheader("📈 SNR Metrics")
    col_plot1, col_plot2 = st.columns(2)
    with col_plot1:
        st.plotly_chart(
            plot_snr_spectrum(results, "after_fiber", "SNR Metrics After Fiber"),
            use_container_width=True
        )
    with col_plot2:
        if "after_amplifier" in results and results["after_amplifier"]:
            st.plotly_chart(
                plot_snr_spectrum(results, "after_amplifier", "SNR Metrics After Amplifier"),
                use_container_width=True
            )
    
    # ----- Statistical Summary -----
    st.subheader("📊 Statistical Summary")
    
    stats_data = []
    for stage_name, stage_key in [("Input", "input"), ("After Fiber", "after_fiber"), ("After Amp", "after_amplifier")]:
        if stage_key in results and results[stage_key]:
            stage_data = results[stage_key]
            signal_stats = compute_statistics(stage_data["signal_dbm"])
            
            row = {
                "Stage": stage_name,
                "Power Min (dBm)": f"{signal_stats['min']:.2f}",
                "Power Max (dBm)": f"{signal_stats['max']:.2f}",
                "Power Avg (dBm)": f"{signal_stats['mean']:.2f}",
                "Power Std (dB)": f"{signal_stats['std']:.2f}",
                "Tilt (dB)": f"{signal_stats['range']:.2f}",
            }
            
            if "gsnr_db" in stage_data:
                gsnr_stats = compute_statistics(stage_data["gsnr_db"])
                row["GSNR Min (dB)"] = f"{gsnr_stats['min']:.2f}" if np.isfinite(gsnr_stats['min']) else "N/A"
                row["GSNR Max (dB)"] = f"{gsnr_stats['max']:.2f}" if np.isfinite(gsnr_stats['max']) else "N/A"
                row["GSNR Avg (dB)"] = f"{gsnr_stats['mean']:.2f}" if np.isfinite(gsnr_stats['mean']) else "N/A"
            
            stats_data.append(row)
    
    if stats_data:
        st.dataframe(pd.DataFrame(stats_data), use_container_width=True, hide_index=True)
    
    # Data tables
    with st.expander("📊 Detailed Data"):
        if "after_fiber" in results:
            df = pd.DataFrame({
                "Frequency (THz)": results["after_fiber"]["frequency"] * 1e-12,
                "Wavelength (nm)": 299792.458 / (results["after_fiber"]["frequency"] * 1e-12),
                "Signal (dBm)": results["after_fiber"]["signal_dbm"],
                "ASE (dBm)": results["after_fiber"].get("ase_dbm", []),
                "NLI (dBm)": results["after_fiber"].get("nli_dbm", []),
                "OSNR (dB)": results["after_fiber"].get("osnr_db", []),
                "GSNR (dB)": results["after_fiber"].get("gsnr_db", []),
            })
            st.dataframe(df, use_container_width=True)
    
    # Download results
    results_json = json.dumps({
        k: {kk: vv.tolist() if hasattr(vv, 'tolist') else vv for kk, vv in v.items()}
        for k, v in results.items()
    }, indent=2)
    st.download_button(
        "📥 Download Results (JSON)",
        data=results_json,
        file_name="simulation_results.json",
        mime="application/json",
        key="download_results"
    )

st.divider()

# =============================================================================
# SECTION 3.5: Power Sweep Analysis
# =============================================================================
st.header("📈 Power Sweep Analysis")
st.markdown("Sweep transmit power across the transceiver's operating range and analyze GSNR.")

# Get power range from transceiver
tx_min_power = trx_config.get("tx_min_out_power", -10.0) if trx_config else -10.0
tx_max_power = trx_config.get("tx_max_out_power", 10.0) if trx_config else 10.0

col_sweep1, col_sweep2, col_sweep3 = st.columns(3)
with col_sweep1:
    sweep_min = st.number_input("Min Power (dBm)", value=float(tx_min_power), step=1.0, key="sweep_min")
with col_sweep2:
    sweep_max = st.number_input("Max Power (dBm)", value=float(tx_max_power), step=1.0, key="sweep_max")
with col_sweep3:
    sweep_step = st.number_input("Step (dB)", value=1.0, min_value=0.5, max_value=5.0, step=0.5, key="sweep_step")

st.caption(f"Transceiver range: {tx_min_power:.1f} to {tx_max_power:.1f} dBm | Steps: {int((sweep_max - sweep_min) / sweep_step) + 1}")

if st.button("▶️ Run Power Sweep", type="primary", use_container_width=True, key="run_sweep"):
    with st.spinner(f"Running power sweep from {sweep_min} to {sweep_max} dBm..."):
        try:
            # Load simulation parameters
            if selected_sim_params:
                sim_params_sweep = load_component_json(SIM_PARAMS_DIR, selected_sim_params)
            else:
                sim_params_sweep = {"raman_params": {"flag": False}, "nli_params": {"method": "gn_model_analytic"}}
            
            sweep_results = run_power_sweep(
                fiber_config=fiber_config,
                fiber_length=fiber_length,
                spectrum_config=spectrum_config,
                use_raman=use_raman,
                sim_params=sim_params_sweep,
                amplifier_config=amp_config if use_amplifier else None,
                amp_gain_db=amp_gain if use_amplifier else None,
                power_min=sweep_min,
                power_max=sweep_max,
                power_step=sweep_step,
                tx_osnr=tx_osnr
            )
            st.session_state.sweep_results = sweep_results
            st.success("Power sweep completed!")
            
        except Exception as e:
            st.error(f"Sweep error: {e}")
            import traceback
            st.code(traceback.format_exc())

# Display sweep results if available
if "sweep_results" in st.session_state and st.session_state.sweep_results:
    sweep = st.session_state.sweep_results
    required_osnr_sweep = mode_config.get("OSNR", 24.0) if mode_config else 24.0
    
    # Main plots
    st.plotly_chart(plot_power_sweep(sweep, required_osnr_sweep), use_container_width=True)
    st.plotly_chart(plot_power_sweep_output(sweep), use_container_width=True)
    
    # Find optimal power point
    gsnr_vals = sweep["after_fiber"]["gsnr_mean"]
    if any(np.isfinite(g) for g in gsnr_vals):
        valid_indices = [i for i, g in enumerate(gsnr_vals) if np.isfinite(g)]
        opt_idx = max(valid_indices, key=lambda i: gsnr_vals[i])
        opt_power = sweep["power_levels"][opt_idx]
        opt_gsnr = gsnr_vals[opt_idx]
        margin = opt_gsnr - required_osnr_sweep
        
        col_opt1, col_opt2, col_opt3 = st.columns(3)
        with col_opt1:
            st.metric("Optimal Input Power", f"{opt_power:.1f} dBm")
        with col_opt2:
            st.metric("Max GSNR (After Fiber)", f"{opt_gsnr:.2f} dB")
        with col_opt3:
            st.metric("Margin to Threshold", f"{margin:.1f} dB", delta=f"{'+' if margin >= 0 else ''}{margin:.1f}")
    
    # Summary table
    with st.expander("📊 Sweep Data Table"):
        sweep_df = pd.DataFrame({
            "Pin (dBm)": sweep["power_levels"],
            "Fiber Pout (dBm)": [f"{p:.2f}" if np.isfinite(p) else "N/A" for p in sweep["after_fiber"]["power_mean"]],
            "Fiber GSNR Mean (dB)": [f"{g:.2f}" if np.isfinite(g) else "N/A" for g in sweep["after_fiber"]["gsnr_mean"]],
            "Fiber GSNR Min (dB)": [f"{g:.2f}" if np.isfinite(g) else "N/A" for g in sweep["after_fiber"]["gsnr_min"]],
            "Fiber GSNR Max (dB)": [f"{g:.2f}" if np.isfinite(g) else "N/A" for g in sweep["after_fiber"]["gsnr_max"]],
            "Fiber OSNR (dB)": [f"{g:.2f}" if np.isfinite(g) else "N/A" for g in sweep["after_fiber"]["osnr_mean"]],
            "Fiber SNR_NL (dB)": [f"{g:.2f}" if np.isfinite(g) else "N/A" for g in sweep["after_fiber"]["snr_nl_mean"]],
            "Amp Pout (dBm)": [f"{p:.2f}" if np.isfinite(p) else "N/A" for p in sweep["after_amplifier"]["power_mean"]],
            "Amp GSNR (dB)": [f"{g:.2f}" if np.isfinite(g) else "N/A" for g in sweep["after_amplifier"]["gsnr_mean"]],
        })
        st.dataframe(sweep_df, use_container_width=True, hide_index=True)
        
        # Download sweep results
        sweep_csv = sweep_df.to_csv(index=False)
        st.download_button(
            "📥 Download Sweep Results (CSV)",
            data=sweep_csv,
            file_name="power_sweep_results.csv",
            mime="text/csv",
            key="download_sweep"
        )

st.divider()

# =============================================================================
# SECTION 4: Raman Comparison
# =============================================================================
st.header("⚖️ Raman Comparison")
st.markdown("Run both simulations to compare the effect of Raman scattering.")

if st.button("▶️ Run Comparison", type="primary", use_container_width=True, key="run_compare"):
    with st.spinner("Running comparison simulations..."):
        try:
            # Load configs
            raman_sim_params = load_component_json(SIM_PARAMS_DIR, "raman_gn") if "raman_gn" in get_sim_params() else {"raman_params": {"flag": True}, "nli_params": {"method": "gn_model_analytic"}}
            no_raman_sim_params = load_component_json(SIM_PARAMS_DIR, "no_raman_gn") if "no_raman_gn" in get_sim_params() else {"raman_params": {"flag": False}, "nli_params": {"method": "gn_model_analytic"}}
            
            # Create spectrum
            if spectrum_config.get("method") == "parameters":
                spectrum_raman = create_spectrum_from_params(
                    f_min=spectrum_config["f_min"],
                    f_max=spectrum_config["f_max"],
                    spacing=spectrum_config["spacing"],
                    baud_rate=spectrum_config["baud_rate"],
                    roll_off=spectrum_config["roll_off"],
                    signal_power_dbm=signal_power_dbm,
                    tx_osnr=tx_osnr
                )
                spectrum_no_raman = create_spectrum_from_params(
                    f_min=spectrum_config["f_min"],
                    f_max=spectrum_config["f_max"],
                    spacing=spectrum_config["spacing"],
                    baud_rate=spectrum_config["baud_rate"],
                    roll_off=spectrum_config["roll_off"],
                    signal_power_dbm=signal_power_dbm,
                    tx_osnr=tx_osnr
                )
            elif spectrum_config.get("method") == "file" and spectrum_config.get("file_path"):
                spectrum_raman = load_spectrum_from_file(
                    Path(spectrum_config["file_path"]),
                    signal_power_dbm=signal_power_dbm,
                    tx_osnr=tx_osnr
                )
                spectrum_no_raman = load_spectrum_from_file(
                    Path(spectrum_config["file_path"]),
                    signal_power_dbm=signal_power_dbm,
                    tx_osnr=tx_osnr
                )
            else:
                st.error("Please configure spectrum first")
                st.stop()
            
            # Run with Raman
            results_raman = run_single_span_simulation(
                fiber_config=fiber_config,
                fiber_length=fiber_length,
                spectrum=spectrum_raman,
                use_raman=True,
                sim_params=raman_sim_params,
                amplifier_config=amp_config if use_amplifier else None,
                amp_gain_db=amp_gain if use_amplifier else None
            )
            
            # Run without Raman
            results_no_raman = run_single_span_simulation(
                fiber_config=fiber_config,
                fiber_length=fiber_length,
                spectrum=spectrum_no_raman,
                use_raman=False,
                sim_params=no_raman_sim_params,
                amplifier_config=amp_config if use_amplifier else None,
                amp_gain_db=amp_gain if use_amplifier else None
            )
            
            st.session_state.comparison_results = {
                "raman": results_raman,
                "no_raman": results_no_raman
            }
            st.success("Comparison completed!")
            
        except Exception as e:
            st.error(f"Comparison error: {e}")
            import traceback
            st.code(traceback.format_exc())

# Display comparison if available
if "comparison_results" in st.session_state and st.session_state.comparison_results:
    comp = st.session_state.comparison_results
    
    # Get required OSNR from transceiver mode
    required_osnr = mode_config.get("OSNR", 24.0) if mode_config else 24.0
    
    # Summary comparison with delta
    st.subheader("📋 Summary Comparison")
    col_cmp1, col_cmp2, col_cmp3 = st.columns(3)
    
    with col_cmp1:
        st.markdown("**With Raman**")
        if "after_fiber" in comp["raman"]:
            avg_power_raman = np.mean(comp["raman"]["after_fiber"]["signal_dbm"])
            gsnr_raman = comp["raman"]["after_fiber"].get("gsnr_db", [])
            valid_gsnr_raman = gsnr_raman[np.isfinite(gsnr_raman)] if hasattr(gsnr_raman, '__len__') else []
            avg_gsnr_raman = np.mean(valid_gsnr_raman) if len(valid_gsnr_raman) > 0 else float('inf')
            st.metric("Avg Power After Fiber", f"{avg_power_raman:.2f} dBm")
            st.metric("Avg GSNR", f"{avg_gsnr_raman:.2f} dB")
    
    with col_cmp2:
        st.markdown("**Without Raman**")
        if "after_fiber" in comp["no_raman"]:
            avg_power_no_raman = np.mean(comp["no_raman"]["after_fiber"]["signal_dbm"])
            gsnr_no_raman = comp["no_raman"]["after_fiber"].get("gsnr_db", [])
            valid_gsnr_no_raman = gsnr_no_raman[np.isfinite(gsnr_no_raman)] if hasattr(gsnr_no_raman, '__len__') else []
            avg_gsnr_no_raman = np.mean(valid_gsnr_no_raman) if len(valid_gsnr_no_raman) > 0 else float('inf')
            st.metric("Avg Power After Fiber", f"{avg_power_no_raman:.2f} dBm")
            st.metric("Avg GSNR", f"{avg_gsnr_no_raman:.2f} dB")
    
    with col_cmp3:
        st.markdown("**Delta (Raman Benefit)**")
        if "after_fiber" in comp["raman"] and "after_fiber" in comp["no_raman"]:
            delta_power = avg_power_raman - avg_power_no_raman
            delta_gsnr = avg_gsnr_raman - avg_gsnr_no_raman if np.isfinite(avg_gsnr_raman) and np.isfinite(avg_gsnr_no_raman) else 0
            st.metric("ΔPower", f"{delta_power:+.2f} dB", delta_color="normal")
            st.metric("ΔGSNR", f"{delta_gsnr:+.2f} dB", delta_color="normal")
    
    # ----- Delta Power Plot (Raman Gain) -----
    st.subheader("📊 Raman Gain Analysis")
    st.plotly_chart(
        plot_delta_power(comp["raman"], comp["no_raman"]),
        use_container_width=True
    )
    
    # ----- Tilt Visualization -----
    st.subheader("📐 Tilt Visualization")
    st.plotly_chart(
        plot_tilt_visualization(comp["raman"], comp["no_raman"]),
        use_container_width=True
    )
    
    # ----- Original Comparison Plot -----
    st.subheader("📈 Power & GSNR Comparison")
    st.plotly_chart(
        plot_comparison(comp["raman"], comp["no_raman"]),
        use_container_width=True
    )
    
    # ----- Statistical Summary -----
    st.subheader("📊 Statistical Summary")
    
    # Build comparison stats table
    stats_table = []
    
    for scenario_name, results in [("With Raman", comp["raman"]), ("Without Raman", comp["no_raman"])]:
        if "after_fiber" in results:
            signal = results["after_fiber"]["signal_dbm"]
            signal_stats = compute_statistics(signal)
            
            gsnr = results["after_fiber"].get("gsnr_db", np.array([]))
            gsnr_stats = compute_statistics(gsnr)
            
            # Calculate tilt (linear fit slope in dB/THz)
            freq_thz = results["after_fiber"]["frequency"] * 1e-12
            if len(freq_thz) > 2:
                z = np.polyfit(freq_thz, signal, 1)
                tilt_db_thz = z[0]
            else:
                tilt_db_thz = 0
            
            stats_table.append({
                "Scenario": scenario_name,
                "Power Min (dBm)": f"{signal_stats['min']:.2f}",
                "Power Max (dBm)": f"{signal_stats['max']:.2f}",
                "Power Avg (dBm)": f"{signal_stats['mean']:.2f}",
                "Power Std (dB)": f"{signal_stats['std']:.3f}",
                "Power Range (dB)": f"{signal_stats['range']:.2f}",
                "Tilt (dB/THz)": f"{tilt_db_thz:.2f}",
                "GSNR Min (dB)": f"{gsnr_stats['min']:.2f}" if np.isfinite(gsnr_stats['min']) else "N/A",
                "GSNR Max (dB)": f"{gsnr_stats['max']:.2f}" if np.isfinite(gsnr_stats['max']) else "N/A",
                "GSNR Avg (dB)": f"{gsnr_stats['mean']:.2f}" if np.isfinite(gsnr_stats['mean']) else "N/A",
                "GSNR Std (dB)": f"{gsnr_stats['std']:.3f}" if np.isfinite(gsnr_stats['std']) else "N/A",
            })
    
    # Add delta row
    if len(stats_table) == 2:
        raman_stats = stats_table[0]
        no_raman_stats = stats_table[1]
        
        def safe_delta(r_val, nr_val):
            try:
                r = float(r_val)
                nr = float(nr_val)
                return f"{r - nr:+.2f}"
            except:
                return "N/A"
        
        stats_table.append({
            "Scenario": "Δ (Raman - No Raman)",
            "Power Min (dBm)": safe_delta(raman_stats["Power Min (dBm)"], no_raman_stats["Power Min (dBm)"]),
            "Power Max (dBm)": safe_delta(raman_stats["Power Max (dBm)"], no_raman_stats["Power Max (dBm)"]),
            "Power Avg (dBm)": safe_delta(raman_stats["Power Avg (dBm)"], no_raman_stats["Power Avg (dBm)"]),
            "Power Std (dB)": safe_delta(raman_stats["Power Std (dB)"], no_raman_stats["Power Std (dB)"]),
            "Power Range (dB)": safe_delta(raman_stats["Power Range (dB)"], no_raman_stats["Power Range (dB)"]),
            "Tilt (dB/THz)": safe_delta(raman_stats["Tilt (dB/THz)"], no_raman_stats["Tilt (dB/THz)"]),
            "GSNR Min (dB)": safe_delta(raman_stats["GSNR Min (dB)"], no_raman_stats["GSNR Min (dB)"]),
            "GSNR Max (dB)": safe_delta(raman_stats["GSNR Max (dB)"], no_raman_stats["GSNR Max (dB)"]),
            "GSNR Avg (dB)": safe_delta(raman_stats["GSNR Avg (dB)"], no_raman_stats["GSNR Avg (dB)"]),
            "GSNR Std (dB)": safe_delta(raman_stats["GSNR Std (dB)"], no_raman_stats["GSNR Std (dB)"]),
        })
    
    st.dataframe(pd.DataFrame(stats_table), use_container_width=True, hide_index=True)
    
    # Per-channel delta table (expandable)
    with st.expander("📊 Per-Channel Delta Analysis"):
        if "after_fiber" in comp["raman"] and "after_fiber" in comp["no_raman"]:
            freq_thz = comp["raman"]["after_fiber"]["frequency"] * 1e-12
            wl_nm = 299792.458 / freq_thz
            
            power_raman = comp["raman"]["after_fiber"]["signal_dbm"]
            power_no_raman = comp["no_raman"]["after_fiber"]["signal_dbm"]
            delta_power = power_raman - power_no_raman
            
            gsnr_raman = comp["raman"]["after_fiber"].get("gsnr_db", np.zeros_like(power_raman))
            gsnr_no_raman = comp["no_raman"]["after_fiber"].get("gsnr_db", np.zeros_like(power_no_raman))
            delta_gsnr = gsnr_raman - gsnr_no_raman
            
            delta_df = pd.DataFrame({
                "Channel": range(1, len(freq_thz) + 1),
                "Freq (THz)": freq_thz,
                "λ (nm)": wl_nm,
                "Raman Power (dBm)": power_raman,
                "No-Raman Power (dBm)": power_no_raman,
                "ΔPower (dB)": delta_power,
                "Raman GSNR (dB)": gsnr_raman,
                "No-Raman GSNR (dB)": gsnr_no_raman,
                "ΔGSNR (dB)": delta_gsnr,
            })
            
            st.dataframe(delta_df, use_container_width=True, hide_index=True)

# Footer
st.markdown("---")
st.caption("GNPy Single Span Simulator | Built with Streamlit and GNPy")
