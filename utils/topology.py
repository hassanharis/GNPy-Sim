"""
Topology Handling Utilities
Functions for loading, parsing, and manipulating network topologies
"""

import json
import networkx as nx
from typing import Dict, List, Tuple, Optional
import pandas as pd


def parse_json_topology(topology_data: Dict) -> nx.Graph:
    """
    Parse JSON topology and create NetworkX graph
    
    Args:
        topology_data: Dictionary containing topology information
        
    Returns:
        NetworkX graph object
    """
    G = nx.Graph()
    
    if 'elements' in topology_data:
        # Parse elements-based topology format
        nodes = []
        edges = []
        
        for element in topology_data['elements']:
            elem_type = element.get('type', '')
            
            # Add nodes (ROADM, ILA, Transceiver, Fused)
            if elem_type in ['ROADM', 'ILA', 'Transceiver', 'Fused']:
                node_id = element.get('uid')
                if node_id:
                    nodes.append({
                        'id': node_id,
                        'type': elem_type,
                        'metadata': element
                    })
            
            # Add edges (Fiber)
            elif elem_type == 'Fiber':
                source = element.get('from')
                dest = element.get('to')
                if source and dest:
                    edges.append({
                        'source': source,
                        'dest': dest,
                        'length': element.get('length', 80.0),
                        'metadata': element
                    })
        
        # Add nodes to graph
        for node in nodes:
            G.add_node(
                node['id'],
                node_type=node['type'],
                metadata=node['metadata']
            )
        
        # Add edges to graph
        for edge in edges:
            G.add_edge(
                edge['source'],
                edge['dest'],
                length=edge['length'],
                metadata=edge['metadata']
            )
    
    return G


def parse_excel_topology(file_content: bytes) -> Tuple[nx.Graph, Dict]:
    """
    Parse Excel topology file
    
    Args:
        file_content: Excel file bytes
        
    Returns:
        Tuple of (NetworkX graph, topology data dictionary)
    """
    try:
        # Read Excel sheets
        nodes_df = pd.read_excel(file_content, sheet_name='Nodes')
        links_df = pd.read_excel(file_content, sheet_name='Links')
        
        G = nx.Graph()
        
        # Add nodes
        for _, row in nodes_df.iterrows():
            node_id = row.get('Node', row.get('node_id'))
            node_type = row.get('Type', 'ROADM')
            
            G.add_node(
                node_id,
                node_type=node_type,
                metadata=row.to_dict()
            )
        
        # Add links
        for _, row in links_df.iterrows():
            source = row.get('From', row.get('source'))
            dest = row.get('To', row.get('dest'))
            length = row.get('Length', 80.0)
            
            if source and dest:
                G.add_edge(
                    source,
                    dest,
                    length=length,
                    metadata=row.to_dict()
                )
        
        topology_data = {
            'nodes': nodes_df.to_dict('records'),
            'links': links_df.to_dict('records')
        }
        
        return G, topology_data
        
    except Exception as e:
        return nx.Graph(), {'error': str(e)}


def generate_linear_topology(num_nodes: int, span_length: float = 80.0) -> Tuple[nx.Graph, Dict]:
    """
    Generate a linear topology
    
    Args:
        num_nodes: Number of nodes
        span_length: Length of each span in km
        
    Returns:
        Tuple of (NetworkX graph, topology data)
    """
    G = nx.path_graph(num_nodes)
    
    # Add node attributes
    for i in range(num_nodes):
        node_type = 'ROADM' if i % 3 == 0 else 'ILA'
        G.nodes[i]['node_type'] = node_type
        G.nodes[i]['uid'] = f'Node_{i}'
    
    # Add edge attributes
    for i in range(num_nodes - 1):
        G.edges[i, i+1]['length'] = span_length
        G.edges[i, i+1]['type'] = 'Fiber'
    
    # Convert to topology dictionary
    topology_data = graph_to_json(G)
    
    return G, topology_data


def generate_random_topology(
    num_nodes: int,
    density: float = 0.3,
    min_span_length: float = 50.0,
    max_span_length: float = 100.0
) -> Tuple[nx.Graph, Dict]:
    """
    Generate a random network topology
    
    Args:
        num_nodes: Number of nodes
        density: Network density (0-1)
        min_span_length: Minimum span length in km
        max_span_length: Maximum span length in km
        
    Returns:
        Tuple of (NetworkX graph, topology data)
    """
    import random
    
    # Create random graph
    G = nx.erdos_renyi_graph(num_nodes, density)
    
    # Add node attributes
    for i in range(num_nodes):
        node_type = 'ROADM' if random.random() > 0.3 else 'ILA'
        G.nodes[i]['node_type'] = node_type
        G.nodes[i]['uid'] = f'Node_{i}'
    
    # Add edge attributes
    for edge in G.edges():
        span_length = random.uniform(min_span_length, max_span_length)
        G.edges[edge]['length'] = span_length
        G.edges[edge]['type'] = 'Fiber'
    
    topology_data = graph_to_json(G)
    
    return G, topology_data


