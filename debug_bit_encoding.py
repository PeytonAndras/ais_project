#!/usr/bin/env python3

import sys
sys.path.append('debug')

from maritime_transmitter import MaritimeAISTransmitter

def test_bit_encoding():
    """Test what the payload should encode to"""
    print("🔧 BIT ENCODING TEST")
    print("=" * 40)
    
    transmitter = MaritimeAISTransmitter()
    payload = "15MvlfP000G?n@@K>OW`4?vN0<0="
    
    print(f"📡 Payload: '{payload}'")
    print(f"📡 First char: '{payload[0]}' = ASCII {ord(payload[0])}")
    
    # Convert to bits
    bits = transmitter.ais_6bit_encode(payload)
    
    print(f"📊 Total bits: {len(bits)}")
    print(f"📊 First 24 bits: {''.join(map(str, bits[:24]))}")
    print(f"📊 Expected msg type 1: 000001")
    
    # Check first character encoding
    first_char_bits = bits[:6]
    first_char_val = 0
    for i, bit in enumerate(first_char_bits):
        first_char_val |= (bit << (5 - i))
    
    print(f"🔧 First 6 bits: {''.join(map(str, first_char_bits))} = {first_char_val}")
    
    # Expected: character '1' (ASCII 49) should encode to 6-bit value 1
    # ASCII 49 is in range 48-87, so 6-bit = 49 - 48 = 1
    # 6-bit value 1 = binary 000001
    
    print(f"🔧 Character '1' (ASCII 49):")
    print(f"   ASCII 49 is in range 48-87")
    print(f"   6-bit value = 49 - 48 = 1")
    print(f"   Binary 1 = 000001")
    
    if first_char_bits == [0, 0, 0, 0, 0, 1]:
        print("✅ First character encoding is correct")
    else:
        print("❌ First character encoding is wrong")
        print(f"   Expected: [0, 0, 0, 0, 0, 1]")
        print(f"   Got:      {first_char_bits}")

if __name__ == "__main__":
    test_bit_encoding()
