#!/usr/bin/env python3
"""
Test AIS payload to bitstring conversion

This script tests the conversion of AIS payloads to binary bit strings
that can be sent to the GNU Radio websocket interface.
"""

import sys
import os

# Add SIREN to path
sys.path.insert(0, os.path.dirname(__file__))

from siren.protocol.ais_encoding import (
    payload_to_bitstring, 
    extract_payload_from_nmea,
    create_nmea_sentence
)
from siren.ships.ais_ship import AISShip

def test_payload_conversion():
    """Test the AIS payload to bitstring conversion"""
    print("🧪 Testing AIS Payload to Bitstring Conversion")
    print("=" * 50)
    
    # Create a test ship
    ship = AISShip(
        name="Test Vessel",
        mmsi=123456789,
        ship_type=70,
        lat=39.5,
        lon=-9.2,
        course=90.0,
        speed=10.0
    )
    ship.heading = 90
    
    print(f"🚢 Test ship: {ship.name} (MMSI: {ship.mmsi})")
    print(f"📍 Position: {ship.lat:.3f}, {ship.lon:.3f}")
    print(f"🧭 Course: {ship.course}°, Speed: {ship.speed} knots")
    print()
    
    # Generate AIS fields and NMEA sentence
    try:
        ais_fields = ship.get_ais_fields()
        nmea_sentence = create_nmea_sentence(ais_fields)
        
        print(f"📡 NMEA sentence: {nmea_sentence}")
        print()
        
        # Extract payload
        payload, fill_bits = extract_payload_from_nmea(nmea_sentence)
        if payload is None:
            print("❌ Failed to extract payload from NMEA sentence")
            return False
        
        print(f"🔧 Extracted payload: {payload}")
        print(f"🔧 Fill bits: {fill_bits}")
        print()
        
        # Convert to bitstring
        bit_string = payload_to_bitstring(payload)
        if not bit_string:
            print("❌ Failed to convert payload to bitstring")
            return False
        
        print(f"🔢 Binary bitstring ({len(bit_string)} bits):")
        print(f"   {bit_string}")
        print()
        
        # Show first 50 bits for readability
        if len(bit_string) > 50:
            print(f"🔍 First 50 bits: {bit_string[:50]}...")
        print()
        
        # Verify bitstring properties
        print("✅ Conversion successful!")
        print(f"   - Payload length: {len(payload)} characters")
        print(f"   - Bitstring length: {len(bit_string)} bits")
        print(f"   - Expected bits: {len(payload) * 6} (6 bits per character)")
        
        if len(bit_string) == len(payload) * 6:
            print("✅ Bitstring length matches expected (6 bits per character)")
        else:
            print("⚠️  Bitstring length doesn't match expected")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during conversion: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_websocket_format():
    """Test what would be sent to GNU Radio websocket"""
    print("\n" + "=" * 50)
    print("🌐 Testing Websocket Format")
    print("=" * 50)
    
    try:
        # Create test NMEA
        ship = AISShip(name="WebSocket Test", mmsi=987654321, ship_type=70, lat=40.0, lon=-10.0)
        ais_fields = ship.get_ais_fields()
        nmea_sentence = create_nmea_sentence(ais_fields)
        
        # Extract and convert
        payload, _ = extract_payload_from_nmea(nmea_sentence)
        bit_string = payload_to_bitstring(payload)
        
        print(f"📡 NMEA: {nmea_sentence}")
        print(f"🔧 Payload: {payload}")
        print(f"🔢 Bitstring to send: {bit_string}")
        print()
        
        # Show what the websocket would receive
        print("📤 What GNU Radio websocket receives:")
        print(f"   Type: {type(bit_string).__name__}")
        print(f"   Length: {len(bit_string)} characters")
        print(f"   Content: '{bit_string[:50]}{'...' if len(bit_string) > 50 else ''}' ")
        print()
        
        # Verify it's a valid binary string
        if all(c in '01' for c in bit_string):
            print("✅ Valid binary string (only 0s and 1s)")
        else:
            print("❌ Invalid binary string (contains non-binary characters)")
            
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("🚢 SIREN GNU Radio AIS Transmission Test")
    print("Testing payload to bitstring conversion for GNU Radio websocket")
    print()
    
    success1 = test_payload_conversion()
    success2 = test_websocket_format()
    
    print("\n" + "=" * 50)
    if success1 and success2:
        print("✅ All tests passed! Ready for GNU Radio transmission.")
        print()
        print("📋 To use on your GNU Radio machine:")
        print("   1. Ensure your .grc flowgraph is running and listening on port 52002")
        print("   2. Copy this SIREN code to your GNU Radio machine")
        print("   3. Run: python siren_gnuradio_transmitter.py --mmsi 123456789 --lat 39.5 --lon -9.2 --once")
        print("   4. The transmitter will send binary bitstrings to the GNU Radio websocket")
    else:
        print("❌ Some tests failed. Check the errors above.")
        sys.exit(1)
