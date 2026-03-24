# GNPy Simulator Project

## 🎯 Project Overview

A comprehensive Streamlit web application that replicates the functionality of https://gnpy.app for optical network path computation and simulation using the GNPy (Gaussian Noise Python) library.

## 📁 Project Structure

```
GNPy-Simulator/
│
├── app.py                      # Main Streamlit application (700+ lines)
│   ├── Equipment library management
│   ├── Network auto-design configuration
│   ├── Topology upload and visualization
│   ├── Path computation interface
│   ├── Results display and analysis
│   └── Session state management
│
├── utils/                      # Utility modules
│   ├── __init__.py            # Package initialization
│   ├── gnpy_wrapper.py        # GNPy library integration (400+ lines)
│   │   ├── Equipment library loading
│   │   ├── Network creation and auto-design
│   │   ├── Path computation and simulation
│   │   ├── Power sweep analysis
│   │   └── Transceiver mode optimization
│   │
│   ├── topology.py            # Topology handling (450+ lines)
│   │   ├── JSON/Excel topology parsing
│   │   ├── Network graph creation
│   │   ├── Topology generation (linear, random, national)
│   │   ├── Format conversion
│   │   └── Validation
│   │
│   └── visualization.py       # Visualization utilities (500+ lines)
│       ├── Network graph plotting (matplotlib & plotly)
│       ├── Signal/noise spectrum plots
│       ├── Power sweep visualization
│       ├── Path profile charts
│       └── Interactive topology display
│
├── examples/                   # Example data files
│   ├── README.md              # Example files documentation
│   ├── simple_topology.json   # 3-node linear topology
│   ├── simple_equipment.json  # Standard equipment library
│   └── simple_services.json   # Sample service requests
│
├── .streamlit/                # Streamlit configuration
│   └── config.toml           # UI theme and server settings
│
├── requirements.txt           # Python dependencies
├── README.md                  # Main documentation (comprehensive)
├── QUICKSTART.md             # Quick start guide
├── LICENSE                    # BSD 3-Clause License
├── .gitignore                # Git ignore rules
├── start.bat                 # Windows quick start script
└── test_installation.py      # Installation verification script

```

## ✨ Features Implemented

### 1. Equipment Library (Section 1)
- ✅ Upload custom equipment JSON files
- ✅ Select from example libraries
- ✅ OpenROADM v4 and v5 support
- ✅ Equipment summary display
- ✅ Advanced EDFA model support

### 2. Network Auto-Design (Section 2)
- ✅ Power mode operation
- ✅ Gain mode operation
- ✅ Configurable span lengths
- ✅ Target power settings
- ✅ OpenROADM MSA compliance
- ✅ Channel configuration

### 3. Network Topology (Section 3)
- ✅ JSON topology upload
- ✅ Excel topology support
- ✅ Example topology selection
- ✅ Linear topology generation
- ✅ Random network generation
- ✅ National network generation
- ✅ Interactive visualization
- ✅ Save/download functionality

### 4. Simulation Parameters (Section 4)
- ✅ Raman fiber configuration
- ✅ Custom parameter upload
- ✅ Default parameters

### 5. Services (Section 5)
- ✅ JSON/Excel service upload
- ✅ Batch path requests
- ✅ Automatic computation
- ✅ Export responses (JSON/CSV)

### 6. Path Configuration (Section 6)
- ✅ Multi-path computation
- ✅ Diverse path calculation
- ✅ Reverse path calculation
- ✅ Source/destination selection
- ✅ Include/exclude node constraints
- ✅ Transceiver type selection
- ✅ Mode optimization (capacity maximization)
- ✅ Spectral load configuration
- ✅ ROADM parameters
- ✅ Power sweep analysis
- ✅ Real-time computation

### 7. Results Display (Section 7)
- ✅ Summary metrics (GSNR, OSNR, length, loss)
- ✅ Path feasibility indication
- ✅ Detailed path information
- ✅ Signal spectrum plots
- ✅ Noise spectrum plots
- ✅ Power sweep graphs
- ✅ Path visualization on topology
- ✅ CD, PMD, PDL metrics
- ✅ Export capabilities

## 🔧 Technical Implementation

### Core Technologies
- **Streamlit**: Web interface framework
- **NetworkX**: Graph data structures and algorithms
- **Matplotlib**: Static plotting
- **Plotly**: Interactive visualizations
- **Pandas**: Data manipulation
- **NumPy**: Numerical computations
- **GNPy**: Optical network simulation (optional, with fallback)

### Application Architecture
```
┌─────────────────────────────────────────────┐
│          Streamlit UI Layer                 │
│  (app.py - 7 sections with navigation)      │
└────────────┬────────────────────────────────┘
             │
┌────────────▼────────────────────────────────┐
│         Business Logic Layer                │
│  ┌──────────────────────────────────────┐   │
│  │  utils/gnpy_wrapper.py               │   │
│  │  - GNPy integration                  │   │
│  │  - Path computation                  │   │
│  │  - Auto-design                       │   │
│  └──────────────────────────────────────┘   │
│  ┌──────────────────────────────────────┐   │
│  │  utils/topology.py                   │   │
│  │  - Topology parsing                  │   │
│  │  - Graph generation                  │   │
│  │  - Format conversion                 │   │
│  └──────────────────────────────────────┘   │
│  ┌──────────────────────────────────────┐   │
│  │  utils/visualization.py              │   │
│  │  - Network plots                     │   │
│  │  - Result charts                     │   │
│  └──────────────────────────────────────┘   │
└────────────┬────────────────────────────────┘
             │
┌────────────▼────────────────────────────────┐
│            Data Layer                       │
│  - Session state management                 │
│  - File uploads (in-memory)                 │
│  - Example data files                       │
└─────────────────────────────────────────────┘
```

