# Network Topologies (TransNet and TNPS formats)

This directory contains network topology files in TransNet and TNPS formats. These files define the structure and 
configuration of various network topologies used for network simulations and research.

## Directory Structure

- `transnet/`: Contains network topology files in TransNet format.
  - `transnet/DT/`: Contains the DT (Deutsche Telekom) files.
  - `transnet/TEF/`: Contains the TEF (Telefónica) files.
  - `transnet/TIM National/`: Contains the TIM (Telecom Italia) files.
  - `transnet/CORONET/`: Contains the CORONET (Continental USA) files.
- `topologies/tnps/`: Contains network topology files in TNPS format.

## Usage

Load and plot a topology in your Python project:

```python
from tools.folders import Folders
from interfaces.cpe_interface.parameters import create_simple_topology
from interfaces.network.network_plot import plot_topology

from research_tools.plot import show

# Example of DT plotting
topology = create_simple_topology(Folders.transnet_path('DT'))

fig, ax = plot_topology(
    network=topology,
    x_lim=[5.7, 14.4], y_lim=[47.2, 54.5], fig_size=(3, 3),
    nodes_position=None, node_size=100, node_color='lightblue',
    show_nodes_labels=True, node_font_size=14,
    shift_x=0.2, shift_y=0.0,
    dict_node_shift=None,
    node_icon_name='OTS', node_icon_size=0.04,
    plot_edges=True, edges_width=2, edges_style='-', edges_color='navy',
    plot_map=True, map_edge_color='dimgrey', map_color='gainsboro'
)

fig.tight_layout()

show()
```