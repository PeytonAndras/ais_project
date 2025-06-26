#!/usr/bin/env python3

import sys
import numpy as np
sys.path.append('debug')

from maritime_transmitter import MaritimeAISTransmitter
from maritime_decoder import ProductionMaritimeDecoder

def debug_symbol_extraction():
    """Debug exactly why we're only getting 167 symbols"""
    print("🔧 SYMBOL EXTRACTION LENGTH DEBUG")
    print("=" * 40)
    
    transmitter = MaritimeAISTransmitter()
    decoder = ProductionMaritimeDecoder()
    
    test_msg = "!AIVDM,1,1,,A,15MvlfP000G?n@@K>OW`4?vN0<0=,0*47"
    
    # Generate frame and signal
    frame = transmitter.create_maritime_frame(test_msg)
    gmsk_signal = transmitter.generate_gmsk(frame)
    
    print(f"📊 Frame: {len(frame)} bits")
    print(f"📡 Signal: {len(gmsk_signal)} samples")
    
    # FM demodulate
    demod_signal, activity = decoder.fm_demodulate(gmsk_signal)
    print(f"📡 Demodulated: {len(demod_signal)} samples")
    
    # Manually debug clock recovery
    samples_per_symbol = int(decoder.sample_rate / decoder.symbol_rate)
    print(f"🔧 Samples per symbol: {samples_per_symbol}")
    
    # Create training template
    training_bits = [0, 1] * 12
    training_nrz = []
    for bit in training_bits:
        level = 1.0 if bit else -1.0
        training_nrz.extend([level] * samples_per_symbol)
    training_template = np.array(training_nrz)
    
    print(f"🔧 Training template: {len(training_template)} samples")
    
    # Run actual clock recovery (this should now be fixed)
    symbols, offset = decoder.clock_recovery(demod_signal)
    
    print(f"🔧 Clock recovery result:")
    print(f"🔧 Symbols extracted: {len(symbols) if symbols else 0}")
    print(f"🔧 Clock offset: {offset}")
    
    # Manually debug correlation (for comparison)
    correlation = np.correlate(demod_signal, training_template, mode='valid')
    abs_corr = np.abs(correlation)
    
    max_idx = np.argmax(abs_corr)
    max_corr = abs_corr[max_idx]
    
    print(f"🔧 Best correlation: {max_corr:.1f} at sample {max_idx}")
    print(f"🔧 Signal length: {len(demod_signal)} samples")
    
    # Calculate maximum symbols possible from correlation point
    remaining_samples = len(demod_signal) - max_idx
    max_symbols_possible = remaining_samples // samples_per_symbol
    
    print(f"🔧 Remaining samples after correlation: {remaining_samples}")
    print(f"🔧 Maximum symbols possible: {max_symbols_possible}")
    
    # Extract symbols manually to see where it stops
    start_sample = max_idx
    symbols = []
    
    for i in range(max_symbols_possible):
        sample_pos = start_sample + i * samples_per_symbol + samples_per_symbol // 2
        if sample_pos < len(demod_signal):
            value = demod_signal[int(sample_pos)]
            symbol = 1 if value > 0 else 0
            symbols.append(symbol)
        else:
            print(f"🔧 Stopped at symbol {i}: sample_pos {sample_pos} >= signal_len {len(demod_signal)}")
            break
    
    print(f"🔧 Actually extracted: {len(symbols)} symbols")
    
    # Show the math
    expected_signal_length = len(frame) * samples_per_symbol
    print(f"\n📊 EXPECTED vs ACTUAL:")
    print(f"Expected signal length: {len(frame)} symbols × {samples_per_symbol} = {expected_signal_length} samples")
    print(f"Actual signal length: {len(gmsk_signal)} samples")
    print(f"Demodulated length: {len(demod_signal)} samples")
    print(f"Correlation at: sample {max_idx}")
    print(f"Expected symbols from start: {len(frame)}")
    print(f"Actual symbols extracted: {len(symbols)}")
    
    # The issue might be that correlation finds training late in signal
    # Calculate where training SHOULD be (at the beginning)
    expected_training_start = 0
    actual_training_start = max_idx
    
    print(f"\n🔍 TIMING ANALYSIS:")
    print(f"Expected training at sample: {expected_training_start}")
    print(f"Found training at sample: {actual_training_start}")
    print(f"Timing offset: {actual_training_start} samples")
    print(f"Timing offset in symbols: {actual_training_start / samples_per_symbol:.2f}")
    
    # Test if the decoder's full end-to-end processing works
    if symbols:
        print(f"\n🔧 FULL END-TO-END DECODE TEST:")
        frame_start, inverted = decoder.find_frame_start(symbols)
        if frame_start >= 0:
            print(f"✅ Frame start found at position: {frame_start}")
            # Extract bits after training pattern
            frame_symbols = symbols[frame_start + 24:]  # Skip training
            if len(frame_symbols) > 50:
                bits = decoder.nrzi_decode(frame_symbols, inverted)
                if len(bits) > 200:
                    message = decoder.extract_message(bits)
                    if message:
                        print(f"✅ Successfully decoded message: {message}")
                    else:
                        print(f"❌ Failed to extract message from {len(bits)} bits")
                else:
                    print(f"❌ Not enough bits decoded: {len(bits)}")
            else:
                print(f"❌ Not enough frame symbols: {len(frame_symbols)}")
        else:
            print(f"❌ Frame start not found")

    if actual_training_start > len(training_template):
        print("⚠️  Training found late in signal - this reduces available symbols!")

if __name__ == "__main__":
    debug_symbol_extraction()
