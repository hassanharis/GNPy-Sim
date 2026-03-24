"""
GNPy Simulator - Streamlit Web Application
A web interface for optical network path computation and simulation using GNPy
"""

import streamlit as st
import json
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import plotly.express as px
import requests
from pathlib import Path
import io
import base64
from typing import Optional, Dict, List, Tuple
import tempfile
import os
import random
import gnpy

# Import utils
from utils import gnpy_wrapper
from utils import topology as topology_utils

from gnpy.tools.json_io import load_equipment
from gnpy.topology.request import PathRequest

st.markdown(gnpy.tools.json_io.load_network(filename= Path, equipment= {
  "Edfa": [{
      "type_variety": "std_medium_gain",
      "type_def": "variable_gain",
      "gain_flatmax": 26,
      "gain_min": 15,
      "p_max": 23,
      "nf_min": 6,
      "nf_max": 10,
      "out_voa_auto": false,
      "allowed_for_design": true
    },
    {
      "type_variety": "std_low_gain",
      "type_def": "variable_gain",
      "gain_flatmax": 16,
      "gain_min": 8,
      "p_max": 23,
      "nf_min": 6.5,
      "nf_max": 11,
      "out_voa_auto": false,
      "allowed_for_design": true
      }
    ],
  "Fiber": [{
      "type_variety": "SSMF",
      "dispersion": 1.67e-05,
      "effective_area": 83e-12,
      "pmd_coef": 1.265e-15
    }
  ]
})

# Page configuration
st.set_page_config(
    page_title="GNPy Optical Network Simulator",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'equipment_data' not in st.session_state:
    st.session_state.equipment_data = None
if 'equipment_obj' not in st.session_state:
    st.session_state.equipment_obj = None
if 'topology_data' not in st.session_state:
    st.session_state.topology_data = None
if 'network_obj' not in st.session_state:
    st.session_state.network_obj = None
if 'sim_params' not in st.session_state:
    st.session_state.sim_params = None
if 'services_data' not in st.session_state:
    st.session_state.services_data = None
if 'services_obj' not in st.session_state:
    st.session_state.services_obj = None
if 'source_node' not in st.session_state:
    st.session_state.source_node = None
if 'destination_node' not in st.session_state:
    st.session_state.destination_node = None
if 'results' not in st.session_state:
    st.session_state.results = None
if 'network_graph' not in st.session_state:
    st.session_state.network_graph = None
if 'topology_generated' not in st.session_state:
    st.session_state.topology_generated = False
if 'topology_config' not in st.session_state:
    st.session_state.topology_config = {}
if 'graph_stats' not in st.session_state:
    st.session_state.graph_stats = {'nodes': 0, 'edges': 0, 'fibers_added': 0, 'fibers_missing': 0, 'missing_nodes': []}
if 'autodesign_params' not in st.session_state:
    st.session_state.autodesign_params = {
        'mode': 'none',
        'target_power': 0.0,
        'span_length': 80.0,
        'power_per_channel': 0.0,
        'num_channels': 80
    }

# Example data URLs - from GNPy official repository
EXAMPLE_EQUIPMENT_FILES = {
    "🔧 Default Equipment": "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/eqpt_config.json",
    "🔧 OpenROADM v4": "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/eqpt_config_openroadm_ver4.json",
    "🔧 OpenROADM v5": "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/eqpt_config_openroadm_ver5.json",
    "🔧 Multiband Equipment": "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/eqpt_config_multiband.json",
    "🔧 Extra Equipment": "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/extra_eqpt_config.json",
    "🔧 Juniper Booster": "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/Juniper-BoosterHG.json"
}

EXAMPLE_TOPOLOGY_FILES = {
    "🌐 Mesh Topology": "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/meshTopologyExampleV2.json",
    "🌐 CORONET CONUS": "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/CORONET_CONUS_Topology.json",
    "🌐 CORONET Global": "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/CORONET_Global_Topology.json",
    "🌐 Sweden OpenROADM v4": "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/Sweden_OpenROADMv4_example_network.json",
    "🌐 Sweden OpenROADM v5": "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/Sweden_OpenROADMv5_example_network.json",
    "🌐 EDFA Example": "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/edfa_example_network.json",
    "🌐 Fused ROADM": "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/fused_roadm_example_network.json",
    "🌐 Raman EDFA": "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/raman_edfa_example_network.json",
    "🌐 Multiband": "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/multiband_example_network.json",
    "⚙️ Generate Linear": "linear",
    "⚙️ Generate Random": "random",
    "⚙️ Generate National": "random_national"
}

EXAMPLE_SERVICES_FILES = {
    "📋 Mesh Services": "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/meshTopologyExampleV2_services.json",
    "📋 Pluggable Services": "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/service_pluggable.json"
}

EXAMPLE_SPECTRUM_FILES = {
    "📡 Spectrum 1": "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/initial_spectrum1.json",
    "📡 Spectrum 2": "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/initial_spectrum2.json",
    "📡 Multiband Spectrum": "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/multiband_spectrum.json"
}

EXAMPLE_SIM_PARAMS = {
    "⚙️ Default Simulation": "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/sim_params.json"
}


def main():
    st.title("🌐 GNPy Optical Network Simulator")
    st.markdown("---")
   
    col1, col2, col3 = st.columns([3, 4, 2])
    with col1:
        show_equipment_section()
    with col2:
        show_autodesign_section()
    with col3:
        show_topology_section_compact()


    col1, col2 = st.columns([5,2])
    # Full-width topology visualization
    with col1:
        if st.session_state.network_graph is not None and len(st.session_state.network_graph) > 0:
            st.markdown("---")
            
            # Visualization options
            viz_type = st.radio(
                "Select Visualization Type",
                ["Animated Network Graph", "Geographic Map View"],
                horizontal=True,
                help="Choose between topology graph or geographic map visualization"
            )
            
            if viz_type == "Animated Network Graph":
                visualize_network_graph()
            else:
                visualize_network_on_map()
            
            st.markdown("---")

    with col2:
        show_simulation_params_section()
        show_services_section()
        show_path_configuration_section()
        show_results_section()

def show_equipment_section():
    """Section 1: Equipment Library Upload"""
    st.subheader("1. Equipment Library")
    
    st.info("""
    Optional. For no upoaded file, the default library is used.
            An equipment file with advanced model EDFAs requires additional configuration files.
    """)
    
    col1, col2 = st.columns([ 3,2])
    example_choice = st.selectbox(
        "Choose an equipment library or upload Json:",
        ["None"] + list(EXAMPLE_EQUIPMENT_FILES.keys()) + ["Upload JSON"],
        key='equipment_example_select'
    )
    
    if example_choice != "None" and example_choice != "Upload JSON":
        st.info(f"✓ Selected: {example_choice}")
        st.markdown(f"[🔗 View on GitHub]({EXAMPLE_EQUIPMENT_FILES[example_choice]})")
        
        if st.button("Load Example Equipment File", key='load_equipment_example'):
            url = EXAMPLE_EQUIPMENT_FILES[example_choice]
            equipment_json = fetch_json_from_url(url)
            if equipment_json:
                with st.spinner("Loading equipment library..."):
                    equipment_obj = gnpy_wrapper.load_equipment_library(
                        file_content=json.dumps(equipment_json),
                        use_default=False
                    )
                    st.json(equipment_json)
                    st.json(equipment_obj)
                    if equipment_obj is None:
                        st.error("Failed to initialize equipment object.")
                    else:
                        st.session_state.equipment_data = equipment_json
                        st.session_state.equipment_obj = equipment_obj
                        st.success(f"✓ Loaded {example_choice}")
            else:
                st.error("Failed to load equipment file")
    elif example_choice == "Upload JSON":
        st.info("Please use the file uploader to upload your equipment library in JSON format.")
        uploaded_file = st.file_uploader(
            "Upload equipment library (JSON)",
            type=['json'],
            key='equipment_upload',
            help="Upload your custom equipment library file"
        )
        
        if uploaded_file is not None:
            try:
                with st.spinner("Loading equipment library..."):
                    equipment_data = json.load(uploaded_file)
                    
                    # Load into GNPy
                    equipment_obj = gnpy_wrapper.load_equipment_library(
                        file_content=json.dumps(equipment_data),
                        use_default=False
                    )
                    
                    if equipment_obj is None:
                        st.error("Failed to initialize equipment object. Check the file format.")
                    else:
                        st.session_state.equipment_data = equipment_data
                        st.session_state.equipment_obj = equipment_obj
                        st.success("✓ Equipment library loaded successfully!")
                        
                        # Show summary
                        if 'Edfa' in equipment_data:
                            st.metric("EDFAs", len(equipment_data['Edfa']))
                        if 'Fiber' in equipment_data:
                            st.metric("Fiber Types", len(equipment_data['Fiber']))
                
            except Exception as e:
                st.error(f"Error loading equipment file: {str(e)}")
    
    # Display current equipment data
    if st.session_state.equipment_data:
        with st.expander("View Current Equipment Library"):
            st.json(st.session_state.equipment_data)

def show_openroadm_section():  
    openroadm_version = st.selectbox(
        "OpenROADM version:",
        ["None", "Version 4", "Version 5"],
        help="Select OpenROADM MSA specification version"
    )
    st.info("""
    Select an OpenROADM equipment file for MSA-compliant design (ver. 4 or ver. 5).
    This will override any previously uploaded equipment library file.
    """)

    if openroadm_version != "None":
        st.warning("""
        The auto-design will select inline amplifiers (ILAs) following the low noise MSA specification.
        To use standard ILAs, save the topology and manually replace "type_variety": "low_noise" 
        with "type_variety": "standard".
        """)
        
        fiber_padding = st.number_input(
            "Fiber padding (dB):",
            min_value=0.0,
            max_value=10.0,
            value=0.0,
            step=0.1
        )


def show_autodesign_section():
    """Section 2: Network Auto-Design Parameters"""
    st.subheader("2. Auto-Design Settings")
    
    st.info("""
    Auto-design splits fiber spans, inserts EDFAs and sets the gain or output power of EDFAs based on design rules.
    EDFAs are selected from the equipment library based on required target gain and output power.
    """)
    

        
    autodesign_mode = st.radio(
        "Auto-design mode:",
        ["None (Disable)","Power Mode", "Gain Mode"],
        help="Select the mode for automatic EDFA design",
        horizontal =True
    )
    
    # Map display names to internal values
    mode_map = {
        "None (Disable)": "none",
        "Power Mode": "power",
        "Gain Mode": "gain"
    }
    st.session_state.autodesign_params['mode'] = mode_map[autodesign_mode]
    
    if autodesign_mode != "None (Disable)":
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            target_power = st.number_input(
                "Target output power (dBm):",
                min_value=-10.0,
                max_value=20.0,
                value=st.session_state.autodesign_params.get('target_power', 0.0),
                step=0.5,
                help="Target output power level for EDFAs"
            )
            st.session_state.autodesign_params['target_power'] = target_power
        
        with col2:
            span_length = st.number_input(
                "Max span length (km):",
                min_value=10.0,
                max_value=150.0,
                value=st.session_state.autodesign_params.get('span_length', 80.0),
                step=5.0,
                help="Maximum fiber span length before EDFA insertion"
            )
            st.session_state.autodesign_params['span_length'] = span_length
        with col3:
            power_per_channel = st.number_input(
                "Power per channel (dBm):",
                min_value=-10.0,
                max_value=5.0,
                value=st.session_state.autodesign_params.get('power_per_channel', 0.0),
                step=0.5
            )
            st.session_state.autodesign_params['power_per_channel'] = power_per_channel
            
        with col4:
            num_channels = st.number_input(
                "Number of channels:",
                min_value=1,
                max_value=96,
                value=st.session_state.autodesign_params.get('num_channels', 80),
                step=1
            )
            st.session_state.autodesign_params['num_channels'] = num_channels
    
   


def show_topology_section():
    """Section 3: Network Topology Upload and Visualization"""
    st.subheader("3. Network Topology")
    
    st.info("""
    Upload a network topology in JSON or Excel format, or select an example topology.
    The topology graph will be displayed after loading.
    """)
    
    st.subheader("Select Example Topology or upload your own")
    example_choice = st.selectbox(
        "Select an example topology:",
        ["None"] + list(EXAMPLE_TOPOLOGY_FILES.keys()) + ["Upload JSON, XLS, XLSX"],
        key='topology_example_select'
    )
    
    if example_choice != "None" and "Generate" not in example_choice and example_choice != "Upload JSON, XLS, XLSX":
        st.markdown(f"[📌 View on GitHub]({EXAMPLE_TOPOLOGY_FILES[example_choice]})")
        
        if st.button("Load Example Topology", key='load_example_topology_btn'):
            url = EXAMPLE_TOPOLOGY_FILES[example_choice]
            topology_json = fetch_topology_from_url(url)
            if topology_json:
                st.session_state.topology_data = topology_json
                st.session_state.topology_generated = False
                parse_topology_for_graph(topology_json)
                st.success(f"✓ Loaded {example_choice}")
            else:
                st.error("Failed to load topology")
    
    # Special configuration for generated topologies
    if "Generate" in example_choice:
        st.subheader("Topology Configuration")
        num_nodes = st.slider("Number of nodes:", 5, 50, 10, key='topo_num_nodes')
        
        if "Linear" in example_choice:
            span_length = st.slider("Span length (km):", 10, 100, 80, key='topo_span_length')
        elif "Random" in example_choice:
            density = st.slider("Network density:", 0.1, 1.0, 0.3, key='topo_density')
            
        if st.button("Generate Topology", key='generate_topology_btn'):
            generate_example_topology(example_choice, num_nodes)
            st.session_state.topology_generated = True
    elif example_choice == "Upload JSON, XLS, XLSX":
        uploaded_file = st.file_uploader(
            "Upload network topology (JSON, XLS, XLSX)",
            type=['json', 'xls', 'xlsx'],
            key='topology_upload'
        )
        
        if uploaded_file is not None:
            try:
                if uploaded_file.name.endswith('.json'):
                    topology_data = json.load(uploaded_file)
                    st.session_state.topology_data = topology_data
                    st.success("✓ Topology loaded successfully!")
                    
                    # Parse topology for visualization
                    parse_topology_for_graph(topology_data)
                else:
                    # Handle Excel files
                    df = pd.read_excel(uploaded_file)
                    st.session_state.topology_data = {"excel": df.to_dict()}
                    st.success("✓ Topology loaded from Excel!")
                    
            except Exception as e:
                st.error(f"Error loading topology: {str(e)}")
    
    # Download topology
    if st.session_state.topology_data:
        st.subheader("💾 Save Network")
        json_str = json.dumps(st.session_state.topology_data, indent=2)
        st.download_button(
            label="Download Network Topology (JSON)",
            data=json_str,
            file_name="network_topology.json",
            mime="application/json"
        )


def show_topology_section_compact():
    """Section 3 Compact: Network Topology Upload (no visualization - shown in full width later)"""
    st.subheader("3. Network Topology")
    
    
    
    
    example_choice = st.selectbox(
        "Select an example topology:",
        ["None"] + list(EXAMPLE_TOPOLOGY_FILES.keys()) + ["Upload JSON, XLS, XLSX"],
        key='topology_example_select'
    )
    
    if example_choice != "None" and "Generate" not in example_choice and example_choice != "Upload JSON, XLS, XLSX":
        if st.button("Load", key='load_example_topology_btn', use_container_width=True):
            url = EXAMPLE_TOPOLOGY_FILES[example_choice]
            topology_json = fetch_topology_from_url(url)
            if topology_json:
                with st.spinner("Loading topology..."):
                    st.session_state.topology_data = topology_json
                    st.session_state.topology_generated = False
                    
                    # Create GNPy network object if equipment exists
                    if st.session_state.equipment_obj:
                        network_obj, nodes = gnpy_wrapper.create_network_from_json(
                            topology_json,
                            st.session_state.equipment_obj
                        )
                        if network_obj is None:
                            st.warning("⚠️ Network initialization failed. Visualization available.")
                        else:
                            st.session_state.network_obj = network_obj
                    else:
                        st.warning("⚠️ Load equipment first for simulation capability")
                    
                    parse_topology_for_graph(topology_json)
                    st.success(f"✓ Loaded!")
            else:
                st.error("Failed to load")
    
    # Special configuration for generated topologies
    if "Generate" in example_choice:
        num_nodes = st.slider("Nodes:", 5, 50, 10, key='topo_num_nodes_compact')
        if st.button("Generate", key='generate_topology_btn_compact', use_container_width=True):
            generate_example_topology(example_choice, num_nodes)
            st.session_state.topology_generated = True

    elif example_choice == "Upload JSON, XLS, XLSX":
        uploaded_file = st.file_uploader(
            "Upload network topology (JSON, XLS, XLSX)",
            type=['json', 'xls', 'xlsx'],
            key='topology_upload_compact',
            help="Upload your custom network topology file"
        )
        
        if uploaded_file is not None:
            try:
                with st.spinner("Loading topology..."):
                    if uploaded_file.name.endswith('.json'):
                        topology_data = json.load(uploaded_file)
                        st.session_state.topology_data = topology_data
                        
                        # Create GNPy network object if equipment exists
                        if st.session_state.equipment_obj:
                            network_obj, nodes = gnpy_wrapper.create_network_from_json(
                                topology_data,
                                st.session_state.equipment_obj
                            )
                            if network_obj is None:
                                st.warning("⚠️ Network initialization failed. Visualization available.")
                            else:
                                st.session_state.network_obj = network_obj
                        else:
                            st.warning("⚠️ Load equipment first for simulation capability")
                        
                        parse_topology_for_graph(topology_data)
                        st.success("✓ Topology loaded successfully!")
                    else:
                        df = pd.read_excel(uploaded_file)
                        st.session_state.topology_data = {"excel": df.to_dict()}
                        st.success("✓ Topology loaded from Excel!")
                    
            except Exception as e:
                st.error(f"Error loading topology: {str(e)}")


def show_simulation_params_section():
    """Section 4: Simulation Parameters"""
    st.subheader("4. Simulation Parameters")
    
    st.info("""
    This is only relevant if the topology contains Raman fibers.
    If not uploaded, default simulation parameters will be used.
    """)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        uploaded_file = st.file_uploader(
            "Upload simulation parameters (JSON)",
            type=['json'],
            key='sim_params_upload'
        )
        
        if uploaded_file is not None:
            try:
                sim_params = json.load(uploaded_file)
                st.session_state.sim_params = sim_params
                st.success("✓ Simulation parameters loaded!")
                
                with st.expander("View Parameters"):
                    st.json(sim_params)
                    
            except Exception as e:
                st.error(f"Error loading parameters: {str(e)}")
    
    with col2:
        example_choice = st.selectbox(
            "Choose simulation parameters:",
            ["None"] + list(EXAMPLE_SIM_PARAMS.keys()),
            key='sim_params_example_select'
        )
        
        if example_choice != "None":
            st.markdown(f"[🔗 View on GitHub]({EXAMPLE_SIM_PARAMS[example_choice]})")
            
            if st.button("Load Default Simulation Parameters", key='load_sim_params_example'):
                url = EXAMPLE_SIM_PARAMS[example_choice]
                sim_params_json = fetch_json_from_url(url)
                if sim_params_json:
                    st.session_state.sim_params = sim_params_json
                    st.success(f"✓ Loaded {example_choice}")
                else:
                    st.error("Failed to load simulation parameters")


def show_services_section():
    """Section 5: Services File Upload"""
    st.subheader("5. Services Configuration")
    
    st.info("""
    Upload a services file to define specific path requests.
    When uploaded, paths will be immediately computed and simulated.
    """)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        uploaded_file = st.file_uploader(
            "Upload services file (JSON, XLS, XLSX)",
            type=['json', 'xls', 'xlsx'],
            key='services_upload'
        )
        
        if uploaded_file is not None:
            try:
                if uploaded_file.name.endswith('.json'):
                    services_data = json.load(uploaded_file)
                    st.session_state.services_data = services_data
                    st.success("✓ Services file loaded!")
                    
                    # Show services summary
                    if 'path-request' in services_data:
                        st.metric("Number of path requests", len(services_data['path-request']))
                else:
                    df = pd.read_excel(uploaded_file)
                    st.session_state.services_data = {"excel": df.to_dict()}
                    st.success("✓ Services loaded from Excel!")
                    
            except Exception as e:
                st.error(f"Error loading services: {str(e)}")
    
    with col2:
        example_choice = st.selectbox(
            "Choose example services:",
            ["None"] + list(EXAMPLE_SERVICES_FILES.keys()),
            key='services_example_select'
        )
        
        if example_choice != "None":
            st.markdown(f"[🔗 View on GitHub]({EXAMPLE_SERVICES_FILES[example_choice]})")
            
            if st.button("Load Example Services", key='load_services_example'):
                url = EXAMPLE_SERVICES_FILES[example_choice]
                services_json = fetch_json_from_url(url)
                if services_json:
                    st.session_state.services_data = services_json
                    st.success(f"✓ Loaded {example_choice}")
                else:
                    st.error("Failed to load services file")
    
    # Display services if loaded
    if st.session_state.services_data:
        with st.expander("View Services"):
            st.json(st.session_state.services_data)
        
        # Process batch services
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🚀 Process All Services (Batch Compute)", key='process_services_batch', use_container_width=True):
                if st.session_state.network_obj is None or st.session_state.equipment_obj is None:
                    st.error("❌ Please load topology and equipment first")
                else:
                    process_batch_services()
        
        with col2:
            if st.button("💾 Download Path Responses (CSV)", key='download_services_csv', use_container_width=True):
                if st.session_state.services_obj:
                    csv_data = generate_services_csv(st.session_state.services_obj)
                    st.download_button(
                        label="Download CSV",
                        data=csv_data,
                        file_name="service_responses.csv",
                        mime="text/csv"
                    )
                else:
                    st.info("Process services first to generate responses")


def show_path_configuration_section():
    """Section 6: Path Configuration"""
    st.subheader("6. Path Configuration and Computation")
    
    if not st.session_state.topology_data:
        st.warning("⚠️ Please load a network topology first (Section 3)")
        return
    
    st.subheader("Path Computation Settings")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        num_paths = st.number_input(
            "Number of paths:",
            min_value=1,
            max_value=10,
            value=1,
            help="Number of paths to compute"
        )
    
    with col2:
        compute_diverse = st.checkbox(
            "Compute diverse paths",
            help="Compute link-disjoint diverse paths"
        )
    
    with col3:
        compute_reverse = st.checkbox(
            "Compute reverse paths",
            help="Also compute paths in reverse direction"
        )
    
    st.markdown("---")
    
    # Node selection
    st.subheader("Source and Destination Selection")
    
    # Get available nodes
    nodes = get_available_nodes()
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.session_state.source_node and st.session_state.source_node in nodes:
            st.session_state.source_select = st.session_state.source_node
        source_node = st.selectbox(
            "Source node:",
            options=[""] + nodes,
            index=0,
            key='source_select'
        )
        st.session_state.source_node = source_node if source_node else None

    with col2:
        if st.session_state.destination_node and st.session_state.destination_node in nodes:
            st.session_state.dest_select = st.session_state.destination_node
        destination_node = st.selectbox(
            "Destination node:",
            options=[""] + nodes,
            index=0,
            key='dest_select'
        )
        st.session_state.destination_node = destination_node if destination_node else None
    
    # Include/Exclude nodes
    st.subheader("Path Constraints (Optional)")
    
    col1, col2 = st.columns(2)
    
    with col1:
        include_nodes = st.multiselect(
            "Include nodes (path must traverse these):",
            options=nodes
        )
    
    with col2:
        exclude_nodes = st.multiselect(
            "Exclude nodes (path must avoid these):",
            options=nodes
        )
    
    st.markdown("---")
    
    # Transceiver configuration
    st.subheader("Transceiver Configuration")
    
    col1, col2 = st.columns(2)
    
    with col1:
        transceiver_type = st.selectbox(
            "Transceiver type:",
            ["Auto", "100G", "200G", "400G", "Custom"]
        )
        
        transceiver_mode = st.selectbox(
            "Transceiver mode:",
            ["Maximize capacity", "DP-QPSK", "DP-16QAM", "DP-64QAM", "Custom"]
        )
        
        if transceiver_mode == "Maximize capacity":
            consider_penalties = st.checkbox(
                "Consider penalties (CD, PMD, PDL)",
                value=True
            )
    
    with col2:
        baudrate = st.number_input("Baudrate (Gbaud):", value=32.0, step=1.0)
        rolloff = st.number_input("Roll-off:", value=0.15, step=0.01, format="%.2f")
        tx_osnr = st.number_input("Tx OSNR (dB):", value=40.0, step=0.5)
        min_osnr = st.number_input("Min OSNR (dB):", value=15.0, step=0.5)
        system_margin = st.number_input("System margin (dB):", value=3.0, step=0.5)
    
    st.markdown("---")
    
    # Spectral Load and ROADM Parameters
    st.subheader("Spectral Load and ROADM Parameters")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        ref_power = st.number_input(
            "Reference power (dBm):",
            value=0.0,
            step=0.5,
            help="Leave empty to use equipment library default"
        )
    
    with col2:
        spacing = st.number_input(
            "Channel spacing (GHz):",
            value=50.0,
            step=12.5
        )
    
    with col3:
        roadm_loss = st.number_input(
            "ROADM loss (dB):",
            value=20.0,
            step=0.5
        )
    
    # Power Sweep
    st.subheader("Power Sweep (Optional)")
    
    enable_sweep = st.checkbox("Enable power sweep")
    
    if enable_sweep:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            sweep_start = st.number_input("Start power (dBm):", value=-3.0, step=0.5)
        with col2:
            sweep_stop = st.number_input("Stop power (dBm):", value=3.0, step=0.5)
        with col3:
            sweep_step = st.number_input("Step (dB):", value=0.5, step=0.1, format="%.1f")
    
    st.markdown("---")
    
    # Compute button
    if st.button("🚀 Compute and Simulate Paths", type="primary", use_container_width=True):
        if not st.session_state.source_node or not st.session_state.destination_node:
            st.error("❌ Please select both source and destination nodes")
        else:
            with st.spinner("Computing paths and running simulation..."):
                sweep_params = {}
                if enable_sweep:
                    sweep_params = {
                        'enable_sweep': True,
                        'sweep_start': sweep_start,
                        'sweep_stop': sweep_stop,
                        'sweep_step': sweep_step,
                    }
                
                results = compute_paths(
                    st.session_state.source_node,
                    st.session_state.destination_node,
                    num_paths=num_paths,
                    diverse=compute_diverse,
                    reverse=compute_reverse,
                    include_nodes=include_nodes,
                    exclude_nodes=exclude_nodes,
                    power=ref_power,
                    spacing=spacing,
                    min_osnr=min_osnr,
                    system_margin=system_margin,
                    **sweep_params
                )
                st.session_state.results = results
                if results:
                    st.success("✓ Computation complete! View results in Section 7.")
                else:
                    st.error("❌ Computation failed. Check the errors above.")


def show_results_section():
    """Section 7: Results Display"""
    st.subheader("7. Simulation Results")
    
    if not st.session_state.results:
        st.info("ℹ️ No results available. Please run a simulation in Section 6.")
        return
    
    results = st.session_state.results
    
    # Path selection
    st.subheader("Select Path")
    path_options = results.get('available_paths', ['Working Path'])
    selected_path = st.selectbox("Path:", path_options)
    
    # Summary results
    st.subheader("Summary Results")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Path Length", f"{results.get('path_length', 0):.1f} km")
    with col2:
        st.metric("GSNR", f"{results.get('gsnr', 0):.2f} dB")
    with col3:
        st.metric("OSNR", f"{results.get('osnr', 0):.2f} dB")
    with col4:
        st.metric("Feasibility", "✓ Feasible" if results.get('feasible', False) else "✗ Not Feasible")
    
    # Detailed metrics
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Number of Spans", results.get('num_spans', 0))
        st.metric("Total Loss", f"{results.get('total_loss', 0):.2f} dB")
        st.metric("CD", f"{results.get('cd', 0):.0f} ps/nm")
    
    with col2:
        st.metric("Number of EDFAs", results.get('num_edfas', 0))
        st.metric("PMD", f"{results.get('pmd', 0):.2f} ps")
        st.metric("PDL", f"{results.get('pdl', 0):.2f} dB")
    
    st.markdown("---")
    
    # Detail buttons
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 Detailed Path Information"):
            show_detailed_path_info(results)
    
    with col2:
        if st.button("📈 Signal & Noise Spectra"):
            show_spectra_plots(results)
    
    with col3:
        if st.button("🗺️ Path on Network Map"):
            show_path_on_map(results)
    
    # Power sweep results
    if results.get('power_sweep'):
        st.subheader("Power Sweep Results")
        show_power_sweep_plot(results['power_sweep'])
        
        # Download button
        csv_data = generate_power_sweep_csv(results['power_sweep'])
        st.download_button(
            label="💾 Download Power Sweep Data (CSV)",
            data=csv_data,
            file_name="power_sweep_results.csv",
            mime="text/csv"
        )


# Helper Functions

def fetch_json_from_url(url: str) -> Optional[Dict]:
    """Fetch JSON from GitHub URL"""
    try:
        response = requests.get(url, timeout=10, verify=False)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching from URL: {str(e)}")
        return None


def fetch_topology_from_url(url: str) -> Optional[Dict]:
    """Fetch topology JSON from GitHub URL"""
    try:
        response = requests.get(url, timeout=10, verify=False)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching topology from URL: {str(e)}")
        return None


from typing import Dict, Any
import networkx as nx
import streamlit as st
import pandas as pd


def parse_topology_for_graph(topology_data: Dict[str, Any]):
    """Parse topology data and create network graph using pandas DataFrame"""

    nodes_list = []
    edges_list = []

    if not topology_data:
        nodes_df = pd.DataFrame(columns=['uid', 'type', 'city', 'latitude', 'longitude'])
        edges_df = pd.DataFrame(columns=['from_node', 'to_node', 'type_variety', 'length', 'loss_coef', 'con_in', 'con_out'])
    
        st.session_state.network_graph = nodes_df
        st.session_state.network_edges = edges_df
        return nodes_df, edges_df

    elements = topology_data.get("elements", [])
    connections = topology_data.get("connections", [])

    # ------------------------------------------------------------------
    # STEP 1: Collect ALL real network nodes (exclude Fiber elements)
    # ------------------------------------------------------------------
    valid_node_types = {"transceiver", "roadm", "ila", "edfa", "fused"}
    node_dict = {}  # Keep track of nodes for edge filtering
    
    elem_types = list(dict.fromkeys([element.get("type", "").lower() for element in elements]))

    import json

    # Assuming 'data' is your JSON object/dictionary
    # If you have a string, use: data = json.loads(your_json_string)

    dff = pd.json_normalize(topology_data['elements'])
    dff.rename(columns=lambda x: x.split('.')[-1], inplace=True)

    # Optional: Clean up column names to be more concise
    fibers = dff[dff['type'].str.lower()=='fiber'].dropna(axis=1, how='all')
    nodes = dff.dropna(axis=1, how='all')


    dffc = pd.json_normalize(topology_data['connections'])
    dffc.rename(columns=lambda x: x.split('.')[-1], inplace=True)

    # ------------------------------------------------------------------
    # STEP 2: Add edges from connections array (skip fiber intermediates)
    # ------------------------------------------------------------------
    edges_added = 0
    connections_processed = 0

    for conn in connections:
        from_node = conn.get("from_node")
        to_node = conn.get("to_node")

        if not from_node or not to_node:
            continue

        connections_processed += 1

        # Skip connections involving fiber elements
        if from_node.startswith("fiber") or to_node.startswith("fiber"):
            continue

        # Only add edges between actual network nodes
        if from_node in node_dict and to_node in node_dict:
            # Skip transceiver-roadm connections at same location (redundant)
            from_type = node_dict[from_node].get("type", "").lower()
            to_type = node_dict[to_node].get("type", "").lower()
            
            if (from_type == "transceiver" and to_type == "roadm") or \
               (from_type == "roadm" and to_type == "transceiver"):
                continue

            # Add edge if not already present
            edge_exists = any((e['from_node'] == from_node and e['to_node'] == to_node) or 
                             (e['to_node'] == from_node and e['from_node'] == to_node) 
                             for e in edges_list)
            
            if not edge_exists:
                edges_list.append({"from_node": from_node, "to_node": to_node})
                edges_added += 1
    
    # Create DataFrames
    # nodes_df = pd.DataFrame(nodes_list) if nodes_list else pd.DataFrame(columns=['uid', 'type', 'city', 'latitude', 'longitude'])
    # edges_df = pd.DataFrame(edges_list) if edges_list else pd.DataFrame(columns=['from_node', 'to_node', 'type_variety', 'length', 'loss_coef', 'con_in', 'con_out'])



    edges_df = dffc
    nodes_df = nodes
    # Show elements in a table for debugging

    # ------------------------------------------------------------------
    # Store debug info
    # ------------------------------------------------------------------
    st.session_state.network_graph = nodes_df
    st.session_state.network_edges = edges_df
    st.session_state.graph_stats = {
        "nodes": len(nodes_df),
        "edges": len(edges_df),
        "edges_added": edges_added,
        "connections_processed": connections_processed,
        "missing_nodes": [],
    }

    st.session_state.nodes = nodes_df
    st.session_state.edges = edges_df
    return nodes_df, edges_df



def render_animated_network(nodes_df, edges_df):
    """Render animated network visualization using Plotly with DataFrames"""
    
    if nodes_df is None or len(nodes_df) == 0:
        st.warning("No nodes to visualize")
        return
    
    # Create a simple layout using coordinates if available, or random positions
    import numpy as np
    
    # Extract node positions
    nodes_df_copy = nodes_df.copy()
    if 'metadata' in nodes_df_copy.columns:
        # Try to extract lat/lon from metadata if available
        positions = {}
        for idx, row in nodes_df_copy.iterrows():
            uid = row.get('uid', f'node_{idx}')
            positions[uid] = (np.random.rand(), np.random.rand())  # Default random
    else:
        # Generate random positions for all nodes
        positions = {uid: (np.random.rand(), np.random.rand()) for uid in nodes_df_copy['uid'].unique()}
    
    # Prepare edge traces
    edge_x = []
    edge_y = []
    edge_colors = []
    edge_hover = []
    
    if edges_df is not None and len(edges_df) > 0:
        for idx, row in edges_df.iterrows():
            from_node = row.get('from_node')
            to_node = row.get('to_node')
            
            if from_node in positions and to_node in positions:
                x0, y0 = positions[from_node]
                x1, y1 = positions[to_node]
                edge_x.extend([x0, x1, None])
                edge_y.extend([y0, y1, None])
                
                traffic = random.randint(10, 100)
                edge_colors.append(traffic)
                edge_hover.append(f"Traffic: {traffic}%")
    
    # Create edge trace
    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        mode='lines',
        line=dict(width=2, color='rgba(0, 255, 204, 0.5)'),
        hoverinfo='skip',
        showlegend=False
    )
    
    # Prepare node traces
    node_x = []
    node_y = []
    node_text = []
    node_colors = []
    node_types = []
    
    color_map = {
        "roadm": "#ffcc00",
        "transceiver": "#00ccff",
        "ila": "#ff6699",
        "edfa": "#ff9966",
        "fused": "#cccccc",
    }
    
    for uid in nodes_df_copy['uid'].unique():
        if uid in positions:
            x, y = positions[uid]
            node_x.append(x)
            node_y.append(y)
            node_text.append(str(uid))
            
            # Get node type
            node_info = nodes_df_copy[nodes_df_copy['uid'] == uid].iloc[0]
            node_type = str(node_info.get('type', 'unknown')).lower()
            node_types.append(node_type)
            node_colors.append(color_map.get(node_type, "#888888"))
    
    # Create node trace
    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        text=node_text,
        textposition='top center',
        textfont=dict(size=9, color='white'),
        hoverinfo='text',
        hovertext=[f"<b>{node}</b><br>Type: {node_types[i]}" for i, node in enumerate(node_text)],
        marker=dict(
            size=15,
            color=node_colors,
            line=dict(width=2, color='white')
        ),
        showlegend=False
    )
    
    # Create figure
    fig = go.Figure(data=[edge_trace, node_trace])
    
    # Update layout
    fig.update_layout(
        title=f"Network Topology ({len(nodes_df_copy)} nodes, {len(edges_df) if edges_df is not None else 0} links)",
        showlegend=False,
        hovermode='closest',
        margin=dict(b=20, l=5, r=5, t=40),
        plot_bgcolor='#111111',
        paper_bgcolor='#0a0a0a',
        font=dict(color='white', size=12),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        height=750
    )
    
    st.plotly_chart(fig, use_container_width=True)


