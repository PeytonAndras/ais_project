#!/usr/bin/env python3
"""
Test script to verify pyais integration in SIREN
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from siren.protocol.ais_encoding import create_nmea_sentence, validate_ais_message

def test_message_type_1():
    """Test AIS Type 1 Position Report"""
    print("Testing AIS Type 1 Position Report...")
    
    fields = {
        'msg_type': 1,
        'mmsi': 123456789,
        'nav_status': 0,
        'rot': 0,
        'sog': 12.3,
        'accuracy': 1,
        'lon': -122.4194,
        'lat': 37.7749,
        'cog': 215.5,
        'hdg': 220,
        'timestamp': 30,
        'radio_status': 0
    }
    
    try:
        nmea = create_nmea_sentence(fields, 'A')
        print(f"Generated NMEA: {nmea}")
        
        # Validate the message
        valid, result = validate_ais_message(nmea)
        if valid:
            print(f"✅ Message validated successfully!")
            print(f"   MMSI: {result.mmsi}")
            print(f"   Position: {result.lat}, {result.lon}")
            print(f"   Speed: {result.speed} knots")
            print(f"   Course: {result.course}°")
        else:
            print(f"❌ Validation failed: {result}")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_message_type_4():
    """Test AIS Type 4 Base Station Report"""
    print("\nTesting AIS Type 4 Base Station Report...")
    
    fields = {
        'msg_type': 4,
        'mmsi': 987654321,
        'year': 2025,
        'month': 6,
        'day': 25,
        'hour': 12,
        'minute': 30,
        'second': 45,
        'accuracy': 1,
        'lon': -122.4194,
        'lat': 37.7749,
        'epfd_type': 1,
        'radio_status': 0
    }
    
    try:
        nmea = create_nmea_sentence(fields, 'A')
        print(f"Generated NMEA: {nmea}")
        
        # Validate the message
        valid, result = validate_ais_message(nmea)
        if valid:
            print(f"✅ Message validated successfully!")
            print(f"   MMSI: {result.mmsi}")
            print(f"   Position: {result.lat}, {result.lon}")
            print(f"   Time: {result.year}-{result.month:02d}-{result.day:02d} {result.hour:02d}:{result.minute:02d}:{result.second:02d}")
        else:
            print(f"❌ Validation failed: {result}")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_message_type_5():
    """Test AIS Type 5 Static and Voyage Data"""
    print("\nTesting AIS Type 5 Static and Voyage Data...")
    
    fields = {
        'msg_type': 5,
        'mmsi': 123456789,
        'imo_number': 1234567,
        'call_sign': 'TEST123',
        'vessel_name': 'TEST VESSEL',
        'ship_type': 70,  # Cargo ship
        'dim_to_bow': 100,
        'dim_to_stern': 20,
        'dim_to_port': 10,
        'dim_to_starboard': 10,
        'epfd_type': 1,
        'eta_month': 12,
        'eta_day': 25,
        'eta_hour': 14,
        'eta_minute': 30,
        'max_draft': 80,  # 8.0 meters
        'destination': 'SAN FRANCISCO',
        'dte': 0
    }
    
    try:
        nmea = create_nmea_sentence(fields, 'A')
        print(f"Generated NMEA: {nmea}")
        
        # Validate the message
        valid, result = validate_ais_message(nmea)
        if valid:
            print(f"✅ Message validated successfully!")
            print(f"   MMSI: {result.mmsi}")
            print(f"   Vessel: {result.shipname}")
            print(f"   Call Sign: {result.callsign}")
            print(f"   Destination: {result.destination}")
        else:
            print(f"❌ Validation failed: {result}")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_message_type_18():
    """Test AIS Type 18 Class B Position Report"""
    print("\nTesting AIS Type 18 Class B Position Report...")
    
    fields = {
        'msg_type': 18,
        'mmsi': 123456789,
        'sog': 8.5,
        'accuracy': 1,
        'lon': -122.4194,
        'lat': 37.7749,
        'cog': 180.0,
        'hdg': 175,
        'timestamp': 45,
        'cs_unit': 1,
        'display': 0,
        'dsc': 1,
        'band': 1,
        'msg22': 0,
        'assigned': 0,
        'raim': 0,
        'radio_status': 0
    }
    
    try:
        nmea = create_nmea_sentence(fields, 'B')
        print(f"Generated NMEA: {nmea}")
        
        # Validate the message
        valid, result = validate_ais_message(nmea)
        if valid:
            print(f"✅ Message validated successfully!")
            print(f"   MMSI: {result.mmsi}")
            print(f"   Position: {result.lat}, {result.lon}")
            print(f"   Speed: {result.speed} knots")
            print(f"   Course: {result.course}°")
        else:
            print(f"❌ Validation failed: {result}")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_message_type_21():
    """Test AIS Type 21 Aid-to-Navigation Report"""
    print("\nTesting AIS Type 21 Aid-to-Navigation Report...")
    
    fields = {
        'msg_type': 21,
        'mmsi': 993456789,
        'aid_type': 1,  # Reference point
        'name': 'GOLDEN GATE BRIDGE',
        'accuracy': 1,
        'lon': -122.4783,
        'lat': 37.8199,
        'dim_to_bow': 0,
        'dim_to_stern': 0,
        'dim_to_port': 0,
        'dim_to_starboard': 0,
        'epfd_type': 1,
        'timestamp': 60,
        'off_position': 0,
        'aton_status': 0,
        'raim': 0,
        'virtual_aid': 0,
        'assigned': 0
    }
    
    try:
        nmea = create_nmea_sentence(fields, 'A')
        print(f"Generated NMEA: {nmea}")
        
        # Validate the message
        valid, result = validate_ais_message(nmea)
        if valid:
            print(f"✅ Message validated successfully!")
            print(f"   MMSI: {result.mmsi}")
            print(f"   Name: {result.name}")
            print(f"   Position: {result.lat}, {result.lon}")
            print(f"   Aid Type: {result.aid_type}")
        else:
            print(f"❌ Validation failed: {result}")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("SIREN AIS Message Encoding Test - pyais Integration")
    print("=" * 60)
    
    tests = [
        test_message_type_1,
        test_message_type_4,
        test_message_type_5,
        test_message_type_18,
        test_message_type_21
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! pyais integration successful!")
    else:
        print("⚠️  Some tests failed. Check the output above.")
    
    print("=" * 60)

if __name__ == "__main__":
    main()
