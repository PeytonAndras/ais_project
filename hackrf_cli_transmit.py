#!/usr/bin/env python3
import numpy as np
import time
import tempfile
import subprocess
import os
from datetime import datetime

# AIS parameters
FREQUENCY = 161975000  # 161.975 MHz (AIS Ch. 1)
SAMPLE_RATE = 2006400  # 2.0064 MHz sample rate (9600 Hz * 209)
BIT_RATE = 9600  # AIS bit rate
TX_REPEAT = 5   # Number of times to repeat the message in the generated file (Increased)

# AIS message (just the payload part) - Standard Test Payload (MMSI: 211234560)
AIS_PAYLOAD = "15NNevP000qNMgpAHv4EVAa00<1s" # Example Type 1 payload from pyais tests

# HDLC flag (0x7E = 01111110) - This is the on-air pattern
HDLC_FLAG = [0, 1, 1, 1, 1, 1, 1, 0]

# --- CRC Helper Functions (Crucial for AIS) ---
def _reflect_byte(b):
    r = 0
    for i in range(8):
        if (b >> i) & 1:
            r |= (1 << (7 - i))
    return r

def _reflect16(val):
    r = 0
    for i in range(16):
        if (val >> i) & 1:
            r |= (1 << (15 - i))
    return r

def calculate_crc_standard_ais(bits_msb_first: list[int]) -> list[int]:
    """
    Calculates CRC-16-CCITT (poly 0x1021, init 0xFFFF, non-reflected).
    Input bits should be MSB first for the entire message.
    Returns CRC as a list of 16 bits, MSB first.
    """
    crc = 0xFFFF
    polynomial = 0x1021
    for bit in bits_msb_first:
        xorbit = ((crc >> 15) & 1) ^ bit # Test MSB of CRC XOR current data bit
        crc = (crc << 1) & 0xFFFF      # Shift CRC left
        if xorbit:
            crc = crc ^ polynomial     # XOR with polynomial
    
    # Return CRC as list of 16 bits, MSB first
    crc_bits_out = []
    for i in range(16):
        crc_bits_out.append((crc >> (15 - i)) & 1)
    return crc_bits_out

# --- End CRC Helper Functions ---

def nmea_to_binary(nmea_payload):
    binary = []
    for char_val in nmea_payload:
        val = ord(char_val) - 48
        if val > 40: val -= 8
        # Output bits MSB first for each 6-bit character
        char_bits = [(val >> i) & 1 for i in range(5, -1, -1)] 
        binary.extend(char_bits)
    return binary

def nrz_to_nrzi(stuffed_data_bits):
    nrzi_levels = []
    current_level = 1 # Assume line is high before this data block (after start flag)
    for bit in stuffed_data_bits:
        if bit == 1: # Data '1' means no transition
            nrzi_levels.append(current_level)
        else: # Data '0' means transition
            current_level = 1 - current_level
            nrzi_levels.append(current_level)
    return nrzi_levels

def bit_stuff(data_with_crc_bits):
    result = []
    consecutive_ones = 0
    for bit in data_with_crc_bits:
        result.append(bit)
        if bit == 1:
            consecutive_ones += 1
            if consecutive_ones == 5:
                result.append(0)
                consecutive_ones = 0
        else:
            consecutive_ones = 0
    return result

def gmsk_modulate(bits_for_gmsk_modulation, sample_rate, bit_rate, bt=0.4): # Changed bt back to 0.4
    samples_per_bit = int(sample_rate / bit_rate) # 2006400 / 9600 = 209
    signal_levels = np.array([1.0 if bit == 1 else -1.0 for bit in bits_for_gmsk_modulation])
    signal_upsampled = np.repeat(signal_levels, samples_per_bit)

    n_taps = samples_per_bit * 4 # Span of Gaussian filter (e.g., 4 bit periods)
    if n_taps % 2 == 0: n_taps += 1 # Ensure odd number of taps for symmetry

    sigma_t = np.sqrt(np.log(2.0)) / (2.0 * np.pi * bt * bit_rate)
    sigma_samples = sigma_t * sample_rate 

    gauss_filter_time_indices = np.arange(n_taps) - (n_taps - 1.0) / 2.0
    h_gauss = np.exp(-0.5 * (gauss_filter_time_indices / sigma_samples)**2)
    h_gauss = h_gauss / np.sum(h_gauss)

    frequency_pulse_train = np.convolve(signal_upsampled, h_gauss, mode='same')
    phase = np.cumsum(frequency_pulse_train) * (np.pi / 2.0) / samples_per_bit
    
    i_samples = np.cos(phase)
    q_samples = np.sin(phase)
    return i_samples + 1j * q_samples

