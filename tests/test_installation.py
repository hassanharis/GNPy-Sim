"""
Test/Demo Script for GNPy Simulator
Run this to verify the installation and test basic functionality
"""

import sys
import json
from pathlib import Path

def check_imports():
    """Check if all required packages can be imported"""
    print("Checking package imports...")
    packages = [
        'streamlit',
        'pandas',
        'numpy',
        'networkx',
        'matplotlib',
        'plotly'
    ]
    
    missing = []
    for package in packages:
        try:
            __import__(package)
            print(f"  ✓ {package}")
        except ImportError:
            print(f"  ✗ {package} - NOT FOUND")
            missing.append(package)
    
    # Check GNPy separately (optional)
    try:
        import gnpy
        print(f"  ✓ gnpy (version: {gnpy.__version__})")
    except ImportError:
        print(f"  ⚠ gnpy - NOT FOUND (optional, some features will use mock data)")
    
    if missing:
        print(f"\n❌ Missing packages: {', '.join(missing)}")
        print("Run: pip install -r requirements.txt")
        return False
    else:
        print("\n✅ All required packages installed!")
        return True


def test_utils():
    """Test utility modules"""
    print("\nTesting utility modules...")
    
    try:
        from utils import topology, gnpy_wrapper, visualization
        print("  ✓ Utils modules imported successfully")
        
        # Test topology generation
        G, topo_data = topology.generate_linear_topology(5, 80.0)
        if G.number_of_nodes() == 5:
            print("  ✓ Topology generation works")
        else:
            print("  ✗ Topology generation failed")
            return False
        
        # Test graph validation
        is_valid, errors = topology.validate_topology(G)
        if is_valid:
            print("  ✓ Topology validation works")
        else:
            print(f"  ✗ Topology validation failed: {errors}")
            return False
        
        print("✅ Utility modules working correctly!")
        return True
        
    except Exception as e:
        print(f"  ✗ Error testing utils: {str(e)}")
        return False


def test_example_files():
    """Test that example files exist and are valid"""
    print("\nChecking example files...")
    
    examples_dir = Path("examples")
    if not examples_dir.exists():
        print("  ✗ Examples directory not found")
        return False
    
    files = [
        "simple_topology.json",
        "simple_equipment.json",
        "simple_services.json"
    ]
    
    all_valid = True
    for filename in files:
        filepath = examples_dir / filename
        if not filepath.exists():
            print(f"  ✗ {filename} not found")
            all_valid = False
        else:
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                print(f"  ✓ {filename} - valid JSON")
            except json.JSONDecodeError as e:
                print(f"  ✗ {filename} - invalid JSON: {str(e)}")
                all_valid = False
    
    if all_valid:
        print("✅ All example files are valid!")
    return all_valid


def test_streamlit_app():
    """Check if the main app file exists and is valid Python"""
    print("\nChecking Streamlit app...")
    
    app_file = Path("app.py")
    if not app_file.exists():
        print("  ✗ app.py not found")
        return False
    
    try:
        with open(app_file, 'r', encoding='utf-8') as f:
            code = f.read()
        
        # Basic syntax check
        compile(code, 'app.py', 'exec')
        print("  ✓ app.py syntax is valid")
        
        # Check for main components
        required_strings = [
            'streamlit',
            'st.title',
            'show_equipment_section',
            'show_topology_section',
            'show_results_section'
        ]
        
        missing = []
        for req in required_strings:
            if req not in code:
                missing.append(req)
        
        if missing:
            print(f"  ⚠ Missing components: {', '.join(missing)}")
        else:
            print("  ✓ All main components found")
        
        print("✅ Streamlit app file is valid!")
        return True
        
    except SyntaxError as e:
        print(f"  ✗ Syntax error in app.py: {str(e)}")
        return False
    except Exception as e:
        print(f"  ✗ Error checking app.py: {str(e)}")
        return False


def main():
    """Run all tests"""
    print("="*50)
    print("  GNPy Simulator - Installation Test")
    print("="*50)
    print()
    
    results = []
    
    # Run tests
    results.append(("Package Imports", check_imports()))
    results.append(("Utility Modules", test_utils()))
    results.append(("Example Files", test_example_files()))
    results.append(("Streamlit App", test_streamlit_app()))
    
    # Summary
    print("\n" + "="*50)
    print("  Test Summary")
    print("="*50)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name}: {status}")
    
    all_passed = all(result[1] for result in results)
    
    print("\n" + "="*50)
    if all_passed:
        print("🎉 All tests passed! You're ready to run the simulator.")
        print("\nTo start the application:")
        print("  1. Run: streamlit run app.py")
        print("  2. Or double-click: start.bat (Windows)")
        print("\nThe app will open at: http://localhost:8501")
    else:
        print("⚠️  Some tests failed. Please fix the issues above.")
        print("\nCommon fixes:")
        print("  - Install missing packages: pip install -r requirements.txt")
        print("  - Ensure you're in the correct directory")
        print("  - Check Python version: python --version (need 3.8+)")
    print("="*50)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
