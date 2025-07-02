#!/usr/bin/env python3
"""
SIREN with GNU Radio Integration
===============================

Launch SIREN with the new GNU Radio transmission capabilities.
This script demonstrates the integration of the proven ais-simulator.py
GNU Radio method into the SIREN project.
"""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    """Launch SIREN with GNU Radio integration"""
    print("🚢 SIREN: Spoofed Identification & Real-time Emulation Node")
    print("📡 GNU Radio Integration Active")
    print("=" * 60)
    
    try:
        # Import and run SIREN
        from siren.ui.main_window import AISMainWindow
        
        # Create and run the main window
        app = AISMainWindow()
        
        print("✅ SIREN started successfully!")
        print("🎯 Features available:")
        print("   - Ship simulation and management")
        print("   - GNU Radio transmission (if installed)")
        print("   - SoapySDR transmission (fallback)")
        print("   - Real-time map visualization")
        print("   - Live parameter editing")
        print()
        print("📋 Transmission Methods:")
        
        # Check available transmission methods
        try:
            from siren.transmission.gnuradio_transmitter import GnuRadioAISTransmitter
            if GnuRadioAISTransmitter.is_available():
                print("   ✅ GNU Radio (recommended)")
            else:
                print("   ❌ GNU Radio (not available)")
        except ImportError:
            print("   ❌ GNU Radio (not installed)")
        
        try:
            from siren.transmission.sdr_controller import TransmissionController
            controller = TransmissionController()
            if controller.is_available():
                print("   ✅ SoapySDR")
            else:
                print("   ❌ SoapySDR (not available)")
        except ImportError:
            print("   ❌ SoapySDR (not installed)")
        
        print()
        print("🚀 Starting SIREN UI...")
        
        # Run the application
        app.root.mainloop()
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure all dependencies are installed:")
        print("  pip install -r requirements.txt")
        print("  ./setup_gnuradio.sh  # For GNU Radio support")
        
    except Exception as e:
        print(f"❌ Error starting SIREN: {e}")
        raise

if __name__ == '__main__':
    main()
