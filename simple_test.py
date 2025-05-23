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
    
    return np.array(samples)

# HackRF setup function
def setup_hackrf():
    hackrf_device = hackrf.HackRF()
    hackrf_device.setup()
    hackrf_device.set_freq(161975000)  # AIS transmission frequency (161.975 MHz)
    hackrf_device.set_sample_rate(2000000)  # 2 MHz sample rate (can adjust as necessary)
    hackrf_device.set_lna_gain(16)  # Adjust gain as needed
    return hackrf_device

# Transmit the modulated signal via HackRF
def transmit_signal(hackrf_device, modulated_signal):
    hackrf_device.send(modulated_signal)

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
        while True:
            transmit_signal(hackrf_device, modulated_signal)
            time.sleep(1)  # Adjust the sleep time based on the transmission requirements
    except KeyboardInterrupt:
        print("Transmission stopped.")
        hackrf_device.close()

if __name__ == "__main__":
    main()
