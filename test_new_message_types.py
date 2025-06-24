#!/usr/bin/env python3
"""
Test script for new AIS message types (4, 5, 18, 21)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'siren'))

from siren.protocol.ais_encoding import build_ais_payload, create_nmea_sentence
from datetime import datetime

def test_type4_base_station():
    """Test Type 4 Base Station Report"""
    print("Testing Type 4 - Base Station Report")
    fields = {
        'msg_type': 4,
        'repeat': 0,
        'mmsi': 366123456,
        'year': 2025,
        'month': 6,
        'day': 24,
        'hour': 12,
        'minute': 30,
        'second': 45,
        'accuracy': 1,
        'lon': -74.0060,
        'lat': 40.7128,
        'epfd_type': 1,
        'raim': 0,
        'radio_status': 0
    }
    
    try:
        payload, fill = build_ais_payload(fields)
        nmea = create_nmea_sentence(fields)
        print(f"✅ Payload: {payload}")
        print(f"✅ Fill: {fill}")
        print(f"✅ NMEA: {nmea}")
        print()
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_type5_static_voyage():
    """Test Type 5 Static and Voyage Related Data"""
    print("Testing Type 5 - Static and Voyage Related Data")
    fields = {
        'msg_type': 5,
        'repeat': 0,
        'mmsi': 234567890,
        'ais_version': 0,
        'imo_number': 1234567,
        'call_sign': 'TEST123',
        'vessel_name': 'ATLANTIC TRADER',
        'ship_type': 70,
        'dim_to_bow': 120,
        'dim_to_stern': 60,
        'dim_to_port': 14,
        'dim_to_starboard': 14,
        'epfd_type': 1,
        'eta_month': 12,
        'eta_day': 25,
        'eta_hour': 14,
        'eta_minute': 30,
        'max_draft': 85,
        'destination': 'LISBON',
        'dte': 1
    }
    
    try:
        payload, fill = build_ais_payload(fields)
        nmea = create_nmea_sentence(fields)
        print(f"✅ Payload: {payload}")
        print(f"✅ Fill: {fill}")
        print(f"✅ NMEA: {nmea}")
        print()
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_type18_class_b():
    """Test Type 18 Standard Class B Position Report"""
    print("Testing Type 18 - Standard Class B Position Report")
    fields = {
        'msg_type': 18,
        'repeat': 0,
        'mmsi': 345678901,
        'sog': 4.5,
        'accuracy': 1,
        'lon': -9.32,
        'lat': 39.45,
        'cog': 180.0,
        'hdg': 180,
        'timestamp': 15,
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
        payload, fill = build_ais_payload(fields)
        nmea = create_nmea_sentence(fields)
        print(f"✅ Payload: {payload}")
        print(f"✅ Fill: {fill}")
        print(f"✅ NMEA: {nmea}")
        print()
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_type21_aid_to_navigation():
    """Test Type 21 Aid-to-Navigation Report"""
    print("Testing Type 21 - Aid-to-Navigation Report")
    fields = {
        'msg_type': 21,
        'repeat': 0,
        'mmsi': 992123456,
        'aid_type': 5,  # Light without sectors
        'name': 'LIGHTHOUSE BEACON',
        'accuracy': 1,
        'lon': -9.25,
        'lat': 39.50,
        'dim_to_bow': 10,
        'dim_to_stern': 10,
        'dim_to_port': 5,
        'dim_to_starboard': 5,
        'epfd_type': 1,
        'timestamp': 60,
        'off_position': 0,
        'aton_status': 0,
        'raim': 0,
        'virtual_aid': 0,
        'assigned': 0
    }
    
    try:
        payload, fill = build_ais_payload(fields)
        nmea = create_nmea_sentence(fields)
        print(f"✅ Payload: {payload}")
        print(f"✅ Fill: {fill}")
        print(f"✅ NMEA: {nmea}")
        print()
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_type1_position_report():
    """Test Type 1 Position Report (existing functionality)"""
    print("Testing Type 1 - Position Report (verification)")
    fields = {
        'msg_type': 1,
        'repeat': 0,
        'mmsi': 123456789,
        'nav_status': 0,
        'rot': 0,
        'sog': 10.0,
        'accuracy': 1,
        'lon': -74.0060,
        'lat': 40.7128,
        'cog': 90.0,
        'hdg': 90,
        'timestamp': 30
    }
    
    try:
        payload, fill = build_ais_payload(fields)
        nmea = create_nmea_sentence(fields)
        print(f"✅ Payload: {payload}")
        print(f"✅ Fill: {fill}")
        print(f"✅ NMEA: {nmea}")
        print()
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing New AIS Message Types Implementation")
    print("=" * 60)
    
    tests = [
        test_type1_position_report,
        test_type4_base_station,
        test_type5_static_voyage,
        test_type18_class_b,
        test_type21_aid_to_navigation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("=" * 60)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! New message types are working correctly.")
    else:
        print("⚠️  Some tests failed. Check the implementation.")
