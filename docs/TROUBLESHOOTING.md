# Known Issues and Solutions

## GNPy Installation on Windows

### Issue
GNPy has a dependency (`oopt_gnpy_libyang`) that requires:
- CMake
- C++ compiler (Visual Studio Build Tools or Visual Studio)

This causes installation failures on Windows without these tools.

### Solution 1: Run Without GNPy (Recommended for Testing)
The application is designed to work with **mock data** when GNPy is not installed. All features are available for testing and demonstration.

**Installation:**
```bash
pip install -r requirements.txt
```

This installs only the core dependencies and the app will work with simulated optical network calculations.

### Solution 2: Install GNPy (For Production Use)

If you need real GNPy calculations:

#### Step 1: Install CMake
1. Download from: https://cmake.org/download/
2. Install and add to PATH
3. Verify: `cmake --version`

#### Step 2: Install Visual Studio Build Tools
1. Download "Build Tools for Visual Studio" from:
   https://visualstudio.microsoft.com/downloads/
2. Install with "Desktop development with C++" workload
3. Or install full Visual Studio Community (free)

#### Step 3: Install GNPy
```bash
pip install gnpy
```

### Solution 3: Use Linux/WSL
GNPy installs easily on Linux:

```bash
# Ubuntu/Debian
sudo apt-get install cmake build-essential
pip install gnpy

# Or use WSL on Windows
wsl --install
# Then follow Linux instructions
```

### Solution 4: Use Docker (Future)
A Docker image can be created with all dependencies pre-installed.

## Feature Comparison

| Feature | Without GNPy | With GNPy |
|---------|--------------|-----------|
| UI and Navigation | ✅ Full | ✅ Full |
| Topology Visualization | ✅ Full | ✅ Full |
| Path Computation | ✅ Mock Data | ✅ Real Calculations |
| OSNR/GSNR | ✅ Simulated | ✅ Accurate Physics |
| Power Sweep | ✅ Simulated | ✅ Real Analysis |
| Auto-Design | ✅ Mock | ✅ Real EDFA Selection |
| File Import/Export | ✅ Full | ✅ Full |

## Other Common Issues

### Port Already in Use
```bash
# Use different port
streamlit run app.py --server.port 8502
```

### Package Version Conflicts
```bash
# Create fresh virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### Matplotlib Display Issues
Already handled in the code with:
```python
import matplotlib
matplotlib.use('Agg')
```

### Excel File Not Loading
Ensure `openpyxl` is installed:
```bash
pip install openpyxl
```

## Testing the Installation

Run the test script:
```bash
python test_installation.py
```

This will verify:
- ✅ All required packages
- ✅ Utility modules working
- ✅ Example files valid
- ✅ App syntax correct
- ⚠️ GNPy availability (optional)

## Getting Help

1. **Check test output**: `python test_installation.py`
2. **Read error messages**: Often indicate missing packages
3. **Virtual environment**: Create clean environment if issues persist
4. **GNPy Documentation**: https://gnpy.readthedocs.io/
5. **GitHub Issues**: https://github.com/Telecominfraproject/oopt-gnpy/issues

## Recommended Setup for Different Use Cases

### 1. Quick Demo/Learning
```bash
pip install -r requirements.txt
streamlit run app.py
```
✅ Works immediately, no build tools needed

### 2. Development/Testing
Same as above - mock data is sufficient for UI development

### 3. Production/Real Networks
Install build tools + GNPy for accurate calculations

### 4. Academic/Research
Consider Linux/WSL for easier GNPy installation

## Summary

**The application works perfectly without GNPy installed!** 

GNPy is only needed for production optical network calculations. For learning, testing, and UI development, the built-in mock data provides full functionality.
