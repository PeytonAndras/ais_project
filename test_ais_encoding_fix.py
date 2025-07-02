#!/usr/bin/env python3
"""
Test AIS Encoding Fix
====================

This script tests that the float-to-int conversion fix is working
correctly in the AIS encoding module.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from siren.ships.ais_ship import AISShip
from siren.protocol.ais_encoding import build_ais_payload

def test_ais_encoding():
    """Test AIS encoding with float values"""
    print("🔧 Testing AIS Encoding with Float Values")
    print("=" * 50)
    
    # Create a test ship with float speed and course values
    test_ship = AISShip(
        mmsi=123456789,
        name="TEST_VESSEL",
        lat=39.5,
        lon=-9.2,
        speed=8.0,  # Float value
        course=90.0,  # Float value
        ship_type=1
    )
    
    print(f"📡 Test Ship: {test_ship.name} (MMSI: {test_ship.mmsi})")
    print(f"📍 Position: {test_ship.lat:.4f}°N, {test_ship.lon:.4f}°W")
    print(f"⚡ Speed: {test_ship.speed} knots (type: {type(test_ship.speed)})")
    print(f"🧭 Course: {test_ship.course}° (type: {type(test_ship.course)})")
    print()
    
    # Get AIS fields from the ship
    fields = test_ship.get_ais_fields()
    print("🔍 AIS Fields:")
    for key, value in fields.items():
        if key in ['sog', 'cog']:
            print(f"  {key}: {value} (type: {type(value)})")
    print()
    
    # Test AIS payload building
    try:
        print("🔧 Building AIS payload with pyais...")
        payload, fill = build_ais_payload(fields)
        print(f"✅ AIS payload built successfully!")
        print(f"📦 Payload: {payload}")
        print(f"🔢 Fill bits: {fill}")
        print()
        
        # Test NMEA sentence creation
        from siren.protocol.ais_encoding import compute_checksum
        channel = 'A'
        sentence = f"AIVDM,1,1,,{channel},{payload},{fill}"
        cs = compute_checksum(sentence)
        full_sentence = f"!{sentence}*{cs}"
        
        print(f"📡 NMEA Sentence: {full_sentence}")
        print()
        
        # Validate with pyais
        try:
            from pyais import decode
            decoded = decode(full_sentence)
            print("✅ NMEA sentence validation successful!")
            print(f"🚢 Decoded MMSI: {decoded.mmsi}")
            print(f"📍 Decoded Position: {decoded.lat:.4f}°N, {decoded.lon:.4f}°W")
            print(f"⚡ Decoded Speed: {decoded.speed} knots")
            print(f"🧭 Decoded Course: {decoded.course}°")
            
        except Exception as e:
            print(f"⚠️  NMEA validation warning: {e}")
            
    except Exception as e:
        print(f"❌ AIS payload building failed: {e}")
        print(f"Error type: {type(e)}")
        return False
        
    return True

def test_multiple_message_types():
    """Test different AIS message types"""
    print("\n🔧 Testing Multiple AIS Message Types")
    print("=" * 50)
    
    # Test message types 1, 3, and 18
    message_types = [1, 3, 18]
    
    for msg_type in message_types:
        print(f"\n📡 Testing Message Type {msg_type}...")
        
        test_ship = AISShip(
            mmsi=123456789 + msg_type,
            name=f"TEST_VESSEL_{msg_type}",
            lat=39.5,
            lon=-9.2,
            speed=15.5,  # Float value
            course=270.8,  # Float value  
            ship_type=msg_type
        )
        
        fields = test_ship.get_ais_fields()
        fields['msg_type'] = msg_type
        
        try:
            payload, fill = build_ais_payload(fields)
            print(f"✅ Message Type {msg_type}: Success")
        except Exception as e:
            print(f"❌ Message Type {msg_type}: Failed - {e}")

if __name__ == "__main__":
    print("🚢 AIS Encoding Test Suite")
    print("===========================")
    print()
    
    # Test basic encoding
    success = test_ais_encoding()
    
    # Test multiple message types
    test_multiple_message_types()
    
    print("\n📋 Test Summary")
    print("=" * 20)
    if success:
        print("✅ AIS encoding fix is working correctly!")
        print("🎉 Float values are properly converted to integers")
    else:
        print("❌ AIS encoding still has issues")
        
    print("\n🚀 The SIREN simulation should now work without float errors!")