def visualize_network_graph():
    """Visualize network topology using pyvis animated network"""
    
    nodes_df = st.session_state.network_graph
    edges_df = st.session_state.get('network_edges', pd.DataFrame())
    
    if nodes_df is None or len(nodes_df) == 0:
        st.warning("No topology data to visualize")
        return
    
    # DEBUG INFO SECTION
    if 'graph_stats' in st.session_state:
        stats = st.session_state.graph_stats
        with st.expander("🔧 Debug: Connection Info", expanded=(stats['edges'] == 0)):
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Nodes Found", stats['nodes'])
            with col2:
                st.metric("Edges Created", stats['edges'])
            with col3:
                st.metric("Connections Processed", stats['connections_processed'])
            with col4:
                st.metric("Edges Added", stats['edges_added'])
    
    st.markdown("**🔗 Animated Network Graph Visualization**")
    
    # Render animated network
    render_animated_network(nodes_df, edges_df)


def visualize_network_on_map():
    """Visualize network nodes on an interactive geographic map using px.scatter_mapbox()"""
    
    if not st.session_state.topology_data:
        st.warning("No topology data available")
        return
    
    topology = st.session_state.topology_data
    
    # Extract node data with coordinates
    nodes_data = st.session_state.nodes
    

    
   
    # Create DataFrame
    df = pd.DataFrame(nodes_data)
    
    # Define color mapping for node types
    color_map = {
        'Transceiver': '#00ccff',
        'ROADM': '#ffcc00',
        'ILA': '#7ED321',
        'Edfa': '#ff9966',
        'Fused': '#BD10E0',
        'Fiber': '#cc99ff',
    }
    
    # Create scatter mapbox
    fig = px.scatter_mapbox(
        df,
        lat='latitude',
        lon='longitude',
        hover_name='uid',
        color='type',
        zoom=4,
        height=700,
        title="🗺️ Network Topology - Geographic Map View",
        hover_data={
            'type': True,
            'city': True,
            'latitude': ':.4f',
            'longitude': ':.4f',
        },
        mapbox_style='open-street-map',
    )

    fig.update_traces(marker=dict(size=15))
    
    # Customize hover template
    fig.update_traces(
        hovertemplate='<b>%{customdata[2]}</b><br>' +
                     'Type: %{customdata[0]}<br>' +
                     'City: %{customdata[1]}<br>' +
                     'Lat: %{customdata[3]:.4f}<br>' +
                     'Lon: %{customdata[4]:.4f}<extra></extra>',
        customdata=df[['type', 'city', 'uid', 'latitude', 'longitude']].values,
    )
    
    # Update layout for better appearance
    fig.update_layout(
        font=dict(size=11),
        margin=dict(l=0, r=0, t=40, b=0),
    )
    

    
    # Get fiber connections from edges
    fibers = st.session_state.edges
    nodes_data = st.session_state.nodes
    
    # Remove columns with all null values
    if not fibers.empty:
        fibers = fibers.dropna(axis=1, how='all')
    if not nodes_data.empty:
        nodes_data = nodes_data.dropna(axis=1, how='all')
    
    # Create node lookup dictionary for coordinates
    node_lookup = {}
    if not nodes_data.empty and 'uid' in nodes_data.columns:
        for _, row in nodes_data.iterrows():
            if pd.notna(row.get('latitude')) and pd.notna(row.get('longitude')):
                node_lookup[row['uid']] = {
                    'latitude': row['latitude'],
                    'longitude': row['longitude']
                }
    
    # Debug: Show what columns we have
    # with st.expander("🔧 Debug: Available Columns", expanded=False):
    #     st.write("**Fiber columns:**", list(fibers.columns) if not fibers.empty else "No fibers")
    #     st.write("**Node lookup sample:**", list(node_lookup.keys())[:5] if node_lookup else "No nodes with coordinates")
    
    # Show fiber connections toggle
    show_fibers_toggle = st.checkbox("Show fiber connections", value=True)
    
    if show_fibers_toggle and not fibers.empty:
        fiber_lats = []
        fiber_lons = []
        connections_added = 0
        
        # Check which column names exist for connections
        from_col = None
        to_col = None
        
        for possible_from in ['from_node', 'source', 'from', 'node_a']:
            if possible_from in fibers.columns:
                from_col = possible_from
                break
        
        for possible_to in ['to_node', 'destination', 'to', 'node_b']:
            if possible_to in fibers.columns:
                to_col = possible_to
                break
        
        if from_col and to_col:
            for _, row in fibers.iterrows():
                start_node = row.get(from_col)
                end_node = row.get(to_col)
                
                if pd.isna(start_node) or pd.isna(end_node):
                    continue
                
                start = node_lookup.get(start_node)
                end = node_lookup.get(end_node)

                if start and end:
                    fiber_lats.extend([
                        start["latitude"],
                        end["latitude"],
                        None
                    ])
                    fiber_lons.extend([
                        start["longitude"],
                        end["longitude"],
                        None
                    ])
                    connections_added += 1

            if fiber_lats:
                fig.add_trace(
                    go.Scattermapbox(
                        mode="lines",
                        lat=fiber_lats,
                        lon=fiber_lons,
                        line=dict(width=2, color="rgba(255, 165, 0, 0.6)"),
                        name="Fiber Connections",
                        hoverinfo="skip"
                    )
                )
                st.success(f"✓ Added {connections_added} fiber connections to map")
            else:
                st.warning("No valid fiber connections found with coordinates")
        else:
            st.error(f"Could not find connection columns. Available: {list(fibers.columns)}")

    fig.update_traces(marker=dict(size=12))
    
    # Render the chart and capture selection
    selection = st.plotly_chart(
        fig,
        use_container_width=True,
        key="network_distance_graph",
        on_select="rerun"
    )

    # Process node selection from map clicks
    if selection and "selection" in selection and "points" in selection["selection"]:
        selected_points = selection["selection"]["points"]
        
        if len(selected_points) > 0:
            st.markdown("---")
            st.subheader("📍 Selected Nodes for Path Computation")
            
            selected_nodes = []
            for point in selected_points:
                # Extract node UID from the point data
                if "customdata" in point:
                    node_uid = point["customdata"][2]  # UID is at index 2
                    selected_nodes.append(node_uid)
            
            selected_nodes = list(dict.fromkeys(selected_nodes))  # Remove duplicates
            
            if len(selected_nodes) >= 1:
                col1, col2 = st.columns(2)
                
                with col1:
                    st.info(f"**Source Node:** {selected_nodes[0]}")
                    st.session_state.source_node = selected_nodes[0]
                    st.session_state.source_select = selected_nodes[0]
                
                with col2:
                    if len(selected_nodes) >= 2:
                        st.info(f"**Destination Node:** {selected_nodes[1]}")
                        st.session_state.destination_node = selected_nodes[1]
                        st.session_state.dest_select = selected_nodes[1]
                    else:
                        st.warning("Click on a second node to set destination")
            
            if len(selected_nodes) >= 2:
                if st.button("✅ Confirm Selection and Go to Path Configuration", use_container_width=True):
                    st.success(f"Source: {selected_nodes[0]} → Destination: {selected_nodes[1]}")
                    st.info("Scroll down to Section 6 to compute paths with these nodes")
    


    # Display node statistics
    with st.expander("📊 Network Statistics", expanded=False):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Nodes", len(df))
        with col2:
            st.metric("Node Types", df['type'].nunique())
        with col3:
            st.metric("Cities", df['city'].nunique())
        
        st.dataframe(
            df[['uid', 'type', 'city', 'latitude', 'longitude']].sort_values('uid'),
            use_container_width=True
        )




