#!/usr/bin/env python3
import numpy as np
import subprocess
import tempfile
import os
import time
from scipy import signal
from datetime import datetime

# Parameters
FREQ = 161975000  # 161.975 MHz
SAMPLE_RATE = 2_000_000  # 2 MHz
BAUD = 9600  # AIS baud rate
AMPLITUDE = 127 * 0.5  # Output amplitude (0 to 127)

# Example AIS message from the original script
ais_bits = (
    '000001'      # Message ID: 1
    '00'          # Repeat: 0
    '000111010110111100110100010101'  # MMSI: 123456789
    '0000'        # Nav status: 0 (under way)
    '10000000'    # ROT: 128 (not available)
    '0000000000'  # SOG: 0
    '0'           # Accuracy: 0
    '0000000000000000000000000000'  # Longitude: 0
    '000000000000000000000000000'   # Latitude: 0
    '000000000000' # COG: 0
    '000000000'    # Heading: 0
    '111100'       # Timestamp: 60 (not available)
    '00'           # Maneuver: 0
    '000'          # Spare: 0
    '0'            # RAIM: 0
    '0000000000000000000' # Radio: 0
)

# Define our own gaussian function as it's not available in newer scipy versions
def gaussian_filter(M, std):
    """Return a Gaussian window."""
    n = np.arange(0, M) - (M - 1)/2
    return np.exp(-0.5 * (n/std)**2)

def gmsk_modulate(bits, baud, sample_rate, bt=0.4):
    bit_samples = int(sample_rate / baud)
    NRZ = np.array([1 if b == '1' else -1 for b in bits])
    NRZ = np.repeat(NRZ, bit_samples)
    # Gaussian filter
    span = 4
    # Instead of scipy.signal.gaussian, use our own implementation
    h = gaussian_filter(span * bit_samples, bt * bit_samples)
    h /= np.sum(h)
    filtered = np.convolve(NRZ, h, mode='same')
    # Integrate phase
    phase = np.pi/2 * np.cumsum(filtered) / bit_samples
    iq = np.exp(1j * phase)
    return iq

# Generate GMSK signal
print("Generating GMSK signal...")
iq = gmsk_modulate(ais_bits, BAUD, SAMPLE_RATE)
iq = (iq * AMPLITUDE).astype(np.complex64)

# Convert to 8-bit I/Q format for hackrf_transfer
print("Converting to 8-bit I/Q format...")
iq_bytes = np.zeros(len(iq) * 2, dtype=np.int8)
iq_bytes[0::2] = np.clip(np.real(iq), -127, 127).astype(np.int8)
iq_bytes[1::2] = np.clip(np.imag(iq), -127, 127).astype(np.int8)

# Save to temporary file
print("Saving to temporary file...")
temp_file = tempfile.NamedTemporaryFile(delete=False)
temp_file.close()
iq_bytes.tofile(temp_file.name)
print(f"Saved to temporary file: {temp_file.name}")

# Also save a permanent copy in the project directory
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
project_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"ais_signal_{timestamp}.iq")
iq_bytes.tofile(project_file)
print(f"Also saved permanent copy to: {project_file}")

# Use hackrf_transfer to transmit
try:
    cmd = [
        "hackrf_transfer",
        "-t", temp_file.name,
        "-f", str(FREQ),
        "-s", str(SAMPLE_RATE),
        "-a", "1",  # Enable antenna
        "-x", "40",  # TX gain
       # "-b", "2.5"  # Use 2.5 MHz baseband filter (valid value)
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    time.sleep(1)  # Let the transmission finish
finally:
    os.unlink(temp_file.name)

print(f"Transmission complete. Permanent IQ file saved at: {project_file}")
