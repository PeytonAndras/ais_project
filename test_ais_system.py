#!/usr/bin/env python3
"""
Test AIS system without hardware - generate signal to file and decode it
"""
import numpy as np
from scipy.io.wavfile import write
from pyais import decode

class AISTestSystem:
    def __init__(self):
        self.sample_rate = 250000
        self.symbol_rate = 9600
        self.freq_deviation = 2400
        
    def ais_6bit_encode(self, payload):
        """Standard AIS 6-bit encoding"""
        bits = []
        for char in payload:
            ascii_val = ord(char)
            
            if 48 <= ascii_val <= 87:      # '0' to 'W'
                six_bit = ascii_val - 48
            elif 96 <= ascii_val <= 119:   # '`' to 'w'  
                six_bit = ascii_val - 56
            else:
                six_bit = 0
            
            for i in range(5, -1, -1):
                bits.append((six_bit >> i) & 1)
                
        return bits
    
    def create_frame(self, nmea_sentence):
        """Create AIS frame"""
        try:
            decoded = decode(nmea_sentence)
            print(f"✅ Valid AIS: Type {decoded.msg_type}, MMSI {decoded.mmsi}")
        except:
            print("❌ Invalid NMEA sentence")
            return None, None
            
        parts = nmea_sentence.split(',')
        payload = parts[5]
        
        message_bits = self.ais_6bit_encode(payload)
        
        # Pad to 168 bits
        if len(message_bits) > 168:
            message_bits = message_bits[:168]
        else:
            message_bits.extend([0] * (168 - len(message_bits)))
        
        # Frame structure
        training = [0, 1] * 12  # 24 bits
        start_flag = [0, 1, 1, 1, 1, 1, 1, 0]  # 8 bits
        end_flag = [0, 1, 1, 1, 1, 1, 1, 0]    # 8 bits
        buffer_bits = [0] * 8                  # 8 bits
        
        # NRZI encode everything except training
        data_for_nrzi = start_flag + message_bits + end_flag + buffer_bits
        nrzi_data = self.nrzi_encode(data_for_nrzi)
        
        complete_frame = training + nrzi_data
        print(f"🔧 Frame: {len(training)} training + {len(nrzi_data)} NRZI = {len(complete_frame)} total bits")
        
        return complete_frame, payload
    
    def nrzi_encode(self, bits):
        """NRZI encoding"""
        if not bits:
            return []
            
        encoded = [0]
        current = 0
        
        for bit in bits:
            if bit == 0:
                current = 1 - current
            encoded.append(current)
            
        return encoded[1:]
    
    def generate_gmsk_signal(self, symbols):
        """Generate GMSK signal with proper MSK approach"""
        samples_per_symbol = int(self.sample_rate / self.symbol_rate)
        
        # Convert symbols to frequency shifts
        # 0 -> -deviation, 1 -> +deviation
        freq_shifts = []
        for symbol in symbols:
            freq = self.freq_deviation if symbol else -self.freq_deviation
            freq_shifts.extend([freq] * samples_per_symbol)
        
        freq_shifts = np.array(freq_shifts)
        
        # Show first few symbols to debug
        print(f"🔧 Input symbols: {''.join(map(str, symbols[:24]))}")
        print(f"🔧 First freq shifts: {freq_shifts[:10]}")
        
        # Generate phase by integrating frequency
        dt = 1.0 / self.sample_rate
        phase = 2 * np.pi * np.cumsum(freq_shifts) * dt
        
        # Generate complex signal
        signal = np.exp(1j * phase)
        
        return signal.astype(np.complex64)
    
    def fm_demodulate(self, complex_samples):
        """FM demodulation"""
        if len(complex_samples) < 100:
            return None
            
        # Remove DC offset
        complex_samples = complex_samples - np.mean(complex_samples)
        
        # AGC
        power = np.mean(np.abs(complex_samples) ** 2)
        if power > 0:
            complex_samples = complex_samples / np.sqrt(power) * 100
        
        # Instantaneous frequency
        phase = np.unwrap(np.angle(complex_samples))
        freq = np.diff(phase) * self.sample_rate / (2 * np.pi)
        
        # Normalize
        normalized = freq / self.freq_deviation
        normalized = np.clip(normalized, -2, 2)
        
        return normalized
    
    def clock_recovery(self, signal):
        """Symbol timing recovery"""
        samples_per_symbol = int(self.sample_rate / self.symbol_rate)
        
        # Training template
        training_bits = [0, 1] * 12
        training_nrz = []
        for bit in training_bits:
            level = 1.0 if bit else -1.0
            training_nrz.extend([level] * samples_per_symbol)
        training_template = np.array(training_nrz)
        
        print(f"🔧 Template length: {len(training_template)} samples ({len(training_bits)} bits)")
        print(f"🔧 Signal length: {len(signal)} samples")
        print(f"🔧 Samples per symbol: {samples_per_symbol}")
        
        if len(signal) < len(training_template):
            return None, -1
            
        # Correlate
        best_correlation = 0
        best_offset = -1
        best_polarity = 1
        
        for polarity in [1, -1]:
            test_signal = signal * polarity
            correlation = np.correlate(test_signal, training_template, mode='valid')
            abs_corr = np.abs(correlation)
            
            max_idx = np.argmax(abs_corr)
            max_corr = abs_corr[max_idx]
            
            print(f"🔧 Polarity {polarity}: max correlation = {max_corr:.1f} at offset {max_idx}")
            
            if max_corr > best_correlation:
                best_correlation = max_corr
                best_offset = max_idx
                best_polarity = polarity
        
        print(f"🔧 Best correlation: {best_correlation:.1f} at offset {best_offset}")
        
        if best_correlation < 5:  # Very low threshold for test
            return None, -1
            
        # Extract symbols - sample at symbol centers starting from correlation peak
        signal = signal * best_polarity
        start_sample = best_offset
        
        symbols = []
        for i in range(300):
            sample_pos = start_sample + i * samples_per_symbol + samples_per_symbol // 2
            if sample_pos < len(signal):
                symbols.append(1 if signal[int(sample_pos)] > 0 else 0)
            else:
                break
        
        # Debug: show where we're sampling
        print(f"🔧 Start sample: {start_sample}")
        print(f"🔧 First few sample positions: {[start_sample + i * samples_per_symbol + samples_per_symbol // 2 for i in range(10)]}")
        
        return symbols, best_offset
    
    def nrzi_decode(self, symbols, invert=False):
        """NRZI decoding"""
        if len(symbols) < 1:
            return []
            
        bits = []
        
        # First bit: assume previous state was 0
        prev = 0
        
        for symbol in symbols:
            bit = 0 if symbol != prev else 1
            if invert:
                bit = 1 - bit
            bits.append(bit)
            prev = symbol
            
        return bits
    
    def extract_message(self, bits):
        """Extract message from bits"""
        if len(bits) < 190:
            return None
            
        bit_str = ''.join(map(str, bits))
        
        # Find start flag
        hdlc_flag = "01111110"
        flag_pos = bit_str.find(hdlc_flag)
        
        if flag_pos == -1 or flag_pos > 10:
            print(f"❌ No start flag. First 20 bits: {bit_str[:20]}")
            return None
            
        print(f"✅ Start flag at position {flag_pos}")
        
        # Extract message
        msg_start = flag_pos + 8
        if msg_start + 168 > len(bits):
            return None
            
        return bits[msg_start:msg_start + 168]
    
    def bits_to_nmea(self, message_bits):
        """Convert bits to NMEA"""
        if len(message_bits) != 168:
            print(f"❌ Wrong message length: {len(message_bits)} (expected 168)")
            return None
            
        payload_chars = []
        
        print(f"🔧 Converting {len(message_bits)} bits to NMEA...")
        print(f"🔧 First 24 bits: {''.join(map(str, message_bits[:24]))}")
        
        for i in range(0, 168, 6):
            if i + 6 <= 168:
                char_bits = message_bits[i:i+6]
                
                char_val = 0
                for bit in char_bits:
                    char_val = (char_val << 1) | bit
                
                # AIS 6-bit to ASCII
                if char_val <= 31:
                    ascii_val = char_val + 48
                else:
                    ascii_val = char_val + 56
                    
                if 32 <= ascii_val <= 126:
                    payload_chars.append(chr(ascii_val))
                else:
                    payload_chars.append('0')  # Safe fallback
                    
                if i < 36:  # Debug first few characters
                    print(f"🔧 Bits {i:2d}-{i+5:2d}: {''.join(map(str, char_bits))} -> {char_val:2d} -> {ascii_val:3d} -> '{chr(ascii_val) if 32 <= ascii_val <= 126 else '?'}'")
        
        payload = ''.join(payload_chars).rstrip('\x00')
        print(f"🔧 Reconstructed payload: '{payload}'")
        
        nmea_base = f"!AIVDM,1,1,,A,{payload},0"
        
        checksum = 0
        for char in nmea_base:
            checksum ^= ord(char)
            
        nmea = f"{nmea_base}*{checksum:02X}"
        
        print(f"🔧 Candidate NMEA: {nmea}")
        
        try:
            decoded = decode(nmea)
            print(f"✅ Valid NMEA! MMSI: {decoded.mmsi}")
            return nmea
        except Exception as e:
            print(f"❌ Invalid NMEA: {e}")
            return None

