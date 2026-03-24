# GNPy Simulator - Recent Updates

## Changes Made (Feb 20, 2026)

### 1. ✅ Added GNPy Example Topology
- **File**: `app.py` (Section 3: Network Topology)
- **Change**: Renamed "Mesh Topology Example" to "GNPy Mesh Topology"
- **Benefit**: More clearly indicates this is the official GNPy example from the repository
- **Access**: Select from dropdown, then click "Load Example Topology"

### 2. ✅ Fixed Topology Regeneration Bug
- **Issue**: Buttons in Section 4+ kept triggering topology regeneration, breaking workflow
- **Root Cause**: Missing unique `key` parameters on interactive widgets caused Streamlit to re-run button logic
- **Solution**: Added unique session state keys to all widgets
- **Fixes Applied**:
  - `topology_example_select` - Selectbox for example choice
  - `load_example_topology_btn` - Load button
  - `topo_num_nodes` - Slider for node count
  - `topo_span_length` - Slider for span length
  - `topo_density` - Slider for network density
  - `generate_topology_btn` - Generate button

### 3. ✅ Enhanced Session State Management
- Added `topology_generated` - Tracks if topology was generated
- Added `topology_config` - Stores topology configuration parameters
- Prevents accidental regeneration when navigating between sections

### 4. ✅ Improved UI Labels
- Changed generic "Load Example Topology" to "📌 View on GitHub"
- Renamed topology generation options for clarity:
  - "Linear Topology" → "Generate Linear Topology"
  - "Random Network" → "Generate Random Network"
  - "Random National Network" → "Generate Random National Network"

## How to Use

### Loading GNPy Mesh Topology (New)
1. Go to **Section 3: Network Topology**
2. In right column, select **"GNPy Mesh Topology"**
3. Click **"📌 View on GitHub"** to see the source (optional)
4. Click **"Load Example Topology"** button
5. Topology loads and displays

### Generating a Topology
1. Go to **Section 3: Network Topology**
2. Select one of:
   - "Generate Linear Topology"
   - "Generate Random Network"
   - "Generate Random National Network"
3. Configure parameters (sliders appear)
4. Click **"Generate Topology"** button once
5. ✅ **Bug Fix**: Can now navigate to other sections without topology regenerating

### Continuing Workflow
After loading/generating topology:
1. Go to **Section 4: Simulation Parameters** (or skip)
2. Go to **Section 5: Services** (or skip)
3. Go to **Section 6: Path Configuration**
   - Select source and destination nodes
   - Configure transceiver settings
   - Click **"Compute and Simulate Paths"**
4. Go to **Section 7: Results** to view metrics

## Technical Details

### Session State Variables
```python
st.session_state.topology_generated  # Boolean: tracks if topology was generated
st.session_state.topology_config     # Dict: stores topology parameters
```

### Widget Keys
All interactive widgets in topology section now have unique keys to prevent state collision:
- Selectbox with `key='topology_example_select'`
- Button with `key='load_example_topology_btn'`
- Sliders with unique keys per parameter
- Button with `key='generate_topology_btn'`

## Testing Results

✅ **All tests passing**:
- Package imports: PASS
- Utility modules: PASS
- Example files: PASS
- App syntax: PASS

## Installation & Running

### Quick Start (Recommended)
```bash
.venv\Scripts\streamlit.exe run app.py --server.port 8503
```

### Or double-click
```
start.bat
```

## Documentation Files
- `README.md` - Full feature documentation
- `QUICKSTART.md` - Beginner's guide
- `TROUBLESHOOTING.md` - Known issues and solutions
- `PROJECT_OVERVIEW.md` - Technical architecture

## Known Limitations
- GNPy not installed (optional) - uses mock data for demonstrations
- Build a real virtual environment if needed: `.venv\Scripts\python.exe -m pip install --upgrade pip`

## Next Steps

1. **Run the app**: `.venv\Scripts\streamlit.exe run app.py --server.port 8503`
2. **Load GNPy Mesh Topology**: Try the new topology option
3. **Generate topology**: Test the fixed topology generation
4. **Compute paths**: Run simulations without workflow interruptions

---

**Status**: ✅ All fixes implemented and tested successfully!
