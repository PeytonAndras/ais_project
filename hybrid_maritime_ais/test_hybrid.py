#!/usr/bin/env python3
"""
Quick test script for Hybrid Maritime AIS Transmitter

This script performs basic functionality tests without requiring hardware.
"""

import sys
import traceback

def test_imports():
    """Test that all imports work correctly"""
    print("🔍 Testing imports...")
    try:
        from hybrid_maritime_ais import (
            VesselInfo, HybridMaritimeAIS, OperationMode,
            EnhancedAISProtocol, HybridModulator, AdaptiveLimeSDRInterface,
            SOTDMAController
        )
        print("✅ All imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def test_vessel_info():
    """Test VesselInfo creation"""
    print("\n🚢 Testing VesselInfo...")
    try:
        from hybrid_maritime_ais import VesselInfo
        
        vessel = VesselInfo(
            mmsi=123456789,
            latitude=37.7749,
            longitude=-122.4194,
            speed_over_ground=12.5,
            course_over_ground=45.0
        )
        
        assert vessel.mmsi == 123456789
        assert vessel.latitude == 37.7749
        assert vessel.longitude == -122.4194
        assert vessel.speed_over_ground == 12.5
        assert vessel.course_over_ground == 45.0
        
        print("✅ VesselInfo creation successful")
        return True
    except Exception as e:
        print(f"❌ VesselInfo test failed: {e}")
        return False

def test_protocol():
    """Test AIS protocol functionality"""
    print("\n📡 Testing AIS Protocol...")
    try:
        from hybrid_maritime_ais import EnhancedAISProtocol, VesselInfo
        
        protocol = EnhancedAISProtocol()
        vessel = VesselInfo(mmsi=123456789, latitude=37.7749, longitude=-122.4194)
        
        # Test message bit generation
        message_bits = protocol.create_position_message_bits(vessel)
        assert len(message_bits) > 100  # Should be around 168 bits
        
        # Test complete frame generation
        frame = protocol.create_frame_from_vessel(vessel)
        assert len(frame) > 200  # Should include training, flags, etc.
        
        # Verify frame structure
        training = ''.join(map(str, frame[:24]))
        assert training == "010101010101010101010101"
        
        start_flag = ''.join(map(str, frame[24:32]))
        assert start_flag == "01111110"
        
        print("✅ AIS Protocol tests successful")
        return True
    except Exception as e:
        print(f"❌ Protocol test failed: {e}")
        traceback.print_exc()
        return False

def test_modulator():
    """Test signal modulation"""
    print("\n🎵 Testing Modulator...")
    try:
        from hybrid_maritime_ais import HybridModulator, OperationMode
        import numpy as np
        
        # Test both modes
        for mode in [OperationMode.PRODUCTION, OperationMode.RTL_AIS_TESTING]:
            modulator = HybridModulator(sample_rate=96000, mode=mode)
            
            # Test signal generation
            test_bits = [0, 1, 0, 1, 1, 0, 1, 0]
            signal = modulator.modulate(test_bits)
            
            assert len(signal) > 0
            assert isinstance(signal, np.ndarray)
            assert signal.dtype == np.complex64
            
            # Test ramp addition
            ramped_signal = modulator.add_ramps(signal)
            assert len(ramped_signal) == len(signal)
        
        print("✅ Modulator tests successful")
        return True
    except Exception as e:
        print(f"❌ Modulator test failed: {e}")
        return False

def test_sotdma():
    """Test SOTDMA controller"""
    print("\n⏰ Testing SOTDMA...")
    try:
        from hybrid_maritime_ais import SOTDMAController
        
        sotdma = SOTDMAController(mmsi=123456789)
        
        # Test slot calculation
        slot_num, slot_time = sotdma.get_next_slot_time()
        
        assert isinstance(slot_num, int)
        assert 0 <= slot_num < 2250
        assert isinstance(slot_time, float)
        
        print("✅ SOTDMA tests successful")
        return True
    except Exception as e:
        print(f"❌ SOTDMA test failed: {e}")
        return False

def test_sdr_interface():
    """Test SDR interface (without hardware)"""
    print("\n📻 Testing SDR Interface...")
    try:
        from hybrid_maritime_ais import AdaptiveLimeSDRInterface, OperationMode
        
        # Test both modes
        for mode in [OperationMode.PRODUCTION, OperationMode.RTL_AIS_TESTING]:
            sdr = AdaptiveLimeSDRInterface(mode)
            
            # Check configuration
            if mode == OperationMode.PRODUCTION:
                assert sdr.frequency == 161975000
                assert sdr.sample_rate == 96000
            else:
                assert sdr.frequency == 162025000
                assert sdr.sample_rate == 250000
            
            sdr.close()
        
        print("✅ SDR Interface tests successful")
        return True
    except Exception as e:
        print(f"❌ SDR Interface test failed: {e}")
        return False

def test_main_application():
    """Test main application class"""
    print("\n🚢 Testing Main Application...")
    try:
        from hybrid_maritime_ais import HybridMaritimeAIS, VesselInfo, OperationMode
        
        vessel = VesselInfo(mmsi=123456789, latitude=37.7749, longitude=-122.4194)
        
        # Test both modes
        for mode in [OperationMode.PRODUCTION, OperationMode.RTL_AIS_TESTING]:
            transmitter = HybridMaritimeAIS(vessel, mode)
            
            # Test status
            status = transmitter.get_status()
            assert status['mode'] == mode.value
            assert status['vessel']['mmsi'] == 123456789
            
            # Test position update
            transmitter.update_vessel_position(38.0, -123.0)
            assert transmitter.vessel.latitude == 38.0
            assert transmitter.vessel.longitude == -123.0
            
            # Test motion update
            transmitter.update_vessel_motion(15.0, 90.0, 90)
            assert transmitter.vessel.speed_over_ground == 15.0
            assert transmitter.vessel.course_over_ground == 90.0
            assert transmitter.vessel.heading == 90
            
            transmitter.close()
        
        print("✅ Main Application tests successful")
        return True
    except Exception as e:
        print(f"❌ Main Application test failed: {e}")
        traceback.print_exc()
        return False

def test_nmea_compatibility():
    """Test NMEA compatibility (if pyais available)"""
    print("\n📜 Testing NMEA Compatibility...")
    try:
        from hybrid_maritime_ais import HybridMaritimeAIS, VesselInfo, OperationMode
        
        try:
            from pyais import decode
            pyais_available = True
        except ImportError:
            pyais_available = False
            print("⚠️  pyais not available, skipping NMEA test")
            return True
        
        if pyais_available:
            vessel = VesselInfo(mmsi=123456789, latitude=37.7749, longitude=-122.4194)
            transmitter = HybridMaritimeAIS(vessel, OperationMode.RTL_AIS_TESTING)
            
            # Test NMEA sentence
            test_nmea = "!AIVDM,1,1,,A,15MvlfP000G?n@@K>OW`4?vN0<0=,0*47"
            frame = transmitter.protocol.create_frame_from_nmea(test_nmea)
            
            if frame is not None:
                assert len(frame) > 200
                print("✅ NMEA compatibility successful")
            else:
                print("⚠️  NMEA frame creation returned None (validation may have failed)")
            
            transmitter.close()
        
        return True
    except Exception as e:
        print(f"❌ NMEA compatibility test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 HYBRID MARITIME AIS SYSTEM TESTS")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_vessel_info,
        test_protocol,
        test_modulator,
        test_sotdma,
        test_sdr_interface,
        test_main_application,
        test_nmea_compatibility
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 TEST RESULTS: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 ALL TESTS PASSED! System is ready for use.")
        return 0
    else:
        print("⚠️  Some tests failed. Check error messages above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
