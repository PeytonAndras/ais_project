#!/usr/bin/env python3
"""
Simple AIS Bit Monitor - Receives and displays raw bits on AIS frequencies
with improved noise filtering
"""
import sys
import time
import numpy as np
from scipy import signal
import rtlsdr

# AIS frequencies
AIS_FREQ_A = 161.975e6  # MHz - Channel A
AIS_FREQ_B = 162.025e6  # MHz - Channel B

# GMSK parameters
SAMPLE_RATE = 1.024e6  # Hz
SYMBOL_RATE = 9600  # Hz
SAMPLES_PER_SYMBOL = int(SAMPLE_RATE / SYMBOL_RATE)

def setup_sdr(freq, gain=40, ppm=0):
    """Initialize and configure RTL-SDR"""
    print(f"Initializing RTL-SDR on {freq/1e6:.3f} MHz...")
    try:
        sdr = rtlsdr.RtlSdr()
        sdr.sample_rate = SAMPLE_RATE
        
        # Try to set frequency correction - use try/except to handle errors
        try:
            if ppm != 0:
                sdr.freq_correction = ppm
                print(f"Set frequency correction to {ppm} ppm")
        except Exception as e:
            print(f"Warning: Could not set frequency correction: {e}")
        
        # Set center frequency
        sdr.center_freq = freq
        print(f"Set center frequency to {freq/1e6:.3f} MHz")
        
        # Set gain
        sdr.gain = gain
        print(f"Set gain to {gain} dB")
        
        return sdr
        
    except Exception as e:
        print(f"Error setting up RTL-SDR: {e}")
        return None

def demodulate_gmsk(samples):
    """Enhanced GMSK demodulation for AIS signals with noise reduction"""
    if len(samples) < 100:
        return []
    
    # Apply bandpass filter to reduce noise outside signal bandwidth
    # AIS signal bandwidth is ~14 kHz (9600 baud × 1.4 BT factor)
    nyquist = SAMPLE_RATE / 2
    low_cutoff = 7000 / nyquist   # 7 kHz below center
    high_cutoff = 7000 / nyquist  # 7 kHz above center
    b, a = signal.butter(5, [low_cutoff, high_cutoff], btype='band')
    filtered_samples = signal.filtfilt(b, a, samples)
    
    # Apply a Gaussian filter matched to AIS GMSK (BT=0.4)
    bt = 0.4  # AIS standard
    span = 4
    t = np.linspace(-span/2, span/2, span*SAMPLES_PER_SYMBOL)
    h = np.exp(-2*np.pi**2 * t**2 / bt**2)
    h = h / np.sum(h)
    
    # Apply the filter to I/Q components separately
    i_filt = signal.convolve(np.real(filtered_samples), h, mode='same')
    q_filt = signal.convolve(np.imag(filtered_samples), h, mode='same')
    
    # Phase demodulation
    samples_complex = i_filt + 1j*q_filt
    diff_phase = np.diff(np.unwrap(np.angle(samples_complex)))
    
    # Additional low-pass filtering on the demodulated signal
    b, a = signal.butter(5, 1.5*SYMBOL_RATE/SAMPLE_RATE)
    filtered_diff_phase = signal.filtfilt(b, a, diff_phase)
    
    # Downsample to symbol rate with improved timing recovery
    # Look for transitions to identify symbol boundaries
    symbols = []
    
    # Use zero-crossing detection for better timing
    # Only consider chunks with significant signal energy
    chunk_size = SAMPLES_PER_SYMBOL * 20  # Look at 20 symbols at a time
    for chunk_start in range(0, len(filtered_diff_phase), chunk_size):
        chunk_end = min(chunk_start + chunk_size, len(filtered_diff_phase))
        chunk = filtered_diff_phase[chunk_start:chunk_end]
        
        # Only process chunks with enough variance (actual signal present)
        if np.var(chunk) > 0.01:  # Threshold for signal vs noise
            for i in range(0, len(chunk), SAMPLES_PER_SYMBOL):
                if i + SAMPLES_PER_SYMBOL < len(chunk):
                    # Use the middle of the symbol period for more robust sampling
                    mid_point = i + SAMPLES_PER_SYMBOL // 2
                    symbol_value = chunk[mid_point]
                    symbols.append(1 if symbol_value > 0 else 0)
    
    return symbols

