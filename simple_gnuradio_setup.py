#!/usr/bin/env python3
"""
Simple GNU Radio Setup for SIREN

This script sets up the simple GNU Radio integration that uses the 
ais-simulator websocket interface instead of requiring complex GNU Radio bindings.

Usage:
1. Run this setup script
2. Download and set up ais-simulator
3. Use SIREN with "GNU Radio (Simple)" transmission option

@ author: Peyton Andras @ Louisiana State University 2025
"""

import sys
import os
import subprocess
import shutil
from pathlib import Path

def check_python_dependencies():
    """Check if required Python packages are installed"""
    required = ['websocket-client', 'pyais']
    missing = []
    
    for package in required:
        try:
            if package == 'websocket-client':
                import websocket
            elif package == 'pyais':
                import pyais
        except ImportError:
            missing.append(package)
    
    return missing

def install_python_dependencies(missing):
    """Install missing Python dependencies"""
    print("Installing Python dependencies...")
    for package in missing:
        print(f"  Installing {package}...")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
            print(f"  ✅ {package} installed")
        except subprocess.CalledProcessError as e:
            print(f"  ❌ Failed to install {package}: {e}")
            return False
    return True

def check_ais_simulator():
    """Check if ais-simulator is available"""
    ais_sim_path = Path("ais-simulator")
    if ais_sim_path.exists():
        python_file = ais_sim_path / "ais-simulator.py"
        if python_file.exists():
            return True, "Found in current directory"
        else:
            return False, "Directory exists but ais-simulator.py not found"
    else:
        return False, "ais-simulator directory not found"

def download_ais_simulator():
    """Download ais-simulator if not present"""
    print("\nSetting up ais-simulator...")
    
    available, msg = check_ais_simulator()
    if available:
        print(f"  ✅ ais-simulator already available: {msg}")
        return True
    
    print(f"  ⚠️ ais-simulator not found: {msg}")
    print("  📥 You need to download ais-simulator manually")
    print("  Available options:")
    print("  1. Clone from GitHub:")
    print("     git clone https://github.com/Mictronics/ais-simulator.git")
    print("  2. Download from: https://github.com/Mictronics/ais-simulator")
    print("  3. Copy from another location if you already have it")
    print("")
    
    # Check if git is available
    if shutil.which('git'):
        response = input("  Would you like to clone ais-simulator now? (y/N): ").strip().lower()
        if response in ['y', 'yes']:
            try:
                print("  📥 Cloning ais-simulator...")
                subprocess.check_call(['git', 'clone', 'https://github.com/Mictronics/ais-simulator.git'])
                print("  ✅ ais-simulator cloned successfully")
                return True
            except subprocess.CalledProcessError as e:
                print(f"  ❌ Failed to clone ais-simulator: {e}")
                return False
    
    return False

def test_simple_integration():
    """Test the simple GNU Radio integration"""
    print("\nTesting SIREN GNU Radio integration...")
    
    try:
        from siren.config.simple_gnuradio_config import check_dependencies
        from siren.transmission.simple_gnuradio import SimpleGnuRadioTransmitter
        
        # Check dependencies
        deps = check_dependencies()
        if all(deps.values()):
            print("  ✅ All Python dependencies available")
        else:
            missing_deps = [name for name, available in deps.items() if not available]
            print(f"  ❌ Missing dependencies: {', '.join(missing_deps)}")
            return False
        
        # Test transmitter creation
        tx = SimpleGnuRadioTransmitter()
        print("  ✅ Simple GNU Radio transmitter can be created")
        
        print("  ✅ SIREN GNU Radio integration is ready!")
        return True
        
    except Exception as e:
        print(f"  ❌ Integration test failed: {e}")
        return False

def print_usage_instructions():
    """Print usage instructions"""
    print("\n" + "="*60)
    print("SIREN GNU Radio Simple Integration Setup Complete!")
    print("="*60)
    
    print("\n📋 How to use:")
    print("1. Start the GNU Radio flowgraph:")
    print("   cd ais-simulator")
    print("   python3 ais-simulator.py")
    print("   (This creates a websocket server on port 52002)")
    
    print("\n2. Start SIREN:")
    print("   python3 siren_main.py")
    
    print("\n3. In SIREN's Ship Simulation tab:")
    print("   - Select 'GNU Radio (Simple)' as transmission method")
    print("   - Choose AIS channel (A or B)")
    print("   - Select ships to simulate")
    print("   - Click 'Start Simulation'")
    
    print("\n4. SIREN will send AIS bitstrings to GNU Radio via websocket")
    print("   GNU Radio will transmit them as RF signals")
    
    print("\n📡 Testing transmission:")
    print("   Use rtl_ais or other AIS receivers to verify transmission")
    
    print("\n🔧 Troubleshooting:")
    print("   - Make sure ais-simulator.py is running before starting SIREN")
    print("   - Check that port 52002 is not blocked by firewall")
    print("   - Verify GNU Radio dependencies are installed on the system running ais-simulator")
    
    print("\n📖 For more information:")
    print("   - SIREN documentation: README.md")
    print("   - ais-simulator: https://github.com/Mictronics/ais-simulator")

def main():
    """Main setup function"""
    print("SIREN GNU Radio Simple Integration Setup")
    print("="*50)
    
    # Check Python dependencies
    print("Checking Python dependencies...")
    missing = check_python_dependencies()
    
    if missing:
        print(f"Missing dependencies: {', '.join(missing)}")
        if install_python_dependencies(missing):
            print("✅ All Python dependencies installed")
        else:
            print("❌ Failed to install some dependencies")
            return 1
    else:
        print("✅ All Python dependencies available")
    
    # Check/download ais-simulator
    if not download_ais_simulator():
        print("\n⚠️ ais-simulator setup incomplete")
        print("You can continue without it, but will need to set it up manually for transmission")
    
    # Test integration
    if test_simple_integration():
        print_usage_instructions()
        return 0
    else:
        print("\n❌ Setup incomplete - please check errors above")
        return 1

if __name__ == "__main__":
    sys.exit(main())