def generate_example_topology(topology_type: str, num_nodes: int):
    """Generate example topology"""
    if topology_type == "Linear Topology":
        G = nx.path_graph(num_nodes)
    elif topology_type == "Random Network":
        G = nx.erdos_renyi_graph(num_nodes, 0.3)
    else:  # Random National Network
        G = nx.random_geometric_graph(num_nodes, 0.3)
    
    # Convert to topology data format
    topology_data = {
        "elements": []
    }
    
    for node in G.nodes():
        topology_data["elements"].append({
            "uid": f"Node_{node}",
            "type": "ROADM"
        })
    
    for edge in G.edges():
        topology_data["elements"].append({
            "type": "Fiber",
            "from": f"Node_{edge[0]}",
            "to": f"Node_{edge[1]}",
            "length": 80.0
        })
    
    st.session_state.topology_data = topology_data
    parse_topology_for_graph(topology_data)
    st.success(f"✓ Generated {topology_type} with {num_nodes} nodes")


def get_available_nodes() -> List[str]:
    """Get list of available nodes from topology"""
    if st.session_state.network_graph is not None and len(st.session_state.network_graph) > 0:
        return sorted(list(st.session_state.network_graph['uid'].unique()))
    return []


def compute_paths(source: str, destination: str, **kwargs) -> Dict:
    """Compute and simulate paths using GNPy"""
    
    try:
        # Check if we have a network object
        if st.session_state.network_obj is None:
            st.warning("⚠️ Network not initialized for simulation.")
            st.info("**Solution:** Make sure to:")
            st.info("1. Load an **Equipment Library** (Section 1)")
            st.info("2. Load a **Network Topology** (Section 3)")
            st.info("If issues persist, check the console for detailed error messages.")
            return {}
        
        if st.session_state.equipment_obj is None:
            st.error("❌ Equipment library not loaded. Please load equipment first (Section 1).")
            return {}
        
        # Apply auto-design if enabled
        network_obj = st.session_state.network_obj
        if st.session_state.autodesign_params['mode'] != 'none':
            with st.spinner("Applying auto-design..."):
                network_obj = gnpy_wrapper.perform_autodesign(
                    network_obj,
                    st.session_state.equipment_obj,
                    st.session_state.autodesign_params
                )
        
        # Prepare path parameters from kwargs
        path_params = {
            'bidirectional': kwargs.get('bidirectional', False),
            'include_nodes': kwargs.get('include_nodes', []),
            'exclude_nodes': kwargs.get('exclude_nodes', []),
            'spacing': kwargs.get('spacing', 50.0),  # GHz
            'power': kwargs.get('power', 0.0),  # dBm
            'min_osnr': kwargs.get('min_osnr', 15.0),  # dB
            'system_margin': kwargs.get('system_margin', 3.0),  # dB
        }
        
        # Compute main path
        with st.spinner("Computing path with GNPy..."):
            result = gnpy_wrapper.compute_path(
                network_obj,
                st.session_state.equipment_obj,
                source,
                destination,
                path_params
            )
        
        if 'error' in result:
            st.error(f"❌ Path computation failed: {result.get('error', 'Unknown error')}")
            return {}
        
        # Build results structure
        results = {
            'source': source,
            'destination': destination,
            'path': result.get('path', []),
            'path_length': result.get('path_length', 0.0),
            'gsnr': result.get('gsnr', 0.0),
            'osnr': result.get('osnr', 0.0),
            'feasible': result.get('feasible', False),
            'num_spans': result.get('num_spans', 0),
            'num_edfas': result.get('num_edfas', 0),
            'total_loss': result.get('total_loss', 0.0),
            'cd': result.get('cd', 0.0),
            'pmd': result.get('pmd', 0.0),
            'pdl': result.get('pdl', 0.0),
            'available_paths': ['Working Path']
        }
        
        # Compute diverse path if requested
        if kwargs.get('diverse', False):
            # Would need to implement diverse path computation in GNPy
            results['available_paths'].append('Diverse Path')
        
        # Compute reverse path if requested
        if kwargs.get('reverse', False):
            results['available_paths'].append('Reverse Path')
        
        # Perform power sweep if enabled
        if kwargs.get('enable_sweep', False):
            with st.spinner("Running power sweep..."):
                sweep_start = kwargs.get('sweep_start', -3.0)
                sweep_stop = kwargs.get('sweep_stop', 3.0)
                sweep_step = kwargs.get('sweep_step', 0.5)
                
                sweep_results = gnpy_wrapper.power_sweep(
                    network_obj,
                    st.session_state.equipment_obj,
                    source,
                    destination,
                    (sweep_start, sweep_stop, sweep_step),
                    path_params
                )
                results['power_sweep'] = sweep_results
        
        return results
        
    except Exception as e:
        st.error(f"❌ Error computing paths: {str(e)}")
        import traceback
        traceback.print_exc()
        return {}