def create_ais_packet_bits():
    payload_bits = nmea_to_binary(AIS_PAYLOAD) # Now MSB first per char
    crc_bits = calculate_crc_standard_ais(payload_bits) 
    
    data_to_stuff = payload_bits + crc_bits
    stuffed_data = bit_stuff(data_to_stuff)
    
    # Assemble the entire content that needs NRZI encoding:
    # HDLC_FLAG + stuffed_data + HDLC_FLAG
    frame_content_before_nrzi = HDLC_FLAG + stuffed_data + HDLC_FLAG
    
    # Perform NRZI encoding on this complete frame content
    nrzi_encoded_frame_content = nrz_to_nrzi(frame_content_before_nrzi)
    
    # AIS Training sequence (preamble)
    # Standard is 24 bits of 0101...
    # These are directly used as levels for GMSK modulation (0 maps to one phase state, 1 to another)
    # which creates the necessary alternating frequency shifts for receiver synchronization.
    preamble_levels = [i % 2 for i in range(24)] # 24 bits: 0,1,0,1...

    # Final bit stream for the GMSK modulator:
    # Preamble (as direct levels) + NRZI encoded (flags + data + flags)
    final_bits_for_modulation = preamble_levels + nrzi_encoded_frame_content
    return final_bits_for_modulation

