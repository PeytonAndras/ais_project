#!/usr/bin/env python3

import sys
import numpy as np
import matplotlib.pyplot as plt
sys.path.append('debug')

from maritime_transmitter import MaritimeAISTransmitter
from maritime_decoder import ProductionMaritimeDecoder

def analyze_gmsk_signal():
    """Analyze GMSK signal to find why training pattern appears late"""
    print("🔧 GMSK SIGNAL ANALYSIS")
    print("=" * 40)
    
    transmitter = MaritimeAISTransmitter()
    decoder = ProductionMaritimeDecoder()
    
    test_msg = "!AIVDM,1,1,,A,15MvlfP000G?n@@K>OW`4?vN0<0=,0*47"
    
    # Generate frame and signal
    frame = transmitter.create_maritime_frame(test_msg)
    gmsk_signal = transmitter.generate_gmsk(frame)
    
    print(f"📊 Frame: {len(frame)} bits")
    print(f"📡 GMSK Signal: {len(gmsk_signal)} samples")
    
    # Analyze the raw GMSK signal before FM demodulation
    magnitude = np.abs(gmsk_signal)
    phase = np.angle(gmsk_signal)
    
    # Find where signal activity actually starts
    activity_threshold = 0.1 * np.max(magnitude)
    signal_start = 0
    for i, mag in enumerate(magnitude):
        if mag > activity_threshold:
            signal_start = i
            break
    
    print(f"🔧 Signal magnitude range: {np.min(magnitude):.3f} to {np.max(magnitude):.3f}")
    print(f"🔧 Activity threshold: {activity_threshold:.3f}")
    print(f"🔧 Signal activity starts at sample: {signal_start}")
    
    # Analyze frequency content
    instant_freq = np.diff(np.unwrap(phase)) * transmitter.sample_rate / (2 * np.pi)
    
    print(f"🔧 Instantaneous frequency range: {np.min(instant_freq):.1f} to {np.max(instant_freq):.1f} Hz")
    print(f"🔧 Expected deviation: ±{transmitter.freq_deviation} Hz")
    
    # FM demodulate
    demod_signal, activity = decoder.fm_demodulate(gmsk_signal)
    print(f"📡 Demodulated: {len(demod_signal)} samples")
    
    # Find first significant activity in demodulated signal
    demod_activity_threshold = 0.1 * np.max(np.abs(demod_signal))
    demod_start = 0
    for i, val in enumerate(demod_signal):
        if abs(val) > demod_activity_threshold:
            demod_start = i
            break
    
    print(f"🔧 Demod activity starts at sample: {demod_start}")
    
    # Check if the problem is in the correlation template
    samples_per_symbol = int(decoder.sample_rate / decoder.symbol_rate)
    training_bits = [0, 1] * 12  # 24 bits alternating
    
    # Convert to NRZ signal levels for correlation
    training_nrz = []
    for bit in training_bits:
        level = 1.0 if bit else -1.0
        training_nrz.extend([level] * samples_per_symbol)
    training_template = np.array(training_nrz)
    
    print(f"🔧 Training template: {len(training_template)} samples")
    
    # Try correlation at different positions
    print(f"\n🔧 CORRELATION ANALYSIS:")
    test_positions = [0, 100, 500, 1000, 1500, 1800, 2000]
    
    for pos in test_positions:
        if pos + len(training_template) < len(demod_signal):
            test_segment = demod_signal[pos:pos + len(training_template)]
            correlation = np.sum(test_segment * training_template)
            print(f"Position {pos:4d}: correlation = {correlation:8.1f}")
    
    # Full correlation to find peak
    correlation = np.correlate(demod_signal, training_template, mode='valid')
    abs_corr = np.abs(correlation)
    max_idx = np.argmax(abs_corr)
    max_corr = abs_corr[max_idx]
    
    print(f"\n🔧 Peak correlation: {max_corr:.1f} at sample {max_idx}")
    
    # Look at the actual demodulated signal around the correlation peak
    peak_start = max(0, max_idx - 100)
    peak_end = min(len(demod_signal), max_idx + len(training_template) + 100)
    peak_signal = demod_signal[peak_start:peak_end]
    
    print(f"🔧 Peak signal segment: samples {peak_start} to {peak_end}")
    print(f"🔧 Peak signal range: {np.min(peak_signal):.3f} to {np.max(peak_signal):.3f}")
    
    # Check if we can extract symbols from the expected position (beginning)
    print(f"\n🔧 SYMBOL EXTRACTION FROM START:")
    early_symbols = []
    for i in range(min(50, len(demod_signal) // samples_per_symbol)):
        sample_pos = i * samples_per_symbol + samples_per_symbol // 2
        if sample_pos < len(demod_signal):
            value = demod_signal[sample_pos]
            symbol = 1 if value > 0 else 0
            early_symbols.append(symbol)
    
    if len(early_symbols) >= 24:
        early_training = ''.join(map(str, early_symbols[:24]))
        expected_training = "010101010101010101010101"
        matches = sum(a == b for a, b in zip(early_training, expected_training))
        print(f"Early symbols (first 24): {early_training}")
        print(f"Expected training:        {expected_training}")
        print(f"Matches: {matches}/24")
        
        if matches < 20:
            # Try inverted
            inverted_early = ''.join('1' if s == '0' else '0' for s in early_training)
            inv_matches = sum(a == b for a, b in zip(inverted_early, expected_training))
            print(f"Inverted early:           {inverted_early}")
            print(f"Inverted matches: {inv_matches}/24")
    
    # Save a plot for visual inspection
    plt.figure(figsize=(15, 10))
    
    plt.subplot(3, 1, 1)
    plt.plot(magnitude[:2000])
    plt.title("GMSK Signal Magnitude (first 2000 samples)")
    plt.ylabel("Magnitude")
    
    plt.subplot(3, 1, 2)
    plt.plot(instant_freq[:2000])
    plt.title("Instantaneous Frequency")
    plt.ylabel("Frequency (Hz)")
    
    plt.subplot(3, 1, 3)
    plt.plot(demod_signal[:2000])
    plt.title("FM Demodulated Signal")
    plt.ylabel("Amplitude")
    plt.xlabel("Sample")
    
    plt.tight_layout()
    plt.savefig('debug/gmsk_signal_analysis.png', dpi=150, bbox_inches='tight')
    print(f"🖼️ Signal plot saved to debug/gmsk_signal_analysis.png")

if __name__ == "__main__":
    analyze_gmsk_signal()
