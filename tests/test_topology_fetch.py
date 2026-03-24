#!/usr/bin/env python
"""Test fetching and parsing topology files from GitHub"""

import requests
import json
import networkx as nx
import urllib3

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def fetch_topology_from_url(url: str):
    """Fetch topology JSON from GitHub URL"""
    try:
        response = requests.get(url, timeout=10, verify=False)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching topology from URL: {str(e)}")
        return None

def parse_topology_for_graph(topology_data):
    """Parse topology data and create network graph - fibers connect nodes"""
    G = nx.Graph()
    
    if topology_data is None:
        return G
    
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
    
    return G

# Test with Mesh Topology
print("Testing Mesh Topology...")
mesh_url = "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/meshTopologyExampleV2.json"
mesh_data = fetch_topology_from_url(mesh_url)

if mesh_data:
    print(f"✓ Successfully fetched Mesh topology")
    print(f"  Top-level keys: {list(mesh_data.keys())}")
    
    if 'elements' in mesh_data:
        print(f"  Number of elements: {len(mesh_data['elements'])}")
        # Show first few elements
        for i, elem in enumerate(mesh_data['elements'][:3]):
            print(f"    Element {i}: type={elem.get('type')}, uid={elem.get('uid')}")
    
    graph = parse_topology_for_graph(mesh_data)
    print(f"✓ Parsed graph with {len(graph.nodes())} nodes and {len(graph.edges())} edges")
else:
    print("✗ Failed to fetch Mesh topology")

# Test with CORONET CONUS
print("\nTesting CORONET CONUS Topology...")
coronet_url = "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/CORONET_CONUS_Topology.json"
coronet_data = fetch_topology_from_url(coronet_url)

if coronet_data:
    print(f"✓ Successfully fetched CORONET CONUS topology")
    print(f"  Top-level keys: {list(coronet_data.keys())}")
    
    if 'elements' in coronet_data:
        print(f"  Number of elements: {len(coronet_data['elements'])}")
        # Show first few elements
        for i, elem in enumerate(coronet_data['elements'][:3]):
            print(f"    Element {i}: type={elem.get('type')}, uid={elem.get('uid')}")
    
    graph = parse_topology_for_graph(coronet_data)
    print(f"✓ Parsed graph with {len(graph.nodes())} nodes and {len(graph.edges())} edges")
else:
    print("✗ Failed to fetch CORONET CONUS topology")

print("\n✅ All tests completed!")
