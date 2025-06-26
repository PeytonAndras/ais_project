#!/usr/bin/env python3

import sys
sys.path.append('debug')

from maritime_transmitter import MaritimeAISTransmitter
from maritime_decoder import ProductionMaritimeDecoder

def debug_frame_extraction():
    """Debug frame symbol extraction and NRZI decoding"""
    print("🔧 FRAME EXTRACTION DEBUG")
    print("=" * 40)
    
    transmitter = MaritimeAISTransmitter()
    decoder = ProductionMaritimeDecoder()
    
    test_msg = "!AIVDM,1,1,,A,15MvlfP000G?n@@K>OW`4?vN0<0=,0*47"
    
    # Generate frame and signal
    frame = transmitter.create_maritime_frame(test_msg)
    gmsk_signal = transmitter.generate_gmsk(frame)
    
    print(f"📊 Original frame: {len(frame)} bits")
    print(f"📊 Frame structure: Training(24) + StartFlag(8) + NRZI_Payload + EndFlag(8) + Buffer(8)")
    
    # Show original frame bits
    print(f"🔧 Training (24):    {''.join(map(str, frame[:24]))}")
    print(f"🔧 Start flag (8):   {''.join(map(str, frame[24:32]))}")
    print(f"🔧 First data (24):  {''.join(map(str, frame[32:56]))}")
    
    # Decode using the full pipeline
    demod_signal, activity = decoder.fm_demodulate(gmsk_signal)
    symbols, timing_offset = decoder.clock_recovery(demod_signal)
    
    print(f"\n📡 Decoded symbols: {len(symbols)}")
    
    # Find frame start
    frame_pos, pattern_inverted = decoder.find_frame_start(symbols)
    print(f"🔧 Frame start position: {frame_pos}")
    print(f"🔧 Pattern inverted: {pattern_inverted}")
    
    # Extract training from symbols
    if frame_pos >= 0:
        training_symbols = symbols[frame_pos:frame_pos+24]
        start_flag_symbols = symbols[frame_pos+24:frame_pos+32] if len(symbols) > frame_pos+32 else []
        data_symbols = symbols[frame_pos+32:frame_pos+56] if len(symbols) > frame_pos+56 else []
        
        print(f"🔧 Training symbols:  {''.join(map(str, training_symbols))}")
        print(f"🔧 Start flag symbols: {''.join(map(str, start_flag_symbols))}")
        print(f"🔧 First data symbols: {''.join(map(str, data_symbols))}")
        
        # Check if these match the original frame
        original_training = frame[:24]
        original_start_flag = frame[24:32]
        original_data = frame[32:56]
        
        print(f"\n🔍 COMPARISON:")
        print(f"Training match:   {'✅' if training_symbols == original_training else '❌'}")
        print(f"Start flag match: {'✅' if start_flag_symbols == original_start_flag else '❌'}")
        print(f"Data match:       {'✅' if data_symbols == original_data else '❌'}")
        
        if training_symbols != original_training:
            print(f"   Expected: {''.join(map(str, original_training))}")
            print(f"   Got:      {''.join(map(str, training_symbols))}")
        
        if start_flag_symbols != original_start_flag:
            print(f"   Expected: {''.join(map(str, original_start_flag))}")
            print(f"   Got:      {''.join(map(str, start_flag_symbols))}")
        
        if data_symbols != original_data:
            print(f"   Expected: {''.join(map(str, original_data))}")
            print(f"   Got:      {''.join(map(str, data_symbols))}")
            
        # Now test NRZI decoding on the payload part
        print(f"\n🔧 NRZI DECODING TEST:")
        
        # The payload in the original frame is NRZI encoded
        # Let's extract the NRZI encoded part and see what happens when we decode it
        nrzi_start = 32  # After training + start flag
        nrzi_end = len(frame) - 16  # Before end flag + buffer
        original_nrzi_payload = frame[nrzi_start:nrzi_end]
        
        print(f"🔧 Original NRZI payload ({len(original_nrzi_payload)} bits): {''.join(map(str, original_nrzi_payload[:24]))}")
        
        # NRZI decode this
        nrzi_decoded = decoder.nrzi_decode(original_nrzi_payload, invert=False)
        
        print(f"🔧 NRZI decoded ({len(nrzi_decoded)} bits): {''.join(map(str, nrzi_decoded[:24]))}")
        
        # This should give us the original message bits
        # Let's see what the original message bits should be
        payload = "15MvlfP000G?n@@K>OW`4?vN0<0="
        original_message_bits = transmitter.ais_6bit_encode(payload)
        
        print(f"🔧 Expected message bits: {''.join(map(str, original_message_bits[:24]))}")
        
        if nrzi_decoded[:24] == original_message_bits[:24]:
            print("✅ NRZI decoding is correct")
        else:
            print("❌ NRZI decoding is wrong")

if __name__ == "__main__":
    debug_frame_extraction()
