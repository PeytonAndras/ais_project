"""
Signal Processing Module

Handles GMSK modulation, signal generation, and RF signal creation.
Contains all signal processing functions from the original implementation.
"""

import numpy as np
from ..protocol.ais_encoding import char_to_sixbit, calculate_crc

# Signal configuration presets
SIGNAL_PRESETS = [
    {"name": "AIS Channel A", "freq": 161.975e6, "gain": 70, "modulation": "GMSK", "sdr_type": "hackrf"},
    {"name": "AIS Channel B", "freq": 162.025e6, "gain": 65, "modulation": "GMSK", "sdr_type": "hackrf"},
]

def create_ais_signal(nmea_sentence, sample_rate=2e6, repetitions=6):
    """Create a properly modulated AIS signal from NMEA sentence"""
    # Extract payload from NMEA sentence
    parts = nmea_sentence.split(',')
    if len(parts) < 6:
        raise ValueError("Invalid NMEA sentence")
    
    payload = parts[5]
    print(f"Creating AIS signal from payload: {payload}")
    
    # Convert 6-bit ASCII to bits
    bits = []
    for char in payload:
        char_bits = char_to_sixbit(char)
        bits.extend(char_bits)
    
    # Calculate and append CRC
    crc_bits = calculate_crc(bits)
    bits.extend(crc_bits)
    print(f"Added CRC bits: {crc_bits}")
    
    # Create HDLC frame with flags and bit stuffing
    start_flag = [0, 1, 1, 1, 1, 1, 1, 0]
    stuffed_bits = []
    consecutive_ones = 0
    
    # Start flag
    stuffed_bits.extend(start_flag)
    
    # Training sequence
    stuffed_bits.extend([0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1])
    
    # Log bit stuffing process
    print(f"Original bits length: {len(bits)}")
    
    # Add data bits with bit stuffing
    for i, bit in enumerate(bits):
        if bit == 1:
            consecutive_ones += 1
        else:
            consecutive_ones = 0
            
        stuffed_bits.append(bit)
        
        # After 5 consecutive ones, insert a 0
        if consecutive_ones == 5:
            stuffed_bits.append(0)
            consecutive_ones = 0
            print(f"Bit stuffing: Added zero after position {i}")
    
    # End flag
    stuffed_bits.extend(start_flag)
    
    print(f"After bit stuffing: length={len(stuffed_bits)}")
    
    # NRZI encoding
    nrzi_bits = []
    # Initialize with last bit of training sequence for better sync
    current_level = stuffed_bits[24] if len(stuffed_bits) > 24 else 0
    
    for bit in stuffed_bits:
        if bit == 0:
            current_level = 1 - current_level
        nrzi_bits.append(current_level)
    
    # GMSK modulation
    bit_rate = 9600.0  # AIS bit rate
    samples_per_bit = int(sample_rate / bit_rate)
    num_samples = len(nrzi_bits) * samples_per_bit
    
    # Create Gaussian filter with proper BT product
    bt = 0.4  # AIS BT product (standard value)
    filter_length = 4
    t = np.arange(-filter_length/2, filter_length/2, 1/samples_per_bit)
    h = np.sqrt(2*np.pi/np.log(2)) * bt * np.exp(-2*np.pi**2*bt**2*t**2/np.log(2))
    h = h / np.sum(h)
    
    # Upsample bits
    upsampled = np.zeros(num_samples)
    for i, bit in enumerate(nrzi_bits):
        upsampled[i*samples_per_bit] = 2*bit - 1
    
    # Apply Gaussian filter
    filtered = np.convolve(upsampled, h, 'same')
    
    # MSK modulation
    phase = np.cumsum(filtered) * np.pi / samples_per_bit
    
    # Generate I/Q samples
    i_samples = np.cos(phase)
    q_samples = np.sin(phase)
    iq_samples = i_samples + 1j * q_samples
    
    # Add pre-emphasis for better reception
    emphasis = np.exp(-1j * np.pi * 0.25)
    iq_samples *= emphasis
    
    # Normalize and scale
    max_amp = np.max(np.abs(iq_samples))
    if max_amp > 0:
        iq_samples = iq_samples / max_amp * 0.9
    
    # Repeat the signal
    return np.tile(iq_samples * 1.0, repetitions)

def get_signal_presets():
    """Get available signal presets"""
    return SIGNAL_PRESETS.copy()

def add_signal_preset(preset):
    """Add a new signal preset"""
    SIGNAL_PRESETS.append(preset)

def update_signal_preset(index, preset):
    """Update an existing signal preset"""
    if 0 <= index < len(SIGNAL_PRESETS):
        SIGNAL_PRESETS[index] = preset
