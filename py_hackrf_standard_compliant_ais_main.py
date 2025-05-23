#!/usr/bin/env python3
"""
AIS Decoder - Uses PyHackRF to receive and decode AIS messages from maritime traffic
Supports both live reception and IQ file analysis

Usage:
    python ais_decode.py --live -f 161.975e6 --gain 40
    python ais_decode.py --file ais_capture.iq -r 2e6
"""
import os
import sys
import json
import time
import argparse
import numpy as np
import threading
from datetime import datetime
from pyais import decode as ais_decode
from pyais.messages import NMEAMessage
import logging

try:
    import hackrf
    HACKRF_AVAILABLE = True
except ImportError:
    HACKRF_AVAILABLE = False
    print("Warning: PyHackRF not found, live reception will be unavailable")
    print("Install with: pip install pyhackrf")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('ais_decoder')

# Signal processing parameters
SAMPLE_RATE = 2.0e6
DEMOD_THRESHOLD = 0.3
MIN_FRAME_LENGTH = 200  # Minimum bits for a valid AIS message (including flags)

# Statistics tracking
stats = {
    'frames_processed': 0,
    'valid_frames': 0,
    'corrupt_frames': 0,
    'valid_messages': 0,
    'start_time': None,
}

# AIS flags and constants
AIS_FLAG = [0, 1, 1, 1, 1, 1, 1, 0]  # HDLC flag 0x7E
AIS_FREQS = {
    'A': 161.975e6,  # MHz - Channel A
    'B': 162.025e6   # MHz - Channel B
}

def nrzi_to_nrz(bits):
    """Convert NRZI bits to NRZ bits"""
    out = []
    last = 0
    for bit in bits:
        out.append(1 if bit == last else 0)
        last = bit
    return out

def bit_unstuff(bits):
    """Remove bit stuffing (remove 0 after five consecutive 1s)"""
    out = []
    ones = 0
    for b in bits:
        if b:
            ones += 1
            out.append(1)
            if ones == 5:   # skip stuffed zero
                ones = 0
                continue
        else:
            ones = 0
            out.append(0)
    return out

def bits_to_bytes(bits):
    """Convert array of bits to bytes"""
    # Ensure bit array length is multiple of 8
    while len(bits) % 8 != 0:
        bits.append(0)
        
    return bytes(int("".join(str(b) for b in bits[i:i+8]), 2)
                for i in range(0, len(bits), 8))

def crc16(data: bytes):
    """Calculate CRC-16-CCITT (same as AIS)"""
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc

def ais_bytes_to_nmea(data: bytes):
    """Convert AIS bytes to NMEA-encoded string"""
    bits = []
    for b in data:
        bits.extend([1 if b & (1 << i) else 0 for i in range(7, -1, -1)])
    
    # Pad to multiple of 6 bits
    padding = (6 - (len(bits) % 6)) % 6
    bits.extend([0] * padding)
    
    # Convert 6-bit groups to ASCII
    nmea = ''
    for i in range(0, len(bits), 6):
        val = 0
        for j in range(6):
            if i+j < len(bits):
                val = (val << 1) | bits[i+j]
        nmea += chr(val + 48 if val < 40 else val + 56)
    
    return f"!AIVDM,1,1,,A,{nmea},{padding}*"

def extract_frames(samples, threshold=DEMOD_THRESHOLD):
    """Extract binary frames from demodulated samples"""
    # Simple FSK demodulation
    diff = np.abs(np.diff(np.angle(samples)))
    # Normalize and threshold
    diff /= np.max(diff) if np.max(diff) > 0 else 1
    bits = (diff > threshold).astype(int)
    
    # Find start/end flags (0x7E = 01111110)
    frames = []
    i = 0
    while i < len(bits) - 8:
        # Look for AIS flag pattern
        if bits[i:i+8].tolist() == AIS_FLAG:
            start = i
            # Find ending flag
            end = -1
            for j in range(start + 8, min(len(bits) - 8, start + 2000)):
                if bits[j:j+8].tolist() == AIS_FLAG:
                    end = j + 8
                    break
                    
            if end > start and end - start >= MIN_FRAME_LENGTH:
                frames.append(bits[start:end])
                i = end
                continue
        i += 1
    
    return frames

