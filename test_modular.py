#!/usr/bin/env python3
"""
Test script for the modular AIS application
"""

import sys
import os

# Add the ais_main package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ais_main'))

def test_modules():
    """Test importing all modules"""
    print("Testing modular AIS application...")
    
    try:
        print("✓ Importing config...")
        from siren.config.settings import check_dependencies
        
        print("✓ Importing protocol...")
        from siren.protocol.ais_encoding import build_ais_payload
        
        print("✓ Importing ships...")
        from siren.ships.ship_manager import get_ship_manager
        
        print("✓ Importing transmission...")
        from siren.transmission.sdr_controller import get_signal_presets
        
        print("✓ Importing simulation...")
        from siren.simulation.simulation_controller import get_simulation_controller
        
        print("✓ Importing utils...")
        from siren.utils.navigation import haversine
        
        print("✓ Importing map...")
        from siren.map.visualization import MapVisualization
        
        print("✓ All core modules imported successfully!")
        
        # Test basic functionality
        sdr, map_avail, pil = check_dependencies()
        print(f"✓ Dependencies checked: SDR={sdr}, Map={map_avail}, PIL={pil}")
        
        ship_mgr = get_ship_manager()
        print(f"✓ Ship manager loaded with {len(ship_mgr.get_ships())} ships")
        
        presets = get_signal_presets()
        print(f"✓ Signal presets loaded: {len(presets)} presets")
        
        # Test navigation
        distance = haversine(40.7128, -74.0060, 40.7829, -73.9654)
        print(f"✓ Navigation test: NYC to Central Park = {distance:.2f} km")
        
        print("\n🎉 All tests passed! Modular structure is working correctly.")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_modules()
    sys.exit(0 if success else 1)
