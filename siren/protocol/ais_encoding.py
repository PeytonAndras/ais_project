"""
AIS Protocol Module

Handles AIS message encoding, NMEA sentence generation, and checksums.
Contains all the core AIS protocol functions from the original implementation.
"""

import numpy as np

def sixbit_to_char(val):
    """Convert 6-bit value to AIS ASCII character"""
    if val < 0 or val > 63:
        raise ValueError("6-bit value out of range")
    return chr(val + 48 if val < 40 else val + 56)

def char_to_sixbit(char):
    """Convert AIS 6-bit ASCII character to bits"""
    val = ord(char)
    if val >= 48 and val < 88:
        val -= 48
    elif val >= 96 and val < 128:
        val -= 56
    else:
        raise ValueError(f"Invalid AIS character: {char}")
    
    # Convert to 6 bits
    return [(val >> 5) & 1, (val >> 4) & 1, (val >> 3) & 1, 
            (val >> 2) & 1, (val >> 1) & 1, val & 1]

def compute_checksum(sentence):
    """Compute NMEA checksum (XOR of all characters)"""
    cs = 0
    for c in sentence:
        cs ^= ord(c)
    return f"{cs:02X}"

def build_ais_payload(fields):
    """Build AIS payload from message fields"""
    bits = []
    
    # Helper function to add bits to the message
    def add(value, length):
        for i in range(length - 1, -1, -1):
            bits.append((value >> i) & 1)
    
    # Add all required fields for position report
    add(fields['msg_type'], 6)   # Message type
    add(fields['repeat'], 2)     # Repeat indicator
    add(fields['mmsi'], 30)      # MMSI (ship ID)
    add(fields['nav_status'], 4) # Navigation status
    add(fields['rot'] & 0xFF, 8) # Rate of Turn
    
    # Speed over ground (1/10 knots)
    add(int(fields['sog'] * 10) & 0x3FF, 10)
    
    # Position accuracy
    add(fields['accuracy'], 1)
    
    # Longitude (1/10000 minute)
    lon_minutes = fields['lon'] * 60
    lon_value = int(lon_minutes * 10000)
    if lon_value < 0:
        lon_value = (1 << 28) + lon_value  # Two's complement
    add(int(lon_value) & ((1 << 28) - 1), 28)
    
    # Latitude (1/10000 minute)
    lat_minutes = fields['lat'] * 60
    lat_value = int(lat_minutes * 10000)
    if lat_value < 0:
        lat_value = (1 << 27) + lat_value  # Two's complement
    add(int(lat_value) & ((1 << 27) - 1), 27)
    
    # Course over ground (1/10 degrees)
    add(int(fields['cog'] * 10) & 0xFFF, 12)
    
    # True heading
    if fields['hdg'] == -1:  # Not available
        add(511, 9)
    else:
        add(int(fields['hdg']) & 0x1FF, 9)
    
    # Timestamp
    add(int(fields['timestamp']) & 0x3F, 6)
    
    # Spare bits
    add(0, 8)
    
    # Pad to 6-bit boundary
    fill = (6 - (len(bits) % 6)) % 6
    for _ in range(fill): 
        bits.append(0)
    
    # Convert binary data to 6-bit ASCII
    payload = ''.join(sixbit_to_char(int(''.join(str(b) for b in bits[i:i+6]), 2))
                      for i in range(0, len(bits), 6))
    
    return payload, fill

def calculate_crc(bits):
    """Calculate CRC-16-CCITT for AIS message correctly at bit level"""
    poly = 0x1021
    crc = 0xFFFF
    
    for bit in bits:
        # Correctly process one bit at a time
        crc ^= (bit << 15)
        crc = (crc << 1) ^ poly if crc & 0x8000 else crc << 1
        crc &= 0xFFFF
    
    return [(crc >> i) & 1 for i in range(15, -1, -1)]

def create_nmea_sentence(fields, channel='A'):
    """Create complete NMEA sentence from AIS fields"""
    # Build payload
    payload, fill = build_ais_payload(fields)
    
    # Create NMEA sentence
    sentence = f"AIVDM,1,1,,{channel},{payload},{fill}"
    cs = compute_checksum(sentence)
    full_sentence = f"!{sentence}*{cs}"
    
    return full_sentence