def test_system():
    """Test the complete system"""
    print("🧪 AIS SYSTEM TEST")
    print("==================")
    
    system = AISTestSystem()
    
    # Test message
    test_message = "!AIVDM,1,1,,A,15MvlfP000G?n@@K>OW`4?vN0<0=,0*47"
    print(f"\n📡 Input:  {test_message}")
    
    # 1. Generate frame
    frame, original_payload = system.create_frame(test_message)
    if frame is None:
        print("❌ Frame generation failed")
        return
    
    print(f"🔧 Original payload: '{original_payload}'")
    
    # 2. Generate signal
    signal = system.generate_gmsk_signal(frame)
    print(f"📊 Signal: {len(signal)} samples")
    
    # Add minimal noise for now
    noise_level = 0.01  # Very low noise
    noise = np.random.normal(0, noise_level, len(signal))
    noisy_signal = signal + noise
    
    # 3. Demodulate
    demod = system.fm_demodulate(noisy_signal)
    if demod is None:
        print("❌ Demodulation failed")
        return
    
    print(f"✅ Demodulated: {len(demod)} samples")
    
    # Debug: try direct symbol extraction without correlation first
    samples_per_symbol = int(system.sample_rate / system.symbol_rate)
    print(f"🔧 Trying direct symbol extraction...")
    
    # Try extracting symbols from different starting points
    for start_offset in [0, samples_per_symbol//2, samples_per_symbol, samples_per_symbol*2]:
        print(f"\n🔧 Testing start offset: {start_offset}")
        
        test_symbols = []
        for i in range(min(50, len(frame))):  # Extract up to 50 symbols
            sample_pos = start_offset + i * samples_per_symbol + samples_per_symbol // 2
            if sample_pos < len(demod):
                test_symbols.append(1 if demod[sample_pos] > 0 else 0)
        
        if len(test_symbols) >= 24:
            symbol_str = ''.join(map(str, test_symbols[:24]))
            print(f"🔧 Symbols: {symbol_str}")
            
            if symbol_str.startswith("010101010101010101010101") or symbol_str.startswith("101010101010101010101010"):
                print("✅ Found correct training sequence!")
                
                # Continue with rest of decode
                symbols = test_symbols
                
                # Check if pattern is inverted
                if symbol_str.startswith("101010101010101010101010"):
                    symbols = [1 - s for s in symbols]
                    print("🔄 Applied pattern inversion")
                
                # Extract NRZI portion
                if len(symbols) >= 40:  # Need enough for training + some data
                    nrzi_symbols = symbols[24:]
                    print(f"📊 NRZI symbols: {len(nrzi_symbols)}")
                    
                    # Try NRZI decode
                    for nrzi_invert in [False, True]:
                        bits = system.nrzi_decode(nrzi_symbols, nrzi_invert)
                        
                        if len(bits) < 10:
                            continue
                        
                        bit_str = ''.join(map(str, bits[:20]))
                        print(f"🔧 First 20 bits (nrzi_inv={nrzi_invert}): {bit_str}")
                        
                        # Look for start flag
                        if "01111110" in bit_str:
                            print(f"✅ Found start flag! (NRZI invert = {nrzi_invert})")
                            
                            # Continue with full decode using this timing
                            symbols_full = []
                            for i in range(len(frame)):
                                sample_pos = start_offset + i * samples_per_symbol + samples_per_symbol // 2
                                if sample_pos < len(demod):
                                    symbols_full.append(1 if demod[sample_pos] > 0 else 0)
                            
                            if symbol_str.startswith("101010101010101010101010"):
                                symbols_full = [1 - s for s in symbols_full]
                            
                            print(f"🔧 Full symbols extracted: {len(symbols_full)}")
                            
                            nrzi_symbols_full = symbols_full[24:]
                            bits_full = system.nrzi_decode(nrzi_symbols_full, nrzi_invert)
                            
                            print(f"🔧 Full NRZI bits: {len(bits_full)}")
                            if len(bits_full) > 20:
                                print(f"🔧 First 40 bits: {''.join(map(str, bits_full[:40]))}")
                            
                            message_bits = system.extract_message(bits_full)
                            if message_bits:
                                print(f"✅ Message extracted: {len(message_bits)} bits")
                                result_nmea = system.bits_to_nmea(message_bits)
                                if result_nmea:
                                    print(f"\n🎉 SUCCESS!")
                                    print(f"📡 Output: {result_nmea}")
                                    
                                    if result_nmea == test_message:
                                        print("🏆 PERFECT MATCH! 🏆")
                                    else:
                                        print("⚠️  Different from input")
                                        print(f"Expected: {test_message}")
                                        print(f"Got:      {result_nmea}")
                                    return True
                                else:
                                    print("❌ NMEA conversion failed")
                            else:
                                print("❌ Message extraction failed")
    
    print("\n❌ Direct symbol extraction failed, trying correlation method...")
    
    # 4. Clock recovery (fallback)
    symbols, offset = system.clock_recovery(demod)
    if symbols is None:
        print("❌ Clock recovery failed")
        return
    
    print(f"✅ Symbols recovered: {len(symbols)}")
    
    # Continue with original approach...
    # [rest of original code]
    
    print("\n❌ ALL DECODE ATTEMPTS FAILED")
    return False

if __name__ == '__main__':
    test_system()
