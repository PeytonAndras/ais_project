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
    """Build AIS payload from message fields - routes to appropriate message builder"""
    msg_type = fields.get('msg_type', 1)
    
    if msg_type in [1, 2, 3]:
        return build_position_report(fields)
    elif msg_type == 4:
        return build_base_station_report(fields)
    elif msg_type == 5:
        return build_static_voyage_data(fields)
    elif msg_type == 18:
        return build_class_b_position_report(fields)
    elif msg_type == 21:
        return build_aid_to_navigation_report(fields)
    else:
        raise ValueError(f"Unsupported AIS message type: {msg_type}")

def build_position_report(fields):
    """Build AIS payload for position report (Types 1, 2, 3)"""
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

def build_base_station_report(fields):
    """Build AIS Type 4 Base Station Report"""
    bits = []
    
    def add(value, length):
        for i in range(length - 1, -1, -1):
            bits.append((value >> i) & 1)
    
    # Message type 4
    add(4, 6)
    add(fields.get('repeat', 0), 2)
    add(fields['mmsi'], 30)
    
    # UTC date and time
    add(fields.get('year', 2024), 14)      # Year (1-9999)
    add(fields.get('month', 1), 4)         # Month (1-12)
    add(fields.get('day', 1), 5)           # Day (1-31)
    add(fields.get('hour', 0), 5)          # Hour (0-23)
    add(fields.get('minute', 0), 6)        # Minute (0-59)
    add(fields.get('second', 0), 6)        # Second (0-59)
    
    # Position accuracy and coordinates
    add(fields.get('accuracy', 1), 1)
    
    # Longitude (same format as position report)
    lon_minutes = fields['lon'] * 60
    lon_value = int(lon_minutes * 10000)
    if lon_value < 0:
        lon_value = (1 << 28) + lon_value
    add(int(lon_value) & ((1 << 28) - 1), 28)
    
    # Latitude
    lat_minutes = fields['lat'] * 60
    lat_value = int(lat_minutes * 10000)
    if lat_value < 0:
        lat_value = (1 << 27) + lat_value
    add(int(lat_value) & ((1 << 27) - 1), 27)
    
    # Electronic Position Fixing Device type
    add(fields.get('epfd_type', 1), 4)     # 1 = GPS
    
    # Spare bits
    add(0, 10)
    
    # RAIM flag
    add(fields.get('raim', 0), 1)
    
    # Radio status
    add(fields.get('radio_status', 0), 19)
    
    # Pad to 6-bit boundary
    fill = (6 - (len(bits) % 6)) % 6
    for _ in range(fill): 
        bits.append(0)
    
    payload = ''.join(sixbit_to_char(int(''.join(str(b) for b in bits[i:i+6]), 2))
                      for i in range(0, len(bits), 6))
    
    return payload, fill

def build_static_voyage_data(fields):
    """Build AIS Type 5 Static and Voyage Related Data"""
    bits = []
    
    def add(value, length):
        for i in range(length - 1, -1, -1):
            bits.append((value >> i) & 1)
    
    def add_string(text, max_chars):
        """Add ASCII string as 6-bit characters"""
        # Truncate or pad to exact length
        text = str(text)[:max_chars].ljust(max_chars, '@')
        for char in text:
            ascii_val = ord(char)
            if ascii_val >= 64:
                ascii_val -= 64
            add(ascii_val, 6)
    
    # Message type 5
    add(5, 6)
    add(fields.get('repeat', 0), 2)
    add(fields['mmsi'], 30)
    
    # AIS Version and IMO number
    add(fields.get('ais_version', 0), 2)   # AIS version (0)
    add(fields.get('imo_number', 0), 30)   # IMO number
    
    # Call sign (7 chars, 6 bits each = 42 bits)
    add_string(fields.get('call_sign', ''), 7)
    
    # Vessel name (20 chars, 6 bits each = 120 bits)
    add_string(fields.get('vessel_name', fields.get('name', 'UNKNOWN')), 20)
    
    # Ship and cargo type
    add(fields.get('ship_type', 0), 8)
    
    # Dimensions
    add(fields.get('dim_to_bow', 0), 9)     # Distance to bow
    add(fields.get('dim_to_stern', 0), 9)   # Distance to stern  
    add(fields.get('dim_to_port', 0), 6)    # Distance to port
    add(fields.get('dim_to_starboard', 0), 6) # Distance to starboard
    
    # Electronic Position Fixing Device type
    add(fields.get('epfd_type', 1), 4)
    
    # ETA fields
    add(fields.get('eta_month', 0), 4)      # Month (1-12, 0=N/A)
    add(fields.get('eta_day', 0), 5)        # Day (1-31, 0=N/A)
    add(fields.get('eta_hour', 24), 5)      # Hour (0-23, 24=N/A)
    add(fields.get('eta_minute', 60), 6)    # Minute (0-59, 60=N/A)
    
    # Maximum draft
    add(fields.get('max_draft', 0), 8)      # In 1/10 meters
    
    # Destination (20 chars, 6 bits each = 120 bits)
    add_string(fields.get('destination', ''), 20)
    
    # DTE (Data Terminal Equipment)
    add(fields.get('dte', 1), 1)           # 1 = not available
    
    # Spare bit
    add(0, 1)
    
    # Pad to 6-bit boundary
    fill = (6 - (len(bits) % 6)) % 6
    for _ in range(fill): 
        bits.append(0)
    
    payload = ''.join(sixbit_to_char(int(''.join(str(b) for b in bits[i:i+6]), 2))
                      for i in range(0, len(bits), 6))
    
    return payload, fill

