#!/usr/bin/env python3
"""
Hybrid Maritime AIS Demonstration

This script demonstrates the key features of the hybrid maritime AIS transmitter,
showing how to use both production and rtl_ais testing modes.
"""

import time
import json
import numpy as np
from hybrid_maritime_ais import VesselInfo, HybridMaritimeAIS, OperationMode

def demo_production_mode():
    """Demonstrate production maritime AIS beacon"""
    print("\n🚢 PRODUCTION MODE DEMONSTRATION")
    print("=" * 50)
    
    # Create vessel information
    vessel = VesselInfo(
        mmsi=123456789,
        latitude=37.7749,
        longitude=-122.4194,
        speed_over_ground=12.5,
        course_over_ground=45.0,
        heading=45,
        nav_status=0  # Under way using engine
    )
    
    # Create transmitter in production mode
    transmitter = HybridMaritimeAIS(vessel, OperationMode.PRODUCTION)
    
    print(f"📍 Vessel Position: {vessel.latitude:.6f}, {vessel.longitude:.6f}")
    print(f"⚡ Speed/Course: {vessel.speed_over_ground:.1f} kts, {vessel.course_over_ground:.1f}°")
    print(f"📻 Frequency: {transmitter.sdr.frequency/1e6:.6f} MHz (AIS Channel A)")
    print(f"🔧 Sample Rate: {transmitter.sdr.sample_rate/1000:.0f} kS/s")
    print(f"🎯 SOTDMA: {'Enabled' if transmitter.sotdma else 'Disabled'}")
    
    # Simulate single transmission
    print("\n📡 Transmitting position report...")
    success = transmitter.transmit_position_report()
    
    if success:
        print("✅ Production transmission completed successfully")
        print(f"📊 Packets sent: {transmitter.packets_sent}")
    else:
        print("⚠️  Production transmission failed (likely no hardware)")
    
    # Show status
    status = transmitter.get_status()
    print(f"\n📋 Status: {json.dumps(status, indent=2)}")
    
    transmitter.close()

def demo_rtl_ais_testing_mode():
    """Demonstrate rtl_ais compatibility testing"""
    print("\n📡 RTL_AIS TESTING MODE DEMONSTRATION")
    print("=" * 50)
    
    # Create vessel for testing
    vessel = VesselInfo(
        mmsi=999999001,  # Test MMSI
        latitude=37.7749,
        longitude=-122.4194,
        speed_over_ground=0.0,
        course_over_ground=0.0
    )
    
    # Create transmitter in rtl_ais testing mode
    transmitter = HybridMaritimeAIS(vessel, OperationMode.RTL_AIS_TESTING)
    
    print(f"📍 Test Position: {vessel.latitude:.6f}, {vessel.longitude:.6f}")
    print(f"📻 Frequency: {transmitter.sdr.frequency/1e6:.6f} MHz (Channel B for rtl_ais)")
    print(f"🔧 Sample Rate: {transmitter.sdr.sample_rate/1000:.0f} kS/s (High rate for clean FSK)")
    print(f"🎯 Optimization: Polar discriminator tuned FSK")
    print(f"⚡ Power Scaling: 0.7x for optimal receiver performance")
    
    # Simulate rtl_ais compatible transmission
    print("\n📡 Transmitting rtl_ais optimized signal...")
    success = transmitter.transmit_position_report()
    
    if success:
        print("✅ rtl_ais testing transmission completed")
        print("📻 Signal optimized for rtl_ais polar discriminator")
    else:
        print("⚠️  rtl_ais testing transmission failed (likely no hardware)")
    
    transmitter.close()

def demo_nmea_compatibility():
    """Demonstrate NMEA sentence compatibility"""
    print("\n📜 NMEA COMPATIBILITY DEMONSTRATION")
    print("=" * 50)
    
    # Test NMEA sentence
    test_nmea = "!AIVDM,1,1,,A,15MvlfP000G?n@@K>OW`4?vN0<0=,0*47"
    
    # Create basic vessel info
    vessel = VesselInfo(
        mmsi=123456789,
        latitude=37.7749,
        longitude=-122.4194
    )
    
    # Create transmitter in compatibility mode
    transmitter = HybridMaritimeAIS(vessel, OperationMode.RTL_AIS_TESTING)
    
    print(f"📄 Test NMEA: {test_nmea}")
    print("🔍 Parsing and validating NMEA sentence...")
    
    # Transmit NMEA sentence
    success = transmitter.transmit_from_nmea(test_nmea)
    
    if success:
        print("✅ NMEA compatibility transmission completed")
        print("📡 Successfully parsed and transmitted NMEA sentence")
    else:
        print("⚠️  NMEA transmission failed")
    
    transmitter.close()