def generate_power_sweep_data() -> Dict:
    """Generate sample power sweep data"""
    import numpy as np
    powers = np.arange(-3, 3.5, 0.5)
    gsnr = 20 - 0.5 * (powers - 0)**2 + np.random.normal(0, 0.2, len(powers))
    osnr = 19 - 0.5 * (powers - 0)**2 + np.random.normal(0, 0.2, len(powers))
    
    return {
        'powers': powers.tolist(),
        'gsnr': gsnr.tolist(),
        'osnr': osnr.tolist()
    }


def show_detailed_path_info(results: Dict):
    """Show detailed path information"""
    with st.expander("Detailed Path Information", expanded=True):
        st.write("**Path Elements:**")
        st.write(f"Source: {results['source']}")
        st.write(f"Destination: {results['destination']}")
        st.json(results)


def show_spectra_plots(results: Dict):
    """Show signal and noise spectra"""
    with st.expander("Signal & Noise Spectra", expanded=True):
        import numpy as np
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
        
        # Sample signal spectrum
        freq = np.linspace(191, 196, 1000)
        signal = -20 + np.random.normal(0, 1, len(freq))
        ax1.plot(freq, signal)
        ax1.set_xlabel('Frequency (THz)')
        ax1.set_ylabel('Power (dBm)')
        ax1.set_title('Signal Spectrum')
        ax1.grid(True)
        
        # Sample noise spectrum
        noise = -50 + np.random.normal(0, 2, len(freq))
        ax2.plot(freq, noise, color='orange')
        ax2.set_xlabel('Frequency (THz)')
        ax2.set_ylabel('NLI (dBm)')
        ax2.set_title('Noise Spectrum')
        ax2.grid(True)
        
        st.pyplot(fig)


