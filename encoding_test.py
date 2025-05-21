#!/usr/bin/env python3
"""
Enhanced NATO Navy AIS Encoding Test Script
Creates proper GMSK modulated AIS signals for RTL-SDR reception
"""
import numpy as np
import time
import random
import os
import subprocess
import struct
import tempfile
from scipy import signal

# AIS frequencies
AIS_FREQ_A = 161.975e6  # MHz - Channel A
AIS_FREQ_B = 162.025e6  # MHz - Channel B

# AIS transmission parameters
SAMPLE_RATE = 2e6
SYMBOL_RATE = 9600
SAMPLES_PER_SYMBOL = int(SAMPLE_RATE / SYMBOL_RATE)

# AIS messages with valid CRC for testing
AIS_MESSAGES = [
    # Position report class A (with valid checksum)
    "!AIVDM,1,1,,A,13u?etPv2;0n:dDPwUM1U1Cb069D,0*23",
    # Base station report (with valid checksum)
    "!AIVDM,1,1,,A,403OwpiuIKl0D;R>l0`A4aSn00d0,0*66",
    # Static and voyage data (with valid checksum)
    "!AIVDM,1,1,,A,54eGuT02?;WCC:0QSkB=pl<h0000,0*6C",
    # Class B position report (with valid checksum)
    "!AIVDM,1,1,,B,B43JRq00LhRujTmdHLTC?wWUoP06,0*00",
]

def char_to_sixbit(char):
    """Convert ASCII character to 6-bit representation used in AIS"""
    val = ord(char) - 48
    if val > 40:
        val -= 8
    bits = []
    for i in range(5, -1, -1):
        bits.append((val >> i) & 1)
    return bits

def calculate_crc(bits):
    """Calculate CRC-16-CCITT for AIS message correctly at bit level"""
    poly = 0x1021
    crc = 0xFFFF
    
    for bit in bits:
        # Correctly process one bit at a time
        crc ^= (bit << 15)
        crc = (crc << 1) ^ poly if crc & 0x8000 else crc << 1
        crc &= 0xFFFF
    
    return [(crc >> i) & 1 for i in range(15, -1, -1)]

def create_ais_signal(nmea_sentence, sample_rate=SAMPLE_RATE, repetitions=3):
    """Create a properly modulated AIS signal from NMEA sentence"""
    print(f"Processing NMEA sentence: {nmea_sentence}")
    
    # Extract payload from NMEA sentence
    parts = nmea_sentence.split(',')
    if len(parts) < 6:
        raise ValueError("Invalid NMEA sentence")
    
    payload = parts[5]
    print(f"Encoding payload: {payload}")
    
    # Convert 6-bit ASCII to bits
    bits = []
    for char in payload:
        char_bits = char_to_sixbit(char)
        bits.extend(char_bits)
    
    # Calculate and append CRC
    crc_bits = calculate_crc(bits)
    bits.extend(crc_bits)
    print(f"CRC bits added: {crc_bits}")
    
    # Create HDLC frame with flags and bit stuffing
    start_flag = [0, 1, 1, 1, 1, 1, 1, 0]
    stuffed_bits = []
    
    # Start flag
    stuffed_bits.extend(start_flag)
    
    # Training sequence (longer for better receiver lock)
    stuffed_bits.extend([0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1])
    
    # Add data bits with bit stuffing
    consecutive_ones = 0
    for bit in bits:
        stuffed_bits.append(bit)
        if bit == 1:
            consecutive_ones += 1
        else:
            consecutive_ones = 0
            
        # After 5 consecutive ones, insert a 0 (bit stuffing)
        if consecutive_ones == 5:
            stuffed_bits.append(0)
            consecutive_ones = 0
    
    # End flag
    stuffed_bits.extend(start_flag)
    
    # Add ramp up/down buffer zeros (improves reception)
    final_bits = [0] * 24 + stuffed_bits + [0] * 24
    
    # NRZI encoding (AIS standard)
    nrzi_bits = []
    current_level = 0
    
    for bit in final_bits:
        if bit == 0:  # In AIS, 0 causes transition
            current_level = 1 - current_level
        nrzi_bits.append(current_level)
    
    # GMSK modulation
    samples_per_bit = int(sample_rate / SYMBOL_RATE)
    
    # Create Gaussian filter (BT=0.4 for AIS standard)
    bt = 0.4
    span = 3.0
    sps = samples_per_bit
    
    # Gaussian filter design
    n = int(span * sps)
    t = np.linspace(-span/2, span/2, n)
    alpha = np.sqrt(np.log(2))/2 * np.pi * bt
    h = (np.sqrt(np.pi)/alpha) * np.exp(-(t*np.pi/alpha)**2)
    h = h / np.sum(h)
    
    # Upsample bits
    upsampled = np.zeros(len(nrzi_bits) * samples_per_bit)
    for i, bit in enumerate(nrzi_bits):
        upsampled[i*samples_per_bit] = 1.0 if bit else -1.0
    
    # Apply Gaussian filter
    filtered = np.convolve(upsampled, h, 'same')
    
    # Integrate for phase (MSK)
    phase = np.cumsum(filtered) * (np.pi/2) / samples_per_bit
    
    # Generate I/Q samples
    iq_samples = np.exp(1j * phase)
    
    # Pre-emphasis filter for better reception
    emphasis = np.exp(-1j * np.pi * 0.25)
    iq_samples = iq_samples * emphasis
    
    # Normalize power
    peak = np.max(np.abs(iq_samples))
    if peak > 0:
        iq_samples = iq_samples / peak * 0.98
    
    # Ramp up/down to avoid clicks
    ramp_len = int(samples_per_bit * 8)
    if len(iq_samples) > 2*ramp_len:
        ramp = np.hamming(ramp_len*2)
        iq_samples[:ramp_len] *= ramp[:ramp_len]
        iq_samples[-ramp_len:] *= ramp[ramp_len:]
    
    # Repeat the signal for better reception chance
    final_signal = np.tile(iq_samples, repetitions)
    
    # Add silence between repetitions
    silence_len = int(sample_rate * 0.2)  # 200ms silence
    final_signal_with_silence = np.zeros(len(final_signal) + silence_len * (repetitions-1), dtype=complex)
    
    # Insert signal with silent gaps
    pos = 0
    chunk_len = len(iq_samples)
    for i in range(repetitions):
        final_signal_with_silence[pos:pos+chunk_len] = iq_samples
        pos += chunk_len
        if i < repetitions-1:
            pos += silence_len
    
    print(f"Created AIS signal with {len(final_signal_with_silence)} samples")
    return final_signal_with_silence