def generate_national_network(
    num_nodes: int,
    region_size: Tuple[float, float] = (1000, 1000)
) -> Tuple[nx.Graph, Dict]:
    """
    Generate a random national network with geographic constraints
    
    Args:
        num_nodes: Number of nodes
        region_size: (width, height) of region in km
        
    Returns:
        Tuple of (NetworkX graph, topology data)
    """
    import random
    import math
    
    # Generate random geographic positions
    positions = {}
    for i in range(num_nodes):
        x = random.uniform(0, region_size[0])
        y = random.uniform(0, region_size[1])
        positions[i] = (x, y)
    
    # Connect nodes based on geographic proximity
    G = nx.Graph()
    
    # Add nodes
    for i in range(num_nodes):
        G.add_node(i, node_type='ROADM', uid=f'Node_{i}', pos=positions[i])
    
    # Add edges for nearby nodes
    threshold_distance = math.sqrt(region_size[0]**2 + region_size[1]**2) * 0.3
    
    for i in range(num_nodes):
        for j in range(i+1, num_nodes):
            pos_i = positions[i]
            pos_j = positions[j]
            
            distance = math.sqrt((pos_i[0] - pos_j[0])**2 + (pos_i[1] - pos_j[1])**2)
            
            if distance < threshold_distance:
                G.add_edge(i, j, length=distance, type='Fiber')
    
    # Ensure connectivity
    if not nx.is_connected(G):
        components = list(nx.connected_components(G))
        for i in range(len(components) - 1):
            # Connect each component to the next
            node1 = list(components[i])[0]
            node2 = list(components[i+1])[0]
            pos1 = positions[node1]
            pos2 = positions[node2]
            distance = math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)
            G.add_edge(node1, node2, length=distance, type='Fiber')
    
    topology_data = graph_to_json(G)
    
    return G, topology_data


def graph_to_json(G: nx.Graph) -> Dict:
    """
    Convert NetworkX graph to GNPy JSON format
    
    Args:
        G: NetworkX graph
        
    Returns:
        Topology dictionary in GNPy format
    """
    elements = []
    
    # Add nodes
    for node, data in G.nodes(data=True):
        element = {
            'uid': data.get('uid', str(node)),
            'type': data.get('node_type', 'ROADM')
        }
        # Add additional metadata
        if 'metadata' in data:
            element.update(data['metadata'])
        
        elements.append(element)
    
    # Add edges
    for source, dest, data in G.edges(data=True):
        source_uid = G.nodes[source].get('uid', str(source))
        dest_uid = G.nodes[dest].get('uid', str(dest))
        
        element = {
            'type': 'Fiber',
            'from': source_uid,
            'to': dest_uid,
            'length': data.get('length', 80.0)
        }
        
        if 'metadata' in data:
            element.update(data['metadata'])
        
        elements.append(element)
    
    return {'elements': elements}


def get_node_list(G: nx.Graph, node_type: Optional[str] = None) -> List[str]:
    """
    Get list of nodes, optionally filtered by type
    
    Args:
        G: NetworkX graph
        node_type: Filter by node type (e.g., 'ROADM')
        
    Returns:
        List of node IDs
    """
    nodes = []
    
    for node, data in G.nodes(data=True):
        if node_type is None or data.get('node_type') == node_type:
            nodes.append(data.get('uid', str(node)))
    
    return sorted(nodes)


def get_roadm_nodes(G: nx.Graph) -> List[str]:
    """Get list of ROADM nodes only"""
    return get_node_list(G, 'ROADM')


def calculate_topology_metrics(G: nx.Graph) -> Dict:
    """
    Calculate basic topology metrics
    
    Args:
        G: NetworkX graph
        
    Returns:
        Dictionary of metrics
    """
    metrics = {
        'num_nodes': G.number_of_nodes(),
        'num_edges': G.number_of_edges(),
        'is_connected': nx.is_connected(G),
        'average_degree': sum(dict(G.degree()).values()) / G.number_of_nodes() if G.number_of_nodes() > 0 else 0,
    }
    
    # Calculate total network length
    total_length = sum(data.get('length', 0) for _, _, data in G.edges(data=True))
    metrics['total_length_km'] = total_length
    
    # Count node types
    node_types = {}
    for _, data in G.nodes(data=True):
        ntype = data.get('node_type', 'Unknown')
        node_types[ntype] = node_types.get(ntype, 0) + 1
    metrics['node_types'] = node_types
    
    return metrics


def validate_topology(G: nx.Graph) -> Tuple[bool, List[str]]:
    """
    Validate topology for consistency
    
    Args:
        G: NetworkX graph
        
    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []
    
    # Check if graph is empty
    if G.number_of_nodes() == 0:
        errors.append("Topology has no nodes")
    
    # Check connectivity
    if G.number_of_nodes() > 1 and not nx.is_connected(G):
        errors.append("Topology is not connected")
    
    # Check for isolated nodes
    isolated = list(nx.isolates(G))
    if isolated:
        errors.append(f"Found {len(isolated)} isolated nodes")
    
    # Check for missing node UIDs
    for node, data in G.nodes(data=True):
        if 'uid' not in data:
            errors.append(f"Node {node} missing UID")
    
    # Check for missing edge lengths
    for source, dest, data in G.edges(data=True):
        if 'length' not in data:
            errors.append(f"Edge {source}-{dest} missing length")
    
    is_valid = len(errors) == 0
    
    return is_valid, errors