def show_path_on_map(results: Dict):
    """Show path highlighted on network map"""
    with st.expander("Path on Network Map", expanded=True):
        st.info("Path visualization on network topology")
        visualize_network_graph()


def show_power_sweep_plot(sweep_data: Dict):
    """Plot power sweep results"""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    ax.plot(sweep_data['powers'], sweep_data['gsnr'], 'o-', label='GSNR', linewidth=2, markersize=8)
    ax.plot(sweep_data['powers'], sweep_data['osnr'], 's-', label='OSNR', linewidth=2, markersize=8)
    
    ax.set_xlabel('Reference Power (dBm)')
    ax.set_ylabel('OSNR/GSNR (dB)')
    ax.set_title('GSNR/OSNR vs. Reference Power')
    ax.legend()
    ax.grid(True)
    
    st.pyplot(fig)


def generate_power_sweep_csv(sweep_data: Dict) -> str:
    """Generate CSV data from power sweep"""
    df = pd.DataFrame({
        'Power (dBm)': sweep_data['powers'],
        'GSNR (dB)': sweep_data['gsnr'],
        'OSNR (dB)': sweep_data['osnr']
    })
    return df.to_csv(index=False)


def process_batch_services():
    """Process all service requests in batch"""
    try:
        if not st.session_state.services_data:
            st.error("No services loaded")
            return
        
        # Prepare path parameters
        path_params = {
            'bidirectional': False,
            'include_nodes': [],
            'exclude_nodes': [],
            'spacing': 50.0,  # GHz
            'power': 0.0,  # dBm
            'min_osnr': 15.0,  # dB
            'system_margin': 3.0,  # dB
        }
        
        # Apply auto-design if enabled
        network_obj = st.session_state.network_obj
        if st.session_state.autodesign_params['mode'] != 'none':
            network_obj = gnpy_wrapper.perform_autodesign(
                network_obj,
                st.session_state.equipment_obj,
                st.session_state.autodesign_params
            )
        
        # Process all services
        with st.spinner("Processing batch services..."):
            results = gnpy_wrapper.process_service_requests(
                network_obj,
                st.session_state.equipment_obj,
                st.session_state.services_data,
                path_params
            )
        
        st.session_state.services_obj = results
        
        # Display results in a table
        st.success(f"✓ Processed {len(results)} service requests")
        
        # Create results DataFrame
        results_df = pd.DataFrame([
            {
                'Request ID': r.get('request_id', 'unknown'),
                'Source': r.get('path', ['', ''])[0],
                'Destination': r.get('path', ['', ''])[-1] if len(r.get('path', [])) > 0 else '',
                'Path Length (km)': f"{r.get('path_length', 0):.1f}",
                'OSNR (dB)': f"{r.get('osnr', 0):.2f}",
                'GSNR (dB)': f"{r.get('gsnr', 0):.2f}",
                'Feasible': '✓ Yes' if r.get('feasible', False) else '✗ No'
            }
            for r in results
        ])
        
        with st.expander("📊 Service Results", expanded=True):
            st.dataframe(results_df, use_container_width=True)
    
    except Exception as e:
        st.error(f"Error processing services: {str(e)}")
        import traceback
        traceback.print_exc()


def generate_services_csv(results: List[Dict]) -> str:
    """Generate CSV from service results"""
    rows = []
    for r in results:
        rows.append({
            'Request ID': r.get('request_id', 'unknown'),
            'Source': r.get('path', ['', ''])[0],
            'Destination': r.get('path', ['', ''])[-1] if len(r.get('path', [])) > 0 else '',
            'Path Length (km)': f"{r.get('path_length', 0):.1f}",
            'OSNR (dB)': f"{r.get('osnr', 0):.2f}",
            'GSNR (dB)': f"{r.get('gsnr', 0):.2f}",
            'Num Spans': r.get('num_spans', 0),
            'Num EDFAs': r.get('num_edfas', 0),
            'Feasible': 'Yes' if r.get('feasible', False) else 'No'
        })
    
    df = pd.DataFrame(rows)
    return df.to_csv(index=False)


if __name__ == "__main__":
    main()
