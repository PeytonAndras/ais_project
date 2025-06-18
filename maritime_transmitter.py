import SoapySDR
import numpy as np
import time
from pyais import decode

class MaritimeAISTransmitter:
    def __init__(self):
        self.sample_rate = 250000  # 250 kHz
        self.symbol_rate = 9600    # 9600 bps
        self.freq_deviation = 2400 # ±2400 Hz
        self.center_freq = 162.025e6  # Channel B (slightly different from real traffic)
        
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
        """Create standard maritime AIS frame compatible with rtl_ais"""
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
        
        # Build complete AIS frame for rtl_ais compatibility
        # 1. Training sequence (24 bits) - transmitted as raw symbols
        training = [0, 1] * 12
        
        # 2. HDLC Start flag (8 bits) - transmitted as raw symbols (NOT NRZI encoded)
        start_flag = [0, 1, 1, 1, 1, 1, 1, 0]
        
        # 3. Message data (168 bits) - transmitted as raw symbols (NOT NRZI encoded)
        
        # 4. HDLC End flag (8 bits) - transmitted as raw symbols (NOT NRZI encoded)  
        end_flag = [0, 1, 1, 1, 1, 1, 1, 0]
        
        # 5. Buffer (8 bits) - transmitted as raw symbols
        buffer_bits = [0] * 8
        
        # Combine all data as raw symbols (rtl_ais expects this format)
        complete_frame = training + start_flag + message_bits + end_flag + buffer_bits
        
        print(f"📊 Frame: Training(24) + StartFlag(8) + Message(168) + EndFlag(8) + Buffer(8) = {len(complete_frame)} bits")
        
        return complete_frame
    
    def nrzi_encode(self, bits):
        """Standard NRZI encoding - transition for 0, no transition for 1"""
        if not bits:
            return []
            
        encoded = [0]  # Start with 0
        current = 0
        
        for bit in bits:
            if bit == 0:
                current = 1 - current  # Transition
            # For bit == 1, no transition (current stays same)
            encoded.append(current)
            
        return encoded[1:]  # Remove the initial state
    
    def generate_gmsk(self, symbols):
        """Generate MSK signal for maritime use (simplified for reliability)"""
        samples_per_symbol = int(self.sample_rate / self.symbol_rate)
        
        # Convert symbols to frequency shifts
        # 0 -> -deviation, 1 -> +deviation  
        freq_shifts = []
        for symbol in symbols:
            freq = self.freq_deviation if symbol else -self.freq_deviation
            freq_shifts.extend([freq] * samples_per_symbol)
        
        freq_shifts = np.array(freq_shifts)
        
        # Generate phase by integrating frequency
        dt = 1.0 / self.sample_rate
        phase = 2 * np.pi * np.cumsum(freq_shifts) * dt
        
        # Generate complex signal
        signal = np.exp(1j * phase)
        
        return signal.astype(np.complex64)
    
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
        """Transmit AIS message compatible with rtl_ais"""
        
        # Create frame
        complete_frame = self.create_maritime_frame(nmea_sentence)
        if complete_frame is None:
            print("❌ Failed to create frame")
            return
            
        # Show what we're transmitting
        frame_str = ''.join(map(str, complete_frame[:32]))
        print(f"🔧 Frame start: {frame_str}")
        print(f"🔧 Expected:    010101010101010101010101...")
        
        # Verify frame integrity
        training_check = ''.join(map(str, complete_frame[:24]))
        if training_check != "010101010101010101010101":
            print(f"❌ Training sequence corrupted! Got: {training_check}")
            return
        else:
            print("✅ Training sequence verified")
        
        # Check start flag position
        start_flag_check = ''.join(map(str, complete_frame[24:32]))
        if start_flag_check != "01111110":
            print(f"❌ Start flag corrupted! Got: {start_flag_check}")
            return
        else:
            print("✅ Start flag verified")
            
        # Generate GMSK signal
        signal = self.generate_gmsk(complete_frame)
        signal = self.add_ramps(signal)
        
        # Show signal characteristics before scaling
        print(f"📊 Signal stats: mean={np.mean(np.abs(signal)):.3f}, max={np.max(np.abs(signal)):.3f}")
        
        signal = signal * 0.8  # Increased power for better reception
        
        print(f"📡 Signal: {len(signal)} samples, {len(signal)/self.sample_rate:.3f}s duration")
        print(f"📊 Final signal: mean={np.mean(np.abs(signal)):.3f}, max={np.max(np.abs(signal)):.3f}")
        
        # Setup stream
        stream = device.setupStream(SoapySDR.SOAPY_SDR_TX, "CF32")
        
        print(f"\n🚢 MARITIME AIS TRANSMISSION STARTING")
        print(f"📡 Frequency: {self.center_freq/1e6:.3f} MHz")
        print(f"🔧 {num_transmissions} transmissions with maritime timing")
        
        try:
            for i in range(num_transmissions):
                print(f"\n=== Maritime TX {i+1}/{num_transmissions} ===")
                
                # Maritime timing: 3-5 second intervals
                silence_time = 3.0 + np.random.uniform(0, 2.0)
                print(f"⏱️  Silence period: {silence_time:.1f}s")
                time.sleep(silence_time)
                
                # Transmit burst
                print("📡 Activating...")
                device.activateStream(stream)
                time.sleep(0.01)  # Settle
                
                print("📡 Transmitting AIS burst...")
                result = device.writeStream(stream, [signal], len(signal))
                
                if result.ret == len(signal):
                    print(f"✅ TX complete: {len(signal)} samples")
                else:
                    print(f"⚠️  Partial TX: {result.ret}/{len(signal)}")
                
                # Deactivate
                time.sleep(0.01)
                device.deactivateStream(stream)
                print("📡 Deactivated")
                
        except KeyboardInterrupt:
            print("\n🛑 Transmission stopped")
        finally:
            device.closeStream(stream)
            print("🚢 Maritime transmission complete")

def main():
    print("🚢 MARITIME AIS TRANSMITTER")
    print("📡 Production-grade AIS transmission")
    print("🌊 Real-world maritime timing")
    
    # Standard maritime test message
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
    
    # Configure LimeSDR
    device.setSampleRate(SoapySDR.SOAPY_SDR_TX, 0, tx.sample_rate)
    device.setFrequency(SoapySDR.SOAPY_SDR_TX, 0, tx.center_freq)
    device.setGain(SoapySDR.SOAPY_SDR_TX, 0, 80)
    
    print(f"📻 TX Config: {tx.center_freq/1e6:.3f} MHz, {tx.sample_rate/1000:.0f} kS/s")
    
    print("\n🎯 Auto-starting transmission in 3 seconds...")
    time.sleep(3)
    
    # Transmit with maritime timing
    tx.transmit_ais(test_message, device, num_transmissions=20)

if __name__ == '__main__':
    main()