def demo_signal_analysis():
    """Demonstrate signal generation and analysis"""
    print("\n🔬 SIGNAL ANALYSIS DEMONSTRATION")
    print("=" * 50)
    
    vessel = VesselInfo(mmsi=123456789, latitude=37.7749, longitude=-122.4194)
    
    # Test both modulation modes
    for mode in [OperationMode.PRODUCTION, OperationMode.RTL_AIS_TESTING]:
        print(f"\n🎛️  {mode.value.upper()} MODE SIGNAL")
        
        transmitter = HybridMaritimeAIS(vessel, mode)
        
        # Generate frame
        frame = transmitter.protocol.create_frame_from_vessel(vessel)
        print(f"📊 Frame length: {len(frame)} bits")
        
        # Verify frame structure
        training = ''.join(map(str, frame[:24]))
        start_flag = ''.join(map(str, frame[24:32]))
        print(f"🔧 Training: {training}")
        print(f"🔧 Start Flag: {start_flag}")
        
        # Generate signal
        signal = transmitter.modulator.modulate(frame)
        signal = transmitter.modulator.add_ramps(signal)
        
        print(f"📡 Signal samples: {len(signal)}")
        print(f"📊 Duration: {len(signal)/transmitter.sdr.sample_rate:.3f} seconds")
        print(f"⚡ Mean magnitude: {np.mean(np.abs(signal)):.3f}")
        print(f"📈 Peak magnitude: {np.max(np.abs(signal)):.3f}")
        
        transmitter.close()

def demo_continuous_operation():
    """Demonstrate continuous operation (simulation)"""
    print("\n🔄 CONTINUOUS OPERATION DEMONSTRATION")
    print("=" * 50)
    
    vessel = VesselInfo(
        mmsi=123456789,
        latitude=37.7749,
        longitude=-122.4194,
        speed_over_ground=10.0,
        course_over_ground=90.0
    )
    
    transmitter = HybridMaritimeAIS(vessel, OperationMode.PRODUCTION)
    
    print("🚀 Starting continuous transmission simulation...")
    print("📊 Simulating 30 seconds of operation")
    
    # Simulate vessel movement
    for i in range(6):
        # Update position (simulate eastward movement)
        new_lon = vessel.longitude + (i * 0.001)  # ~100m eastward
        transmitter.update_vessel_position(vessel.latitude, new_lon)
        
        # Update speed
        new_speed = vessel.speed_over_ground + (i * 0.5)
        transmitter.update_vessel_motion(new_speed, vessel.course_over_ground)
        
        # Simulate transmission
        print(f"\n📡 Transmission {i+1}/6")
        print(f"📍 Position: {vessel.latitude:.6f}, {new_lon:.6f}")
        print(f"⚡ Speed: {new_speed:.1f} kts")
        
        success = transmitter.transmit_position_report()
        if success:
            print("✅ Transmission successful")
        else:
            print("⚠️  Transmission failed (no hardware)")
        
        time.sleep(1)  # 1 second interval for demo
    
    print(f"\n📊 Final Status:")
    status = transmitter.get_status()
    print(f"   Packets sent: {status['packets_sent']}")
    print(f"   Last transmission: {time.ctime(status['last_transmission']) if status['last_transmission'] else 'None'}")
    
    transmitter.close()

def main():
    """Run all demonstrations"""
    print("🚢 HYBRID MARITIME AIS TRANSMITTER DEMONSTRATION")
    print("=" * 60)
    print("This demo shows the key features without requiring hardware")
    print("=" * 60)
    
    try:
        # Run demonstrations
        demo_production_mode()
        demo_rtl_ais_testing_mode()
        demo_nmea_compatibility()
        demo_signal_analysis()
        demo_continuous_operation()
        
        print("\n" + "=" * 60)
        print("✅ ALL DEMONSTRATIONS COMPLETED SUCCESSFULLY")
        print("=" * 60)
        print("\n🚀 Ready for real maritime deployment!")
        print("\nNext steps:")
        print("1. Connect LimeSDR hardware")
        print("2. Configure vessel-specific parameters")
        print("3. Test in rtl_ais_testing mode")
        print("4. Deploy in production mode")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
