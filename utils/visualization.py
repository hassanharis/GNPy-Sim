"""
Visualization Utilities
Functions for creating network graphs and result plots
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import networkx as nx
import numpy as np
from typing import Dict, List, Optional, Tuple
import plotly.graph_objects as go
import plotly.express as px


def plot_network_topology(
    G: nx.Graph,
    highlight_path: Optional[List[str]] = None,
    node_colors: Optional[Dict[str, str]] = None,
    figsize: Tuple[int, int] = (12, 8),
    layout: str = 'spring'
) -> plt.Figure:
    """
    Create a matplotlib figure of the network topology
    
    Args:
        G: NetworkX graph
        highlight_path: List of nodes to highlight as path
        node_colors: Dictionary mapping node types to colors
        figsize: Figure size
        layout: Layout algorithm ('spring', 'circular', 'kamada_kawai')
        
    Returns:
        Matplotlib figure
    """
    fig, ax = plt.subplots(figsize=figsize)
    
    # Default node colors
    if node_colors is None:
        node_colors = {
            'ROADM': '#4A90E2',
            'ILA': '#7ED321',
            'Transceiver': '#F5A623',
            'Fused': '#BD10E0',
            'default': '#D0D0D0'
        }
    
    # Calculate layout
    if layout == 'spring':
        pos = nx.spring_layout(G, k=1, iterations=50, seed=42)
    elif layout == 'circular':
        pos = nx.circular_layout(G)
    elif layout == 'kamada_kawai':
        pos = nx.kamada_kawai_layout(G)
    else:
        pos = nx.spring_layout(G)
    
    # Determine node colors based on type
    node_color_list = []
    for node in G.nodes():
        node_type = G.nodes[node].get('node_type', 'default')
        color = node_colors.get(node_type, node_colors.get('default'))
        node_color_list.append(color)
    
    # Draw all edges
    nx.draw_networkx_edges(
        G, pos,
        edge_color='#CCCCCC',
        width=2,
        alpha=0.6,
        ax=ax
    )
    
    # Highlight path if provided
    if highlight_path and len(highlight_path) > 1:
        path_edges = [(highlight_path[i], highlight_path[i+1]) 
                      for i in range(len(highlight_path)-1)]
        nx.draw_networkx_edges(
            G, pos,
            edgelist=path_edges,
            edge_color='#E74C3C',
            width=4,
            alpha=0.9,
            ax=ax
        )
    
    # Draw nodes
    nx.draw_networkx_nodes(
        G, pos,
        node_color=node_color_list,
        node_size=500,
        alpha=0.9,
        ax=ax
    )
    
    # Draw labels
    labels = {}
    for node in G.nodes():
        labels[node] = G.nodes[node].get('uid', str(node))
    
    nx.draw_networkx_labels(
        G, pos,
        labels=labels,
        font_size=8,
        font_weight='bold',
        ax=ax
    )
    
    # Add legend
    legend_elements = []
    for node_type, color in node_colors.items():
        if node_type != 'default':
            legend_elements.append(
                mpatches.Patch(color=color, label=node_type)
            )
    
    ax.legend(handles=legend_elements, loc='upper right')
    ax.set_title('Network Topology', fontsize=14, fontweight='bold')
    ax.axis('off')
    
    plt.tight_layout()
    return fig


def plot_interactive_topology(
    G: nx.Graph,
    highlight_path: Optional[List[str]] = None
) -> go.Figure:
    """
    Create an interactive Plotly figure of the network topology
    
    Args:
        G: NetworkX graph
        highlight_path: List of nodes to highlight
        
    Returns:
        Plotly figure
    """
    # Calculate layout
    pos = nx.spring_layout(G, k=1, iterations=50, seed=42)
    
    # Create edge traces
    edge_x = []
    edge_y = []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])
    
    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=2, color='#CCCCCC'),
        hoverinfo='none',
        mode='lines'
    )
    
    # Create node traces
    node_x = []
    node_y = []
    node_text = []
    node_color = []
    
    color_map = {
        'ROADM': '#4A90E2',
        'ILA': '#7ED321',
        'Transceiver': '#F5A623',
        'Fused': '#BD10E0',
        'default': '#D0D0D0'
    }
    
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        
        uid = G.nodes[node].get('uid', str(node))
        node_type = G.nodes[node].get('node_type', 'Unknown')
        node_text.append(f"{uid}<br>Type: {node_type}")
        
        color = color_map.get(node_type, color_map['default'])
        node_color.append(color)
    
    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        hoverinfo='text',
        text=[G.nodes[node].get('uid', str(node)) for node in G.nodes()],
        textposition='top center',
        hovertext=node_text,
        marker=dict(
            size=20,
            color=node_color,
            line=dict(width=2, color='white')
        )
    )
    
    # Create figure
    fig = go.Figure(
        data=[edge_trace, node_trace],
        layout=go.Layout(
            title='Interactive Network Topology',
            showlegend=False,
            hovermode='closest',
            margin=dict(b=0, l=0, r=0, t=40),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            plot_bgcolor='white'
        )
    )
    
    return fig


def plot_signal_spectrum(
    frequencies: np.ndarray,
    power: np.ndarray,
    title: str = 'Signal Spectrum',
    figsize: Tuple[int, int] = (10, 5)
) -> plt.Figure:
    """
    Plot signal spectrum
    
    Args:
        frequencies: Frequency array in THz
        power: Power array in dBm
        title: Plot title
        figsize: Figure size
        
    Returns:
        Matplotlib figure
    """
    fig, ax = plt.subplots(figsize=figsize)
    
    ax.plot(frequencies, power, linewidth=2, color='#4A90E2')
    ax.fill_between(frequencies, power, alpha=0.3, color='#4A90E2')
    
    ax.set_xlabel('Frequency (THz)', fontsize=12)
    ax.set_ylabel('Power (dBm)', fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    return fig


def plot_noise_spectrum(
    frequencies: np.ndarray,
    nli: np.ndarray,
    ase: Optional[np.ndarray] = None,
    title: str = 'Noise Spectrum',
    figsize: Tuple[int, int] = (10, 5)
) -> plt.Figure:
    """
    Plot noise spectrum (NLI and optionally ASE)
    
    Args:
        frequencies: Frequency array in THz
        nli: NLI power array in dBm
        ase: ASE power array in dBm (optional)
        title: Plot title
        figsize: Figure size
        
    Returns:
        Matplotlib figure
    """
    fig, ax = plt.subplots(figsize=figsize)
    
    ax.plot(frequencies, nli, linewidth=2, color='#E74C3C', label='NLI')
    
    if ase is not None:
        ax.plot(frequencies, ase, linewidth=2, color='#F5A623', label='ASE')
    
    ax.set_xlabel('Frequency (THz)', fontsize=12)
    ax.set_ylabel('Noise Power (dBm)', fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    return fig


def plot_power_sweep(
    powers: List[float],
    gsnr: List[float],
    osnr: List[float],
    required_osnr: Optional[float] = None,
    figsize: Tuple[int, int] = (10, 6)
) -> plt.Figure:
    """
    Plot power sweep results
    
    Args:
        powers: Reference power values in dBm
        gsnr: GSNR values in dB
        osnr: OSNR values in dB
        required_osnr: Required OSNR threshold
        figsize: Figure size
        
    Returns:
        Matplotlib figure
    """
    fig, ax = plt.subplots(figsize=figsize)
    
    ax.plot(powers, gsnr, 'o-', linewidth=2, markersize=8,
            color='#4A90E2', label='GSNR')
    ax.plot(powers, osnr, 's-', linewidth=2, markersize=8,
            color='#7ED321', label='OSNR')
    
    if required_osnr is not None:
        ax.axhline(y=required_osnr, color='#E74C3C', linestyle='--',
                   linewidth=2, label=f'Required OSNR ({required_osnr} dB)')
    
    ax.set_xlabel('Reference Power (dBm)', fontsize=12)
    ax.set_ylabel('OSNR/GSNR (dB)', fontsize=12)
    ax.set_title('GSNR/OSNR vs. Reference Power', fontsize=14, fontweight='bold')
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    return fig


def plot_path_profile(
    segments: List[Dict],
    figsize: Tuple[int, int] = (12, 6)
) -> plt.Figure:
    """
    Plot path profile showing power evolution along the path
    
    Args:
        segments: List of path segments with power information
        figsize: Figure size
        
    Returns:
        Matplotlib figure
    """
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize, sharex=True)
    
    distances = [seg['distance'] for seg in segments]
    powers = [seg['power'] for seg in segments]
    osnr_values = [seg['osnr'] for seg in segments]
    
    # Power profile
    ax1.plot(distances, powers, 'o-', linewidth=2, markersize=6, color='#4A90E2')
    ax1.set_ylabel('Power (dBm)', fontsize=12)
    ax1.set_title('Path Profile', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    
    # OSNR profile
    ax2.plot(distances, osnr_values, 's-', linewidth=2, markersize=6, color='#7ED321')
    ax2.set_xlabel('Distance (km)', fontsize=12)
    ax2.set_ylabel('OSNR (dB)', fontsize=12)
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    return fig


def plot_osnr_vs_distance(
    paths: List[Dict],
    figsize: Tuple[int, int] = (10, 6)
) -> plt.Figure:
    """
    Plot OSNR vs distance for multiple paths
    
    Args:
        paths: List of path dictionaries with distance and OSNR
        figsize: Figure size
        
    Returns:
        Matplotlib figure
    """
    fig, ax = plt.subplots(figsize=figsize)
    
    colors = ['#4A90E2', '#E74C3C', '#7ED321', '#F5A623', '#BD10E0']
    
    for idx, path in enumerate(paths):
        color = colors[idx % len(colors)]
        ax.plot(
            path['distance'],
            path['osnr'],
            'o-',
            linewidth=2,
            markersize=6,
            color=color,
            label=path.get('name', f'Path {idx+1}')
        )
    
    ax.set_xlabel('Distance (km)', fontsize=12)
    ax.set_ylabel('OSNR (dB)', fontsize=12)
    ax.set_title('OSNR vs. Distance', fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    return fig


def create_summary_table(results: Dict) -> str:
    """
    Create HTML table for results summary
    
    Args:
        results: Results dictionary
        
    Returns:
        HTML string
    """
    html = """
    <style>
        .summary-table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        .summary-table th, .summary-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        .summary-table th {
            background-color: #4A90E2;
            color: white;
            font-weight: bold;
        }
        .summary-table tr:hover {
            background-color: #f5f5f5;
        }
        .feasible {
            color: #7ED321;
            font-weight: bold;
        }
        .not-feasible {
            color: #E74C3C;
            font-weight: bold;
        }
    </style>
    <table class="summary-table">
        <tr>
            <th>Metric</th>
            <th>Value</th>
        </tr>
    """
    
    metrics = [
        ('Path Length', f"{results.get('path_length', 0):.1f} km"),
        ('GSNR', f"{results.get('gsnr', 0):.2f} dB"),
        ('OSNR', f"{results.get('osnr', 0):.2f} dB"),
        ('Number of Spans', str(results.get('num_spans', 0))),
        ('Number of EDFAs', str(results.get('num_edfas', 0))),
        ('Total Loss', f"{results.get('total_loss', 0):.2f} dB"),
        ('Chromatic Dispersion', f"{results.get('cd', 0):.0f} ps/nm"),
        ('PMD', f"{results.get('pmd', 0):.2f} ps"),
        ('PDL', f"{results.get('pdl', 0):.2f} dB"),
    ]
    
    for metric, value in metrics:
        html += f"<tr><td>{metric}</td><td>{value}</td></tr>"
    
    feasible = results.get('feasible', False)
    feasible_class = 'feasible' if feasible else 'not-feasible'
    feasible_text = '✓ Feasible' if feasible else '✗ Not Feasible'
    
    html += f'<tr><td>Feasibility</td><td class="{feasible_class}">{feasible_text}</td></tr>'
    html += "</table>"
    
    return html


def plot_capacity_vs_distance(
    distances: List[float],
    capacities: List[float],
    modes: List[str],
    figsize: Tuple[int, int] = (10, 6)
) -> plt.Figure:
    """
    Plot achievable capacity vs distance for different modulation modes
    
    Args:
        distances: Distance values in km
        capacities: Capacity values in Gbps
        modes: Modulation mode names
        figsize: Figure size
        
    Returns:
        Matplotlib figure
    """
    fig, ax = plt.subplots(figsize=figsize)
    
    colors = ['#4A90E2', '#E74C3C', '#7ED321', '#F5A623']
    
    for idx, mode in enumerate(set(modes)):
        mode_distances = [d for d, m in zip(distances, modes) if m == mode]
        mode_capacities = [c for c, m in zip(capacities, modes) if m == mode]
        
        if mode_distances:
            ax.plot(
                mode_distances,
                mode_capacities,
                'o-',
                linewidth=2,
                markersize=6,
                color=colors[idx % len(colors)],
                label=mode
            )
    
    ax.set_xlabel('Distance (km)', fontsize=12)
    ax.set_ylabel('Capacity (Gbps)', fontsize=12)
    ax.set_title('Achievable Capacity vs. Distance', fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    return fig


def generate_node_info_popup(node_data: Dict) -> str:
    """
    Generate HTML popup content for node information
    
    Args:
        node_data: Node data dictionary
        
    Returns:
        HTML string
    """
    html = f"""
    <div style="padding: 10px;">
        <h4 style="margin: 0 0 10px 0;">{node_data.get('uid', 'Unknown')}</h4>
        <p><strong>Type:</strong> {node_data.get('node_type', 'Unknown')}</p>
    """
    
    if 'location' in node_data:
        html += f"<p><strong>Location:</strong> {node_data['location']}</p>"
    
    if 'degree' in node_data:
        html += f"<p><strong>Degree:</strong> {node_data['degree']}</p>"
    
    html += "</div>"
    
    return html