def build_class_b_position_report(fields):
    """Build AIS Type 18 Standard Class B CS Position Report"""
    bits = []
    
    def add(value, length):
        for i in range(length - 1, -1, -1):
            bits.append((value >> i) & 1)
    
    # Message type 18
    add(18, 6)
    add(fields.get('repeat', 0), 2)
    add(fields['mmsi'], 30)
    
    # Reserved bits
    add(0, 8)
    
    # Speed over ground (same as Type 1)
    add(int(fields['sog'] * 10) & 0x3FF, 10)
    
    # Position accuracy
    add(fields.get('accuracy', 1), 1)
    
    # Longitude and Latitude (same format as Type 1)
    lon_minutes = fields['lon'] * 60
    lon_value = int(lon_minutes * 10000)
    if lon_value < 0:
        lon_value = (1 << 28) + lon_value
    add(int(lon_value) & ((1 << 28) - 1), 28)
    
    lat_minutes = fields['lat'] * 60
    lat_value = int(lat_minutes * 10000)
    if lat_value < 0:
        lat_value = (1 << 27) + lat_value
    add(int(lat_value) & ((1 << 27) - 1), 27)
    
    # Course over ground
    add(int(fields['cog'] * 10) & 0xFFF, 12)
    
    # True heading
    if fields.get('hdg', -1) == -1:
        add(511, 9)
    else:
        add(int(fields['hdg']) & 0x1FF, 9)
    
    # Time stamp
    add(int(fields.get('timestamp', 60)) & 0x3F, 6)
    
    # Regional reserved
    add(0, 2)
    
    # CS Unit flag
    add(fields.get('cs_unit', 1), 1)       # 1 = CS unit
    
    # Display flag
    add(fields.get('display', 0), 1)       # 0 = no display
    
    # DSC flag
    add(fields.get('dsc', 1), 1)           # 1 = not equipped
    
    # Band flag
    add(fields.get('band', 1), 1)          # 1 = capable of operating over whole marine band
    
    # Message 22 flag
    add(fields.get('msg22', 0), 1)         # 0 = no frequency management via Message 22
    
    # Assigned flag
    add(fields.get('assigned', 0), 1)      # 0 = autonomous mode
    
    # RAIM flag
    add(fields.get('raim', 0), 1)
    
    # Radio status
    add(fields.get('radio_status', 0), 20)
    
    # Pad to 6-bit boundary
    fill = (6 - (len(bits) % 6)) % 6
    for _ in range(fill): 
        bits.append(0)
    
    payload = ''.join(sixbit_to_char(int(''.join(str(b) for b in bits[i:i+6]), 2))
                      for i in range(0, len(bits), 6))
    
    return payload, fill

def build_aid_to_navigation_report(fields):
    """Build AIS Type 21 Aid-to-Navigation Report"""
    bits = []
    
    def add(value, length):
        for i in range(length - 1, -1, -1):
            bits.append((value >> i) & 1)
    
    def add_string(text, max_chars):
        """Add ASCII string as 6-bit characters"""
        text = str(text)[:max_chars].ljust(max_chars, '@')
        for char in text:
            ascii_val = ord(char)
            if ascii_val >= 64:
                ascii_val -= 64
            add(ascii_val, 6)
    
    # Message type 21
    add(21, 6)
    add(fields.get('repeat', 0), 2)
    add(fields['mmsi'], 30)
    
    # Aid type (0-31)
    aid_type = fields.get('aid_type', 1)    # 1 = reference point
    add(aid_type, 5)
    
    # Name of aid to navigation (20 chars = 120 bits)
    add_string(fields.get('name', 'AID TO NAVIGATION'), 20)
    
    # Position accuracy
    add(fields.get('accuracy', 1), 1)
    
    # Longitude and Latitude
    lon_minutes = fields['lon'] * 60
    lon_value = int(lon_minutes * 10000)
    if lon_value < 0:
        lon_value = (1 << 28) + lon_value
    add(int(lon_value) & ((1 << 28) - 1), 28)
    
    lat_minutes = fields['lat'] * 60
    lat_value = int(lat_minutes * 10000)
    if lat_value < 0:
        lat_value = (1 << 27) + lat_value
    add(int(lat_value) & ((1 << 27) - 1), 27)
    
    # Dimensions
    add(fields.get('dim_to_bow', 0), 9)
    add(fields.get('dim_to_stern', 0), 9)
    add(fields.get('dim_to_port', 0), 6)
    add(fields.get('dim_to_starboard', 0), 6)
    
    # Electronic Position Fixing Device type
    add(fields.get('epfd_type', 1), 4)
    
    # Time stamp
    add(int(fields.get('timestamp', 60)) & 0x3F, 6)
    
    # Off position indicator
    add(fields.get('off_position', 0), 1)
    
    # AtoN status
    add(fields.get('aton_status', 0), 8)
    
    # RAIM flag
    add(fields.get('raim', 0), 1)
    
    # Virtual aid flag
    add(fields.get('virtual_aid', 0), 1)
    
    # Assigned mode flag
    add(fields.get('assigned', 0), 1)
    
    # Spare bit
    add(0, 1)
    
    # Extension part (optional - Name Extension)
    # For now, we'll leave this empty (0 bits)
    
    # Pad to 6-bit boundary
    fill = (6 - (len(bits) % 6)) % 6
    for _ in range(fill): 
        bits.append(0)
    
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