def main():
    print(f"AIS Payload: {AIS_PAYLOAD}")
    
    single_packet_on_air_bits = create_ais_packet_bits()
    # Consider the samples_per_bit issue. For a quick test, the current modulation might work
    # if CRC and bit order are fixed. A more precise modulator would be better long-term.
    # For example, by ensuring the total number of samples for one bit period is as close to
    # SAMPLE_RATE / BIT_RATE as possible, or by using fractional rate resampling techniques
    # in the filter design or phase accumulation.
    # One simple improvement could be to calculate total samples for the packet based on the true bit rate
    # and adjust the number of samples for the last bit, but this is complex with np.repeat.
    # The current 0.16% bit rate error from using 208 samples_per_bit might still be an issue.
    single_packet_iq = gmsk_modulate(single_packet_on_air_bits, SAMPLE_RATE, BIT_RATE, bt=0.4) # Ensure bt=0.4 is used here
    print(f"Generated {len(single_packet_on_air_bits)} bits for one packet, resulting in {len(single_packet_iq)} IQ samples.")

    silence_duration_seconds = 0.1 # 100 ms
    silence_samples_count = int(SAMPLE_RATE * silence_duration_seconds)
    silence_iq_segment = np.zeros(silence_samples_count, dtype=np.complex64)
    print(f"Silence between packets: {silence_duration_seconds*1000:.0f} ms ({silence_samples_count} zero I/Q samples).")

    all_iq_samples_list = []
    for i in range(TX_REPEAT): # TX_REPEAT is now 5
        all_iq_samples_list.append(single_packet_iq)
        if i < TX_REPEAT - 1:
            all_iq_samples_list.append(silence_iq_segment)
    
    final_iq_samples = np.concatenate(all_iq_samples_list)
    print(f"Total IQ samples for transmission: {len(final_iq_samples)}")

    max_abs_val = np.max(np.abs(final_iq_samples))
    if max_abs_val == 0: max_abs_val = 1.0
    
    scaling_factor = (127.0 / max_abs_val if max_abs_val > 1e-9 else 127.0) * 0.98
    iq_samples_scaled = final_iq_samples * scaling_factor
    
    print("Converting to 8-bit I/Q format...")
    iq_bytes = np.zeros(len(iq_samples_scaled) * 2, dtype=np.int8)
    iq_bytes[0::2] = np.clip(np.real(iq_samples_scaled), -127, 127).astype(np.int8)
    iq_bytes[1::2] = np.clip(np.imag(iq_samples_scaled), -127, 127).astype(np.int8)
    
    temp_file_path = ""
    perm_file_path = ""
    try:
        # Use a more specific temporary file prefix and ensure it's cleaned up
        with tempfile.NamedTemporaryFile(delete=False, suffix=".iq", prefix="hackrf_ais_tx_") as tf:
            temp_file_path = tf.name
            iq_bytes.tofile(tf)
        print(f"Saved temporary IQ data to: {temp_file_path}")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        script_dir = os.path.dirname(os.path.abspath(__file__))
        perm_file_path = os.path.join(script_dir, f"ais_tx_signal_{timestamp}.iq")
        with open(perm_file_path, 'wb') as pf:
            iq_bytes.tofile(pf)
        print(f"Saved permanent IQ data copy to: {perm_file_path}")

        print(f"Starting continuous transmission on {FREQUENCY/1e6:.3f} MHz at {SAMPLE_RATE/1e6:.1f} Msps...")
        print("Press Ctrl+C to stop.")
        
        cmd = [
            "hackrf_transfer",
            "-t", temp_file_path,
            "-f", str(FREQUENCY),
            "-s", str(SAMPLE_RATE),
            "-a", "1",   # Enable antenna port power (amp)
            "-x", "0",  # Max TX VGA gain (0-47 dB) - Increased from 5. Adjust as needed for your setup.
            # Consider adding '-R' if you want hackrf_transfer to repeat the file itself,
            # though the Python script already handles TX_REPEAT internally for the file content.
            # If you want continuous transmission of the *file*, '-R' is an option for hackrf_transfer.
            # However, looping in Python gives more control for potential future changes (e.g. dynamic signal).
        ]
        
        loop_count = 0
        while True:
            loop_count += 1
            print(f"Transmission loop #{loop_count} starting...")
            print(f"Running command: {' '.join(cmd)}")
            # We don't use check=True here in the loop to allow Ctrl+C to be handled by the outer try/except
            process = subprocess.run(cmd, capture_output=True, text=True)
            
            if process.returncode == 0:
                # print("hackrf_transfer stdout:") # Often empty for successful TX
                # print(process.stdout)
                if process.stderr: # hackrf_transfer often prints status to stderr
                    print("hackrf_transfer stderr:")
                    print(process.stderr.strip())
                print(f"Transmission loop #{loop_count} finished successfully.")
            else:
                print(f"Error during hackrf_transfer execution in loop #{loop_count}:")
                print(f"Command: {' '.join(cmd)}")
                print(f"Return code: {process.returncode}")
                if process.stdout:
                    print(f"Stdout: {process.stdout.strip()}")
                if process.stderr:
                    print(f"Stderr: {process.stderr.strip()}")
                print("Stopping loop due to error.")
                break # Exit the loop on error
            
            # Optional: Add a small delay between transmissions if desired,
            # though hackrf_transfer blocks until its current transmission is done.
            # time.sleep(0.1) # Example: 100ms delay

    except KeyboardInterrupt:
        print("\nTransmission stopped by user.")
    except subprocess.CalledProcessError as e: # This might not be hit if check=False in the loop
        print(f"Error during hackrf_transfer execution (outside loop or initial setup):")
        print(f"Command: {' '.join(e.cmd)}")
        print(f"Return code: {e.returncode}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                print(f"Deleted temporary file: {temp_file_path}")
            except Exception as e_del:
                print(f"Error deleting temporary file {temp_file_path}: {e_del}")

if __name__ == "__main__":
    main()