### Session State Management
```python
- equipment_data: Loaded equipment library
- topology_data: Network topology
- network_graph: NetworkX graph object
- sim_params: Simulation parameters
- services_data: Service requests
- source_node: Selected source
- destination_node: Selected destination
- results: Computation results
```

## 🚀 Getting Started

### Quick Start (3 commands)
```bash
pip install -r requirements.txt
python test_installation.py
streamlit run app.py
```

### Windows Users
Simply double-click `start.bat`

### First Run Workflow
1. Section 1: Select "Default Equipment Library"
2. Section 3: Select "Linear Topology" → Generate
3. Section 6: Select nodes → Click "Compute"
4. Section 7: View results

## 📊 Key Capabilities

| Feature | Status | Notes |
|---------|--------|-------|
| Equipment Management | ✅ Complete | JSON upload + examples |
| Auto-Design | ✅ Complete | Power/gain modes |
| Topology Visualization | ✅ Complete | Interactive graphs |
| Path Computation | ✅ Complete | Multi-path support |
| Power Sweep | ✅ Complete | GSNR/OSNR analysis |
| Mode Optimization | ✅ Complete | Capacity maximization |
| Services Batch Processing | ✅ Complete | JSON/CSV export |
| OpenROADM Support | ✅ Complete | v4 & v5 MSA |
| Real GNPy Integration | ⚠️ Partial | Falls back to mock data if GNPy not installed |

## 🧪 Testing

Run comprehensive tests:
```bash
python test_installation.py
```

Tests verify:
- Package installations
- Utility module functionality
- Example file validity
- Application syntax
- Component integration

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| **README.md** | Complete feature documentation |
| **QUICKSTART.md** | Step-by-step guide for beginners |
| **examples/README.md** | Example file documentation |
| **LICENSE** | BSD 3-Clause license terms |

## 🎨 User Interface

### Navigation
- Sidebar with 7 main sections
- Sequential workflow design
- Progress tracking
- Contextual help text

### Visual Design
- Professional color scheme (blues, greens)
- Responsive layout
- Interactive graphs
- Clear metrics display
- Intuitive file uploaders

### User Experience
- No server-side storage (privacy)
- Real-time validation
- Progress indicators
- Error handling with helpful messages
- Download/export capabilities

## 🔌 GNPy Integration

The application integrates with GNPy for:
- Optical propagation simulation
- EDFA auto-design
- OSNR/GSNR calculation
- Chromatic dispersion
- PMD and PDL effects

**Fallback Mode**: If GNPy is not installed, the application uses realistic mock data for demonstration purposes.

## 📈 Performance

- Instant topology visualization
- Sub-second path computation (small networks)
- Efficient session state management
- Responsive UI updates
- Memory-efficient file handling

## 🔐 Security & Privacy

- No files stored on server
- All processing in-memory
- Session-based data isolation
- Safe file upload handling
- XSRF protection enabled

## 🌐 Deployment Options

### Local Development
```bash
streamlit run app.py
```

### Streamlit Cloud
1. Push to GitHub
2. Connect to Streamlit Cloud
3. Deploy with requirements.txt

### Docker (Future)
- Dockerfile can be added
- Include GNPy dependencies
- Expose port 8501

## 🛠️ Customization

### Adding New Equipment
- Upload custom JSON in Section 1
- Follows GNPy equipment schema

### Custom Topologies
- Upload JSON/Excel in Section 3
- Or modify example files

### Extending Functionality
- Add new sections to `app.py`
- Create new utilities in `utils/`
- Extend visualization options

## 📝 Future Enhancements

Potential additions:
- [ ] Real-time collaborative editing
- [ ] Database integration for projects
- [ ] Advanced filtering and search
- [ ] Comparison between multiple paths
- [ ] Network optimization algorithms
- [ ] Cost analysis
- [ ] Multi-vendor equipment support
- [ ] API endpoint exposure

## 🤝 Integration with GNPy Ecosystem

Compatible with:
- GNPy command-line tools
- TransportPCE controller
- OpenROADM equipment
- Standard JSON formats
- Excel input/output

## 💡 Tips for Users

1. **Start Simple**: Use example files first
2. **Iterate**: Make small changes and test
3. **Export Often**: Save topologies you like
4. **Read Tooltips**: Hover over (?) icons
5. **Check GNPy Docs**: For format specifications

## 📞 Support Resources

- **GNPy Docs**: https://gnpy.readthedocs.io/
- **GNPy GitHub**: https://github.com/Telecominfraproject/oopt-gnpy
- **Excel Format**: https://gnpy.readthedocs.io/en/master/excel.html
- **Test Script**: Run `python test_installation.py`

## ✅ Quality Assurance

- All code syntax validated
- Utility modules tested
- Example files validated
- Error handling implemented
- User-friendly messages
- Clear documentation

## 🎉 Achievement Summary

**Total Lines of Code**: ~2,500+
**Files Created**: 16
**Sections Implemented**: 7 complete
**Example Files**: 3 working examples
**Utility Modules**: 3 comprehensive
**Documentation Pages**: 4 detailed guides

---

**Ready to simulate optical networks!** 🌐📡🔬
