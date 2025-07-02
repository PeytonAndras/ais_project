#!/usr/bin/env python3
"""
Simple GNU Radio AIS Transmitter Test

This script tests the simple GNU Radio integration by sending AIS messages
to the ais-simulator.py websocket interface.

Usage:
1. Start ais-simulator.py in another terminal:
   cd ais-simulator && python3 ais-simulator.py
   
2. Run this test script:
   python3 simple_gnuradio_test.py

@ author: Peyton Andras @ Louisiana State University 2025
"""

import sys
import time
import argparse
import logging
import signal
from pathlib import Path

# Add SIREN to path
sys.path.append(str(Path(__file__).parent))

from siren.transmission.simple_gnuradio import SIRENGnuRadioIntegration
from siren.config.simple_gnuradio_config import check_dependencies, get_installation_instructions

class SimpleGnuRadioTest:
    """Test class for simple GNU Radio integration"""
    
    def __init__(self):
        self.integration = None
        self.running = False
        
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info("Received shutdown signal, stopping...")
        self.stop()
        sys.exit(0)
    
    def check_dependencies(self):
        """Check if all dependencies are available"""
        deps = check_dependencies()
        missing = [name for name, available in deps.items() if not available]
        
        if missing:
            print("❌ Missing dependencies!")
            print(get_installation_instructions())
            return False
        else:
            print("✅ All dependencies are available")
            return True
    
    def test_single_transmission(self, mmsi=123456789, lat=39.5, lon=-9.2):
        """Test sending a single AIS message"""
        print(f"\n🧪 Testing single AIS transmission")
        print(f"   MMSI: {mmsi}")
        print(f"   Position: {lat:.3f}, {lon:.3f}")
        
        # Create integration
        self.integration = SIRENGnuRadioIntegration(
            websocket_port=52002,
            transmission_interval=1,  # Fast for testing
            auto_reconnect=False
        )
        
        # Set up status callback
        def status_callback(status):
            print(f"   Status: {status}")
        
        self.integration.on_status_changed = status_callback
        
        # Start and test
        if self.integration.start():
            print("   ✅ Connected to GNU Radio")
            
            # Add test ship
            ship_data = {
                'mmsi': mmsi,
                'latitude': lat,
                'longitude': lon,
                'speed': 12.5,
                'course': 180.0,
                'status': 0
            }
            
            self.integration.add_ship(ship_data)
            print("   📡 Sending AIS message...")
            
            # Wait a bit for transmission
            time.sleep(2)
            
            status = self.integration.get_status()
            tx_status = status['transmitter_status']
            
            print(f"   📊 Status: {tx_status['packets_sent']} packets sent")
            
            if tx_status['packets_sent'] > 0:
                print("   ✅ Transmission successful!")
                return True
            else:
                print("   ❌ No packets sent")
                return False
        else:
            print("   ❌ Failed to connect to GNU Radio")
            print("   💡 Make sure ais-simulator.py is running!")
            return False
    
    def test_continuous_transmission(self, mmsi=123456789, lat=39.5, lon=-9.2, duration=30):
        """Test continuous AIS transmission"""
        print(f"\n🔄 Testing continuous AIS transmission for {duration} seconds")
        print(f"   MMSI: {mmsi}")
        print(f"   Starting position: {lat:.3f}, {lon:.3f}")
        
        # Create integration
        self.integration = SIRENGnuRadioIntegration(
            websocket_port=52002,
            transmission_interval=5,  # Every 5 seconds
            auto_reconnect=True
        )
        
        # Set up status callback
        def status_callback(status):
            print(f"   Status: {status}")
        
        self.integration.on_status_changed = status_callback
        
        # Start transmission
        if self.integration.start():
            print("   ✅ Connected to GNU Radio")
            self.running = True
            
            # Add moving ship
            start_time = time.time()
            
            while self.running and (time.time() - start_time) < duration:
                # Calculate moving position (simple linear movement)
                elapsed = time.time() - start_time
                moving_lat = lat + (elapsed * 0.001)  # Move north slowly
                moving_lon = lon + (elapsed * 0.001)  # Move east slowly
                
                ship_data = {
                    'mmsi': mmsi,
                    'latitude': moving_lat,
                    'longitude': moving_lon,
                    'speed': 10.0,
                    'course': 45.0,  # Northeast
                    'status': 0
                }
                
                # Update ship position
                self.integration.update_ship(mmsi, ship_data)
                
                # Add ship if not already added
                if len(self.integration.ships) == 0:
                    self.integration.add_ship(ship_data)
                
                # Status update
                status = self.integration.get_status()
                tx_status = status['transmitter_status']
                print(f"   📡 Position: {moving_lat:.3f}, {moving_lon:.3f} | "
                      f"Packets sent: {tx_status['packets_sent']}")
                
                time.sleep(5)  # Update every 5 seconds
            
            # Final status
            final_status = self.integration.get_status()
            final_tx_status = final_status['transmitter_status']
            
            print(f"   📊 Final status: {final_tx_status['packets_sent']} packets sent")
            
            if final_tx_status['packets_sent'] > 0:
                print("   ✅ Continuous transmission successful!")
                return True
            else:
                print("   ❌ No packets sent during test")
                return False
        else:
            print("   ❌ Failed to connect to GNU Radio")
            print("   💡 Make sure ais-simulator.py is running!")
            return False
    
    def test_multiple_ships(self, count=3, duration=20):
        """Test multiple ships transmitting"""
        print(f"\n🚢 Testing {count} ships transmitting for {duration} seconds")
        
        # Create integration
        self.integration = SIRENGnuRadioIntegration(
            websocket_port=52002,
            transmission_interval=3,  # Every 3 seconds
            auto_reconnect=True
        )
        
        if self.integration.start():
            print("   ✅ Connected to GNU Radio")
            self.running = True
            
            # Add multiple ships
            ships = []
            for i in range(count):
                ship_data = {
                    'mmsi': 123456789 + i,
                    'latitude': 39.5 + (i * 0.01),   # Spread ships out
                    'longitude': -9.2 + (i * 0.01),
                    'speed': 10.0 + (i * 2),         # Different speeds
                    'course': (i * 60) % 360,        # Different courses
                    'status': 0
                }
                ships.append(ship_data)
                self.integration.add_ship(ship_data)
                print(f"   Added ship MMSI {ship_data['mmsi']}")
            
            # Run for specified duration
            start_time = time.time()
            while self.running and (time.time() - start_time) < duration:
                status = self.integration.get_status()
                tx_status = status['transmitter_status']
                print(f"   📡 {status['ships_count']} ships | "
                      f"Packets sent: {tx_status['packets_sent']}")
                time.sleep(5)
            
            # Final status
            final_status = self.integration.get_status()
            final_tx_status = final_status['transmitter_status']
            
            print(f"   📊 Final: {final_status['ships_count']} ships, "
                  f"{final_tx_status['packets_sent']} packets sent")
            
            if final_tx_status['packets_sent'] > count:  # At least one packet per ship
                print("   ✅ Multiple ship transmission successful!")
                return True
            else:
                print("   ❌ Insufficient packets sent")
                return False
        else:
            print("   ❌ Failed to connect to GNU Radio")
            return False
    
    def stop(self):
        """Stop the test"""
        self.running = False
        if self.integration:
            self.integration.stop()
            self.integration = None


