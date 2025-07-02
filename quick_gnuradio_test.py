#!/usr/bin/env python3
"""
Quick GNU Radio Websocket Test

This script quickly tests if the GNU Radio websocket interface is working
and can receive binary bitstrings from SIREN.
"""

import sys
import time
import json

try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    print("❌ websocket-client not available. Install with: pip install websocket-client")
    sys.exit(1)

def test_websocket_connection(port=52002):
    """Test basic websocket connection to GNU Radio"""
    print(f"🌐 Testing websocket connection to localhost:{port}")
    
    try:
        ws = websocket.create_connection(f"ws://localhost:{port}", timeout=5)
        print("✅ Websocket connection successful!")
        
        # Send a simple test bitstring (AIS Type 1 message)
        test_bitstring = "000001000001110101101111001101000101010000000000001111101000111111010101111000101100000000010110100110100010001000001111111111110010110101011000000000000000000000000000"
        
        print(f"📤 Sending test bitstring ({len(test_bitstring)} bits)")
        print(f"   Content: {test_bitstring[:50]}...")
        
        ws.send(test_bitstring)
        print("✅ Test bitstring sent successfully!")
        
        ws.close()
        return True
        
    except Exception as e:
        print(f"❌ Websocket connection failed: {e}")
        print("💡 Make sure your GNU Radio .grc flowgraph is running and listening on the correct port")
        return False

def test_with_siren_encoding():
    """Test with SIREN's AIS encoding if available"""
    print("\n🚢 Testing with SIREN AIS encoding...")
    
    try:
        from siren.protocol.ais_encoding import payload_to_bitstring, extract_payload_from_nmea, create_nmea_sentence
        from siren.ships.ais_ship import AISShip
        
        # Create test ship
        ship = AISShip(
            name="Quick Test",
            mmsi=123456789,
            ship_type=70,
            lat=39.5,
            lon=-9.2,
            course=90.0,
            speed=10.0
        )
        
        # Generate NMEA and convert to bitstring
        ais_fields = ship.get_ais_fields()
        nmea = create_nmea_sentence(ais_fields)
        payload, _ = extract_payload_from_nmea(nmea)
        bitstring = payload_to_bitstring(payload)
        
        print(f"📡 Generated NMEA: {nmea}")
        print(f"🔢 Generated bitstring ({len(bitstring)} bits): {bitstring[:50]}...")
        
        # Test websocket transmission
        try:
            ws = websocket.create_connection("ws://localhost:52002", timeout=5)
            ws.send(bitstring)
            print("✅ SIREN-generated bitstring sent successfully!")
            ws.close()
            return True
        except Exception as e:
            print(f"❌ Failed to send SIREN bitstring: {e}")
            return False
            
    except ImportError:
        print("⚠️  SIREN modules not available - using basic test only")
        return True
    except Exception as e:
        print(f"❌ SIREN encoding test failed: {e}")
        return False

def main():
    print("🧪 Quick GNU Radio Websocket Test")
    print("=" * 40)
    
    # Test basic websocket connection
    if not test_websocket_connection():
        print("\n❌ Basic websocket test failed!")
        print("📋 Troubleshooting steps:")
        print("   1. Make sure your GNU Radio .grc flowgraph is running")
        print("   2. Check that it's listening on port 52002")
        print("   3. Verify websocket-client is installed: pip install websocket-client")
        return 1
    
    # Test with SIREN encoding
    if not test_with_siren_encoding():
        print("⚠️  SIREN encoding test had issues, but basic websocket works")
    
    print("\n✅ GNU Radio websocket interface is ready!")
    print("🚀 You can now run the full SIREN transmitter:")
    print("   python siren_gnuradio_transmitter.py --mmsi 123456789 --lat 39.5 --lon -9.2 --once")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
