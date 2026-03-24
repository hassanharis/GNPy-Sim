#!/usr/bin/env python
"""Test to verify CORONET has geographic coordinates for mapping"""

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def fetch_json_from_url(url: str):
    """Fetch JSON from GitHub URL"""
    try:
        response = requests.get(url, timeout=10, verify=False)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return None

# Test with CORONET CONUS
print("Testing CORONET CONUS for geographic coordinates...")
coronet_url = "https://raw.githubusercontent.com/Telecominfraproject/oopt-gnpy/master/gnpy/example-data/CORONET_CONUS_Topology.json"
coronet_data = fetch_json_from_url(coronet_url)

if coronet_data and 'elements' in coronet_data:
    elements = coronet_data['elements']
    
    # Count nodes with coordinates
    nodes_with_coords = 0
    nodes_without_coords = 0
    sample_node = None
    
    for elem in elements:
        elem_type = elem.get('type', '').lower()
        if elem_type in ['roadm', 'transceiver', 'edfa', 'fused', 'ila']:
            if 'metadata' in elem and 'location' in elem['metadata']:
                loc = elem['metadata']['location']
                if 'latitude' in loc and 'longitude' in loc:
                    nodes_with_coords += 1
                    if not sample_node:
                        sample_node = (elem.get('uid'), loc)
                else:
                    nodes_without_coords += 1
            else:
                nodes_without_coords += 1
    
    print(f"\nNodes with geographic coordinates: {nodes_with_coords}")
    print(f"Nodes without coordinates: {nodes_without_coords}")
    
    if sample_node:
        print(f"\nSample node with coordinates:")
        print(f"  Name: {sample_node[0]}")
        print(f"  Latitude: {sample_node[1].get('latitude')}")
        print(f"  Longitude: {sample_node[1].get('longitude')}")
        if 'city' in sample_node[1]:
            print(f"  City: {sample_node[1]['city']}")
        if 'region' in sample_node[1]:
            print(f"  Region: {sample_node[1]['region']}")
    
    if nodes_with_coords > 0:
        print("\n✓ CORONET CONUS has geographic coordinates → Will use Plotly map visualization")
    else:
        print("\n✗ CORONET CONUS has no coordinates → Will use NetworkX graph layout")
