#!/usr/bin/env python3
"""
SIREN Main Application - Modular Entry Point
==========================================

This is the main entry point for the modular SIREN Generator & Transmitter application.
It replaces the monolithic ais_main.py file with a clean, modular architecture.

@ author: Peyton Andras @ Louisiana State University 2025

SIREN Generator & Transmitter
- Generate AIS messages with proper encoding
- Transmit using HackRF or other SoapySDR devices
- Simulate vessel movements with AIS position reporting
- Visualize ship movements on interactive map

All functionality from the original monolithic implementation is preserved
while providing a much more maintainable modular structure.
"""

import sys
import os

# Add the ais_main package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ais_main'))

def main():
    """Main entry point for the application"""
    print("=" * 60)
    print("SIREN Generator & Transmitter - Modular Version")
    print("@ Peyton Andras @ Louisiana State University 2025")
    print("=" * 60)
    
    try:
        # Import modules here to handle missing dependencies gracefully
        from siren.config.settings import check_dependencies
        from siren.ui.main_window import AISMainWindow
        from siren.ships.ship_manager import get_ship_manager
        
        # Check dependencies and print status
        sdr_available, map_available, pil_available = check_dependencies()
        
        print(f"SDR Support: {'Available' if sdr_available else 'Not Available'}")
        print(f"Map Support: {'Available' if map_available else 'Not Available'}")
        print(f"PIL Support: {'Available' if pil_available else 'Not Available'}")
        print("=" * 60)
        
        # Initialize ship manager
        ship_manager = get_ship_manager()
        print(f"Loaded {len(ship_manager.get_ships())} ship configurations")
        
        # Create and run the main application
        app = AISMainWindow()
        print("Starting SIREN application...")
        app.run()
        
    except ImportError as e:
        print(f"Import Error: {e}")
        print("Make sure all required modules are in the ais_main directory.")
        return 1
    except Exception as e:
        print(f"Error starting application: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