def demodulate_gmsk(samples):
    """Demodulate GMSK/FSK signal to get bits"""
    # Calculate phase difference (frequency shift)
    phase_diff = np.angle(samples[1:] * np.conj(samples[:-1]))
    
    # Downsample to bit rate 
    samples_per_bit = int(SAMPLE_RATE / 9600)  # AIS is 9600 baud
    bits = []
    
    for i in range(0, len(phase_diff), samples_per_bit):
        if i + samples_per_bit > len(phase_diff):
            break
        
        # Use majority vote over the bit period
        bit_chunk = phase_diff[i:i+samples_per_bit]
        avg_phase = np.mean(bit_chunk)
        bits.append(1 if avg_phase > 0 else 0)
        
    return bits

def process_frame(bits):
    """Process a raw frame to extract AIS message"""
    stats['frames_processed'] += 1
    
    try:
        # Convert NRZI to NRZ and remove bit stuffing
        bits = nrzi_to_nrz(bits)
        bits = bit_unstuff(bits)
        
        # Ensure minimum message length
        if len(bits) < 168:  # shortest AIS message content
            stats['corrupt_frames'] += 1
            return None
        
        # Convert to bytes and check CRC
        data = bits_to_bytes(bits)
        if len(data) < 3:
            stats['corrupt_frames'] += 1
            return None
            
        # Verify CRC if present (last 2 bytes)
        calculated_crc = crc16(data[:-2])
        stored_crc = int.from_bytes(data[-2:], "big")
        
        if calculated_crc != stored_crc:
            logger.debug(f"CRC mismatch: calculated={calculated_crc:04X}, stored={stored_crc:04X}")
            stats['corrupt_frames'] += 1
            return None
            
        stats['valid_frames'] += 1
        
        # Convert to NMEA message
        nmea = ais_bytes_to_nmea(data[:-2])
        
        # Parse AIS message
        try:
            msg = ais_decode(nmea)
            if isinstance(msg, list):
                msg = msg[0]  # Take first message if multiple
                
            stats['valid_messages'] += 1
            return msg
        except Exception as e:
            logger.debug(f"AIS parsing error: {str(e)}")
            return None
            
    except Exception as e:
        logger.debug(f"Frame processing error: {str(e)}")
        stats['corrupt_frames'] += 1
        return None

def process_iq_file(filename, sample_rate=SAMPLE_RATE):
    """Process an IQ file containing AIS signals"""
    logger.info(f"Processing IQ file: {filename}")
    stats['start_time'] = datetime.now()
    
    try:
        # Load IQ samples as complex64
        iq_data = np.fromfile(filename, dtype=np.complex64)
        logger.info(f"Loaded {len(iq_data)} IQ samples")
        
        # Process in chunks to avoid memory issues
        chunk_size = int(sample_rate * 1.0)  # 1 second chunks
        
        for chunk_start in range(0, len(iq_data), chunk_size):
            chunk_end = min(chunk_start + chunk_size, len(iq_data))
            chunk = iq_data[chunk_start:chunk_end]
            
            # Extract frames from the chunk
            bits = demodulate_gmsk(chunk)
            frames = extract_frames(chunk)
            
            for frame in frames:
                msg = process_frame(frame)
                if msg:
                    # Print decoded message as JSON
                    print(json.dumps(msg.asdict(), default=str))
                    
            # Report progress
            progress = chunk_end / len(iq_data) * 100
            logger.info(f"Progress: {progress:.1f}% ({chunk_end}/{len(iq_data)} samples)")
            
    except Exception as e:
        logger.error(f"Error processing IQ file: {str(e)}")
        return False
        
    duration = (datetime.now() - stats['start_time']).total_seconds()
    logger.info(f"File processing complete in {duration:.1f} seconds")
    logger.info(f"Statistics: {stats}")
    return True

