#!/usr/bin/env python
"""Analyze topology structure to understand element types"""

import requests
import json
import urllib3
from collections import Counter

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def fetch_topology_from_url(url: str):
    """Fetch topology JSON from GitHub URL"""
    try:
        response = requests.get(url, timeout=10, verify=False)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching topology: {str(e)}")
        return None

# Test with Mesh Topology
print("=== Mesh Topology Analysis ===")
mesh_url = "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/meshTopologyExampleV2.json"
mesh_data = fetch_topology_from_url(mesh_url)

if mesh_data and 'elements' in mesh_data:
    elements = mesh_data['elements']
    
    # Count element types
    types = Counter([elem.get('type', 'UNKNOWN') for elem in elements])
    print(f"\nElement type distribution:")
    for elem_type, count in types.most_common():
        print(f"  {elem_type}: {count}")
    
    # Show 'connections' structure if present
    if 'connections' in mesh_data:
        print(f"\nConnections: {len(mesh_data['connections'])} total")
        print("First 3 connections:")
        for conn in mesh_data['connections'][:3]:
            print(f"  {conn}")
    
    # Show all element types with their details
    print("\nAll elements:")
    for elem in elements[:5]:
        print(f"  Type: {elem.get('type')}, UID: {elem.get('uid')}, Keys: {list(elem.keys())}")

print("\n=== CORONET CONUS Analysis ===")
coronet_url = "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/CORONET_CONUS_Topology.json"
coronet_data = fetch_topology_from_url(coronet_url)

if coronet_data and 'elements' in coronet_data:
    elements = coronet_data['elements']
    
    # Count element types
    types = Counter([elem.get('type', 'UNKNOWN') for elem in elements])
    print(f"\nElement type distribution:")
    for elem_type, count in types.most_common():
        print(f"  {elem_type}: {count}")
    
    # Show 'connections' structure if present
    if 'connections' in coronet_data:
        print(f"\nConnections: {len(coronet_data['connections'])} total")
        print("First 3 connections:")
        for conn in coronet_data['connections'][:3]:
            print(f"  {conn}")
    
    # Show sample ROADM if present
    roadms = [elem for elem in elements if elem.get('type') == 'ROADM']
    if roadms:
        print(f"\nSample ROADM element:")
        print(f"  {roadms[0]}")
    
    # Show sample Transceiver
    txs = [elem for elem in elements if elem.get('type') == 'Transceiver']
    if txs:
        print(f"\nSample Transceiver element:")
        print(f"  {txs[0]}")
