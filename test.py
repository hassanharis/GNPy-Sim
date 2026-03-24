# Test script for GNPy simulation with Streamlit

from pathlib import Path
from numpy import mean
import streamlit as st
from gnpy.tools.json_io import load_equipment, load_network
from gnpy.core.utils import dbm2watt
from gnpy.topology.request import PathRequest, compute_path_dsjctn

def run_simulation(topology_path, equipment_path, launch_power):

    # Load equipment and topology
    equipment = load_equipment(equipment_path)
    network = load_network(Path(topology_path), equipment)
    
    # Create a path request between actual network nodes
    request = PathRequest(
        request_id="req1",
        source="trx Lannion_CAS",
        destination="trx Lorient_KMA",
        bidir=False,
        trx_type="Voyager",
        trx_mode=None,
        spacing=equipment['SI']['default'].spacing,
        tx_power=dbm2watt(launch_power)
    )

    # Compute the path (expects list of requests, returns list of paths)
    paths = compute_path_dsjctn(network, equipment, [request], [])

    return paths

equipment = load_equipment(r"C:\\Local\\GNPy-Simulator\\Templates\\eqpt_config.json")
print(equipment.keys())


network = load_network(Path("C:\\Local\\GNPy-Simulator\\Templates\\meshTopologyExampleV2.json"), equipment)
print(network)

# for u, v in network.edges():
#     print(u, "->", v)
# for u  in network.nodes():
#     print(u )
print("Is directed:", network.is_directed())
print("Is multigraph:", network.is_multigraph())
print("Is directed:", network.is_directed())
print("Is directed:", network.is_directed())


# Check a specific node's attributes


# Or iterate all nodes with data
# for node, data in network.nodes(data=True):
#     print(f"{node}: {data}")

print(dir(list(network.nodes())[0]))

# Check if latitude exists
if hasattr(list(network.nodes())[0], 'latitude'):
    print("Stored as node object attribute")
else:
    # Check node data dict
    node_data = network.nodes[list(network.nodes())[0]]
    if 'latitude' in node_data or 'metadata' in node_data:
        print("Stored in node attributes")

#print(network.clear_edges())

"""
import streamlit as st

st.title("GNPy Built-in Example Simulator")

launch_power = 5

paths = run_simulation(
    topology_path="C:\\Local\\GNPy-Simulator\\Templates\\meshTopologyExampleV2.json",
    equipment_path="C:\\Local\\GNPy-Simulator\\Templates\\eqpt_config.json",
    launch_power=launch_power
)

st.success("Simulation Complete")

# paths is a list of paths; each path is a list of network elements
if paths and len(paths) > 0:
    path = paths[0]  # Get the first path
    # The last element in the path should be the destination transceiver
    dest_trx = path[-1]
    
    # Display results
    st.write("### Results")
    st.write(f"**Average OSNR (ASE):** {mean(dest_trx.osnr_ase):.2f} dB")
    st.write(f"**Average OSNR (ASE) @ 0.1nm:** {mean(dest_trx.osnr_ase_01nm):.2f} dB")
    st.write(f"**Average SNR:** {mean(dest_trx.snr):.2f} dB")
    st.write(f"**Average SNR @ 0.1nm:** {mean(dest_trx.snr_01nm):.2f} dB")
    st.write(f"**Path elements:** {[e.uid for e in path]}")
else:
    st.error("No path found!")
    """
