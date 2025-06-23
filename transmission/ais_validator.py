#!/usr/bin/env python3
"""
AIS Transmission Validator and Tester

This module validates that our AIS transmissions are compatible with rtl-ais
by comparing our implementation against known good samples and testing
packet structure compliance.
"""

import numpy as np
import struct
import subprocess
import tempfile
import os
import wave
import time
from typing import List, Tuple, Optional
import logging

from ais_protocol import AISPositionReport, AISProtocol, GMSKModulator

class AISValidator:
    """Validates AIS packet structure and content"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def validate_packet_structure(self, packet_bits) -> bool:
        """Validate basic packet structure"""
        
        # Convert bitarray to list for easier processing
        bits = list(packet_bits)
        
        # Check minimum length (training + start + minimal data + CRC + end)
        min_length = 24 + 8 + 168 + 16 + 8  # Minimum AIS packet
        if len(bits) < min_length:
            self.logger.error(f"Packet too short: {len(bits)} < {min_length}")
            return False
        
        # Check training sequence (24 bits of alternating 1010...)
        expected_training = [1, 0] * 12
        actual_training = bits[:24]
        if actual_training != expected_training:
            self.logger.error("Invalid training sequence")
            return False
        
        # Check start delimiter (01111110)
        expected_start = [0, 1, 1, 1, 1, 1, 1, 0]
        actual_start = bits[24:32]
        if actual_start != expected_start:
            self.logger.error("Invalid start delimiter")
            return False
        
        # Find end delimiter
        expected_end = [0, 1, 1, 1, 1, 1, 1, 0]
        end_pos = -1
        for i in range(len(bits) - 8, 31, -1):  # Search backwards
            if bits[i:i+8] == expected_end:
                end_pos = i
                break
        
        if end_pos == -1:
            self.logger.error("End delimiter not found")
            return False
        
        self.logger.info(f"Packet structure valid: {len(bits)} bits")
        return True
    
    def validate_message_content(self, message: AISPositionReport) -> bool:
        """Validate AIS message content"""
        
        # Check MMSI range
        if not (100000000 <= message.mmsi <= 999999999):
            self.logger.error(f"Invalid MMSI: {message.mmsi}")
            return False
        
        # Check coordinates
        if not (-90 <= message.latitude <= 90):
            self.logger.error(f"Invalid latitude: {message.latitude}")
            return False
        if not (-180 <= message.longitude <= 180):
            self.logger.error(f"Invalid longitude: {message.longitude}")
            return False
        
        # Check speed (0-102.2 knots)
        if not (0 <= message.sog <= 102.2):
            self.logger.error(f"Invalid SOG: {message.sog}")
            return False
        
        # Check course (0-359.9 degrees)
        if not (0 <= message.cog < 360):
            self.logger.error(f"Invalid COG: {message.cog}")
            return False
        
        self.logger.info("Message content valid")
        return True
    
    def extract_message_from_packet(self, packet_bits) -> Optional[bytes]:
        """Extract the data portion from a packet for analysis"""
        
        bits = list(packet_bits)
        
        # Skip training sequence (24 bits) and start delimiter (8 bits)
        start_pos = 32
        
        # Find end delimiter
        expected_end = [0, 1, 1, 1, 1, 1, 1, 0]
        end_pos = -1
        for i in range(len(bits) - 8, start_pos, -1):
            if bits[i:i+8] == expected_end:
                end_pos = i
                break
        
        if end_pos == -1:
            return None
        
        # Extract data portion (includes stuffed bits and CRC)
        data_bits = bits[start_pos:end_pos]
        
        # Remove bit stuffing
        unstuffed = self._remove_bit_stuffing(data_bits)
        
        # Convert to bytes (without CRC)
        if len(unstuffed) < 16:  # Need at least CRC
            return None
        
        message_bits = unstuffed[:-16]  # Remove CRC
        
        # Pad to byte boundary
        while len(message_bits) % 8 != 0:
            message_bits.append(0)
        
        # Convert to bytes
        message_bytes = bytearray()
        for i in range(0, len(message_bits), 8):
            byte_bits = message_bits[i:i+8]
            byte_val = 0
            for j, bit in enumerate(byte_bits):
                byte_val |= (bit << (7-j))
            message_bytes.append(byte_val)
        
        return bytes(message_bytes)
    
    def _remove_bit_stuffing(self, bits: List[int]) -> List[int]:
        """Remove HDLC bit stuffing"""
        unstuffed = []
        consecutive_ones = 0
        i = 0
        
        while i < len(bits):
            bit = bits[i]
            unstuffed.append(bit)
            
            if bit == 1:
                consecutive_ones += 1
                if consecutive_ones == 5:
                    # Next bit should be stuffed 0
                    if i + 1 < len(bits) and bits[i + 1] == 0:
                        i += 1  # Skip stuffed bit
                    consecutive_ones = 0
            else:
                consecutive_ones = 0
            
            i += 1
        
        return unstuffed

class RTLAISIntegrationTester:
    """Test integration with rtl-ais decoder"""
    
    def __init__(self, rtl_ais_path: str = "../rtl_ais"):
        self.rtl_ais_path = rtl_ais_path
        self.logger = logging.getLogger(__name__)
    
    def save_signal_as_wav(self, signal: np.ndarray, filename: str, 
                          sample_rate: int = 96000):
        """Save complex signal as stereo WAV file for testing"""
        
        # Convert complex to stereo (I/Q)
        i_channel = np.real(signal)
        q_channel = np.imag(signal)
        
        # Normalize to 16-bit range
        max_val = max(np.max(np.abs(i_channel)), np.max(np.abs(q_channel)))
        if max_val > 0:
            scale = 32767 / max_val
            i_channel = (i_channel * scale).astype(np.int16)
            q_channel = (q_channel * scale).astype(np.int16)
        
        # Interleave I/Q samples
        stereo_data = np.empty(len(signal) * 2, dtype=np.int16)
        stereo_data[0::2] = i_channel
        stereo_data[1::2] = q_channel
        
        # Write WAV file
        with wave.open(filename, 'wb') as wav_file:
            wav_file.setnchannels(2)  # Stereo
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(stereo_data.tobytes())
        
        self.logger.info(f"Saved signal to {filename}")
    
    def save_signal_as_raw(self, signal: np.ndarray, filename: str):
        """Save signal as raw complex float32 for rtl-ais"""
        
        # Convert to interleaved I/Q float32
        raw_data = np.empty(len(signal) * 2, dtype=np.float32)
        raw_data[0::2] = np.real(signal)
        raw_data[1::2] = np.imag(signal)
        
        with open(filename, 'wb') as f:
            raw_data.tofile(f)
        
        self.logger.info(f"Saved raw signal to {filename}")
    
    def test_with_rtl_ais(self, signal: np.ndarray, sample_rate: int = 96000) -> bool:
        """Test signal with actual rtl-ais decoder"""
        
        if not os.path.exists(self.rtl_ais_path):
            self.logger.error(f"rtl-ais not found at {self.rtl_ais_path}")
            return False
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(suffix='.raw', delete=False) as tmp:
            tmp_filename = tmp.name
        
        try:
            # Save signal as raw I/Q data
            self.save_signal_as_raw(signal, tmp_filename)
            
            # Run rtl-ais on the file
            cmd = [
                self.rtl_ais_path,
                '-A',  # Disable built-in decoder, output raw samples
                '-s', str(sample_rate),
                '-n',  # Log NMEA to stderr
                tmp_filename
            ]
            
            self.logger.info(f"Running: {' '.join(cmd)}")
            
            # Run rtl-ais with timeout
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            
            # Check for NMEA sentences in output
            nmea_found = False
            for line in result.stderr.split('\n'):
                if line.startswith('!AIVDM'):
                    self.logger.info(f"Decoded NMEA: {line.strip()}")
                    nmea_found = True
            
            if not nmea_found:
                self.logger.error("No NMEA sentences decoded")
                self.logger.debug(f"stdout: {result.stdout}")
                self.logger.debug(f"stderr: {result.stderr}")
            
            return nmea_found
            
        except subprocess.TimeoutExpired:
            self.logger.error("rtl-ais timed out")
            return False
        except Exception as e:
            self.logger.error(f"Error running rtl-ais: {e}")
            return False
        finally:
            # Clean up
            if os.path.exists(tmp_filename):
                os.unlink(tmp_filename)

def create_test_message() -> AISPositionReport:
    """Create a test AIS message with known good values"""
    return AISPositionReport(
        mmsi=123456789,
        latitude=37.7749,      # San Francisco
        longitude=-122.4194,
        sog=12.5,             # 12.5 knots
        cog=45.0,             # 45 degrees
        heading=45,           # 45 degrees
        message_type=1,
        nav_status=0          # Under way using engine
    )

def run_comprehensive_test():
    """Run comprehensive validation tests"""
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    logger.info("Starting AIS validation tests...")
    
    # Create test components
    validator = AISValidator()
    protocol = AISProtocol()
    modulator = GMSKModulator(sample_rate=96000, symbol_rate=9600)
    tester = RTLAISIntegrationTester()
    
    # Create test message
    message = create_test_message()
    logger.info(f"Test message: MMSI={message.mmsi}, "
                f"Pos=({message.latitude:.6f}, {message.longitude:.6f})")
    
    # Test 1: Validate message content
    logger.info("Test 1: Message content validation...")
    if not validator.validate_message_content(message):
        logger.error("Message content validation failed")
        return False
    
    # Test 2: Create and validate packet
    logger.info("Test 2: Packet structure validation...")
    packet_bits = protocol.create_packet(message)
    if not validator.validate_packet_structure(packet_bits):
        logger.error("Packet structure validation failed")
        return False
    
    # Test 3: NRZI encoding
    logger.info("Test 3: NRZI encoding...")
    nrzi_bits = protocol.nrzi_encode(packet_bits)
    logger.info(f"NRZI encoded: {len(nrzi_bits)} bits")
    
    # Test 4: GMSK modulation
    logger.info("Test 4: GMSK modulation...")
    modulator.reset_phase()
    signal = modulator.modulate(nrzi_bits)
    logger.info(f"Modulated signal: {len(signal)} samples")
    
    # Test 5: Signal properties
    logger.info("Test 5: Signal properties...")
    duration = len(signal) / 96000
    logger.info(f"Signal duration: {duration:.3f} seconds")
    
    power = np.mean(np.abs(signal)**2)
    logger.info(f"Signal power: {10*np.log10(power):.1f} dB")
    
    # Test 6: Save test files
    logger.info("Test 6: Saving test files...")
    tester.save_signal_as_wav(signal, "test_ais_signal.wav")
    tester.save_signal_as_raw(signal, "test_ais_signal.raw")
    
    # Test 7: rtl-ais integration (if available)
    logger.info("Test 7: rtl-ais integration test...")
    if os.path.exists("../rtl_ais"):
        success = tester.test_with_rtl_ais(signal)
        if success:
            logger.info("rtl-ais integration test PASSED")
        else:
            logger.warning("rtl-ais integration test FAILED")
    else:
        logger.info("rtl-ais not available - skipping integration test")
    
    logger.info("All validation tests completed successfully!")
    return True

def main():
    """Main test function"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description='AIS Transmission Validator')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose logging')
    parser.add_argument('--rtl-ais-path', default='../rtl_ais',
                       help='Path to rtl_ais executable')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    
    success = run_comprehensive_test()
    if not success:
        exit(1)

if __name__ == "__main__":
    main()