def detect_ais_frame(bits):
    """Look for AIS frame start flag (01111110) and return frame if found"""
    if len(bits) < 24:  # Need at least flag + some data
        return None
    
    # AIS flag pattern (01111110)
    flag = [0, 1, 1, 1, 1, 1, 1, 0]
    
    # Look for the flag pattern
    for i in range(len(bits) - 7):
        match = True
        for j in range(8):
            if bits[i+j] != flag[j]:
                match = False
                break
        
        if match:
            # Found start flag, extract frame until end flag or end of bits
            frame = []
            for k in range(i+8, len(bits)):
                frame.append(bits[k])
                
                # Check if we've reached end flag
                if k >= i+8+7 and all(bits[k-j] == flag[7-j] for j in range(8)):
                    return frame[:-7]  # Return frame without the end flag
    
    return None

def monitor_frequency(freq, duration=30, gain=40, ppm=0):
    """Monitor a specific AIS frequency for the specified duration"""
    # Setup SDR
    sdr = setup_sdr(freq, gain, ppm)
    if not sdr:
        print("Failed to initialize SDR. Exiting.")
        return
    
    try:
        print(f"Monitoring {freq/1e6:.3f} MHz for {duration} seconds...")
        print("Press Ctrl+C to stop early")
        
        start_time = time.time()
        bit_buffer = []  # Keep track of bits across multiple samples
        signal_detected = False
        
        # Main monitoring loop
        while time.time() - start_time < duration:
            try:
                # Read slightly longer samples for better filtering
                samples = sdr.read_samples(int(SAMPLE_RATE * 0.25))
                
                # Calculate signal power
                signal_power = 10 * np.log10(np.mean(np.abs(samples)**2))
                
                # Only show power updates occasionally to reduce console spam
                if not signal_detected:
                    print(f"Signal power: {signal_power:.2f} dB", end="\r")
                
                # Only process strong signals - higher threshold to reduce false positives
                if signal_power > -30:  # Increased threshold
                    if not signal_detected:
                        print(f"\nSignal detected ({signal_power:.2f} dB)! Demodulating...")
                        signal_detected = True
                    
                    # Demodulate and get bits
                    bits = demodulate_gmsk(samples)
                    
                    # Add to buffer
                    bit_buffer.extend(bits)
                    
                    # Keep buffer at a reasonable size
                    if len(bit_buffer) > 1000:
                        bit_buffer = bit_buffer[-1000:]
                    
                    # Try to detect AIS frames
                    frame = detect_ais_frame(bit_buffer)
                    if frame and len(frame) >= 16:  # Minimum meaningful frame size
                        print("\nPossible AIS frame detected!")
                        print("Bits: ", end="")
                        for i in range(0, len(frame), 8):
                            group = frame[i:min(i+8, len(frame))]
                            print(''.join(map(str, group)), end=" ")
                        print("\n")
                        
                        # Clear buffer after finding a frame
                        bit_buffer = []
                else:
                    signal_detected = False
                
                # Small pause to reduce CPU usage
                time.sleep(0.05)
                
            except Exception as e:
                print(f"Error reading samples: {e}")
                time.sleep(0.5)  # Wait a bit before trying again
                
    except KeyboardInterrupt:
        print("\nStopped by user")
    finally:
        # Always clean up the SDR
        print("\nCleaning up...")
        sdr.close()
        print("Done.")

def main():
    print("=== Simple AIS Bit Monitor ===")
    
    # Get PPM correction
    ppm = 0
    try:
        ppm_input = input("Enter frequency correction in PPM (0 if unsure): ")
        if ppm_input.strip():
            ppm = int(ppm_input)
    except ValueError:
        print("Invalid PPM value, using 0")
    
    # Get gain setting
    gain = 40
    try:
        gain_input = input("Enter gain in dB (20-50, 40 recommended): ")
        if gain_input.strip():
            gain = float(gain_input)
    except ValueError:
        print("Invalid gain value, using 40 dB")
        
    # Choose channel
    print("\n1: Channel A (161.975 MHz)")
    print("2: Channel B (162.025 MHz)")
    print("3: Both channels (alternating)")
    
    choice = input("\nSelect channel(s) to monitor: ")
    
    if choice == "1":
        # Monitor Channel A only
        monitor_frequency(AIS_FREQ_A, duration=60, gain=gain, ppm=ppm)
    elif choice == "2":
        # Monitor Channel B only
        monitor_frequency(AIS_FREQ_B, duration=60, gain=gain, ppm=ppm)
    else:
        # Monitor both channels, alternating
        print("\nMonitoring both channels (30 seconds each)")
        
        # Main loop - alternate between channels
        try:
            while True:
                print("\n--- Channel A ---")
                monitor_frequency(AIS_FREQ_A, duration=30, gain=gain, ppm=ppm)
                
                print("\n--- Channel B ---")
                monitor_frequency(AIS_FREQ_B, duration=30, gain=gain, ppm=ppm)
                
        except KeyboardInterrupt:
            print("\nExiting...")

if __name__ == "__main__":
    main()