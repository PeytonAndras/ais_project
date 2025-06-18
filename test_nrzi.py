#!/usr/bin/env python3
"""Test NRZI encoding/decoding to verify the fix"""

def nrzi_encode_transmitter(bits):
    """Transmitter NRZI encoding - starts from training end state (1)"""
    if not bits:
        return []
        
    encoded = []
    current = 1  # Start from training end state
    
    for bit in bits:
        if bit == 0:
            current = 1 - current  # Transition
        encoded.append(current)
        
    return encoded

def nrzi_decode_receiver(symbols):
    """Receiver NRZI decoding - starts from training end state (1)"""
    if len(symbols) < 1:
        return []
        
    bits = []
    prev = 1  # Training ends with state 1
    
    for symbol in symbols:
        bit = 0 if symbol != prev else 1
        bits.append(bit)
        prev = symbol
        
    return bits

def test_nrzi_chain():
    """Test the complete NRZI encode/decode chain"""
    
    # Test the HDLC start flag
    start_flag = [0, 1, 1, 1, 1, 1, 1, 0]
    print(f"Original start flag: {start_flag}")
    
    # Encode
    encoded = nrzi_encode_transmitter(start_flag)
    print(f"NRZI encoded:        {encoded}")
    
    # Decode
    decoded = nrzi_decode_receiver(encoded)
    print(f"NRZI decoded:        {decoded}")
    
    # Check if round-trip works
    success = decoded == start_flag
    print(f"Round-trip success:  {success}")
    
    if success:
        print("✅ NRZI encoding/decoding is working correctly!")
        
        # Test a longer sequence
        test_data = [0, 1, 1, 1, 1, 1, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0]
        encoded_long = nrzi_encode_transmitter(test_data)
        decoded_long = nrzi_decode_receiver(encoded_long)
        
        print(f"\nLonger test:")
        print(f"Original: {test_data}")
        print(f"Encoded:  {encoded_long}")
        print(f"Decoded:  {decoded_long}")
        print(f"Success:  {decoded_long == test_data}")
        
    else:
        print("❌ NRZI encoding/decoding has issues!")
        
    return success

if __name__ == '__main__':
    test_nrzi_chain()
