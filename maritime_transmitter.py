import SoapySDR
import numpy as np
import time
from pyais import decode

class MaritimeAISTransmitter:
    def __init__(self):
        self.sample_rate = 250000  # 250 kHz - must be high enough for clean FSK
        self.symbol_rate = 9600    # 9600 bps (AIS standard)
        self.freq_deviation = 2400 # ±2400 Hz (AIS standard FSK deviation)
        
        # CRITICAL: Based on rtl_ais source analysis:
        # rtl_ais tunes dongle to center=(left+right)/2 = 162.000MHz
        # It then separates signals using phase rotations and expects
        # Channel A (left) at -25kHz offset, Channel B (right) at +25kHz offset
        # We must transmit on EXACT frequency that will appear in right channel after processing
        self.center_freq = 162.025e6  # Channel B - appears in right stereo channel after rtl_ais processing
        
    def ais_6bit_encode(self, payload):
        """Standard AIS 6-bit encoding - ITU-R M.1371-5 compliant"""
        bits = []
        for char in payload:
            ascii_val = ord(char)
            
            # Standard AIS 6-bit armoring 
            # Reverse of decoder: 0-31 come from ASCII 48-79, 32-63 come from ASCII 88-119
            if 48 <= ascii_val <= 87:      # '0' to 'W' (ASCII 48-87)
                six_bit = ascii_val - 48   # Map to 0-39
            elif 88 <= ascii_val <= 119:   # 'X' to 'w' (ASCII 88-119)  
                six_bit = ascii_val - 56   # Map to 32-63
            else:
                six_bit = 0  # Invalid character - default to '0'
            
            # Convert to 6 bits, MSB first (standard bit order)
            for i in range(5, -1, -1):
                bits.append((six_bit >> i) & 1)
                
        return bits
    
    def create_maritime_frame(self, nmea_sentence):
        """Create EXACT AIS frame with correct NRZI encoding for rtl_ais"""
        # Validate the NMEA sentence
        try:
            decoded = decode(nmea_sentence)
            print(f"✅ Valid AIS: Type {decoded.msg_type}, MMSI {decoded.mmsi}")
        except:
            print("❌ Invalid NMEA sentence")
            return None
            
        # Extract payload
        parts = nmea_sentence.split(',')
        if len(parts) < 6:
            return None
        payload = parts[5]
        
        print(f"📡 Encoding payload: '{payload}'")
        
        # Convert payload to bits
        message_bits = self.ais_6bit_encode(payload)
        
        # Pad or truncate to exactly 168 bits (standard AIS message length)
        if len(message_bits) > 168:
            message_bits = message_bits[:168]
        else:
            message_bits.extend([0] * (168 - len(message_bits)))
        
        # CRITICAL: Complete AIS frame with CRC-16 and HDLC bit stuffing
        
        # Step 1: Calculate CRC-16 for the message payload
        crc_bits = self.calculate_crc16(message_bits)
        print(f"📊 CRC-16 calculated: {len(crc_bits)} bits")
        
        # Step 2: Combine message + CRC
        payload_with_crc = message_bits + crc_bits
        print(f"📊 Payload: Message({len(message_bits)}) + CRC({len(crc_bits)}) = {len(payload_with_crc)} bits")
        
        # Step 3: Apply HDLC bit stuffing to payload
        stuffed_payload = self.hdlc_bit_stuff(payload_with_crc)
        print(f"📊 After bit stuffing: {len(stuffed_payload)} bits")
        
        # Step 4: Apply NRZI encoding to stuffed payload
        nrzi_payload = self.nrzi_encode(stuffed_payload)
        
        # Step 5: Build frame with training, flags, and processed payload
        training = [0, 1] * 12  # Training sequence
        start_delimiter = [0, 1, 1, 1, 1, 1, 1, 0]  # HDLC start flag
        end_delimiter = [0, 1, 1, 1, 1, 1, 1, 0]    # HDLC end flag
        buffer_bits = [0] * 8   # Buffer
        
        # Combine complete frame
        complete_frame = training + start_delimiter + nrzi_payload + end_delimiter + buffer_bits
        
        print(f"📊 Complete AIS Frame: Training(24) + StartFlag(8) + Payload({len(nrzi_payload)}) + EndFlag(8) + Buffer(8) = {len(complete_frame)} bits")
        
        return complete_frame
        print(f"📦 Stuffed AIS Frame: {len(stuffed_frame)} bits (with HDLC bit stuffing)")
        
        return stuffed_frame
    
    def nrzi_encode(self, bits):
        """Standard NRZI encoding - transition for 0, no transition for 1"""
        if not bits:
            return []
            
        encoded = []
        current = 1  # Start with 1 to get 0 as first output after first transition
        
        for bit in bits:
            if bit == 0:
                current = 1 - current  # Transition
            # For bit == 1, no transition (current stays same)
            encoded.append(current)
            
        return encoded
    
    def generate_gmsk(self, symbols):
        """Generate FSK signal optimized for rtl_ais polar discriminator demodulation"""
        samples_per_symbol = int(self.sample_rate / self.symbol_rate)
        
        # CRITICAL: rtl_ais uses polar discriminator: atan2(Im(conj(z1)*z2), Re(conj(z1)*z2))
        # This requires FSK with proper phase continuity and frequency deviation
        signal = []
        phase = 0.0  # Maintain phase continuity - essential for polar discriminator
        
        print(f"🔧 FSK for polar discriminator: {len(symbols)} symbols, {samples_per_symbol} samples/symbol")
        
        # Generate clean 2-FSK with exact AIS standard frequencies
        for i, symbol in enumerate(symbols):
            # AIS standard FSK: Mark (1) = +2400 Hz, Space (0) = -2400 Hz
            # This deviation is critical for rtl_ais to decode properly
            if symbol == 1:
                freq_offset = +self.freq_deviation  # Mark frequency
            else:
                freq_offset = -self.freq_deviation  # Space frequency
            
            # Generate samples for this symbol with continuous phase
            for sample_idx in range(samples_per_symbol):
                # Phase increment for this frequency offset
                phase_increment = 2 * np.pi * freq_offset / self.sample_rate
                phase += phase_increment
                
                # Generate complex sample - clean FSK tone for polar discriminator
                sample = np.exp(1j * phase)
                signal.append(sample)
        
        signal = np.array(signal, dtype=np.complex64)
        
        print(f"📡 FSK signal: {len(signal)} samples, duration={len(signal)/self.sample_rate:.3f}s")
        print(f"📊 Signal characteristics: mean_mag={np.mean(np.abs(signal)):.3f}")
        
        return signal
    
    def add_ramps(self, signal):
        """Add rise/fall ramps to prevent spectral splatter"""
        ramp_samples = int(0.001 * self.sample_rate)  # 1ms ramps
        
        if len(signal) > 2 * ramp_samples:
            # Cosine ramps
            ramp_up = 0.5 * (1 - np.cos(np.linspace(0, np.pi, ramp_samples)))
            ramp_down = 0.5 * (1 + np.cos(np.linspace(0, np.pi, ramp_samples)))
            
            signal[:ramp_samples] *= ramp_up
            signal[-ramp_samples:] *= ramp_down
            
        return signal
    
    def transmit_ais(self, nmea_sentence, device, num_transmissions=10):
        """Transmit AIS message optimized for rtl_ais polar discriminator"""
        
        # Create frame
        complete_frame = self.create_maritime_frame(nmea_sentence)
        if complete_frame is None:
            print("❌ Failed to create frame")
            return
            
        # Verify frame structure for rtl_ais compatibility
        frame_str = ''.join(map(str, complete_frame[:32]))
        print(f"🔧 Frame start: {frame_str}")
        print(f"🔧 Expected:    010101010101010101010101...")
        
        # Verify training sequence (critical for rtl_ais sync)
        training_check = ''.join(map(str, complete_frame[:24]))
        if training_check != "010101010101010101010101":
            print(f"❌ Training sequence corrupted! Got: {training_check}")
            return
        else:
            print("✅ Training sequence verified for rtl_ais")
        
        # Check start flag position (HDLC framing)
        start_flag_check = ''.join(map(str, complete_frame[24:32]))
        if start_flag_check != "01111110":
            print(f"❌ Start flag corrupted! Got: {start_flag_check}")
            return
        else:
            print("✅ HDLC start flag verified")
            
        # Generate FSK signal optimized for rtl_ais polar discriminator
        signal = self.generate_gmsk(complete_frame)
        signal = self.add_ramps(signal)
        
        # Signal power optimization for rtl_ais polar discriminator
        # Based on rtl_ais source: it converts uint8 to int16 with ((int16_t)buf[i]) - 127
        # This suggests it expects moderate signal levels, not saturated
        signal = signal * 0.7  # Optimized power for rtl_ais demodulation chain
        
        print(f"📡 Signal: {len(signal)} samples, {len(signal)/self.sample_rate:.3f}s duration")
        print(f"📊 Power: mean={np.mean(np.abs(signal)):.3f}, max={np.max(np.abs(signal)):.3f}")
        
        # Setup stream
        stream = device.setupStream(SoapySDR.SOAPY_SDR_TX, "CF32")
        
        print(f"\n🚢 AIS TRANSMISSION (RTL_AIS COMPATIBLE)")
        print(f"📡 Frequency: {self.center_freq/1e6:.6f} MHz (Channel B)")
        print(f"🔧 Optimized for rtl_ais polar discriminator and sounddecoder")
        
        try:
            for i in range(num_transmissions):
                print(f"\n=== AIS TX {i+1}/{num_transmissions} ===")
                
                # Standard AIS timing: 2-10 second intervals for Class A stations
                silence_time = 2.5 + np.random.uniform(0, 2.5)
                print(f"⏱️  AIS silence: {silence_time:.1f}s")
                time.sleep(silence_time)
                
                # Transmit AIS burst
                print("📡 Activating AIS transmission...")
                device.activateStream(stream)
                time.sleep(0.01)  # Brief settle time
                
                print("📡 Transmitting AIS message for rtl_ais...")
                result = device.writeStream(stream, [signal], len(signal))
                
                if result.ret == len(signal):
                    print(f"✅ AIS transmission complete: {len(signal)} samples")
                else:
                    print(f"⚠️  Partial AIS transmission: {result.ret}/{len(signal)}")
                
                # Clean shutdown
                time.sleep(0.01)
                device.deactivateStream(stream)
                print("📡 AIS transmission finished")
                
        except KeyboardInterrupt:
            print("\n🛑 AIS transmission stopped")
        finally:
            device.closeStream(stream)
            print("🚢 AIS transmission session complete")

    def calculate_crc16(self, data_bits):
        """Calculate CRC-16 for AIS message (ITU-R M.1371-5)"""
        # AIS uses CRC-16-CCITT with polynomial 0x1021
        crc = 0xFFFF  # Initial value
        
        for bit in data_bits:
            crc ^= (bit << 15)
            for _ in range(1):
                if crc & 0x8000:
                    crc = (crc << 1) ^ 0x1021
                else:
                    crc = crc << 1
                crc &= 0xFFFF
        
        # Convert CRC to 16 bits (MSB first)
        crc_bits = []
        for i in range(15, -1, -1):
            crc_bits.append((crc >> i) & 1)
        
        return crc_bits
    
    def hdlc_bit_stuff(self, bits):
        """HDLC bit stuffing - insert 0 after five consecutive 1s"""
        stuffed = []
        consecutive_ones = 0
        
        for bit in bits:
            stuffed.append(bit)
            
            if bit == 1:
                consecutive_ones += 1
                if consecutive_ones == 5:
                    stuffed.append(0)  # Stuff a zero
                    consecutive_ones = 0
            else:
                consecutive_ones = 0
        
        return stuffed

