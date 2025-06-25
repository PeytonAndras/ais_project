"""
AIS Protocol Module

Handles AIS message encoding using pyais library for standards compliance.
Provides a clean interface for SIREN to generate AIS messages.
"""

import numpy as np
from pyais.messages import MessageType1, MessageType2, MessageType3, MessageType4, MessageType5, MessageType18, MessageType21
from pyais.encode import encode_msg
from pyais import decode

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
    """Build AIS payload from message fields using pyais"""
    msg_type = fields.get('msg_type', 1)
    
    try:
        if msg_type in [1, 2, 3]:
            return build_position_report_pyais(fields)
        elif msg_type == 4:
            return build_base_station_report_pyais(fields)
        elif msg_type == 5:
            return build_static_voyage_data_pyais(fields)
        elif msg_type == 18:
            return build_class_b_position_report_pyais(fields)
        elif msg_type == 21:
            return build_aid_to_navigation_report_pyais(fields)
        else:
            raise ValueError(f"Unsupported AIS message type: {msg_type}")
    except Exception as e:
        print(f"Error building AIS payload with pyais: {e}")
        # Fallback to custom implementation if needed
        raise

def build_position_report_pyais(fields):
    """Build AIS position report (Types 1, 2, 3) using pyais"""
    msg_type = fields.get('msg_type', 1)
    
    # Map fields to pyais format
    msg_data = {
        'msg_type': msg_type,
        'repeat': fields.get('repeat', 0),
        'mmsi': fields['mmsi'],
        'status': fields.get('nav_status', 0),
        'turn': fields.get('rot', 0),
        'speed': fields['sog'],
        'accuracy': fields.get('accuracy', 1),
        'lon': fields['lon'],
        'lat': fields['lat'],
        'course': fields['cog'],
        'heading': fields.get('hdg', 511),
        'second': int(fields.get('timestamp', 60)),
        'maneuver': 0,  # Not used in SIREN
        'spare_1': 0,
        'raim': fields.get('raim', 0),
        'radio': fields.get('radio_status', 0)
    }
    
    # Create message based on type
    if msg_type == 1:
        msg = MessageType1(**msg_data)
    elif msg_type == 2:
        msg = MessageType2(**msg_data)
    else:  # msg_type == 3
        msg = MessageType3(**msg_data)
    
    # Encode to NMEA
    encoded = encode_msg(msg)
    
    # Extract payload and fill bits from the encoded sentence
    parts = encoded[0].split(',')
    payload = parts[5]
    fill = int(parts[6].split('*')[0])
    
    return payload, fill

def build_base_station_report_pyais(fields):
    """Build AIS Type 4 Base Station Report using pyais"""
    from datetime import datetime
    
    # Get timestamp or use current time
    if all(k in fields for k in ['year', 'month', 'day', 'hour', 'minute', 'second']):
        timestamp = datetime(
            fields['year'], fields['month'], fields['day'],
            fields['hour'], fields['minute'], fields['second']
        )
    else:
        timestamp = datetime.now()
    
    msg_data = {
        'msg_type': 4,
        'repeat': fields.get('repeat', 0),
        'mmsi': fields['mmsi'],
        'year': timestamp.year,
        'month': timestamp.month,
        'day': timestamp.day,
        'hour': timestamp.hour,
        'minute': timestamp.minute,
        'second': timestamp.second,
        'accuracy': fields.get('accuracy', 1),
        'lon': fields['lon'],
        'lat': fields['lat'],
        'epfd': fields.get('epfd_type', 1),
        'spare_1': 0,
        'raim': fields.get('raim', 0),
        'radio': fields.get('radio_status', 0)
    }
    
    msg = MessageType4(**msg_data)
    encoded = encode_msg(msg)
    
    parts = encoded[0].split(',')
    payload = parts[5]
    fill = int(parts[6].split('*')[0])
    
    return payload, fill

