# GNPy Optical Network Simulator - Streamlit Implementation

A web-based interface for optical network path computation and simulation using GNPy (Gaussian Noise Python), built with Streamlit.

## Overview

This application replicates the functionality of [gnpy.app](https://gnpy.app/) providing a user-friendly interface for:
- Optical network design and simulation
- Path computation and optimization
- EDFA auto-design
- Power sweep analysis
- Network topology visualization

## Features

### 1. Equipment Library Management
- Upload custom equipment library (JSON)
- Select from pre-configured examples (Default, OpenROADM v4, OpenROADM v5)
- Support for advanced EDFA models

### 2. Network Auto-Design
- Power mode or gain mode operation
- Automatic EDFA insertion and configuration
- OpenROADM MSA compliance (ver. 4 & 5)
- Configurable span lengths and power levels

### 3. Network Topology
- Upload topology files (JSON, Excel)
- Select from example topologies
- Generate random or linear topologies
- Interactive network visualization
- Save/download network configurations

### 4. Simulation Parameters
- Raman fiber support
- Custom simulation parameter configuration
- Default parameter templates

### 5. Service Configuration
- Upload service request files (JSON, Excel)
- Automatic path computation upon service load
- Export path responses (JSON, CSV)

### 6. Path Configuration
- Multi-path computation
- Diverse and reverse path options
- Source/destination selection
- Include/exclude node constraints
- Transceiver type and mode selection
- Capacity maximization
- Spectral load configuration
- Power sweep analysis

### 7. Results Visualization
- Path metrics (GSNR, OSNR, length, loss)
- Detailed element-by-element analysis
- Signal and noise spectrum plots
- Power sweep graphs
- Path visualization on network map
- Export results (CSV, JSON)

## Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Setup

1. Clone or download this repository

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. Install GNPy (if not already installed):
```bash
pip install gnpy
```

## Usage

### Running the Application

Start the Streamlit application:

```bash
streamlit run app.py
```

The application will open in your default web browser at `http://localhost:8501`

### Workflow

1. **Equipment Library** (Optional)
   - Upload your equipment library or select an example
   - Default library is used if none provided

2. **Auto-Design Parameters**
   - Configure EDFA auto-design settings
   - Select OpenROADM compliance if needed

3. **Network Topology**
   - Upload your network topology (JSON/Excel)
   - Or generate an example topology
   - View the network graph visualization

4. **Simulation Parameters** (Optional)
   - Upload custom simulation parameters for Raman fibers

5. **Services** (Optional)
   - Upload service requests for batch processing

6. **Path Configuration**
   - Set path computation parameters
   - Select source and destination nodes
   - Configure transceiver settings
   - Set up power sweep if needed

7. **Results**
   - View computed path metrics
   - Analyze signal and noise spectra
   - Download results

## File Formats

### Equipment Library (JSON)
Example: [eqpt_config.json](https://github.com/Telecominfraproject/oopt-gnpy/blob/master/gnpy/example-data/eqpt_config.json)

### Network Topology (JSON)
Example: [meshTopologyExampleV2.json](https://github.com/Telecominfraproject/oopt-gnpy/blob/master/gnpy/example-data/meshTopologyExampleV2.json)

### Services (JSON)
Example: [meshTopologyExampleV2_services.json](https://github.com/Telecominfraproject/oopt-gnpy/blob/master/gnpy/example-data/meshTopologyExampleV2_services.json)

### Excel Format
For Excel topology and service files, refer to the [GNPy documentation](https://gnpy.readthedocs.io/en/master/excel.html)

## Privacy Note

**No files are stored on the server.** All processing is done in-memory during your session.

## GNPy Integration

This application interfaces with the GNPy library for all optical network calculations. For detailed information about GNPy:
- [GNPy Documentation](https://gnpy.readthedocs.io/)
- [GNPy GitHub Repository](https://github.com/Telecominfraproject/oopt-gnpy)

## Architecture

```
GNPy-Simulator/
├── app.py                  # Main Streamlit application
├── requirements.txt        # Python dependencies
├── README.md              # This file
└── utils/                 # Utility modules (optional)
    ├── gnpy_wrapper.py    # GNPy integration functions
    ├── topology.py        # Topology handling
    └── visualization.py   # Visualization utilities
```

## Advanced Features

### Transceiver Mode Optimization
The application supports automatic transceiver mode selection to maximize capacity while meeting OSNR requirements.

### Power Sweep Analysis
Perform multiple simulations across a range of power levels to find optimal operating points.

### OpenROADM Compliance
Automatic configuration for MSA-compliant designs with appropriate power levels and amplifier selection.

## Troubleshooting

### Common Issues

1. **Import errors**: Ensure all requirements are installed:
   ```bash
   pip install -r requirements.txt --upgrade
   ```

2. **GNPy not found**: Install GNPy directly:
   ```bash
   pip install gnpy
   ```

3. **Matplotlib display issues**: Set backend:
   ```python
   import matplotlib
   matplotlib.use('Agg')
   ```

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues.

## License

This project uses GNPy which is licensed under the BSD 3-Clause License.

## Acknowledgments

- [GNPy Project](https://github.com/Telecominfraproject/oopt-gnpy) - The core optical network simulation library
- [Telecom Infra Project](https://telecominfraproject.com/) - Open Optical Packet Transport

## References

- GNPy Web App: https://gnpy.app/
- GNPy Documentation: https://gnpy.readthedocs.io/
- OpenROADM MSA: https://www.openroadm.org/

## Support

For GNPy-specific questions, refer to:
- [GNPy Documentation](https://gnpy.readthedocs.io/)
- [GNPy Issues](https://github.com/Telecominfraproject/oopt-gnpy/issues)

For application issues, please open an issue in this repository.
