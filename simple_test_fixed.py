import hackrf
import numpy as np
import time

# Example AIS message (from your provided message)
ais_message = "!AIVDM,1,1,,A,ENkaRGuSh@@@@@@@@@@@@@@@@@@<gA9C8eJG`00003vP000,0*09"

# Encode the AIS message into a bitstream
def encode_ais_message(ais_message):
    # Convert AIS message to binary format (just as an example; use pyais or another library to convert to bitstream)
    # For simplicity, we mock this here. You should use a full AIS encoding library.
    # This function should return a sequence of bits that represent the AIS message.
    
    # Example: Convert each character in the message to its binary representation
    bitstream = []
    for char in ais_message:
        # Convert each character to a byte and then to binary
        byte = ord(char)
        bits = [int(x) for x in format(byte, '08b')]
        bitstream.extend(bits)
    
    return np.array(bitstream)

# Modulate the bitstream with FSK (Frequency Shift Keying)
def fsk_modulate(bitstream, sample_rate, frequency_deviation, bit_rate):
    samples = []
    for bit in bitstream:
        if bit == 0:
            # Modulate 0 bit (lower frequency)
            freq = 161975000 - frequency_deviation  # Frequency for bit 0 (example: 161.975 MHz - 2 kHz)
        else:
            # Modulate 1 bit (higher frequency)
            freq = 161975000 + frequency_deviation  # Frequency for bit 1 (example: 161.975 MHz + 2 kHz)

        # Create samples at the frequency
        t = np.arange(0, 1/bit_rate, 1/sample_rate)
        samples.extend(np.cos(2 * np.pi * freq * t))  # Simple cosine modulation
    
    return np.array(samples, dtype=np.complex64)  # Use complex64 for I/Q data

# HackRF setup function
def setup_hackrf():
    hackrf_device = hackrf.HackRF()
    # No setup() method needed - the initialization is done in the constructor
    
    # Set frequency (assuming this method exists)
    if hasattr(hackrf_device, 'set_freq'):
        hackrf_device.set_freq(161975000)  # AIS transmission frequency (161.975 MHz)
    elif hasattr(hackrf_device, 'set_frequency'):
        hackrf_device.set_frequency(161975000)
    else:
        print("Warning: Could not set frequency - method not found")
    
    # Set sample rate
    if hasattr(hackrf_device, 'set_sample_rate'):
        hackrf_device.set_sample_rate(2000000)  # 2 MHz sample rate
    else:
        print("Warning: Could not set sample rate - method not found")
    
    # Set gains
    if hasattr(hackrf_device, 'set_lna_gain'):
        hackrf_device.set_lna_gain(16)  # LNA gain
    
    if hasattr(hackrf_device, 'set_vga_gain'):
        hackrf_device.set_vga_gain(16)  # VGA gain
    
    return hackrf_device

# Transmit the modulated signal via HackRF
def transmit_signal(hackrf_device, modulated_signal):
    # Convert to proper format if needed
    if modulated_signal.dtype != np.complex64:
        print("Converting signal to complex64 format")
        modulated_signal = modulated_signal.astype(np.complex64)
    
    # Normalize signal between -1 and 1
    max_val = max(np.max(np.abs(modulated_signal.real)), np.max(np.abs(modulated_signal.imag)))
    if max_val > 0:
        modulated_signal = modulated_signal / max_val
    
    # Use the correct send method
    if hasattr(hackrf_device, 'send'):
        hackrf_device.send(modulated_signal)
    elif hasattr(hackrf_device, 'transmit'):
        hackrf_device.transmit(modulated_signal)
    elif hasattr(hackrf_device, 'tx'):
        hackrf_device.tx(modulated_signal)
    else:
        print("Error: No suitable transmit method found")

# Main function to encode and transmit the AIS message
def main():
    # Encode the AIS message into a bitstream
    bitstream = encode_ais_message(ais_message)
    
    # Modulate the bitstream with FSK
    sample_rate = 2000000  # 2 MHz sample rate
    frequency_deviation = 2000  # 2 kHz deviation (example for AIS)
    bit_rate = 9600  # Typical bit rate for AIS (can vary)
    
    modulated_signal = fsk_modulate(bitstream, sample_rate, frequency_deviation, bit_rate)
    
    # Setup HackRF and transmit the signal
    hackrf_device = setup_hackrf()
    
    try:
        # Continuously transmit the signal (or send in bursts)
        print("Starting transmission. Press Ctrl+C to stop.")
        while True:
            transmit_signal(hackrf_device, modulated_signal)
            time.sleep(1)  # Adjust the sleep time based on the transmission requirements
    except KeyboardInterrupt:
        print("Transmission stopped.")
    finally:
        if hackrf_device:
            hackrf_device.close()
            print("HackRF device closed.")

if __name__ == "__main__":
    main()
