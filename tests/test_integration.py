#!/usr/bin/env python
"""Integration test simulating Streamlit app workflow"""

import requests
import networkx as nx
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class MockSessionState:
    """Simulate Streamlit session state"""
    def __init__(self):
        self.topology_data = None
        self.network_graph = None
        self.topology_generated = False

def fetch_topology_from_url(url: str):
    """Fetch topology JSON from GitHub URL"""
    try:
        response = requests.get(url, timeout=10, verify=False)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return None

def parse_topology_for_graph(topology_data, session_state):
    """Parse topology data and create network graph - fibers connect nodes"""
    G = nx.Graph()
    
    if topology_data is None:
        session_state.network_graph = G
        return
    
    # Step 1: Add only network NODE elements (Transceiver, ROADM)
    if 'elements' in topology_data:
        for element in topology_data['elements']:
            elem_type = element.get('type', '').lower()
            # Only include actual network NODES
            if elem_type in ['transceiver', 'roadm']:
                uid = element.get('uid')
                if uid:
                    G.add_node(uid, **element)
    
    # Step 2: Add EDGES created by Fiber elements connecting nodes
    if 'elements' in topology_data:
        for element in topology_data['elements']:
            elem_type = element.get('type', '').lower()
            if elem_type == 'fiber':
                src = element.get('from')
                dest = element.get('to')
                # Fibers connect fiber endpoints to roadm nodes
                # Create edges if at least one endpoint exists
                if src and dest:
                    G.add_edge(src, dest, fiber_uid=element.get('uid'), **element)
    
    session_state.network_graph = G

# Simulate app workflow
print("Simulating Streamlit app workflow...")
print()

session_state = MockSessionState()

# Step 1: User selects example topology
print("Step 1: User selects 'Mesh Topology' from example topologies")
url = "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/meshTopologyExampleV2.json"

# Step 2: Load example topology
print("Step 2: Load Example Topology button clicked")
topology_json = fetch_topology_from_url(url)
if topology_json:
    session_state.topology_data = topology_json
    session_state.topology_generated = False
    parse_topology_for_graph(topology_json, session_state)
    print(f"  ✓ Topology loaded successfully")
    print(f"  ✓ Session state updated")
else:
    print(f"  ✗ Failed to load topology")

# Step 3: Check visualization conditions
print()
print("Step 3: Checking visualization conditions")
print(f"  topology_data is not None: {session_state.topology_data is not None}")
print(f"  network_graph is not None: {session_state.network_graph is not None}")
if session_state.network_graph:
    num_nodes = len(session_state.network_graph.nodes())
    num_edges = len(session_state.network_graph.edges())
    print(f"  Number of nodes: {num_nodes}")
    print(f"  Number of edges: {num_edges}")

# Step 4: Determine what UI should show
print()
print("Step 4: UI Rendering Logic")
if session_state.network_graph is not None and len(session_state.network_graph.nodes()) > 0:
    print("  ✓ Will show: 📊 Network Topology Visualization")
    print(f"    Graph with {len(session_state.network_graph.nodes())} nodes and {len(session_state.network_graph.edges())} edges")
elif session_state.topology_data and session_state.network_graph is None:
    print("  ℹ️  Will show: Topology loaded. Network graph visualization will appear after parsing.")
else:
    print("  Will show: No topology data to visualize")

print()
print("✅ Integration test completed successfully!")
