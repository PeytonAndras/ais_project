import subprocess
import threading
import time
import numpy as np
import signal
import sys
from scipy import signal as scipy_signal

class FixedAISDecoder:
    def __init__(self):
        self.running = False
        self.process = None
        
    def signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        print("\n🛑 Stopping decoder...")
        self.stop()
        sys.exit(0)
    
    def demodulate_gmsk(self, samples, sample_rate=250000, symbol_rate=9600):
        """Improved GMSK demodulation"""
        try:
            samples_per_symbol = int(sample_rate / symbol_rate)
            
            # Better FM demodulation
            if np.iscomplexobj(samples):
                # Remove DC bias
                samples = samples - np.mean(samples)
                
                # Calculate instantaneous frequency using phase difference
                phase = np.angle(samples)
                
                # Unwrap phase to handle 2π jumps
                unwrapped_phase = np.unwrap(phase)
                
                # Calculate frequency (derivative of phase)
                instantaneous_freq = np.diff(unwrapped_phase) * sample_rate / (2.0 * np.pi)
            else:
                analytic_signal = scipy_signal.hilbert(samples)
                instantaneous_phase = np.unwrap(np.angle(analytic_signal))
                instantaneous_freq = np.diff(instantaneous_phase) * sample_rate / (2.0 * np.pi)
            
            # Apply low-pass filter to remove noise
            cutoff = symbol_rate * 2  # 2x symbol rate
            nyquist = sample_rate / 2
            normalized_cutoff = cutoff / nyquist
            
            if normalized_cutoff < 1.0:
                b, a = scipy_signal.butter(4, normalized_cutoff, btype='low')
                instantaneous_freq = scipy_signal.filtfilt(b, a, instantaneous_freq)
            
            # Downsample to symbol rate
            if len(instantaneous_freq) >= samples_per_symbol:
                # Use proper decimation with anti-aliasing
                decimated = scipy_signal.decimate(instantaneous_freq, samples_per_symbol, ftype='fir')
            else:
                print(f"❌ Not enough samples for decimation")
                return None
            
            # Convert frequency to bits with proper threshold
            freq_threshold = np.median(decimated)  # Use median as threshold
            symbols = (decimated > freq_threshold).astype(int)
            
            return symbols
            
        except Exception as e:
            print(f"Demodulation error: {e}")
            return None
    
    def nrzi_decode(self, symbols):
        """NRZI decoding with error checking"""
        if len(symbols) < 2:
            return []
            
        bits = []
        prev_symbol = symbols[0]
        
        for symbol in symbols[1:]:
            if symbol == prev_symbol:
                bits.append(1)  # No transition = 1
            else:
                bits.append(0)  # Transition = 0
            prev_symbol = symbol
            
        return bits
    
    def find_training_sequence(self, bits):
        """Find AIS training sequence with better tolerance"""
        if len(bits) < 24:
            return -1
            
        best_match = -1
        best_score = 0
        
        # Look for alternating pattern: 010101...
        for start in range(min(200, len(bits) - 24)):
            score = 0
            for i in range(24):
                expected = i % 2  # 0,1,0,1,0,1...
                if bits[start + i] == expected:
                    score += 1
            
            if score > best_score:
                best_score = score
                best_match = start
        
        # Require at least 18/24 correct bits
        if best_score >= 18:
            print(f"✅ Training sequence found with score {best_score}/24")
            return best_match + 24
        
        return -1
    
    def find_hdlc_flags_improved(self, bits):
        """Improved HDLC flag detection"""
        flag_pattern = [0, 1, 1, 1, 1, 1, 1, 0]
        positions = []
        
        i = 0
        while i < len(bits) - 8:
            # Check for exact match
            if bits[i:i+8] == flag_pattern:
                positions.append(i)
                i += 8  # Skip past this flag to avoid overlaps
            else:
                i += 1
        
        # Filter out flags that are too close together (likely noise)
        filtered_positions = []
        for pos in positions:
            if not filtered_positions or pos - filtered_positions[-1] > 50:  # At least 50 bits apart
                filtered_positions.append(pos)
        
        return filtered_positions
    
    def remove_bit_stuffing_improved(self, bits):
        """Improved bit stuffing removal"""
        unstuffed = []
        ones_count = 0
        
        i = 0
        while i < len(bits):
            bit = bits[i]
            
            if bit == 1:
                ones_count += 1
                unstuffed.append(bit)
                
                # After 5 consecutive ones, next bit should be stuffed 0
                if ones_count == 5:
                    if i + 1 < len(bits) and bits[i + 1] == 0:
                        i += 1  # Skip the stuffed 0
                        print(f"🔧 Removed stuffed bit at position {i}")
                    ones_count = 0
            else:
                ones_count = 0
                unstuffed.append(bit)
            
            i += 1
            
        return unstuffed
    
    def bits_to_nmea_improved(self, bits):
        """Improved bits to NMEA conversion"""
        if len(bits) < 168:
            print(f"❌ Not enough bits: {len(bits)} < 168")
            return None
            
        try:
            # Show the bit pattern for debugging
            print(f"🔍 Message bits (first 48): {''.join(map(str, bits[:48]))}")
            
            chars = []
            for i in range(0, min(len(bits), 168), 6):
                if i + 6 <= len(bits):
                    # Extract 6 bits (MSB first)
                    char_bits = bits[i:i+6]
                    char_val = 0
                    for j, bit in enumerate(char_bits):
                        char_val = (char_val << 1) | bit
                    
                    # Convert using AIS 6-bit ASCII table
                    if char_val <= 31:
                        ascii_char = char_val + 48  # '0' to '?'
                    elif char_val <= 63:
                        ascii_char = char_val + 56  # '@' to '_'
                    else:
                        ascii_char = 63  # '?' for invalid
                    
                    if 32 <= ascii_char <= 126:
                        chars.append(chr(ascii_char))
                    else:
                        chars.append('?')
            
            if len(chars) >= 28:
                payload = ''.join(chars[:28])
                print(f"🔍 Decoded payload: {payload}")
                
                # Create NMEA sentence
                nmea_base = f"!AIVDM,1,1,,A,{payload},0"
                
                # Calculate checksum
                checksum = 0
                for char in nmea_base:
                    checksum ^= ord(char)
                
                nmea = f"{nmea_base}*{checksum:02X}"
                return nmea
            else:
                print(f"❌ Not enough characters: {len(chars)}")
                
        except Exception as e:
            print(f"NMEA conversion error: {e}")
            
        return None
    
    def decode_ais_message_improved(self, samples):
        """Improved AIS decoding pipeline"""
        try:
            print("🔧 Starting improved AIS decoding...")
            
            # Step 1: Demodulate
            symbols = self.demodulate_gmsk(samples)
            if symbols is None or len(symbols) < 50:
                print("❌ Demodulation failed")
                return None
                
            print(f"✅ Demodulated to {len(symbols)} symbols")
            
            # Step 2: NRZI decode
            bits = self.nrzi_decode(symbols)
            if len(bits) < 50:
                print("❌ NRZI decode failed")
                return None
                
            print(f"✅ NRZI decoded to {len(bits)} bits")
            
            # Debug: Show bit statistics
            ones_count = sum(bits)
            zeros_count = len(bits) - ones_count
            print(f"🔍 Bit stats: {ones_count} ones, {zeros_count} zeros ({ones_count/len(bits)*100:.1f}% ones)")
            
            # Step 3: Find training sequence
            training_end = self.find_training_sequence(bits)
            if training_end == -1:
                print("❌ Training sequence not found")
                # Try searching for flags from the beginning
                search_start = 0
            else:
                print(f"✅ Training sequence found, data starts at {training_end}")
                search_start = training_end
            
            # Step 4: Find HDLC flags
            remaining_bits = bits[search_start:]
            flag_positions = self.find_hdlc_flags_improved(remaining_bits)
            
            print(f"🔍 Found {len(flag_positions)} valid HDLC flags")
            
            if len(flag_positions) >= 2:
                # Extract message between first two flags
                start_pos = flag_positions[0] + 8
                end_pos = flag_positions[1]
                
                if end_pos > start_pos and (end_pos - start_pos) >= 168:
                    message_bits = remaining_bits[start_pos:end_pos]
                    print(f"✅ Extracted {len(message_bits)} message bits")
                    
                    # Remove bit stuffing
                    clean_bits = self.remove_bit_stuffing_improved(message_bits)
                    print(f"✅ After unstuffing: {len(clean_bits)} bits")
                    
                    # Convert to NMEA
                    nmea = self.bits_to_nmea_improved(clean_bits)
                    if nmea:
                        return nmea
                else:
                    print(f"❌ Message too short: {end_pos - start_pos} bits")
            
            # If flag method fails, try direct decoding
            print("🔧 Trying direct decoding without flags...")
            if len(remaining_bits) >= 168:
                nmea = self.bits_to_nmea_improved(remaining_bits[:200])  # Try first 200 bits
                if nmea:
                    print(f"✅ Direct decode successful!")
                    return nmea
                
        except Exception as e:
            print(f"💥 Decoding error: {e}")
            import traceback
            traceback.print_exc()
            
        return None
    
    def extract_ais_from_samples(self, samples):
        """Main signal processing function"""
        try:
            # Signal detection
            signal_power = np.abs(samples) ** 2
            mean_power = np.mean(signal_power)
            threshold = mean_power + 1.5 * np.std(signal_power)
            signal_present = signal_power > threshold
            signal_regions = np.where(signal_present)[0]
            
            if len(signal_regions) > 1000:
                print(f"📡 Signal detected! Power: {mean_power:.2f}, Regions: {len(signal_regions)}")
                
                # Extract signal region with padding
                if len(signal_regions) > 0:
                    start_idx = max(0, signal_regions[0] - 2000)
                    end_idx = min(len(samples), signal_regions[-1] + 2000)
                    signal_samples = samples[start_idx:end_idx]
                    
                    print(f"🎯 Processing {len(signal_samples)} samples")
                    
                    # Decode
                    nmea = self.decode_ais_message_improved(signal_samples)
                    if nmea:
                        return nmea
                    else:
                        return "SIGNAL_DETECTED_DECODE_FAILED"
                        
        except Exception as e:
            print(f"Processing error: {e}")
            
        return None
    
    def run_rtl_sdr(self):
        """RTL-SDR capture loop"""
        print("🚀 Starting RTL-SDR...")
        
        cmd = [
            'rtl_sdr',
            '-f', '162000000',
            '-s', '250000',
            '-g', '25',  # Lower gain to reduce noise
            '-n', '2000000',  # More samples
            '-'
        ]
        
        attempt = 0
        
        while self.running:
            try:
                attempt += 1
                print(f"\n📡 Capture attempt {attempt}")
                
                result = subprocess.run(cmd, capture_output=True, timeout=10)
                
                if result.returncode == 0 and len(result.stdout) > 0:
                    raw_samples = np.frombuffer(result.stdout, dtype=np.uint8)
                    
                    if len(raw_samples) > 2000:
                        float_samples = raw_samples.astype(np.float32) - 127.5
                        
                        if len(float_samples) % 2 == 0:
                            complex_samples = float_samples[::2] + 1j * float_samples[1::2]
                            
                            print(f"📊 Processing {len(complex_samples)} samples")
                            
                            result = self.extract_ais_from_samples(complex_samples)
                            if result and result.startswith("!AIVDM"):
                                print(f"🎉 SUCCESS: {result}")
                            elif result:
                                print(f"📡 {result}")
                
                if self.running:
                    time.sleep(3)
                    
            except subprocess.TimeoutExpired:
                print("⏰ Timeout")
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"💥 Error: {e}")
                time.sleep(1)
    
    def start(self):
        """Start the decoder"""
        signal.signal(signal.SIGINT, self.signal_handler)
        
        print("=== Fixed AIS Decoder v2 ===")
        print("📻 Improved decoding pipeline")
        
        self.running = True
        self.run_rtl_sdr()
    
    def stop(self):
        """Stop the decoder"""
        self.running = False
        print("🛑 Decoder stopped")

def main():
    decoder = FixedAISDecoder()
    decoder.start()

if __name__ == '__main__':
    main()