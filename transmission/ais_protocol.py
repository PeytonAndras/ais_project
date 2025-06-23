#!/usr/bin/env python3
"""
AIS Protocol Implementation for Transmission

This module implements the complete AIS protocol stack for generating
compliant AIS messages that can be decoded by rtl-ais and other receivers.

Based on ITU-R M.1371-5 specification and analysis of rtl-ais source code.
"""

import numpy as np
import struct
import time
from typing import List, Tuple, Optional
from bitarray import bitarray
try:
    import crcmod.predefined
    CRCMOD_AVAILABLE = True
except ImportError:
    CRCMOD_AVAILABLE = False

class AISMessage:
    """Base class for AIS messages"""
    
    def __init__(self, mmsi: int, message_type: int = 1):
        self.mmsi = mmsi
        self.message_type = message_type
        self.timestamp = int(time.time())
    
    def to_bits(self) -> bitarray:
        """Convert message to bit array - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement to_bits()")

class AISPositionReport(AISMessage):
    """AIS Position Report (Message Type 1, 2, 3)"""
    
    def __init__(self, mmsi: int, latitude: float, longitude: float, 
                 sog: float = 0.0, cog: float = 0.0, heading: int = 511,
                 message_type: int = 1, nav_status: int = 0):
        super().__init__(mmsi, message_type)
        self.latitude = latitude
        self.longitude = longitude
        self.sog = sog  # Speed over ground in knots
        self.cog = cog  # Course over ground in degrees
        self.heading = heading  # True heading in degrees (511 = not available)
        self.nav_status = nav_status
        
    def to_bits(self) -> bitarray:
        """Convert position report to AIS bit format"""
        bits = bitarray()
        
        # Message Type (6 bits)
        bits.extend(self._int_to_bits(self.message_type, 6))
        
        # Repeat Indicator (2 bits) - always 0 for original transmission
        bits.extend(self._int_to_bits(0, 2))
        
        # MMSI (30 bits)
        bits.extend(self._int_to_bits(self.mmsi, 30))
        
        # Navigation Status (4 bits)
        bits.extend(self._int_to_bits(self.nav_status, 4))
        
        # Rate of Turn (8 bits) - not available
        bits.extend(self._int_to_bits(128, 8))  # 128 = not available
        
        # Speed over Ground (10 bits) - in 0.1 knot resolution
        sog_encoded = min(int(self.sog * 10), 1022)
        bits.extend(self._int_to_bits(sog_encoded, 10))
        
        # Position Accuracy (1 bit) - 0 = low accuracy
        bits.extend(self._int_to_bits(0, 1))
        
        # Longitude (28 bits) - in 1/10000 minute resolution
        lon_encoded = int(self.longitude * 600000)
        if lon_encoded < 0:
            lon_encoded = (1 << 28) + lon_encoded  # Two's complement
        bits.extend(self._int_to_bits(lon_encoded, 28))
        
        # Latitude (27 bits) - in 1/10000 minute resolution
        lat_encoded = int(self.latitude * 600000)
        if lat_encoded < 0:
            lat_encoded = (1 << 27) + lat_encoded  # Two's complement
        bits.extend(self._int_to_bits(lat_encoded, 27))
        
        # Course over Ground (12 bits) - in 0.1 degree resolution
        cog_encoded = int(self.cog * 10) if self.cog != 360.0 else 3600
        bits.extend(self._int_to_bits(cog_encoded, 12))
        
        # True Heading (9 bits)
        bits.extend(self._int_to_bits(self.heading, 9))
        
        # Time Stamp (6 bits) - seconds in UTC minute
        timestamp = int(time.time()) % 60
        bits.extend(self._int_to_bits(timestamp, 6))
        
        # Maneuver Indicator (2 bits) - not available
        bits.extend(self._int_to_bits(0, 2))
        
        # Spare (3 bits)
        bits.extend(self._int_to_bits(0, 3))
        
        # RAIM flag (1 bit)
        bits.extend(self._int_to_bits(0, 1))
        
        # Communication State (19 bits) - SOTDMA
        # Sync state (2 bits), slot timeout (3 bits), sub message (14 bits)
        bits.extend(self._int_to_bits(0, 19))
        
        return bits
    
    def _int_to_bits(self, value: int, num_bits: int) -> bitarray:
        """Convert integer to bitarray with specified number of bits"""
        bits = bitarray()
        for i in range(num_bits - 1, -1, -1):
            bits.append((value >> i) & 1)
        return bits

class AISProtocol:
    """AIS Protocol Layer Implementation"""
    
    # Training sequence: alternating 1010... pattern (24 bits)
    TRAINING_SEQUENCE = bitarray('101010101010101010101010')
    
    # Start delimiter: 01111110 (8 bits)
    START_DELIMITER = bitarray('01111110')
    
    # End delimiter: 01111110 (8 bits) 
    END_DELIMITER = bitarray('01111110')
    
    def __init__(self):
        # Initialize CRC-16 CCITT calculator
        if CRCMOD_AVAILABLE:
            self.crc16 = crcmod.predefined.mkCrcFun('crc-ccitt-false')
        else:
            # Fallback CRC implementation
            self.crc16 = self._crc16_ccitt_fallback
    
    def create_packet(self, message: AISMessage) -> bitarray:
        """Create complete AIS packet with training, delimiters, and CRC"""
        
        # Get message bits
        message_bits = message.to_bits()
        
        # Convert message bits to bytes for CRC calculation
        # Pad to byte boundary if necessary
        padded_bits = message_bits.copy()
        while len(padded_bits) % 8 != 0:
            padded_bits.append(0)
        
        message_bytes = padded_bits.tobytes()
        
        # Calculate CRC-16
        crc_value = self.crc16(message_bytes)
        crc_bits = bitarray()
        for i in range(15, -1, -1):
            crc_bits.append((crc_value >> i) & 1)
        
        # Apply bit stuffing to data + CRC
        data_with_crc = message_bits + crc_bits
        stuffed_data = self._bit_stuff(data_with_crc)
        
        # Assemble complete packet
        packet = bitarray()
        packet.extend(self.TRAINING_SEQUENCE)
        packet.extend(self.START_DELIMITER)
        packet.extend(stuffed_data)
        packet.extend(self.END_DELIMITER)
        
        return packet
    
    def _bit_stuff(self, data: bitarray) -> bitarray:
        """Apply HDLC bit stuffing: insert 0 after five consecutive 1s"""
        stuffed = bitarray()
        consecutive_ones = 0
        
        for bit in data:
            stuffed.append(bit)
            
            if bit == 1:
                consecutive_ones += 1
                if consecutive_ones == 5:
                    stuffed.append(0)  # Insert stuff bit
                    consecutive_ones = 0
            else:
                consecutive_ones = 0
        
        return stuffed
    
    def nrzi_encode(self, data: bitarray) -> bitarray:
        """Apply NRZI (Non-Return-to-Zero Inverted) encoding"""
        encoded = bitarray()
        current_level = 0  # Start with 0
        
        for bit in data:
            if bit == 1:
                # Transition for '1'
                current_level = 1 - current_level
            # No transition for '0'
            encoded.append(current_level)
        
        return encoded

    def _crc16_ccitt_fallback(self, data: bytes) -> int:
        """Fallback CRC-16 CCITT implementation (polynomial 0x1021)"""
        crc = 0xFFFF
        
        for byte in data:
            crc ^= (byte << 8)
            for _ in range(8):
                if crc & 0x8000:
                    crc = ((crc << 1) ^ 0x1021) & 0xFFFF
                else:
                    crc = (crc << 1) & 0xFFFF
        
        return crc ^ 0xFFFF

class GMSKModulator:
    """GMSK Modulator for AIS transmission
    
    Implements Gaussian Minimum Shift Keying with BT=0.4
    as specified in ITU-R M.1371-5
    """
    
    def __init__(self, sample_rate: int = 96000, symbol_rate: int = 9600, 
                 bt: float = 0.4, samples_per_symbol: int = 10):
        self.sample_rate = sample_rate
        self.symbol_rate = symbol_rate
        self.bt = bt
        self.samples_per_symbol = samples_per_symbol
        
        # Verify sample rate compatibility
        if sample_rate % symbol_rate != 0:
            raise ValueError(f"Sample rate {sample_rate} must be multiple of symbol rate {symbol_rate}")
        
        self.actual_sps = sample_rate // symbol_rate
        if self.actual_sps != samples_per_symbol:
            print(f"Warning: Adjusted samples per symbol to {self.actual_sps}")
            self.samples_per_symbol = self.actual_sps
        
        # Generate Gaussian filter
        self.gaussian_filter = self._generate_gaussian_filter()
        
        # Phase accumulator for continuous phase
        self.phase = 0.0
        
    def _generate_gaussian_filter(self) -> np.ndarray:
        """Generate Gaussian pulse shaping filter"""
        # Filter length in symbols
        span = 4  # 4 symbol periods
        
        # Time vector
        n_taps = span * self.samples_per_symbol + 1
        t = np.linspace(-span/2, span/2, n_taps)
        
        # Gaussian filter
        alpha = np.sqrt(np.log(2)) / (2 * self.bt)
        h = np.exp(-2 * (np.pi * alpha * t)**2)
        
        # Normalize
        h = h / np.sum(h)
        
        return h
    
    def modulate(self, bits: bitarray) -> np.ndarray:
        """Modulate bit sequence to GMSK signal"""
        
        # Convert bits to NRZ symbols (+1 for 1, -1 for 0)
        symbols = np.array([1.0 if bit else -1.0 for bit in bits])
        
        # Upsample symbols
        upsampled = np.zeros(len(symbols) * self.samples_per_symbol)
        upsampled[::self.samples_per_symbol] = symbols
        
        # Apply Gaussian filter
        filtered = np.convolve(upsampled, self.gaussian_filter, mode='same')
        
        # MSK modulation: frequency shift keying with continuous phase
        # Frequency deviation = symbol_rate / 4
        freq_dev = self.symbol_rate / 4.0
        
        # Generate complex baseband signal
        output = np.zeros(len(filtered), dtype=complex)
        
        for i in range(len(filtered)):
            # Phase increment based on filtered symbol
            phase_inc = 2 * np.pi * freq_dev * filtered[i] / self.sample_rate
            self.phase += phase_inc
            
            # Generate complex sample
            output[i] = np.exp(1j * self.phase)
        
        return output
    
    def reset_phase(self):
        """Reset phase accumulator"""
        self.phase = 0.0

def main():
    """Test the AIS protocol implementation"""
    
    # Create test position report
    message = AISPositionReport(
        mmsi=123456789,
        latitude=37.7749,    # San Francisco
        longitude=-122.4194,
        sog=12.5,           # 12.5 knots
        cog=45.0,           # 45 degrees
        heading=45,         # 45 degrees
        message_type=1
    )
    
    # Create protocol handler
    protocol = AISProtocol()
    
    # Generate packet
    packet_bits = protocol.create_packet(message)
    print(f"Generated packet with {len(packet_bits)} bits")
    
    # Apply NRZI encoding
    nrzi_bits = protocol.nrzi_encode(packet_bits)
    print(f"NRZI encoded: {len(nrzi_bits)} bits")
    
    # Modulate with GMSK
    modulator = GMSKModulator(sample_rate=96000, symbol_rate=9600)
    signal = modulator.modulate(nrzi_bits)
    print(f"Generated signal: {len(signal)} samples ({len(signal)/96000:.3f} seconds)")
    
    return signal, packet_bits, nrzi_bits

if __name__ == "__main__":
    signal, bits, nrzi = main()
