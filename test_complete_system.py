#!/usr/bin/env python3

import time
import subprocess
import threading
from maritime_transmitter import MaritimeAISTransmitter
from maritime_decoder import ProductionMaritimeDecoder

def test_complete_system():
    """Test the complete AIS system with the fixes implemented"""
    
    print("🧪 COMPLETE AIS SYSTEM TEST")
    print("=" * 50)
    print("Testing maritime_transmitter.py and maritime_decoder.py")
    print("with all fixes implemented")
    print()
    
    # Test 1: Verify transmitter frame generation
    print("📡 TEST 1: Transmitter Frame Generation")
    print("-" * 40)
    
    try:
        tx = MaritimeAISTransmitter()
        test_message = "!AIVDM,1,1,,A,15MvlfP000G?n@@K>OW`4?vN0<0=,0*47"
        
        # Generate frame
        training, data = tx.create_maritime_frame(test_message)
        if training is None:
            print("❌ Failed to create frame")
            return False
            
        print(f"✅ Frame created: Training({len(training)}) + Data({len(data)})")
        
        # Verify training sequence
        training_str = ''.join(map(str, training))
        expected_training = "010101010101010101010101"
        
        if training_str == expected_training:
            print("✅ Training sequence correct")
        else:
            print(f"❌ Training sequence wrong: {training_str}")
            return False
            
        # Apply NRZI
        nrzi_data = tx.nrzi_encode(data)
        complete_frame = training + nrzi_data
        
        print(f"✅ Complete frame: {len(complete_frame)} bits")
        print(f"   Start: {''.join(map(str, complete_frame[:32]))}")
        
    except Exception as e:
        print(f"❌ Transmitter test failed: {e}")
        return False
    
    # Test 2: Verify decoder with simulated signal
    print(f"\n📡 TEST 2: Decoder with Simulated Signal")
    print("-" * 40)
    
    try:
        decoder = ProductionMaritimeDecoder()
        
        # Generate test signal (complex baseband)
        import numpy as np
        signal = tx.generate_gmsk(complete_frame)
        
        # Add padding to simulate real RF environment
        padding = 2000
        padded_signal = np.concatenate([
            np.zeros(padding, dtype=np.complex64),
            signal,
            np.zeros(padding, dtype=np.complex64)
        ])
        
        print(f"✅ Generated test signal: {len(padded_signal)} complex samples")
        
        # Test decoder with complex signal (it will do FM demodulation internally)
        result = decoder.decode_signal(padded_signal)
        
        if result:
            print(f"✅ Decoder success: {result}")
            
            # Verify MMSI matches
            from pyais import decode
            orig_decoded = decode(test_message)
            new_decoded = decode(result)
            
            if orig_decoded.mmsi == new_decoded.mmsi:
                print("✅ MMSI match - decoder working correctly!")
                return True
            else:
                print(f"❌ MMSI mismatch: {orig_decoded.mmsi} != {new_decoded.mmsi}")
                return False
        else:
            print("❌ Decoder failed to decode signal")
            return False
            
    except Exception as e:
        print(f"❌ Decoder test failed: {e}")
        return False

def run_hardware_test():
    """Instructions for running the hardware test"""
    print(f"\n🚢 HARDWARE TEST INSTRUCTIONS")
    print("=" * 50)
    print("The software fixes have been implemented in:")
    print("  ✅ maritime_transmitter.py - Enhanced signal generation and debug")
    print("  ✅ maritime_decoder.py - Fixed pattern inversion handling")
    print()
    print("To test with live hardware:")
    print("1. Start the transmitter:")
    print("   python maritime_transmitter.py")
    print()
    print("2. Start the decoder (in another terminal):")
    print("   python maritime_decoder.py")
    print()
    print("Expected results:")
    print("  📡 Transmitter: Shows training sequence verification")
    print("  📡 Decoder: Detects inverted pattern, applies XOR logic")
    print("  🎉 Success: MMSI 366982330, Message Type 1")
    print()
    print("Key fixes implemented:")
    print("  ✅ Pattern inversion detection without symbol flipping")
    print("  ✅ XOR logic for NRZI decoding: effective_inv = nrzi_inv ^ pattern_inv")
    print("  ✅ Enhanced debugging and validation")
    print("  ✅ Better signal integrity checking")

if __name__ == "__main__":
    print("🌊 MARITIME AIS SYSTEM - PRODUCTION READY")
    print("=" * 60)
    
    # Run simulated tests
    success = test_complete_system()
    
    if success:
        print(f"\n🏆 ALL TESTS PASSED! 🏆")
        print("✅ System is ready for live hardware testing")
        run_hardware_test()
    else:
        print(f"\n❌ TESTS FAILED")
        print("Please check the implementation")
