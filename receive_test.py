import SoapySDR
from SoapySDR import SOAPY_SDR_RX
import numpy as np
import time
from datetime import datetime

def simple_fsk_decode(samples, sample_rate=1e6, baud_rate=1200):
    """Simplified FSK decoder with debug output"""
    if len(samples) < 100:
        return ""
    
    # Calculate instantaneous frequency
    analytic = samples * np.conj(np.roll(samples, 1))
    freq = np.angle(analytic) * sample_rate / (2 * np.pi)
    
    # Simple thresholding
    freq_smooth = np.convolve(freq, np.ones(100)/100, mode='same')
    
    # Convert to bits
    samples_per_bit = int(sample_rate / baud_rate)
    bits = []
    
    for i in range(0, len(freq_smooth) - samples_per_bit, samples_per_bit):
        bit_samples = freq_smooth[i:i+samples_per_bit]
        avg_freq = np.mean(bit_samples)
        bits.append('1' if avg_freq > 0 else '0')
    
    # Try to find ASCII patterns
    bit_string = ''.join(bits)
    
    # Look for any 8-bit ASCII patterns
    chars = []
    for i in range(len(bit_string) - 7):
        try:
            byte = bit_string[i:i+8]
            val = int(byte, 2)
            if 32 <= val <= 126:  # Printable ASCII
                chars.append(chr(val))
        except:
            pass
    
    result = ''.join(chars)
    
    # Look for our target message
    if "Hello" in result or "World" in result or "LimeSDR" in result:
        return result
    
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
    sdr.setFrequency(SOAPY_SDR_RX, 0, 161.975e6)
    sdr.setGain(SOAPY_SDR_RX, 0, 40)  # Higher gain
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Listening on 161.975 MHz...")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Monitoring signal strength...")
    print("-" * 60)
    
    # Setup stream
    rx_stream = sdr.setupStream(SOAPY_SDR_RX, "CF32")
    sdr.activateStream(rx_stream)
    
    try:
        while True:
            # Shorter chunks for better timing
            num_samples = int(0.5e6)  # 0.5 seconds
            samples = np.zeros(num_samples, dtype=np.complex64)
            
            result = sdr.readStream(rx_stream, [samples], num_samples, timeoutUs=1000000)
            
            if result.ret > 0:
                received_data = samples[:result.ret]
                
                # Check signal power
                power = np.mean(np.abs(received_data)**2)
                power_db = 10 * np.log10(power) if power > 0 else -100
                
                timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                
                # Always show power level
                print(f"[{timestamp}] Power: {power_db:.1f} dB", end="")
                
                # Try to decode if there's any reasonable signal
                if power_db > -70:
                    decoded = simple_fsk_decode(received_data)
                    if decoded:
                        print(f" -> DECODED: '{decoded}'")
                    elif power_db > -60:
                        print(f" -> Strong signal, no decode")
                    else:
                        print()
                else:
                    print()
            
            time.sleep(0.05)
            
    except KeyboardInterrupt:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Stopping...")
    
    # Cleanup
    sdr.deactivateStream(rx_stream)
    sdr.closeStream(rx_stream)
    del sdr

if __name__ == "__main__":
    main()