#!/usr/bin/env python3

import sys
import numpy as np
sys.path.append('debug')

from maritime_transmitter import MaritimeAISTransmitter
from maritime_decoder import ProductionMaritimeDecoder

def debug_gmsk_symbols():
    """Debug GMSK symbol extraction vs transmitted frame"""
    print("🔧 GMSK SYMBOL EXTRACTION DEBUG")
    print("Comparing transmitted bits vs received symbols")
    print("=" * 50)
    
    transmitter = MaritimeAISTransmitter()
    decoder = ProductionMaritimeDecoder()
    
    test_msg = "!AIVDM,1,1,,A,15MvlfP000G?n@@K>OW`4?vN0<0=,0*47"
    
    # Generate frame
    frame = transmitter.create_maritime_frame(test_msg)
    print(f"📊 Generated frame: {len(frame)} bits")
    
    # Show first 40 bits of transmitted frame
    frame_str = ''.join(map(str, frame[:40]))
    print(f"🔧 TX Frame: {frame_str}")
    print(f"🔧 Expected: 010101010101010101010101|01111110|...")
    print(f"🔧           ^--- training ---^   ^-flag-^")
    
    # Generate GMSK signal  
    gmsk_signal = transmitter.generate_gmsk(frame)
    print(f"📡 GMSK signal: {len(gmsk_signal)} samples")
    
    # FM demodulate
    demod_signal, activity = decoder.fm_demodulate(gmsk_signal)
    if demod_signal is None:
        print("❌ FM demodulation failed")
        return
    
    print(f"📡 Demodulated: {len(demod_signal)} samples, activity={activity:.1f}")
    
    # Clock recovery
    symbols, timing_offset = decoder.clock_recovery(demod_signal)
    if symbols is None:
        print("❌ Clock recovery failed")
        return
    
    print(f"📊 Extracted symbols: {len(symbols)}")
    
    # Find training pattern
    frame_pos, pattern_inverted = decoder.find_frame_start(symbols)
    print(f"🔧 Training found at position {frame_pos}, inverted={pattern_inverted}")
    
    if frame_pos == -1:
        print("❌ No training pattern found")
        return
    
    # Compare transmitted vs received
    print("\n🔄 SYMBOL COMPARISON:")
    compare_length = min(50, len(frame), len(symbols) - frame_pos)
    
    tx_frame = frame[:]
    rx_symbols = symbols[frame_pos:]
    
    if pattern_inverted:
        rx_symbols = [1 - s for s in rx_symbols]
    
    tx_str = ''.join(map(str, tx_frame[:compare_length]))
    rx_str = ''.join(map(str, rx_symbols[:compare_length]))
    
    print(f"TX: {tx_str}")
    print(f"RX: {rx_str}")
    
    # Calculate match rate
    matches = sum(a == b for a, b in zip(tx_str, rx_str))
    print(f"Match: {matches}/{compare_length} = {matches/compare_length*100:.1f}%")
    
    # Analyze specific sections
    print("\n🔍 SECTION ANALYSIS:")
    
    # Training (0-23)
    if len(tx_str) > 24 and len(rx_str) > 24:
        tx_training = tx_str[:24]
        rx_training = rx_str[:24]
        training_matches = sum(a == b for a, b in zip(tx_training, rx_training))
        print(f"Training: {training_matches}/24 = {training_matches/24*100:.1f}%")
        
        # Start flag (24-31)
        tx_flag = tx_str[24:32] if len(tx_str) > 32 else tx_str[24:]
        rx_flag = rx_str[24:32] if len(rx_str) > 32 else rx_str[24:]
        flag_matches = sum(a == b for a, b in zip(tx_flag, rx_flag))
        print(f"Start flag: {flag_matches}/{len(tx_flag)} = {flag_matches/len(tx_flag)*100:.1f}%")
        print(f"  TX flag: {tx_flag}")
        print(f"  RX flag: {rx_flag}")
        
        # Payload start (32-41)
        if len(tx_str) > 42 and len(rx_str) > 42:
            tx_payload = tx_str[32:42]
            rx_payload = rx_str[32:42]
            payload_matches = sum(a == b for a, b in zip(tx_payload, rx_payload))
            print(f"Payload start: {payload_matches}/10 = {payload_matches/10*100:.1f}%")
    
    # Try different alignments
    print("\n🔧 TRYING ALIGNMENTS:")
    best_match = matches
    best_offset = 0
    
    for offset in range(-5, 6):
        if offset == 0:
            continue
            
        if offset < 0:
            # TX ahead
            tx_test = tx_frame[-offset:compare_length-offset]
            rx_test = rx_symbols[:compare_length+offset]
        else:
            # RX ahead
            tx_test = tx_frame[:compare_length-offset]
            rx_test = rx_symbols[offset:compare_length]
        
        if len(tx_test) == len(rx_test) and len(tx_test) > 0:
            test_matches = sum(a == b for a, b in zip(tx_test, rx_test))
            match_rate = test_matches / len(tx_test) * 100
            
            if test_matches > best_match:
                best_match = test_matches
                best_offset = offset
            
            if offset in [-2, -1, 1, 2]:  # Show key offsets
                print(f"Offset {offset:+2d}: {test_matches:2d}/{len(tx_test):2d} = {match_rate:5.1f}%")
    
    print(f"\n✅ Best alignment: offset {best_offset:+d} with {best_match} matches")

if __name__ == "__main__":
    debug_gmsk_symbols()