class HackRFReceiver:
    """HackRF receiver with PyHackRF"""
    def __init__(self, frequency, sample_rate=SAMPLE_RATE, gain=40):
        self.frequency = frequency
        self.sample_rate = sample_rate
        self.gain = gain
        self.device = None
        self.buffer = []
        self.callback_buffer = []
        self.lock = threading.Lock()
        self.running = False
        
    def start(self):
        """Initialize and start HackRF reception"""
        if not HACKRF_AVAILABLE:
            logger.error("HackRF library not available")
            return False
            
        try:
            # Find and initialize device
            self.device = hackrf.HackRF()
            logger.info(f"Opened HackRF: {self.device.board_id_string()}")
            
            # Configure device
            self.device.sample_rate = self.sample_rate
            self.device.center_freq = self.frequency
            self.device.lna_gain = min(40, max(0, self.gain))
            self.device.vga_gain = min(62, max(0, self.gain))
            
            # Set callback
            self.device.receive_to_buffer = self.rx_callback
            
            logger.info(f"Starting reception on {self.frequency/1e6:.3f} MHz")
            self.device.start_rx_mode()
            self.running = True
            return True
            
        except Exception as e:
            logger.error(f"Error initializing HackRF: {str(e)}")
            self.close()
            return False
    
    def rx_callback(self, hackrf_transfer):
        """Callback for received samples"""
        if not self.running:
            return 0
            
        # Convert buffer to numpy array of complex samples
        buffer = hackrf_transfer.buffer
        samples = np.empty(len(buffer)//2, dtype=np.complex64)
        
        # Convert interleaved I/Q bytes to complex
        samples.real = buffer[::2].astype(np.float32) / 128.0
        samples.imag = buffer[1::2].astype(np.float32) / 128.0
        
        # Add to callback buffer
        with self.lock:
            self.callback_buffer.append(samples)
            
        return 0
    
    def get_samples(self):
        """Get accumulated samples"""
        with self.lock:
            if not self.callback_buffer:
                return np.array([], dtype=np.complex64)
                
            # Combine all buffered chunks
            samples = np.concatenate(self.callback_buffer)
            self.callback_buffer = []
            return samples
    
    def close(self):
        """Close HackRF device"""
        self.running = False
        
        if self.device:
            try:
                self.device.close()
                logger.info("HackRF closed")
            except:
                pass
            self.device = None

def live_decode(frequency, gain=40, duration=None):
    """Live decode AIS messages from HackRF"""
    if not HACKRF_AVAILABLE:
        logger.error("HackRF library not available")
        return False
        
    stats['start_time'] = datetime.now()
    receiver = HackRFReceiver(frequency, SAMPLE_RATE, gain)
    
    if not receiver.start():
        return False
        
    try:
        logger.info("Starting AIS decoder. Press Ctrl+C to stop.")
        end_time = time.time() + duration if duration else None
        
        while True:
            if end_time and time.time() > end_time:
                logger.info(f"Reached specified duration: {duration} seconds")
                break
                
            # Get samples
            samples = receiver.get_samples()
            if len(samples) == 0:
                time.sleep(0.1)
                continue
                
            # Process frames
            frames = extract_frames(samples)
            for frame in frames:
                msg = process_frame(frame)
                if msg:
                    # Print decoded message as JSON
                    print(json.dumps(msg.asdict(), default=str))
            
            # Sleep briefly to reduce CPU usage
            time.sleep(0.05)
            
    except KeyboardInterrupt:
        logger.info("Stopping decoder (Ctrl+C)")
    finally:
        receiver.close()
        
    duration = (datetime.now() - stats['start_time']).total_seconds()
    logger.info(f"Decoding session completed in {duration:.1f} seconds")
    logger.info(f"Statistics: {stats}")
    return True

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='AIS Decoder with HackRF support')
    group = parser.add_mutually_exclusive_group(required=True)
    
    group.add_argument('--file', '-i', help='Input IQ file to process')
    group.add_argument('--live', action='store_true', help='Live decoding from HackRF')
    
    parser.add_argument('--rate', '-r', type=float, default=SAMPLE_RATE,
                       help='Sample rate of IQ data (default: 2e6)')
    parser.add_argument('--freq', '-f', type=float, default=AIS_FREQS['A'],
                       help='Center frequency in Hz (default: 161.975e6)')
    parser.add_argument('--gain', '-g', type=int, default=40,
                       help='Gain setting (default: 40)')
    parser.add_argument('--duration', '-d', type=float, default=None,
                       help='Duration in seconds for live decoding')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    if args.live:
        if not HACKRF_AVAILABLE:
            logger.error("PyHackRF library not available. Install with: pip install pyhackrf")
            return 1
            
        logger.info(f"Starting live AIS decoding on {args.freq/1e6:.3f} MHz")
        live_decode(args.freq, args.gain, args.duration)
    else:
        if not os.path.exists(args.file):
            logger.error(f"File not found: {args.file}")
            return 1
            
        logger.info(f"Processing IQ file: {args.file}")
        process_iq_file(args.file, args.rate)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())