def main():
    """Main test function"""
    parser = argparse.ArgumentParser(description='Test Simple GNU Radio AIS Integration')
    parser.add_argument('--mmsi', type=int, default=123456789, help='Ship MMSI')
    parser.add_argument('--lat', type=float, default=39.5, help='Ship latitude')
    parser.add_argument('--lon', type=float, default=-9.2, help='Ship longitude')
    parser.add_argument('--test', choices=['single', 'continuous', 'multiple', 'all'], 
                       default='single', help='Test type to run')
    parser.add_argument('--duration', type=int, default=30, help='Test duration in seconds')
    parser.add_argument('--ships', type=int, default=3, help='Number of ships for multiple test')
    
    args = parser.parse_args()
    
    print("Simple GNU Radio AIS Transmitter Test")
    print("=" * 50)
    
    # Create test instance
    test = SimpleGnuRadioTest()
    
    try:
        # Check dependencies
        if not test.check_dependencies():
            return 1
        
        print("\n💡 Make sure ais-simulator.py is running:")
        print("   cd ais-simulator && python3 ais-simulator.py")
        print("   (GNU Radio flowgraph should be transmitting on your chosen frequency)")
        
        success = False
        
        if args.test == 'single' or args.test == 'all':
            success = test.test_single_transmission(args.mmsi, args.lat, args.lon)
            if test.integration:
                test.stop()
        
        if args.test == 'continuous' or args.test == 'all':
            if args.test == 'all':
                time.sleep(2)  # Brief pause between tests
            success = test.test_continuous_transmission(args.mmsi, args.lat, args.lon, args.duration)
            if test.integration:
                test.stop()
        
        if args.test == 'multiple' or args.test == 'all':
            if args.test == 'all':
                time.sleep(2)  # Brief pause between tests
            success = test.test_multiple_ships(args.ships, args.duration)
            if test.integration:
                test.stop()
        
        if success:
            print("\n🎉 Test completed successfully!")
            print("📻 Check your AIS receiver (rtl_ais, etc.) to verify transmission")
            return 0
        else:
            print("\n❌ Test failed!")
            return 1
            
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        test.stop()
        return 1
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        test.stop()
        return 1


if __name__ == "__main__":
    sys.exit(main())
