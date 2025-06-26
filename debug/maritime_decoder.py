import subprocess
import numpy as np
import time
import threading
import queue
from pyais import decode

class ProductionMaritimeDecoder:
    def __init__(self):
        self.running = False
        self.signal_queue = queue.Queue()
        self.sample_rate = 250000
        self.symbol_rate = 9600
        self.freq_deviation = 2400
        self.decode_count = 0
        
    def fm_demodulate(self, complex_samples):
        """Production FM demodulation with improved SNR"""
        if len(complex_samples) < 100:
            return None, 0
            
        # Remove DC offset
        complex_samples = complex_samples - np.mean(complex_samples)
        
        # Apply automatic gain control (but don't over-amplify)
        power = np.mean(np.abs(complex_samples) ** 2)
        if power > 0:
            # Scale to unity power instead of 100
            complex_samples = complex_samples / np.sqrt(power)
        
        # Instantaneous phase with proper unwrapping
        phase = np.unwrap(np.angle(complex_samples))
        
        # Frequency is derivative of phase
        freq = np.diff(phase) * self.sample_rate / (2 * np.pi)
        
        # Check signal activity - more sensitive for live hardware
        freq_std = np.std(freq)
        if freq_std < 50:  # Much lower threshold for real weak signals
            return None, freq_std
            
        # Normalize frequency deviation
        normalized = freq / self.freq_deviation
        
        # Clip to reasonable range
        normalized = np.clip(normalized, -2, 2)
        
        # Low-pass filter with better parameters
        if len(normalized) > 100:
            # Design better low-pass filter
            cutoff_samples = max(3, len(normalized) // 2000)
            if cutoff_samples > 1:
                kernel = np.ones(cutoff_samples) / cutoff_samples
                filtered = np.convolve(normalized, kernel, mode='same')
            else:
                filtered = normalized
        else:
            filtered = normalized
            
        return filtered, freq_std
    
    def clock_recovery(self, signal):
        """Production-grade symbol timing recovery using correlation with frequency offset compensation"""
        samples_per_symbol = int(self.sample_rate / self.symbol_rate)
        
        # Create ideal training sequence for correlation
        # Training is: 010101... (24 bits) NOT NRZI encoded
        training_bits = [0, 1] * 12  # 24 bits alternating
        
        # Convert to NRZ signal levels for correlation
        training_nrz = []
        for bit in training_bits:
            level = 1.0 if bit else -1.0
            training_nrz.extend([level] * samples_per_symbol)
        training_template = np.array(training_nrz)
        
        # Search for training pattern with frequency offset compensation
        if len(signal) < len(training_template):
            return None, -1
            
        # Try both polarities of the signal and multiple frequency offsets
        best_correlation = 0
        best_offset = -1
        best_polarity = 1
        best_freq_offset = 0
        
        # Test small frequency offsets (±500 Hz)
        freq_offsets = [0, 100, -100, 200, -200, 300, -300, 500, -500]
        
        for freq_offset in freq_offsets:
            if freq_offset != 0:
                # Apply frequency correction
                t = np.arange(len(signal)) / self.sample_rate
                correction = np.exp(-1j * 2 * np.pi * freq_offset * t)
                # Since signal is real, we simulate the correction effect
                corrected_signal = signal * np.real(correction[:len(signal)])
            else:
                corrected_signal = signal
            
            for polarity in [1, -1]:
                test_signal = corrected_signal * polarity
                
                # Cross-correlate with training template
                correlation = np.correlate(test_signal, training_template, mode='valid')
                abs_corr = np.abs(correlation)
                
                # CRITICAL FIX: Find the FIRST strong correlation, not the global maximum
                # The training pattern should be at the beginning of the signal
                correlation_threshold_early = 150.0  # Lower threshold but still strong
                
                # Search for first strong correlation in the very early part of the signal
                # Training should be within the first 1-2 symbol periods from the start
                max_training_delay = samples_per_symbol * 2  # Allow max 2 symbol delay
                search_limit = min(len(abs_corr), max_training_delay)
                
                early_max_idx = -1
                early_max_corr = 0
                
                for i in range(search_limit):
                    if abs_corr[i] > correlation_threshold_early:
                        early_max_idx = i
                        early_max_corr = abs_corr[i]
                        break  # Take the FIRST strong correlation
                
                # If no strong early correlation found, fall back to global maximum
                # but only if it's reasonably early (within first 10% of signal)
                if early_max_idx == -1:
                    global_max_idx = np.argmax(abs_corr)
                    global_max_corr = abs_corr[global_max_idx]
                    
                    # Only accept global max if it's in the first 10% of the signal
                    signal_length_threshold = len(abs_corr) // 10
                    if global_max_idx < signal_length_threshold:
                        max_idx = global_max_idx
                        max_corr = global_max_corr
                    else:
                        # Skip this correlation - training too late
                        continue
                else:
                    max_idx = early_max_idx
                    max_corr = early_max_corr
                
                if freq_offset == 0 and max_corr > 200:  # Only print for very strong signals
                    print(f"🎯 Found strong signal: correlation = {max_corr:.0f} at sample {max_idx}")
                
                if max_corr > best_correlation:
                    best_correlation = max_corr
                    best_offset = max_idx
                    best_polarity = polarity
                    best_freq_offset = freq_offset
        
        if best_freq_offset != 0:
            # Apply the best frequency correction
            t = np.arange(len(signal)) / self.sample_rate
            correction = np.exp(-1j * 2 * np.pi * best_freq_offset * t)
            signal = signal * np.real(correction[:len(signal)])
        
        # Much lower threshold for live hardware - real signals are weaker
        correlation_threshold = 6.0  # Further reduced for very weak signals
        if best_correlation < correlation_threshold:
            return None, -1
            
        if best_correlation > 200:
            print(f"✅ Strong correlation: {best_correlation:.0f}")
        
        # Extract symbols from the correlated position with improved polarity
        signal = signal * best_polarity
        
        # CRITICAL FIX: Adjust start position to account for correlation peak vs actual training start
        # The correlation peak occurs at the END of the training pattern, not the beginning
        # So we need to backtrack by the training template length to get the actual start
        training_length_samples = len(training_template)
        actual_training_start = best_offset
        
        # For better alignment, the training should start at the beginning of a symbol boundary
        # Adjust to nearest symbol boundary before the correlation peak
        symbol_aligned_start = (actual_training_start // samples_per_symbol) * samples_per_symbol
        
        start_sample = symbol_aligned_start
        
        # Adaptive symbol extraction - try different thresholds and timing offsets
        # First, analyze signal characteristics around the corrected start position
        peak_region_start = max(0, start_sample)
        peak_region_end = min(len(signal), start_sample + training_length_samples + 2000)
        peak_signal = signal[peak_region_start:peak_region_end]
        
        if best_correlation > 200:  # Debug output for strong signals
            print(f"🔧 Correlation peak at sample: {best_offset}")
            print(f"🔧 Adjusted training start: {start_sample}")
            print(f"🔧 Available samples from start: {len(signal) - start_sample}")
            print(f"🔧 Expected symbols: {(len(signal) - start_sample) // samples_per_symbol}")
        
        # Calculate multiple threshold candidates
        signal_mean = np.mean(peak_signal)
        signal_std = np.std(peak_signal)
        signal_median = np.median(peak_signal)
        signal_min = np.min(peak_signal)
        signal_max = np.max(peak_signal)
        
        # Try multiple threshold strategies
        threshold_candidates = [
            signal_mean,                          # Mean-based
            signal_median,                        # Median-based (robust to outliers)
            0.0,                                  # Zero threshold
            (signal_min + signal_max) / 2,       # Mid-range
            signal_mean + 0.5 * signal_std,      # Mean + 0.5 std
            signal_mean - 0.5 * signal_std       # Mean - 0.5 std
        ]
        
        best_symbols = None
        best_symbol_quality = 0
        best_training_match = 0
        best_threshold = None
        best_timing_offset = 0
        
        for threshold in threshold_candidates:
            for timing_offset in range(-5, 6):  # Try more timing adjustments
                symbols = []
                symbol_qualities = []
                
                # Calculate maximum possible symbols from this position
                max_possible = (len(signal) - start_sample - timing_offset) // samples_per_symbol
                extract_count = min(400, max_possible)  # Extract up to 400 symbols or signal limit
                
                for i in range(extract_count):
                    sample_pos = start_sample + i * samples_per_symbol + samples_per_symbol // 2 + timing_offset
                    if sample_pos < len(signal) and sample_pos >= 0:
                        value = signal[int(sample_pos)]
                        # Use current threshold
                        symbol = 1 if value > threshold else 0
                        symbols.append(symbol)
                        symbol_qualities.append(abs(value - threshold))  # Distance from threshold
                    else:
                        break
                
                if len(symbols) >= 50:
                    # Check for training patterns anywhere in first 40 symbols
                    training_match = 0
                    best_pattern_pos = -1
                    
                    for pos in range(min(40, len(symbols) - 24)):
                        pattern_symbols = symbols[pos:pos+24]
                        pattern_str = ''.join(map(str, pattern_symbols))
                        
                        # Check both training patterns
                        expected_patterns = ["010101010101010101010101", "101010101010101010101010"]
                        for pattern in expected_patterns:
                            matches = sum(a == b for a, b in zip(pattern_str, pattern))
                            if matches > training_match:
                                training_match = matches
                                best_pattern_pos = pos
                    
                    # Combined quality metric
                    transitions = sum(symbols[i] != symbols[i+1] for i in range(min(len(symbols)-1, 47)))
                    unique_symbols = len(set(symbols[:48]))
                    quality_score = training_match + transitions * 0.3 + unique_symbols * 1.5
                    
                    if quality_score > best_symbol_quality:
                        best_symbol_quality = quality_score
                        best_symbols = symbols
                        best_training_match = training_match
                        best_threshold = threshold
                        best_timing_offset = timing_offset
        
        if best_symbols is None or len(best_symbols) < 50:
            return None, -1

        symbols = best_symbols
        if best_correlation > 200:  # Only show details for very strong signals
            print(f"✅ Timing lock: {len(symbols)} symbols")
            
        return symbols, best_offset
    
    def find_frame_start(self, symbols):
        """Find the start of AIS frame - search for training pattern anywhere in first part"""
        if len(symbols) < 50:
            return -1, False
            
        # Search for training patterns in first 40 symbols
        search_length = min(40, len(symbols) - 24)
        
        patterns = [
            ("010101010101010101010101", False),
            ("101010101010101010101010", True)
        ]
        
        for start_pos in range(search_length):
            symbol_str = ''.join(map(str, symbols[start_pos:start_pos+24]))
            
            for pattern, inverted in patterns:
                if symbol_str == pattern:
                    print(f"✅ Training pattern found")
                    return start_pos, inverted
        
        # If exact match not found, look for close matches (allow 2-3 bit errors)
        for start_pos in range(search_length):
            symbol_str = ''.join(map(str, symbols[start_pos:start_pos+24]))
            
            for pattern, inverted in patterns:
                matches = sum(a == b for a, b in zip(symbol_str, pattern))
                if matches >= 21:  # Allow 3 bit errors
                    return start_pos, inverted
                    
        return -1, False
    
    def nrzi_decode(self, symbols, invert=False):
        """Standard NRZI decoding"""
        if len(symbols) < 1:
            return []
            
        bits = []
        
        # First bit: assume previous state was 1 (to match transmitter NRZI encoding)
        prev = 1
        
        for symbol in symbols:
            bit = 0 if symbol != prev else 1
            if invert:
                bit = 1 - bit
            bits.append(bit)
            prev = symbol
            
        return bits
    
    def extract_message(self, bits):
        """Extract AIS message from frame bits"""
        if len(bits) < 200:
            return None
            
        # Frame structure:
        # Training (24 bits) + NRZI(Start flag + Message + End flag + Buffer)
        # Training is NOT in the bits array - it was used for timing only
        
        bit_str = ''.join(map(str, bits))
        
        # Look for HDLC start flag at the beginning of NRZI data
        hdlc_flag = "01111110"
        flag_pos = bit_str.find(hdlc_flag)
        
        # Debug: show first 32 bits and search for start flag
        print(f"🔧 First 32 raw bits: {bit_str[:32]}")
        print(f"🔧 Looking for start flag: {hdlc_flag}")
        
        if flag_pos == -1 or flag_pos > 10:  # Should be near start
            return None
            
        print(f"✅ Start flag found")
        
        # Extract 168-bit message after start flag
        msg_start = flag_pos + 8
        if msg_start + 168 > len(bits):
            return None
            
        message_bits = bits[msg_start:msg_start + 168]
        
        return message_bits
    
    def bits_to_nmea(self, message_bits):
        """Convert message bits to NMEA using standard AIS 6-bit encoding"""
        if len(message_bits) != 168:
            return None
            
        payload_chars = []
        
        # Convert 6-bit groups to characters using standard AIS encoding
        for i in range(0, 168, 6):
            if i + 6 <= 168:
                char_bits = message_bits[i:i+6]
                
                # Calculate 6-bit value (MSB first - matching transmitter)
                char_val = 0
                for j, bit in enumerate(char_bits):
                    char_val |= (bit << (5 - j))  # MSB first
                
                # Standard AIS 6-bit to ASCII conversion (ITU-R M.1371-5)
                # This must match the transmitter's ais_6bit_encode function
                if char_val <= 31:
                    ascii_val = char_val + 48    # 0-31 -> 48-79 ('0' to 'O')
                else:
                    ascii_val = char_val + 56    # 32-63 -> 88-119 ('X' to 'w')
                
                # Debug first few characters
                if i < 30:  # First 5 characters
                    bit_str = ''.join(map(str, char_bits))
                    print(f"🔧 Bits {bit_str} -> 6-bit {char_val:02d} -> ASCII {ascii_val} -> '{chr(ascii_val) if 32 <= ascii_val <= 126 else '?'}'")
                
                # Ensure valid ASCII range for AIS
                if 48 <= ascii_val <= 87 or 88 <= ascii_val <= 119:
                    payload_chars.append(chr(ascii_val))
                else:
                    payload_chars.append('0')  # Safe fallback
        
        payload = ''.join(payload_chars).rstrip('\x00')
        
        # Build NMEA sentence
        nmea_base = f"!AIVDM,1,1,,A,{payload},0"
        
        # Calculate checksum
        checksum = 0
        for char in nmea_base:
            checksum ^= ord(char)
            
        nmea = f"{nmea_base}*{checksum:02X}"
        
        # Validate with pyais
        try:
            decoded = decode(nmea)
            return nmea
        except Exception as e:
            return None
    
    def decode_signal(self, complex_samples):
        """Production signal decoder compatible with rtl_ais"""
        # FM demodulate
        demod_signal, activity = self.fm_demodulate(complex_samples)
        if demod_signal is None:
            return None
        
        # Clock recovery - this finds the training and extracts symbols
        symbols, timing_offset = self.clock_recovery(demod_signal)
        if symbols is None:
            return None
        
        # Verify training sequence and find its position
        frame_pos, pattern_inverted = self.find_frame_start(symbols)
        
        if frame_pos == -1:
            return None
            
        # Skip training sequence and process raw symbols (like rtl_ais)
        training_end = frame_pos + 24
        if len(symbols) < training_end + 184:  # Need training + start flag + message + end flag
            print(f"🔧 Insufficient symbols: {len(symbols)} total, need {training_end + 184}")
            return None
            
        # Extract everything after training as mixed format symbols
        data_symbols = symbols[training_end:]
        print(f"🔧 Processing {len(data_symbols)} data symbols (mixed format)")
        
        # Account for signal inversion if needed
        if pattern_inverted:
            data_symbols = [1 - s for s in data_symbols]
        
        # The transmitter format is: StartFlag(8, raw) + NRZI_Payload + EndFlag(8, raw) + Buffer(8, raw)
        # We need to extract the start flag directly, then NRZI decode the payload
        
        if len(data_symbols) < 16:  # Need at least start flag + some payload
            print(f"🔧 Insufficient data symbols: {len(data_symbols)}")
            return None
            
        # Extract start flag (first 8 bits, raw)
        start_flag = data_symbols[:8]
        start_flag_str = ''.join(map(str, start_flag))
        
        print(f"🔧 Start flag: {start_flag_str}")
        
        # Try multiple approaches to find valid start flag
        expected_patterns = [
            "01111110",  # Normal HDLC flag
            "10000001",  # Inverted HDLC flag
        ]
        
        best_match = 0
        best_shift = 0
        best_invert = False
        found_pattern = None
        
        # Try current position and small shifts
        for shift in range(0, 4):  # Try shifts 0, 1, 2, 3
            for invert in [False, True]:
                if shift == 0:
                    test_symbols = data_symbols[:8]
                else:
                    # Positive shift - take from later in data
                    if len(data_symbols) >= 8 + shift:
                        test_symbols = data_symbols[shift:shift+8]
                    else:
                        continue
                
                if invert:
                    test_symbols = [1 - s for s in test_symbols]
                
                test_flag = ''.join(map(str, test_symbols))
                
                # Check against expected patterns (accept good matches for GMSK)
                for pattern in expected_patterns:
                    matches = sum(a == b for a, b in zip(test_flag, pattern))
                    if matches >= 6:  # Reduced to 6/8 bits for GMSK compatibility
                        best_match = matches
                        best_shift = shift
                        best_invert = invert
                        found_pattern = pattern
                        print(f"🔧 Found valid flag: shift {shift}, invert {invert}: {test_flag} vs {pattern} ({matches}/8)")
                        break
                
                if best_match >= 6:
                    break
            
            if best_match >= 6:
                break
        
        if best_match < 6:  # Require reasonable flag match for GMSK
            print(f"🔧 No valid HDLC start flag found: best was {best_match}/8 matches")
            return None
        
        # Apply the best corrections found
        if best_shift > 0:
            data_symbols = data_symbols[best_shift:]
            print(f"🔧 Applied shift of {best_shift} bits")
        
        if best_invert:
            data_symbols = [1 - s for s in data_symbols]
            print(f"🔧 Applied polarity inversion")
        
        print(f"✅ Start flag verified with pattern {found_pattern}")
        
        # Find end flag to determine payload length  
        remaining_symbols = data_symbols[8:]  # After start flag
        
        # Look for end flag in reasonable range
        end_flag_found = False
        payload_length = 0
        end_flag_pattern = "01111110"  # Define the end flag pattern
        
        # Expected payload length: 168 message + 16 CRC + bit stuffing = ~188 bits
        min_search = 180
        max_search = min(200, len(remaining_symbols) - 8)
        
        for pos in range(min_search, max_search):
            if pos + 8 <= len(remaining_symbols):
                end_candidate = remaining_symbols[pos:pos+8]
                end_str = ''.join(map(str, end_candidate))
                end_matches = sum(a == b for a, b in zip(end_str, end_flag_pattern))
                
                if end_matches >= 6:  # Found end flag
                    payload_length = pos
                    end_flag_found = True
                    print(f"🔧 Found end flag at position {pos}: {end_str}")
                    break
        
        if not end_flag_found:
            # Use expected length if end flag not found
            payload_length = min(188, len(remaining_symbols) - 8)
            print(f"🔧 Using expected payload length: {payload_length}")
        
        # Extract NRZI-encoded payload
        nrzi_payload_symbols = remaining_symbols[:payload_length]
        
        if len(nrzi_payload_symbols) < 168:  # Need at least message bits
            print(f"🔧 Insufficient NRZI payload: {len(nrzi_payload_symbols)} symbols")
            return None
            
        # NRZI decode the payload
        payload_bits = self.nrzi_decode(nrzi_payload_symbols, invert=False)
        
        print(f"🔧 NRZI decoded payload: {len(payload_bits)} bits")
        
        # Remove HDLC bit stuffing (remove 0 after five consecutive 1s)
        destuffed_bits = []
        ones_count = 0
        
        for bit in payload_bits:
            if bit == 1:
                ones_count += 1
                destuffed_bits.append(bit)
            else:  # bit == 0
                if ones_count == 5:
                    # This is a stuffed bit, skip it
                    ones_count = 0
                    continue
                else:
                    ones_count = 0
                    destuffed_bits.append(bit)
        
        print(f"🔧 After bit destuffing: {len(destuffed_bits)} bits")
        
        # Extract message bits (first 168 bits)
        if len(destuffed_bits) >= 168:
            message_bits = destuffed_bits[:168]
        else:
            print(f"🔧 Insufficient destuffed bits: {len(destuffed_bits)}")
            return None
        
        print(f"🔧 Extracted {len(message_bits)} message bits")
        
        # Convert to NMEA
        nmea = self.bits_to_nmea(message_bits)
        if nmea:
            print(f"🔧 NMEA conversion successful!")
            return nmea
        else:
            print(f"🔧 NMEA conversion failed (invalid message)")
        
        return None
    
    def rtl_reader(self):
        """RTL-SDR interface with improved buffering"""
        cmd = ['rtl_sdr', '-f', '162025000', '-s', '250000', '-g', '45', '-']
        
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=0)
            buffer = b''
            
            print("📻 RTL-SDR started...")
            
            while self.running:
                chunk = process.stdout.read(8192)  # Smaller chunks
                if not chunk:
                    break
                    
                buffer += chunk
                
                # Process in shorter windows to catch AIS bursts better
                # AIS burst is ~22ms, so use 100ms windows
                window_size = 50000  # 0.1 second at 250kS/s * 2 bytes per sample  
                if len(buffer) >= window_size:
                    raw_data = np.frombuffer(buffer[:window_size], dtype=np.uint8)
                    buffer = buffer[window_size//8:]  # Small overlap
                    
                    # Convert to complex with better scaling
                    float_data = (raw_data.astype(np.float32) - 127.5) / 127.5
                    if len(float_data) % 2 == 0:
                        complex_data = float_data[::2] + 1j * float_data[1::2]
                        
                        # Check power with better threshold
                        power = np.mean(np.abs(complex_data) ** 2)
                        if power > 0.01:  # More sensitive threshold
                            self.signal_queue.put(complex_data)
                            
        except Exception as e:
            print(f"RTL error: {e}")
        finally:
            if 'process' in locals():
                process.terminate()
                print("📻 RTL-SDR stopped")
    
    def processor(self):
        """Signal processor"""
        while self.running:
            try:
                signal = self.signal_queue.get(timeout=1.0)
                
                result = self.decode_signal(signal)
                
                if result:
                    self.decode_count += 1
                    
                    # Check if this is our test message
                    expected_msg = "!AIVDM,1,1,,A,15MvlfP000G?n@@K>OW`4?vN0<0=,0*47"
                    is_our_message = result == expected_msg
                    
                    if is_our_message:
                        print(f"\n🎉🎉🎉 === OUR TEST MESSAGE DECODED! === 🎉🎉🎉")
                        print(f"📡 {result}")
                        print("🏆 TRANSMITTER ↔️ DECODER LINK SUCCESSFUL!")
                    else:
                        print(f"\n🌊 === AIS MESSAGE #{self.decode_count} ===")
                        print(f"📡 {result}")
                    
                    # Decode and display ship information
                    try:
                        from pyais import decode
                        decoded = decode(result)
                        if is_our_message:
                            print(f"🚢 TEST VESSEL: MMSI {decoded.mmsi} | Type: {decoded.msg_type}")
                        else:
                            print(f"🚢 MMSI: {decoded.mmsi} | Type: {decoded.msg_type}")
                        if hasattr(decoded, 'lat') and hasattr(decoded, 'lon'):
                            print(f"📍 {decoded.lat:.4f}°N, {decoded.lon:.4f}°W")
                        if hasattr(decoded, 'speed'):
                            print(f"⚡ {decoded.speed:.1f} knots")
                        if is_our_message:
                            print("🎉" * 20)
                        else:
                            print("=" * 40)
                    except Exception as e:
                        if is_our_message:
                            print(f"🚢 Our test message validated!")
                            print("🎉" * 20)
                        else:
                            print(f"🚢 Valid AIS message")
                            print("=" * 40)
                    print(f"📊 Total successful decodes: {self.decode_count}")
                    print("─" * 50)
                    
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Processor error: {e}")
    
    def run(self):
        """Run production maritime decoder"""
        print("🚢 PRODUCTION MARITIME AIS DECODER")
        print("📡 Real-world grade signal processing")
        print("🌊 Maritime environment simulation")
        print("🎯 Optimized for LimeSDR → RTL-SDR link")
        
        self.running = True
        
        # Start processing threads
        reader_thread = threading.Thread(target=self.rtl_reader, daemon=True)
        processor_thread = threading.Thread(target=self.processor, daemon=True)
        
        reader_thread.start()
        processor_thread.start()
        
        print("\n📻 Maritime decoder operational!")
        print("🔍 Advanced timing recovery active")
        print("🎯 Listening for AIS transmissions...")
        print("Expected: !AIVDM,1,1,,A,15MvlfP000G?n@@K>OW`4?vN0<0=,0*47")
        
        try:
            while True:
                time.sleep(2)
                if self.decode_count > 0:
                    print(f"📊 Total decodes: {self.decode_count}")
        except KeyboardInterrupt:
            print("\n🛑 Stopping maritime decoder...")
            self.running = False

def main():
    decoder = ProductionMaritimeDecoder()
    decoder.run()

if __name__ == '__main__':
    main()