def main():
    print("🚢 AIS TRANSMITTER - RTL_AIS COMPATIBLE")
    print("📡 Engineered for rtl_ais polar discriminator and sounddecoder")
    print("🔬 Based on rtl_ais source code analysis")
    
    # Standard AIS test message
    test_message = "!AIVDM,1,1,,A,15MvlfP000G?n@@K>OW`4?vN0<0=,0*47"
    
    # Find LimeSDR
    results = SoapySDR.Device.enumerate()
    if not results:
        print("❌ No LimeSDR found!")
        return
        
    device = SoapySDR.Device(results[0])
    print(f"✅ Connected: {results[0]['driver'] if 'driver' in results[0] else 'Unknown'}")
    
    # Create transmitter
    tx = MaritimeAISTransmitter()
    
    # Configure LimeSDR for optimal rtl_ais compatibility
    device.setSampleRate(SoapySDR.SOAPY_SDR_TX, 0, tx.sample_rate)
    device.setFrequency(SoapySDR.SOAPY_SDR_TX, 0, tx.center_freq)
    device.setGain(SoapySDR.SOAPY_SDR_TX, 0, 70)  # Optimized gain for rtl_ais
    
    print(f"📻 Configuration: {tx.center_freq/1e6:.6f} MHz, {tx.sample_rate/1000:.0f} kS/s, 70dB gain")
    
    print("\n🎯 Starting AIS transmission in 3 seconds...")
    print("📻 rtl_ais should decode our messages now!")
    time.sleep(3)
    
    # Transmit AIS messages for rtl_ais
    tx.transmit_ais(test_message, device, num_transmissions=20)

if __name__ == '__main__':
    main()
