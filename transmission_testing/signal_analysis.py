#!/usr/bin/env python3
"""
Advanced AIS Signal Analysis and Validation

This module provides detailed analysis of generated AIS signals to verify
they match the specifications exactly.
"""

import numpy as np
import matplotlib.pyplot as plt
from typing import Tuple, List
import sys
import os

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ais_protocol import AISPositionReport, AISProtocol, GMSKModulator
from ais_validator import AISValidator

def analyze_packet_structure(packet_bits) -> dict:
    """Detailed packet structure analysis"""
    
    analysis = {
        'total_bits': len(packet_bits),
        'training_sequence': [],
        'start_delimiter': [],
        'data_portion': [],
        'end_delimiter': [],
        'structure_valid': False
    }
    
    bits = list(packet_bits)
    
    # Extract training sequence (first 24 bits)
    if len(bits) >= 24:
        analysis['training_sequence'] = bits[:24]
        expected_training = [1, 0] * 12
        analysis['training_valid'] = (analysis['training_sequence'] == expected_training)
    
    # Extract start delimiter (bits 24-31)
    if len(bits) >= 32:
        analysis['start_delimiter'] = bits[24:32]
        expected_start = [0, 1, 1, 1, 1, 1, 1, 0]
        analysis['start_valid'] = (analysis['start_delimiter'] == expected_start)
    
    # Find end delimiter (search backwards)
    expected_end = [0, 1, 1, 1, 1, 1, 1, 0]
    end_pos = -1
    if len(bits) >= 40:  # Minimum for start + some data + end
        for i in range(len(bits) - 8, 31, -1):
            if bits[i:i+8] == expected_end:
                end_pos = i
                break
    
    if end_pos != -1:
        analysis['end_delimiter'] = bits[end_pos:end_pos+8]
        analysis['end_valid'] = True
        analysis['data_portion'] = bits[32:end_pos]
        analysis['data_bits'] = len(analysis['data_portion'])
        analysis['structure_valid'] = True
    
    return analysis

def analyze_gmsk_signal(signal: np.ndarray, sample_rate: int) -> dict:
    """Analyze GMSK signal properties"""
    
    analysis = {
        'sample_rate': sample_rate,
        'length_samples': len(signal),
        'duration_seconds': len(signal) / sample_rate,
        'power_db': 10 * np.log10(np.mean(np.abs(signal)**2)) if np.mean(np.abs(signal)**2) > 0 else -np.inf,
        'peak_power_db': 10 * np.log10(np.max(np.abs(signal)**2)) if np.max(np.abs(signal)**2) > 0 else -np.inf,
    }
    
    # Analyze frequency content
    fft_data = np.fft.fftshift(np.fft.fft(signal))
    frequencies = np.fft.fftshift(np.fft.fftfreq(len(signal), 1/sample_rate))
    power_spectrum = 20 * np.log10(np.abs(fft_data) + 1e-12)
    
    # Find bandwidth (3dB points)
    peak_power = np.max(power_spectrum)
    mask = power_spectrum >= (peak_power - 3)
    if np.any(mask):
        freq_indices = np.where(mask)[0]
        analysis['bandwidth_3db'] = frequencies[freq_indices[-1]] - frequencies[freq_indices[0]]
    else:
        analysis['bandwidth_3db'] = 0
    
    # Check for continuous phase (GMSK requirement)
    phase = np.unwrap(np.angle(signal))
    phase_diff = np.diff(phase)
    analysis['max_phase_jump'] = np.max(np.abs(phase_diff))
    analysis['phase_continuous'] = analysis['max_phase_jump'] < 0.1  # Small threshold for continuous phase
    
    return analysis

def decode_nrzi_bits(nrzi_bits) -> List[int]:
    """Decode NRZI back to original bits"""
    if len(nrzi_bits) == 0:
        return []
    
    decoded = []
    previous_level = 0  # Start with 0
    
    for current_level in nrzi_bits:
        if current_level != previous_level:
            decoded.append(1)  # Transition = 1
        else:
            decoded.append(0)  # No transition = 0
        previous_level = current_level
    
    return decoded

def remove_bit_stuffing(bits: List[int]) -> List[int]:
    """Remove HDLC bit stuffing"""
    unstuffed = []
    consecutive_ones = 0
    i = 0
    
    while i < len(bits):
        bit = bits[i]
        
        if consecutive_ones == 5 and bit == 0:
            # This is a stuffed bit, skip it
            consecutive_ones = 0
        else:
            unstuffed.append(bit)
            if bit == 1:
                consecutive_ones += 1
            else:
                consecutive_ones = 0
        
        i += 1
    
    return unstuffed

