#!/usr/bin/env python
"""Comprehensive test of all example file loading and parsing"""

import requests
import json
import networkx as nx
import urllib3
from collections import Counter

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def fetch_json_from_url(url: str):
    """Fetch JSON from GitHub URL"""
    try:
        response = requests.get(url, timeout=10, verify=False)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return None

def parse_topology_for_graph(topology_data):
    """Parse topology data and create network graph"""
    G = nx.Graph()
    
    if topology_data is None:
        return G
    
    if 'elements' in topology_data:
        for element in topology_data['elements']:
            elem_type = element.get('type', '')
            if elem_type.lower() in ['roadm', 'transceiver', 'edfa', 'fused', 'ila']:
                uid = element.get('uid')
                if uid:
                    G.add_node(uid, **element)
    
    if 'connections' in topology_data:
        for conn in topology_data['connections']:
            from_node = conn.get('from_node')
            to_node = conn.get('to_node')
            if from_node and to_node:
                G.add_edge(from_node, to_node, **conn)
    
    return G

# Define example files
EXAMPLE_EQUIPMENT_FILES = {
    "🔧 Default Equipment": "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/eqpt_config.json",
    "🔧 OpenROADM v4": "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/eqpt_config_openroadm_ver4.json",
}

EXAMPLE_TOPOLOGY_FILES = {
    "🌐 Mesh Topology": "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/meshTopologyExampleV2.json",
    "🌐 CORONET CONUS": "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/CORONET_CONUS_Topology.json",
    "🌐 Sweden OpenROADM v4": "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/Sweden_OpenROADMv4_example_network.json",
}

EXAMPLE_SERVICES_FILES = {
    "📋 Mesh Services": "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/meshTopologyExampleV2_services.json",
}

EXAMPLE_SIM_PARAMS = {
    "⚙️ Default Simulation": "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/sim_params.json"
}

# Test equipment files
print("=" * 60)
print("TESTING EQUIPMENT FILES")
print("=" * 60)
for name, url in EXAMPLE_EQUIPMENT_FILES.items():
    data = fetch_json_from_url(url)
    status = "✓" if data else "✗"
    print(f"{status} {name}")
    if data:
        keys = list(data.keys())[:5]
        print(f"  Keys: {keys}")

# Test topology files and parsing
print("\n" + "=" * 60)
print("TESTING TOPOLOGY FILES")
print("=" * 60)
for name, url in EXAMPLE_TOPOLOGY_FILES.items():
    data = fetch_json_from_url(url)
    if data:
        graph = parse_topology_for_graph(data)
        print(f"✓ {name}")
        print(f"  Nodes: {len(graph.nodes())}, Edges: {len(graph.edges())}")
    else:
        print(f"✗ {name}")

# Test services files
print("\n" + "=" * 60)
print("TESTING SERVICES FILES")
print("=" * 60)
for name, url in EXAMPLE_SERVICES_FILES.items():
    data = fetch_json_from_url(url)
    status = "✓" if data else "✗"
    print(f"{status} {name}")
    if data:
        if isinstance(data, dict):
            print(f"  Type: dict, Keys: {list(data.keys())[:3]}")
        elif isinstance(data, list):
            print(f"  Type: list, Items: {len(data)}")

# Test simulation parameters
print("\n" + "=" * 60)
print("TESTING SIMULATION PARAMETERS")
print("=" * 60)
for name, url in EXAMPLE_SIM_PARAMS.items():
    data = fetch_json_from_url(url)
    status = "✓" if data else "✗"
    print(f"{status} {name}")
    if data:
        print(f"  Keys: {list(data.keys())[:5]}")

print("\n" + "=" * 60)
print("✅ END-TO-END TEST COMPLETED")
print("=" * 60)
