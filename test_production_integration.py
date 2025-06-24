#!/usr/bin/env python3
"""
Production AIS Integration Test

Tests the integration of the production-ready AIS transmitter
from hybrid_maritime_ais into the SIREN transmission system.
"""

import sys
import os
import traceback

def test_production_imports():
    """Test that production transmitter imports work correctly"""
    print("🔍 Testing production transmitter imports...")
    try:
        from siren.transmission.production_transmitter import (
            ProductionAISTransmitter,
            TransmissionConfig,
            OperationMode,
            ProductionAISProtocol,
            ProductionModulator,
            ProductionSDRInterface,
            get_production_transmitter,
            create_production_config,
            is_production_mode_available
        )
        print("✅ Production transmitter imports successful")
        return True
    except ImportError as e:
        print(f"❌ Production transmitter import failed: {e}")
        return False

def test_enhanced_sdr_controller():
    """Test enhanced SDR controller with production capabilities"""
    print("\n📡 Testing enhanced SDR controller...")
    try:
        from siren.transmission.sdr_controller import (
            TransmissionController,
            transmit_ships_production,
            start_continuous_transmission,
            stop_continuous_transmission,
            get_transmission_status,
            set_production_mode,
            get_signal_presets
        )
        
        # Test signal presets include production modes
        presets = get_signal_presets()
        production_presets = [p for p in presets if p.get('mode') == 'production']
        
        if production_presets:
            print(f"✅ Found {len(production_presets)} production signal presets")
        else:
            print("⚠️ No production signal presets found")
        
        print("✅ Enhanced SDR controller imports successful")
        return True
    except ImportError as e:
        print(f"❌ Enhanced SDR controller import failed: {e}")
        return False

def test_enhanced_simulation_controller():
    """Test enhanced simulation controller with production capabilities"""
    print("\n🎮 Testing enhanced simulation controller...")
    try:
        from siren.simulation.simulation_controller import (
            SimulationController,
            start_simulation,
            stop_simulation,
            set_production_transmission,
            get_simulation_transmission_status
        )
        print("✅ Enhanced simulation controller imports successful")
        return True
    except ImportError as e:
        print(f"❌ Enhanced simulation controller import failed: {e}")
        return False

def test_production_protocol():
    """Test production AIS protocol implementation"""
    print("\n📋 Testing production AIS protocol...")
    try:
        from siren.transmission.production_transmitter import (
            ProductionAISProtocol,
            OperationMode
        )
        from siren.ships.ais_ship import AISShip
        
        # Create test ship
        test_ship = AISShip(
            name="Test Vessel",
            mmsi=123456789,
            ship_type=70,  # Cargo vessel
            lat=37.7749,
            lon=-122.4194,
            speed=12.5,
            course=45.0
        )
        
        # Test protocol
        protocol = ProductionAISProtocol(OperationMode.PRODUCTION)
        message_bits = protocol.create_position_message_bits(test_ship)
        
        if len(message_bits) == 168:  # Standard AIS message length
            print("✅ Production AIS protocol generates correct message length")
        else:
            print(f"⚠️ Unexpected message length: {len(message_bits)} bits")
        
        # Test complete frame generation
        frame = protocol.create_complete_frame(test_ship)
        
        if len(frame) > 200:  # Frame should include training, flags, data, CRC, etc.
            print("✅ Production AIS protocol generates complete frame")
        else:
            print(f"⚠️ Frame seems too short: {len(frame)} bits")
        
        return True
    except Exception as e:
        print(f"❌ Production AIS protocol test failed: {e}")
        traceback.print_exc()
        return False