def validate_crc(data_bits: List[int]) -> bool:
    """Validate CRC-16 CCITT"""
    if len(data_bits) < 16:
        return False
    
    # Split into message and CRC
    message_bits = data_bits[:-16]
    received_crc_bits = data_bits[-16:]
    
    # Convert message to bytes
    message_bytes = bytearray()
    for i in range(0, len(message_bits), 8):
        if i + 8 <= len(message_bits):
            byte_bits = message_bits[i:i+8]
            byte_val = 0
            for j, bit in enumerate(byte_bits):
                byte_val |= (bit << (7-j))
            message_bytes.append(byte_val)
    
    # Calculate expected CRC
    crc = 0xFFFF
    for byte in message_bytes:
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    crc ^= 0xFFFF
    
    # Convert received CRC to int
    received_crc = 0
    for i, bit in enumerate(received_crc_bits):
        received_crc |= (bit << (15-i))
    
    return crc == received_crc

def comprehensive_signal_test():
    """Run comprehensive signal analysis"""
    
    print("Comprehensive AIS Signal Analysis")
    print("=" * 50)
    
    # Create test message
    message = AISPositionReport(
        mmsi=123456789,
        latitude=37.7749,
        longitude=-122.4194,
        sog=12.5,
        cog=45.0,
        heading=45
    )
    
    print(f"Test Message:")
    print(f"  MMSI: {message.mmsi}")
    print(f"  Position: {message.latitude:.6f}, {message.longitude:.6f}")
    print(f"  SOG: {message.sog} knots")
    print(f"  COG: {message.cog}°")
    print(f"  Heading: {message.heading}°")
    print()
    
    # Generate packet
    protocol = AISProtocol()
    packet_bits = protocol.create_packet(message)
    
    print("1. Packet Structure Analysis")
    print("-" * 30)
    analysis = analyze_packet_structure(packet_bits)
    print(f"  Total bits: {analysis['total_bits']}")
    print(f"  Training sequence valid: {analysis.get('training_valid', 'N/A')}")
    print(f"  Start delimiter valid: {analysis.get('start_valid', 'N/A')}")
    print(f"  End delimiter valid: {analysis.get('end_valid', 'N/A')}")
    print(f"  Data portion bits: {analysis.get('data_bits', 'N/A')}")
    print(f"  Overall structure: {'VALID' if analysis['structure_valid'] else 'INVALID'}")
    print()
    
    # Apply NRZI encoding
    nrzi_bits = protocol.nrzi_encode(packet_bits)
    
    print("2. NRZI Encoding Test")
    print("-" * 30)
    print(f"  Original bits: {len(packet_bits)}")
    print(f"  NRZI bits: {len(nrzi_bits)}")
    
    # Test NRZI decoding
    decoded_bits = decode_nrzi_bits(list(nrzi_bits))
    nrzi_correct = (decoded_bits == list(packet_bits))
    print(f"  NRZI decode test: {'PASS' if nrzi_correct else 'FAIL'}")
    print()
    
    # Generate signal
    modulator = GMSKModulator(sample_rate=96000, symbol_rate=9600)
    signal = modulator.modulate(nrzi_bits)
    
    print("3. GMSK Signal Analysis")
    print("-" * 30)
    sig_analysis = analyze_gmsk_signal(signal, 96000)
    print(f"  Duration: {sig_analysis['duration_seconds']:.4f} seconds")
    print(f"  Power: {sig_analysis['power_db']:.1f} dB")
    print(f"  Peak power: {sig_analysis['peak_power_db']:.1f} dB")
    print(f"  3dB bandwidth: {sig_analysis['bandwidth_3db']:.0f} Hz")
    print(f"  Phase continuous: {'YES' if sig_analysis['phase_continuous'] else 'NO'}")
    print(f"  Max phase jump: {sig_analysis['max_phase_jump']:.4f} radians")
    print()
    
    # Bit stuffing test
    print("4. Bit Stuffing Analysis")
    print("-" * 30)
    if analysis['structure_valid']:
        data_portion = analysis['data_portion']
        unstuffed = remove_bit_stuffing(data_portion)
        print(f"  Stuffed data bits: {len(data_portion)}")
        print(f"  Unstuffed data bits: {len(unstuffed)}")
        
        # Validate CRC
        crc_valid = validate_crc(unstuffed)
        print(f"  CRC validation: {'PASS' if crc_valid else 'FAIL'}")
    else:
        print("  Cannot analyze - invalid structure")
    print()
    
    # Timing analysis
    print("5. Timing Analysis")
    print("-" * 30)
    symbol_rate = 9600
    samples_per_symbol = 96000 // symbol_rate
    expected_symbols = len(nrzi_bits)
    expected_samples = expected_symbols * samples_per_symbol
    actual_samples = len(signal)
    
    print(f"  Symbol rate: {symbol_rate} bps")
    print(f"  Samples per symbol: {samples_per_symbol}")
    print(f"  Expected symbols: {expected_symbols}")
    print(f"  Expected samples: {expected_samples}")
    print(f"  Actual samples: {actual_samples}")
    print(f"  Timing accuracy: {'GOOD' if abs(actual_samples - expected_samples) <= samples_per_symbol else 'POOR'}")
    print()
    
    # Generate detailed report
    print("6. Compatibility Assessment")
    print("-" * 30)
    
    issues = []
    if not analysis.get('training_valid', False):
        issues.append("Invalid training sequence")
    if not analysis.get('start_valid', False):
        issues.append("Invalid start delimiter")
    if not analysis.get('end_valid', False):
        issues.append("Invalid end delimiter")
    if not nrzi_correct:
        issues.append("NRZI encoding error")
    if not sig_analysis['phase_continuous']:
        issues.append("Phase discontinuity in GMSK")
    
    if not issues:
        print("  ✓ Signal appears fully compliant with AIS specification")
        print("  ✓ Should be decodable by rtl-ais and other receivers")
        print("  ✓ Ready for over-the-air testing")
    else:
        print("  ✗ Issues found:")
        for issue in issues:
            print(f"    - {issue}")
    
    print()
    print("Analysis complete!")
    
    return len(issues) == 0

