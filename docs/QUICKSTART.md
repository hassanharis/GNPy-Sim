# GNPy Simulator - Quick Start Guide

## Installation

### Step 1: Install Python
Make sure you have Python 3.8 or higher installed:
```bash
python --version
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

## Running the Application

### Option 1: Quick Start (Windows)
Double-click `start.bat`

### Option 2: Command Line
```bash
streamlit run app.py
```

The application will open automatically in your browser at `http://localhost:8501`

## First Time User Guide

### Simple Workflow

1. **Start with Example Data**
   - Go to "1. Equipment Library"
   - Select "Default Equipment Library" from dropdown
   - Click "Load Example Equipment File"

2. **Load Network Topology**
   - Go to "3. Network Topology"
   - Select "Mesh Topology Example" or "Linear Topology"
   - If Linear, configure number of nodes and click "Generate Topology"

3. **Configure Path**
   - Go to "6. Path Configuration"
   - Select source and destination from dropdowns
   - Leave other settings at default
   - Click "Compute and Simulate Paths"

4. **View Results**
   - Go to "7. Results"
   - See summary metrics
   - Click detail buttons for more information

### Advanced Features

#### Upload Custom Files
- Equipment library: JSON format
- Network topology: JSON or Excel format
- Services: JSON or Excel format

#### Auto-Design
- Go to "2. Auto-Design Parameters"
- Choose "Power Mode" or "Gain Mode"
- Configure target power and span length

#### Power Sweep
- Go to "6. Path Configuration"
- Enable "Enable power sweep"
- Set start, stop, and step values
- Results will show GSNR/OSNR vs power graph

#### Transceiver Optimization
- Select "Maximize capacity" in transceiver mode
- System will find optimal modulation format

## Example Files

### Equipment Library Example
```json
{
  "Edfa": [
    {
      "type_variety": "std_medium_gain",
      "gain_flatmax": 25,
      "gain_min": 15,
      "p_max": 21,
      "nf_min": 5.5
    }
  ],
  "Fiber": [
    {
      "type_variety": "SSMF",
      "dispersion": 1.67e-05,
      "gamma": 0.00127
    }
  ]
}
```

### Simple Topology Example
```json
{
  "elements": [
    {"uid": "NodeA", "type": "ROADM"},
    {"uid": "NodeB", "type": "ROADM"},
    {"type": "Fiber", "from": "NodeA", "to": "NodeB", "length": 80.0}
  ]
}
```

## Troubleshooting

### Application won't start
```bash
# Reinstall dependencies
pip install -r requirements.txt --upgrade

# Try running directly
python -m streamlit run app.py
```

### "Module not found" errors
```bash
# Install individual packages
pip install streamlit gnpy pandas networkx matplotlib
```

### GNPy not installed
```bash
pip install gnpy
```

### Port already in use
```bash
# Use different port
streamlit run app.py --server.port 8502
```

## Tips

1. **No files are stored** - All processing happens in memory
2. **Use sidebar** - Navigate between sections using sidebar
3. **Download results** - Use download buttons to save configurations
4. **Start simple** - Begin with example files before custom data
5. **Check GNPy docs** - For detailed format specifications

## Getting Help

- GNPy Documentation: https://gnpy.readthedocs.io/
- GNPy GitHub: https://github.com/Telecominfraproject/oopt-gnpy
- Excel Format Guide: https://gnpy.readthedocs.io/en/master/excel.html

## Common Use Cases

### 1. Quick Path Analysis
Load example topology → Select nodes → Compute path → View OSNR

### 2. Network Design
Upload topology → Configure auto-design → Generate network → Save

### 3. Power Optimization
Load network → Enable power sweep → Find optimal power level

### 4. Batch Processing
Upload services file → Automatic computation → Export results

## Keyboard Shortcuts

- `Ctrl + C` - Stop server (in terminal)
- `R` - Rerun application
- `C` - Clear cache

## Next Steps

1. Try the example workflows above
2. Upload your own network topology
3. Experiment with different transceiver modes
4. Explore power sweep analysis
5. Read the full README.md for details

---

**Need help?** Check the GNPy documentation or open an issue in the repository.