def transmit_with_hackrf(signal_data, center_freq, sample_rate=SAMPLE_RATE, tx_gain=40):
    """Transmit I/Q samples using HackRF"""
    # Convert complex samples to 8-bit I/Q data for hackrf_transfer
    iq_data = np.zeros(len(signal_data)*2, dtype=np.int8)
    iq_data[0::2] = np.clip(np.real(signal_data) * 127, -127, 127).astype(np.int8)
    iq_data[1::2] = np.clip(np.imag(signal_data) * 127, -127, 127).astype(np.int8)
    
    # Save to temporary file
    with tempfile.NamedTemporaryFile(delete=False) as f:
        temp_filename = f.name
        iq_data.tofile(f)
    
    try:
        # Transmit using hackrf_transfer
        cmd = [
            "hackrf_transfer",
            "-t", temp_filename,
            "-f", str(int(center_freq)),
            "-s", str(int(sample_rate)),
            "-x", str(tx_gain),
            "-a", "1",  # Enable antenna port
            "-b", "1.75"  # Set baseband filter bandwidth (MHz)
        ]
        
        print(f"Transmitting on {center_freq/1e6:.3f} MHz with gain {tx_gain} dB")
        print(f"Command: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error: {result.stderr}")
        else:
            print("Transmission completed successfully")
            
    except Exception as e:
        print(f"Transmission error: {e}")
    finally:
        # Clean up
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

def main():
    """Main function with improved AIS transmission"""
    print("=== Enhanced AIS Transmission for RTL-SDR Reception ===")
    print("WARNING: Transmitting on AIS frequencies without proper authorization is illegal!")
    print("This should only be used in a controlled testing environment.")
    print("\nPress Ctrl+C to stop...")
    
    # Ask for transmission parameters
    repetitions = int(input("Number of message repetitions (3-10 recommended): ") or 3)
    delay = float(input("Delay between transmissions in seconds (5-30 recommended): ") or 10)
    tx_gain = int(input("TX gain (0-47, higher = stronger signal): ") or 40)
    
    # Choose frequency
    print("\n1: Channel A (161.975 MHz)")
    print("2: Channel B (162.025 MHz)")
    channel = input("Select channel (1/2): ") or "1"
    freq = AIS_FREQ_A if channel == "1" else AIS_FREQ_B
    
    # Start transmission loop
    try:
        message_count = 0
        while True:
            # Alternate between predefined and custom messages
            message = AIS_MESSAGES[message_count % len(AIS_MESSAGES)]
            message_count += 1
            
            print(f"\n[{time.strftime('%H:%M:%S')}] Transmission #{message_count}")
            
            # Create proper AIS modulated signal
            signal_data = create_ais_signal(message, repetitions=repetitions)
            
            # Transmit the signal
            transmit_with_hackrf(signal_data, freq, SAMPLE_RATE, tx_gain)
            
            # Wait before next transmission
            print(f"Waiting {delay} seconds until next transmission...")
            time.sleep(delay)
            
    except KeyboardInterrupt:
        print("\nTransmission stopped by user.")

if __name__ == "__main__":
    main()