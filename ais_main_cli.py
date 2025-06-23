#!/usr/bin/env python3
"""
Simple CLI test for the modular AIS application
"""

import sys
import os

# Add the ais_main package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ais_main'))

def main():
    """Main entry point for CLI test"""
    print("=" * 60)
    print("AIS NMEA Generator & Transmitter - Modular Version")
    print("Command Line Interface Test")
    print("@ Peyton Andras @ Louisiana State University 2025")
    print("=" * 60)
    
    try:
        # Import modules
        from ais_main.config.settings import check_dependencies
        from ais_main.ships.ship_manager import get_ship_manager
        from ais_main.protocol.ais_encoding import build_ais_payload, compute_checksum
        from ais_main.transmission.sdr_controller import get_signal_presets
        
        # Check dependencies and print status
        sdr_available, map_available, pil_available = check_dependencies()
        
        print(f"SDR Support: {'Available' if sdr_available else 'Not Available'}")
        print(f"Map Support: {'Available' if map_available else 'Not Available'}")
        print(f"PIL Support: {'Available' if pil_available else 'Not Available'}")
        print("=" * 60)
        
        # Initialize ship manager
        ship_manager = get_ship_manager()
        ships = ship_manager.get_ships()
        print(f"Loaded {len(ships)} ship configurations:")
        
        for i, ship in enumerate(ships):
            print(f"  {i+1}. {ship.name} (MMSI: {ship.mmsi}) - "
                  f"Position: {ship.lat:.4f}, {ship.lon:.4f} - "
                  f"Speed: {ship.speed} kts, Course: {ship.course}°")
        
        print("=" * 60)
        
        # Test AIS message generation
        print("Testing AIS message generation...")
        test_fields = {
            'msg_type': 1,
            'repeat': 0,
            'mmsi': 366123456,
            'nav_status': 0,
            'rot': 0,
            'sog': 10.0,
            'accuracy': 1,
            'lon': -74.0060,
            'lat': 40.7128,
            'cog': 90.0,
            'hdg': 90,
            'timestamp': 0
        }
        
        payload, fill = build_ais_payload(test_fields)
        print(f"AIS Payload: {payload}")
        print(f"Fill Bits: {fill}")
        
        # Create NMEA sentence
        channel = 'A'
        sentence = f"AIVDM,1,1,,{channel},{payload},{fill}"
        cs = compute_checksum(sentence)
        full_sentence = f"!{sentence}*{cs}"
        print(f"NMEA Sentence: {full_sentence}")
        
        print("=" * 60)
        
        # Show signal presets
        presets = get_signal_presets()
        print(f"Available signal presets ({len(presets)}):")
        for i, preset in enumerate(presets):
            print(f"  {i+1}. {preset['name']} - {preset['freq']/1e6:.3f} MHz - "
                  f"Gain: {preset['gain']} dB")
        
        print("=" * 60)
        print("✅ Modular AIS application is working correctly!")
        print("To run the GUI version, use: python ais_main_modular.py")
        print("To run the original version, use: python ais_main.py")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