def build_static_voyage_data_pyais(fields):
    """Build AIS Type 5 Static and Voyage Related Data using pyais"""
    msg_data = {
        'msg_type': 5,
        'repeat': fields.get('repeat', 0),
        'mmsi': fields['mmsi'],
        'ais_version': fields.get('ais_version', 0),
        'imo': fields.get('imo_number', 0),
        'callsign': fields.get('call_sign', ''),
        'shipname': fields.get('vessel_name', fields.get('name', 'UNKNOWN')),
        'ship_type': fields.get('ship_type', 0),
        'to_bow': fields.get('dim_to_bow', 0),
        'to_stern': fields.get('dim_to_stern', 0),
        'to_port': fields.get('dim_to_port', 0),
        'to_starboard': fields.get('dim_to_starboard', 0),
        'epfd': fields.get('epfd_type', 1),
        'month': fields.get('eta_month', 0),
        'day': fields.get('eta_day', 0),
        'hour': fields.get('eta_hour', 24),
        'minute': fields.get('eta_minute', 60),
        'draught': fields.get('max_draft', 0) / 10.0 if fields.get('max_draft', 0) > 0 else 0.0,  # Convert from 1/10 meters to meters
        'destination': fields.get('destination', ''),
        'dte': fields.get('dte', 1),
        'spare_1': 0
    }
    
    msg = MessageType5(**msg_data)
    encoded = encode_msg(msg)
    
    parts = encoded[0].split(',')
    payload = parts[5]
    fill = int(parts[6].split('*')[0])
    
    return payload, fill

def build_class_b_position_report_pyais(fields):
    """Build AIS Type 18 Standard Class B CS Position Report using pyais"""
    msg_data = {
        'msg_type': 18,
        'repeat': fields.get('repeat', 0),
        'mmsi': fields['mmsi'],
        'reserved_1': 0,
        'speed': fields['sog'],
        'accuracy': fields.get('accuracy', 1),
        'lon': fields['lon'],
        'lat': fields['lat'],
        'course': fields['cog'],
        'heading': fields.get('hdg', 511),
        'second': int(fields.get('timestamp', 60)),
        'reserved_2': 0,
        'cs': fields.get('cs_unit', 1),
        'display': fields.get('display', 0),
        'dsc': fields.get('dsc', 1),
        'band': fields.get('band', 1),
        'msg22': fields.get('msg22', 0),
        'assigned': fields.get('assigned', 0),
        'raim': fields.get('raim', 0),
        'radio': fields.get('radio_status', 0)
    }
    
    msg = MessageType18(**msg_data)
    encoded = encode_msg(msg)
    
    parts = encoded[0].split(',')
    payload = parts[5]
    fill = int(parts[6].split('*')[0])
    
    return payload, fill

def build_aid_to_navigation_report_pyais(fields):
    """Build AIS Type 21 Aid-to-Navigation Report using pyais"""
    msg_data = {
        'msg_type': 21,
        'repeat': fields.get('repeat', 0),
        'mmsi': fields['mmsi'],
        'aid_type': fields.get('aid_type', 1),
        'name': fields.get('name', 'AID TO NAVIGATION'),
        'accuracy': fields.get('accuracy', 1),
        'lon': fields['lon'],
        'lat': fields['lat'],
        'to_bow': fields.get('dim_to_bow', 0),
        'to_stern': fields.get('dim_to_stern', 0),
        'to_port': fields.get('dim_to_port', 0),
        'to_starboard': fields.get('dim_to_starboard', 0),
        'epfd': fields.get('epfd_type', 1),
        'second': int(fields.get('timestamp', 60)),
        'off_position': fields.get('off_position', 0),
        'reserved_1': fields.get('aton_status', 0),
        'raim': fields.get('raim', 0),
        'virtual_aid': fields.get('virtual_aid', 0),
        'assigned': fields.get('assigned', 0),
        'spare_1': 0,
        'name_ext': ''  # Extension name - not used in SIREN
    }
    
    msg = MessageType21(**msg_data)
    encoded = encode_msg(msg)
    
    parts = encoded[0].split(',')
    payload = parts[5]
    fill = int(parts[6].split('*')[0])
    
    return payload, fill

# Keep legacy functions for compatibility and bit-level operations
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
    """Create complete NMEA sentence from AIS fields using pyais"""
    try:
        # Use pyais for encoding
        payload, fill = build_ais_payload(fields)
        
        # Create NMEA sentence
        sentence = f"AIVDM,1,1,,{channel},{payload},{fill}"
        cs = compute_checksum(sentence)
        full_sentence = f"!{sentence}*{cs}"
        
        return full_sentence
    except Exception as e:
        print(f"Error creating NMEA sentence: {e}")
        raise

def validate_ais_message(nmea_sentence):
    """Validate AIS message using pyais decoder"""
    try:
        decoded = decode(nmea_sentence)
        return True, decoded
    except Exception as e:
        return False, str(e)
