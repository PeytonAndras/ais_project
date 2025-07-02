#!/usr/bin/env python3
"""
SIREN Dependency Installer
==========================

This script checks and installs missing Python dependencies for SIREN,
including the GNU Radio integration support.
"""

import subprocess
import sys
import os

def run_command(cmd, description):
    """Run a command and return success status"""
    print(f"📦 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description} completed successfully")
            return True
        else:
            print(f"❌ {description} failed:")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"❌ {description} failed with exception: {e}")
        return False

def check_python_package(package_name, import_name=None):
    """Check if a Python package is available"""
    if import_name is None:
        import_name = package_name
    
    try:
        __import__(import_name)
        print(f"✅ {package_name} is available")
        return True
    except ImportError:
        print(f"❌ {package_name} is not available")
        return False

def install_python_dependencies():
    """Install missing Python dependencies"""
    print("🐍 Checking Python Dependencies")
    print("=" * 40)
    
    # Check core dependencies
    dependencies = {
        'numpy': 'numpy',
        'websocket-client': 'websocket',
        'pyais': 'pyais',
        'SoapySDR': 'SoapySDR',
        'scipy': 'scipy',
        'matplotlib': 'matplotlib'
    }
    
    missing = []
    for package, import_name in dependencies.items():
        if not check_python_package(package, import_name):
            missing.append(package)
    
    if missing:
        print(f"\n📦 Installing missing packages: {', '.join(missing)}")
        cmd = f"{sys.executable} -m pip install {' '.join(missing)}"
        if run_command(cmd, f"Installing {', '.join(missing)}"):
            print("✅ Python dependencies installed successfully")
        else:
            print("❌ Failed to install some Python dependencies")
            return False
    else:
        print("✅ All Python dependencies are available")
    
    return True

def check_gnuradio_availability():
    """Check GNU Radio availability"""
    print("\n📡 Checking GNU Radio Integration")
    print("=" * 40)
    
    # Check if GNU Radio core is available
    gnuradio_available = check_python_package('gnuradio', 'gnuradio')
    osmosdr_available = check_python_package('gr-osmosdr', 'osmosdr')
    
    # Check for AIS simulator module
    ais_available = False
    try:
        from gnuradio import ais_simulator
        ais_available = True
        print("✅ gr-ais_simulator is available")
    except ImportError:
        try:
            from gnuradio import ais
            ais_available = True
            print("✅ gr-ais is available")
        except ImportError:
            print("❌ gr-ais/gr-ais_simulator is not available")
    
    websocket_available = check_python_package('websocket-client', 'websocket')
    
    if gnuradio_available and osmosdr_available and ais_available and websocket_available:
        print("🎉 GNU Radio integration is fully available!")
        return True
    else:
        print("\n⚠️  GNU Radio integration is not fully available")
        print("To enable GNU Radio transmission, install:")
        print("  - GNU Radio core (gnuradio)")
        print("  - GNU Radio OsmoSDR (gr-osmosdr)")  
        print("  - GNU Radio AIS (gr-ais or gr-ais_simulator)")
        print("  - WebSocket client (websocket-client)")
        print("\nSee GNURADIO_INTEGRATION.md for detailed instructions")
        return False

def main():
    """Main dependency check and installation"""
    print("🚢 SIREN Dependency Installer")
    print("=============================")
    print()
    
    # Install Python dependencies
    python_success = install_python_dependencies()
    
    # Check GNU Radio
    gnuradio_success = check_gnuradio_availability()
    
    print("\n📋 Summary")
    print("=" * 20)
    
    if python_success:
        print("✅ Python dependencies: OK")
    else:
        print("❌ Python dependencies: Issues found")
    
    if gnuradio_success:
        print("✅ GNU Radio integration: Fully available")
    else:
        print("⚠️  GNU Radio integration: Limited (SoapySDR fallback available)")
    
    print("\n🚀 You can now run SIREN:")
    print("   python siren_with_gnuradio.py")
    
    if not gnuradio_success:
        print("\nFor full GNU Radio support, see:")
        print("   ./setup_gnuradio.sh")
        print("   GNURADIO_INTEGRATION.md")

if __name__ == "__main__":
    main()
