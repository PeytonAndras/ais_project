#!/usr/bin/env python3
"""
Test script for GNU Radio integration with SIREN
================================================

This script tests the GNU Radio transmission integration by creating
a test ship and attempting to transmit using both methods.
"""

import sys
import time
from siren.ships.ais_ship import AISShip
from siren.transmission.siren_gnuradio_integration import SIRENGnuRadioTransmitter

def test_gnuradio_integration():
    """Test the GNU Radio integration"""
    print("🚢 SIREN GNU Radio Integration Test")
    print("=" * 50)
    
    # Create a test ship
    test_ship = AISShip(
        mmsi=123456789,
        name="TEST_VESSEL",
        lat=39.5,
        lon=-9.2,
        speed=10.0,
        course=90.0,
        ship_type=1
    )
    
    print(f"📡 Test Ship: {test_ship.name} (MMSI: {test_ship.mmsi})")
    print(f"📍 Position: {test_ship.lat:.4f}°N, {test_ship.lon:.4f}°W")
    print(f"⚡ Speed: {test_ship.speed} knots, Course: {test_ship.course}°")
    print()
    
    # Test GNU Radio transmission
    print("🔧 Testing GNU Radio transmission...")
    try:
        gnuradio_tx = SIRENGnuRadioTransmitter(use_gnuradio=True, channel='A')
        
        if gnuradio_tx.start():
            print("✅ GNU Radio transmitter started successfully")
            
            # Transmit test message
            success = gnuradio_tx.transmit_ship(test_ship)
            if success:
                print("✅ GNU Radio transmission successful!")
            else:
                print("❌ GNU Radio transmission failed")
                
            gnuradio_tx.stop()
        else:
            print("❌ Failed to start GNU Radio transmitter")
            
    except Exception as e:
        print(f"❌ GNU Radio test failed: {e}")
    
    print()
    
    # Test SoapySDR fallback
    print("🔧 Testing SoapySDR fallback...")
    try:
        soapy_tx = SIRENGnuRadioTransmitter(use_gnuradio=False, channel='A')
        
        if soapy_tx.start():
            print("✅ SoapySDR transmitter started successfully")
            
            # Transmit test message
            success = soapy_tx.transmit_ship(test_ship)
            if success:
                print("✅ SoapySDR transmission successful!")
            else:
                print("❌ SoapySDR transmission failed")
                
            soapy_tx.stop()
        else:
            print("❌ Failed to start SoapySDR transmitter")
            
    except Exception as e:
        print(f"❌ SoapySDR test failed: {e}")
    
    print()
    print("🎯 Test completed!")

def test_transmission_methods():
    """Test available transmission methods"""
    print("🔍 Checking available transmission methods...")
    print()
    
    # Check GNU Radio availability
    try:
        from siren.transmission.gnuradio_transmitter import GnuRadioAISTransmitter
        if GnuRadioAISTransmitter.is_available():
            print("✅ GNU Radio: Available")
        else:
            print("❌ GNU Radio: Not available (check installation)")
    except ImportError as e:
        print(f"❌ GNU Radio: Import failed - {e}")
    
    # Check SoapySDR availability
    try:
        from siren.transmission.sdr_controller import TransmissionController
        controller = TransmissionController()
        if controller.is_available():
            print("✅ SoapySDR: Available")
        else:
            print("❌ SoapySDR: Not available (check installation)")
    except ImportError as e:
        print(f"❌ SoapySDR: Import failed - {e}")
    
    print()

if __name__ == '__main__':
    print("🚢 SIREN GNU Radio Integration Test Suite")
    print("==========================================")
    print()
    
    test_transmission_methods()
    
    if len(sys.argv) > 1 and sys.argv[1] == '--transmission-test':
        test_gnuradio_integration()
    else:
        print("ℹ️  Use --transmission-test to run actual transmission tests")
        print("   (Make sure your SDR hardware is connected)")
