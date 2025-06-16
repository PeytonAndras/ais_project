import SoapySDR
from SoapySDR import SOAPY_SDR_RX
import numpy as np
import time
from datetime import datetime

def ook_decode(samples, sample_rate=1e6, baud_rate=300):
    """Decode OOK signal back to text"""
    if len(samples) < 1000:
        return ""
    
    # Calculate signal envelope (amplitude)
    envelope = np.abs(samples)
    
    # Smooth the envelope
    window_size = int(sample_rate / baud_rate / 4)
    envelope_smooth = np.convolve(envelope, np.ones(window_size)/window_size, mode='same')
    
    # Threshold detection
    threshold = np.mean(envelope_smooth) + 2 * np.std(envelope_smooth)
    
    # Convert to bits
    samples_per_bit = int(sample_rate / baud_rate)
    bits = []
    
    for i in range(0, len(envelope_smooth) - samples_per_bit, samples_per_bit):
        bit_samples = envelope_smooth[i:i+samples_per_bit]
        avg_amplitude = np.mean(bit_samples)
        bits.append('1' if avg_amplitude > threshold else '0')
    
    bit_string = ''.join(bits)
    
    # Look for message pattern: START + data + END
    if 'START' not in bit_string and 'END' not in bit_string:
        # Try simple character decoding
        chars = []
        i = 0
        while i < len(bit_string) - 11:  # Need 12 bits minimum (start + 8 data + stop)
            if bit_string[i:i+2] == '01':  # Found start bits
                if i + 11 < len(bit_string) and bit_string[i+10:i+12] == '11':  # Found stop bits
                    data_bits = bit_string[i+2:i+10]
                    try:
                        ascii_val = int(data_bits, 2)
                        if 32 <= ascii_val <= 126:
                            chars.append(chr(ascii_val))
                        i += 12
                    except:
                        i += 1
                else:
                    i += 1
            else:
                i += 1
        
        decoded = ''.join(chars)
        
        # Look for our message markers
        if 'START' in decoded and 'END' in decoded:
            start_idx = decoded.find('START') + 5
            end_idx = decoded.find('END')
            if start_idx < end_idx:
                return decoded[start_idx:end_idx]
        
        return decoded if len(decoded) > 3 else ""
    
    return ""

def main():
    # Find RTL-SDR
    devices = SoapySDR.Device.enumerate()
    rtlsdr = None
    
    for device in devices:
        if device['driver'] == 'rtlsdr':
            rtlsdr = device
            break
    
    if not rtlsdr:
        print("RTL-SDR not found!")
        return

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Opening RTL-SDR...")
    sdr = SoapySDR.Device(rtlsdr)
    
    # Configure receiver
    sdr.setSampleRate(SOAPY_SDR_RX, 0, 1e6)
    sdr.setFrequency(SOAPY_SDR_RX, 0, 433e6)  # Match transmitter frequency
    sdr.setGain(SOAPY_SDR_RX, 0, 40)
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Listening on 433 MHz...")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Looking for: 'Hello World from LimeSDR!'")
    print("-" * 60)
    
    # Setup stream
    rx_stream = sdr.setupStream(SOAPY_SDR_RX, "CF32")
    sdr.activateStream(rx_stream)
    
    message_count = 0
    
    try:
        while True:
            # Capture 2 seconds of data
            num_samples = int(2e6)
            samples = np.zeros(num_samples, dtype=np.complex64)
            
            result = sdr.readStream(rx_stream, [samples], num_samples, timeoutUs=3000000)
            
            if result.ret > 0:
                received_data = samples[:result.ret]
                
                # Check signal power
                power = np.mean(np.abs(received_data)**2)
                power_db = 10 * np.log10(power) if power > 0 else -100
                
                timestamp = datetime.now().strftime('%H:%M:%S')
                
                # Try to decode
                if power_db > -70:
                    decoded = ook_decode(received_data)
                    
                    if decoded:
                        if "Hello World from LimeSDR!" in decoded:
                            message_count += 1
                            print(f"[{timestamp}] *** TARGET MESSAGE #{message_count} RECEIVED ***")
                            print(f"[{timestamp}] MESSAGE: '{decoded}' (Power: {power_db:.1f} dB)")
                        elif len(decoded) > 3:
                            print(f"[{timestamp}] Other message: '{decoded}' (Power: {power_db:.1f} dB)")
                    elif power_db > -60:
                        print(f"[{timestamp}] Strong signal detected (Power: {power_db:.1f} dB)")
                else:
                    print(f"[{timestamp}] Monitoring... (Power: {power_db:.1f} dB)")
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Stopping...")
        print(f"Total target messages received: {message_count}")
    
    # Cleanup
    sdr.deactivateStream(rx_stream)
    sdr.closeStream(rx_stream)
    del sdr

if __name__ == "__main__":
    main()