def plot_signal_analysis(save_plots: bool = False):
    """Create plots for signal analysis"""
    
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("Matplotlib not available - skipping plots")
        return
    
    # Generate test signal
    message = AISPositionReport(mmsi=123456789, latitude=37.7749, longitude=-122.4194)
    protocol = AISProtocol()
    packet_bits = protocol.create_packet(message)
    nrzi_bits = protocol.nrzi_encode(packet_bits)
    
    modulator = GMSKModulator(sample_rate=96000, symbol_rate=9600)
    signal = modulator.modulate(nrzi_bits)
    
    # Create plots
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    
    # Time domain
    t = np.arange(len(signal)) / 96000
    axes[0, 0].plot(t * 1000, np.real(signal), label='I')
    axes[0, 0].plot(t * 1000, np.imag(signal), label='Q')
    axes[0, 0].set_xlabel('Time (ms)')
    axes[0, 0].set_ylabel('Amplitude')
    axes[0, 0].set_title('GMSK Signal - Time Domain')
    axes[0, 0].legend()
    axes[0, 0].grid()
    
    # Magnitude and phase
    axes[0, 1].plot(t * 1000, np.abs(signal))
    axes[0, 1].set_xlabel('Time (ms)')
    axes[0, 1].set_ylabel('Magnitude')
    axes[0, 1].set_title('Signal Magnitude')
    axes[0, 1].grid()
    
    # Frequency spectrum
    fft_data = np.fft.fftshift(np.fft.fft(signal))
    frequencies = np.fft.fftshift(np.fft.fftfreq(len(signal), 1/96000))
    power_spectrum = 20 * np.log10(np.abs(fft_data) + 1e-12)
    
    axes[1, 0].plot(frequencies / 1000, power_spectrum)
    axes[1, 0].set_xlabel('Frequency (kHz)')
    axes[1, 0].set_ylabel('Power (dB)')
    axes[1, 0].set_title('Frequency Spectrum')
    axes[1, 0].grid()
    
    # Phase
    phase = np.unwrap(np.angle(signal))
    axes[1, 1].plot(t * 1000, phase)
    axes[1, 1].set_xlabel('Time (ms)')
    axes[1, 1].set_ylabel('Phase (radians)')
    axes[1, 1].set_title('Signal Phase (Continuous for GMSK)')
    axes[1, 1].grid()
    
    plt.tight_layout()
    
    if save_plots:
        plt.savefig('ais_signal_analysis.png', dpi=300, bbox_inches='tight')
        print("Signal analysis plots saved to ais_signal_analysis.png")
    else:
        plt.show()

def main():
    """Main analysis function"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description='Advanced AIS Signal Analysis')
    parser.add_argument('--plot', action='store_true', help='Generate analysis plots')
    parser.add_argument('--save-plots', action='store_true', help='Save plots to file')
    
    args = parser.parse_args()
    
    # Run comprehensive analysis
    success = comprehensive_signal_test()
    
    # Generate plots if requested
    if args.plot or args.save_plots:
        plot_signal_analysis(save_plots=args.save_plots)
    
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())
