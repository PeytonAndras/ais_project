#!/usr/bin/env python3
"""
SIREN GNU Radio Setup Checklist

Run this script to verify everything is ready for SIREN GNU Radio transmission.
"""

import sys
import os
import subprocess

def check_python_packages():
    """Check required Python packages"""
    print("🐍 Checking Python packages...")
    
    packages = {
        'websocket': 'websocket-client',
        'gnuradio': 'gnuradio',
        'osmosdr': 'gr-osmosdr',
        'pyais': 'pyais'
    }
    
    missing = []
    for module, package in packages.items():
        try:
            if module == 'websocket':
                import websocket
            elif module == 'gnuradio':
                from gnuradio import gr, blocks
            elif module == 'osmosdr':
                import osmosdr
            elif module == 'pyais':
                import pyais
            
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package}")
            missing.append(package)
    
    return missing

def check_gnuradio_modules():
    """Check GNU Radio specific modules"""
    print("\n📡 Checking GNU Radio modules...")
    
    try:
        from gnuradio import ais_simulator
        print("  ✅ gr-ais (ais_simulator)")
        return True
    except ImportError:
        try:
            from gnuradio import ais
            print("  ✅ gr-ais (ais)")
            return True
        except ImportError:
            print("  ❌ gr-ais (neither ais_simulator nor ais)")
            return False

def check_siren_modules():
    """Check SIREN modules"""
    print("\n🚢 Checking SIREN modules...")
    
    try:
        from siren.ships.ais_ship import AISShip
        from siren.protocol.ais_encoding import create_nmea_sentence, payload_to_bitstring
        from siren.transmission.gnuradio_transmitter import GnuRadioAISTransmitter
        print("  ✅ All SIREN modules available")
        return True
    except ImportError as e:
        print(f"  ❌ SIREN modules missing: {e}")
        return False

def check_websocket_port(port=52002):
    """Check if websocket port is accessible"""
    print(f"\n🌐 Checking websocket port {port}...")
    
    try:
        import websocket
        ws = websocket.create_connection(f"ws://localhost:{port}", timeout=2)
        ws.close()
        print(f"  ✅ Port {port} is accessible (GNU Radio is running)")
        return True
    except Exception as e:
        print(f"  ❌ Port {port} not accessible: {e}")
        print("     Make sure your GNU Radio .grc flowgraph is running")
        return False

def main():
    print("🧪 SIREN GNU Radio Setup Checklist")
    print("=" * 50)
    
    all_good = True
    
    # Check Python packages
    missing_packages = check_python_packages()
    if missing_packages:
        all_good = False
        print(f"\n❌ Missing packages: {', '.join(missing_packages)}")
        print("Install with:")
        for pkg in missing_packages:
            if pkg == 'websocket-client':
                print(f"  pip install {pkg}")
            elif pkg in ['gnuradio', 'gr-osmosdr']:
                print(f"  sudo apt-get install {pkg}")
            else:
                print(f"  pip install {pkg}")
    
    # Check GNU Radio modules
    if not check_gnuradio_modules():
        all_good = False
        print("\n❌ GNU Radio AIS modules missing!")
        print("Install with: sudo apt-get install gr-ais")
    
    # Check SIREN modules
    if not check_siren_modules():
        all_good = False
        print("\n❌ SIREN modules not found!")
        print("Make sure you're running this from the correct directory")
    
    # Check websocket port
    websocket_ok = check_websocket_port()
    
    print("\n" + "=" * 50)
    
    if all_good and websocket_ok:
        print("✅ Everything looks good! Ready to transmit.")
        print("\n🚀 Quick test commands:")
        print("  # Test websocket only:")
        print("  python quick_gnuradio_test.py")
        print()
        print("  # Send one AIS message:")
        print("  python siren_gnuradio_transmitter.py --mmsi 123456789 --lat 39.5 --lon -9.2 --once")
        print()
        print("  # Continuous transmission:")
        print("  python siren_gnuradio_transmitter.py --mmsi 123456789 --lat 39.5 --lon -9.2 --continuous --interval 10")
        
    elif all_good and not websocket_ok:
        print("⚠️  Dependencies OK, but GNU Radio not running")
        print("\n📋 Next steps:")
        print("  1. Start your GNU Radio .grc flowgraph")
        print("  2. Verify it's listening on port 52002")
        print("  3. Run: python quick_gnuradio_test.py")
        
    else:
        print("❌ Some dependencies missing")
        print("\n📋 Fix the missing dependencies above, then run this checklist again")
    
    return 0 if (all_good and websocket_ok) else 1

if __name__ == "__main__":
    sys.exit(main())