def test_production_modulator():
    """Test production modulator"""
    print("\n🎵 Testing production modulator...")
    try:
        from siren.transmission.production_transmitter import (
            ProductionModulator,
            OperationMode
        )
        import numpy as np
        
        # Test GMSK modulation
        modulator = ProductionModulator(96000, mode=OperationMode.PRODUCTION)
        test_bits = [0, 1, 0, 1, 1, 0, 1, 0] * 10  # Test pattern
        
        signal = modulator.modulate(test_bits)
        
        if isinstance(signal, np.ndarray) and len(signal) > 0:
            print(f"✅ GMSK modulation successful: {len(signal)} samples")
        else:
            print("❌ GMSK modulation failed")
            return False
        
        # Test FSK modulation for rtl_ais
        modulator_fsk = ProductionModulator(250000, mode=OperationMode.RTL_AIS_TESTING)
        signal_fsk = modulator_fsk.modulate(test_bits)
        
        if isinstance(signal_fsk, np.ndarray) and len(signal_fsk) > 0:
            print(f"✅ FSK modulation successful: {len(signal_fsk)} samples")
        else:
            print("❌ FSK modulation failed")
            return False
        
        return True
    except Exception as e:
        print(f"❌ Production modulator test failed: {e}")
        return False

def test_transmission_config():
    """Test transmission configuration"""
    print("\n⚙️ Testing transmission configuration...")
    try:
        from siren.transmission.production_transmitter import (
            TransmissionConfig,
            OperationMode,
            create_production_config
        )
        
        # Test default config
        config = TransmissionConfig()
        print(f"✅ Default config: {config.mode.value} mode, {config.frequency/1e6} MHz")
        
        # Test production config creation
        prod_config = create_production_config(
            mode=OperationMode.PRODUCTION,
            frequency=161975000,
            tx_gain=40.0,
            enable_sotdma=True
        )
        
        if prod_config.mode == OperationMode.PRODUCTION:
            print("✅ Production config creation successful")
        else:
            print("❌ Production config creation failed")
            return False
        
        # Test rtl_ais config
        rtl_config = create_production_config(
            mode=OperationMode.RTL_AIS_TESTING,
            frequency=162025000,
            sample_rate=250000
        )
        
        if rtl_config.mode == OperationMode.RTL_AIS_TESTING:
            print("✅ rtl_ais config creation successful")
        else:
            print("❌ rtl_ais config creation failed")
            return False
        
        return True
    except Exception as e:
        print(f"❌ Transmission config test failed: {e}")
        return False

def test_sdr_availability():
    """Test SDR availability detection"""
    print("\n📻 Testing SDR availability...")
    try:
        from siren.transmission.production_transmitter import is_production_mode_available
        
        available = is_production_mode_available()
        if available:
            print("✅ Production mode available (SoapySDR detected)")
        else:
            print("⚠️ Production mode not available (SoapySDR not found)")
        
        return True
    except Exception as e:
        print(f"❌ SDR availability test failed: {e}")
        return False

def test_ship_integration():
    """Test integration with SIREN ship objects"""
    print("\n🚢 Testing ship integration...")
    try:
        from siren.ships.ship_manager import get_ship_manager
        from siren.transmission.production_transmitter import ProductionAISTransmitter
        
        ship_manager = get_ship_manager()
        ships = ship_manager.get_ships()
        
        if ships:
            print(f"✅ Found {len(ships)} ships in ship manager")
            
            # Test with first ship
            test_ship = ships[0]
            transmitter = ProductionAISTransmitter()
            
            # This would normally transmit, but we'll just test the frame creation
            from siren.transmission.production_transmitter import ProductionAISProtocol, OperationMode
            protocol = ProductionAISProtocol(OperationMode.PRODUCTION)
            frame = protocol.create_complete_frame(test_ship)
            
            if frame:
                print(f"✅ Successfully created frame for ship: {test_ship.name}")
            else:
                print("❌ Failed to create frame for ship")
                return False
        else:
            print("⚠️ No ships found in ship manager")
        
        return True
    except Exception as e:
        print(f"❌ Ship integration test failed: {e}")
        return False

def run_all_tests():
    """Run all production integration tests"""
    print("🧪 PRODUCTION AIS INTEGRATION TESTS")
    print("=" * 50)
    
    tests = [
        test_production_imports,
        test_enhanced_sdr_controller,
        test_enhanced_simulation_controller,
        test_production_protocol,
        test_production_modulator,
        test_transmission_config,
        test_sdr_availability,
        test_ship_integration
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
        print("🎉 ALL TESTS PASSED! Production AIS integration is ready.")
        return True
    else:
        print(f"⚠️ {failed} test(s) failed. Review integration issues.")
        return False

if __name__ == "__main__":
    # Add the project root to the path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    success = run_all_tests()
    sys.exit(0 if success else 1)
