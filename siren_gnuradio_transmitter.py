#!/usr/bin/env python3
"""
SIREN GNU Radio AIS Transmitter

This script implements a GNU Radio-based AIS transmitter for SIREN,
based on the proven working ais-simulator.py method.

Usage:
    python siren_gnuradio_transmitter.py --mmsi 123456789 --lat 39.5 --lon -9.2

@ author: Peyton Andras @ Louisiana State University 2025
Based on ais-simulator.py (Embyte & Pastus, Mictronics)
"""

import argparse
import signal
import sys
import time
import threading
import json
import logging
from typing import Optional, Dict, Any

# Check for GNU Radio availability
try:
    from gnuradio import blocks
    from gnuradio import digital
    from gnuradio import gr, pdu
    from gnuradio.eng_option import eng_option
    from gnuradio import ais_simulator
    import osmosdr
    GNURADIO_AVAILABLE = True
except ImportError as e:
    GNURADIO_AVAILABLE = False
    print(f"❌ GNU Radio not available: {e}")
    print("Install with:")
    print("  sudo apt-get install gnuradio gr-osmosdr gr-ais")
    print("  pip install websocket-client")

# Try to import SIREN components
try:
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
    from siren.ships.ais_ship import AISShip
    from siren.protocol.ais_encoding import create_nmea_sentence
    SIREN_AVAILABLE = True
except ImportError:
    SIREN_AVAILABLE = False
    print("⚠️  SIREN modules not available - using standalone mode")

# Try websocket for communication with GNU Radio
try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    print("⚠️  websocket-client not available")
    print("Install with: pip install websocket-client")


class SIRENGnuRadioTransmitter(gr.top_block):
    """GNU Radio-based AIS transmitter for SIREN"""
    
    def __init__(self, channel="A", sample_rate=8000000, bit_rate=9600, 
                 tx_gain=42, bb_gain=30, ppm=0, websocket_port=52002):
        """Initialize GNU Radio AIS transmitter
        
        Args:
            channel: AIS channel "A" (161.975MHz) or "B" (162.025MHz)
            sample_rate: SDR sample rate (default 8MHz)
            bit_rate: AIS bit rate (default 9600 bps)
            tx_gain: RF gain (default 42 dB)
            bb_gain: Baseband gain (default 30 dB)
            ppm: Frequency correction in ppm
            websocket_port: Port for GNU Radio websocket interface
        """
        if not GNURADIO_AVAILABLE:
            raise RuntimeError("GNU Radio not available")
        
        gr.top_block.__init__(self, 'SIREN GNU Radio AIS Transmitter')
        
        self.channel = channel
        self.sample_rate = sample_rate
        self.bit_rate = bit_rate
        self.websocket_port = websocket_port
        
        # Calculate frequency and channel ID
        channel_id = 0 if channel == "A" else 1
        frequency = 161975000 + 50000 * channel_id
        
        print(f"🚢 SIREN GNU Radio AIS Transmitter")
        print(f"📡 Channel: {channel} ({frequency/1e6:.3f} MHz)")
        print(f"⚡ Sample rate: {sample_rate/1e6:.1f} MHz")
        print(f"🔊 TX Gain: {tx_gain} dB, BB Gain: {bb_gain} dB")
        print(f"🌐 Websocket port: {websocket_port}")
        
        # LimeSDR Sink (matches ais-simulator.py exactly)
        self.osmosdr_sink = osmosdr.sink(args="driver=lime,antenna=BAND1")
        self.osmosdr_sink.set_sample_rate(sample_rate)
        self.osmosdr_sink.set_freq_corr(ppm, 0)
        self.osmosdr_sink.set_center_freq(frequency, 0)
        self.osmosdr_sink.set_gain(tx_gain, 0)
        self.osmosdr_sink.set_bb_gain(bb_gain, 0)
        self.osmosdr_sink.set_antenna("BAND1", 0)
        
        # GMSK Modulator (matches ais-simulator.py exactly)
        self.digital_gmsk_mod = digital.gmsk_mod(
            samples_per_symbol=int(sample_rate / bit_rate),
            bt=0.4,
            verbose=False,
            log=False,
        )
        
        # Websocket PDU source
        self.websocket_pdu = ais_simulator.websocket_pdu("0.0.0.0", str(websocket_port))
        
        # PDU to tagged stream converter
        self.blocks_pdu_to_tagged_stream = pdu.pdu_to_tagged_stream(gr.types.byte_t, 'packet_len')
        
        # Power scaling (matches ais-simulator.py exactly)
        self.blocks_multiply_const = blocks.multiply_const_vcc((0.9, ))
        
        # AIS frame builder
        self.ais_build_frame = ais_simulator.bitstring_to_frame(True, 'packet_len')
        
        # Connect the flowgraph (matches ais-simulator.py exactly)
        self.msg_connect((self.websocket_pdu, 'out'), (self.blocks_pdu_to_tagged_stream, 'pdus'))
        self.connect((self.blocks_pdu_to_tagged_stream, 0), (self.ais_build_frame, 0))
        self.connect((self.ais_build_frame, 0), (self.digital_gmsk_mod, 0))
        self.connect((self.digital_gmsk_mod, 0), (self.blocks_multiply_const, 0))
        self.connect((self.blocks_multiply_const, 0), (self.osmosdr_sink, 0))


class SIRENAISMessageSender:
    """Send AIS messages to GNU Radio via websocket"""
    
    def __init__(self, websocket_port=52002):
        self.websocket_port = websocket_port
        self.websocket_url = f"ws://localhost:{websocket_port}"
        self.ws = None
        self.packets_sent = 0
        
    def connect(self, max_retries=10, retry_delay=0.5):
        """Connect to GNU Radio websocket"""
        if not WEBSOCKET_AVAILABLE:
            raise RuntimeError("websocket-client not available")
        
        for attempt in range(max_retries):
            try:
                self.ws = websocket.create_connection(self.websocket_url, timeout=5)
                print(f"✅ Connected to GNU Radio websocket on port {self.websocket_port}")
                return True
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"🔄 Websocket connection attempt {attempt + 1} failed, retrying...")
                    time.sleep(retry_delay)
                else:
                    print(f"❌ Failed to connect to GNU Radio websocket: {e}")
                    return False
        return False
    
    def send_nmea(self, nmea_sentence: str, ship_name: str = "Unknown") -> bool:
        """Send NMEA sentence to GNU Radio"""
        if not self.ws:
            print("❌ Websocket not connected")
            return False
        
        try:
            # Import payload conversion if SIREN is available
            if SIREN_AVAILABLE:
                from siren.protocol.ais_encoding import payload_to_bitstring, extract_payload_from_nmea
                
                # Extract payload from NMEA sentence
                payload, fill_bits = extract_payload_from_nmea(nmea_sentence)
                if payload is None:
                    print(f"❌ Failed to extract payload from NMEA: {nmea_sentence}")
                    return False
                
                # Convert AIS payload to binary bit string
                bit_string = payload_to_bitstring(payload)
                if not bit_string:
                    print(f"❌ Failed to convert payload to bit string: {payload}")
                    return False
                
                # Send raw binary bit string to GNU Radio (matches ais-simulator)
                self.ws.send(bit_string)
                
                self.packets_sent += 1
                print(f"📡 Transmitted AIS message for {ship_name} (packet #{self.packets_sent})")
                print(f"🔧 NMEA: {nmea_sentence}")
                print(f"🔧 Payload: {payload}")
                print(f"🔧 Bit string ({len(bit_string)} bits): {bit_string[:50]}{'...' if len(bit_string) > 50 else ''}")
                
                return True
            else:
                # Fallback: manual payload extraction (basic implementation)
                parts = nmea_sentence.split(',')
                if len(parts) >= 6:
                    payload = parts[5]
                    
                    # Simple 6-bit ASCII to binary conversion (basic fallback)
                    # Note: This is a simplified version - SIREN has the complete implementation
                    bit_string = ""
                    for char in payload:
                        val = ord(char)
                        if val >= 48 and val < 88:
                            val -= 48
                        elif val >= 96 and val < 128:
                            val -= 56
                        else:
                            continue  # Skip invalid characters
                        
                        # Convert to 6 bits
                        for i in range(5, -1, -1):
                            bit_string += str((val >> i) & 1)
                    
                    # Send raw binary bit string
                    self.ws.send(bit_string)
                    
                    self.packets_sent += 1
                    print(f"📡 Transmitted AIS message for {ship_name} (packet #{self.packets_sent})")
                    print(f"🔧 NMEA: {nmea_sentence}")
                    print(f"🔧 Bit string ({len(bit_string)} bits): {bit_string[:50]}{'...' if len(bit_string) > 50 else ''}")
                    
                    return True
                else:
                    print(f"❌ Invalid NMEA sentence format: {nmea_sentence}")
                    return False
                
        except Exception as e:
            print(f"❌ Failed to send message to GNU Radio: {e}")
            return False
    
    def close(self):
        """Close websocket connection"""
        if self.ws:
            try:
                self.ws.close()
            except:
                pass
            self.ws = None


def create_test_nmea(mmsi: int, lat: float, lon: float, speed: float = 10.0, 
                    course: float = 90.0, heading: int = 90) -> str:
    """Create a test NMEA sentence"""
    if SIREN_AVAILABLE:
        # Use SIREN's AIS ship and protocol
        ship = AISShip(
            name="GNU Radio Test",
            mmsi=mmsi,
            ship_type=70,
            lat=lat,
            lon=lon,
            course=course,
            speed=speed
        )
        ship.heading = heading
        
        ais_fields = ship.get_ais_fields()
        return create_nmea_sentence(ais_fields)
    else:
        # Create a simple NMEA manually (basic implementation)
        # This is a simplified version - real implementation would use proper AIS encoding
        return f"!AIVDM,1,1,,A,15MvlfP000G?n@@K>OW`4?vN0<0=,0*47"


def main():
    """Main function"""
    if not GNURADIO_AVAILABLE:
        print("❌ GNU Radio not available. Cannot start transmitter.")
        return 1
    
    parser = argparse.ArgumentParser(
        description="SIREN GNU Radio AIS Transmitter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic transmission
  python siren_gnuradio_transmitter.py --mmsi 123456789 --lat 39.5 --lon -9.2
  
  # Custom channel and gains
  python siren_gnuradio_transmitter.py --mmsi 123456789 --lat 39.5 --lon -9.2 --channel B --tx-gain 40
  
  # Continuous transmission
  python siren_gnuradio_transmitter.py --mmsi 123456789 --lat 39.5 --lon -9.2 --continuous --interval 10
        """)
    
    parser.add_argument("--mmsi", type=int, required=True,
                       help="MMSI (Maritime Mobile Service Identity)")
    parser.add_argument("--lat", type=float, required=True,
                       help="Latitude in decimal degrees")
    parser.add_argument("--lon", type=float, required=True,
                       help="Longitude in decimal degrees")
    parser.add_argument("--speed", type=float, default=10.0,
                       help="Speed over ground in knots (default: 10.0)")
    parser.add_argument("--course", type=float, default=90.0,
                       help="Course over ground in degrees (default: 90.0)")
    parser.add_argument("--heading", type=int, default=90,
                       help="Heading in degrees (default: 90)")
    
    parser.add_argument("--channel", choices=["A", "B"], default="A",
                       help="AIS channel: A (161.975MHz) or B (162.025MHz)")
    parser.add_argument("--sample-rate", type=int, default=8000000,
                       help="Sample rate in Hz (default: 8MHz)")
    parser.add_argument("--tx-gain", type=int, default=42,
                       help="RF gain in dB (default: 42)")
    parser.add_argument("--bb-gain", type=int, default=30,
                       help="Baseband gain in dB (default: 30)")
    parser.add_argument("--ppm", type=int, default=0,
                       help="Frequency correction in ppm (default: 0)")
    parser.add_argument("--websocket-port", type=int, default=52002,
                       help="Websocket port (default: 52002)")
    
    parser.add_argument("--continuous", action="store_true",
                       help="Continuous transmission mode")
    parser.add_argument("--interval", type=float, default=10.0,
                       help="Transmission interval in seconds (default: 10.0)")
    parser.add_argument("--once", action="store_true",
                       help="Send one message and exit")
    
    args = parser.parse_args()
    
    # Setup signal handler for clean exit
    def signal_handler(signal, frame):
        print("\n🛑 Stopping GNU Radio transmitter...")
        tb.stop()
        tb.wait()
        if 'sender' in locals():
            sender.close()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Create GNU Radio transmitter
        tb = SIRENGnuRadioTransmitter(
            channel=args.channel,
            sample_rate=args.sample_rate,
            bit_rate=9600,
            tx_gain=args.tx_gain,
            bb_gain=args.bb_gain,
            ppm=args.ppm,
            websocket_port=args.websocket_port
        )
        
        # Start GNU Radio flowgraph
        print("🚀 Starting GNU Radio flowgraph...")
        tb.start()
        
        # Wait for GNU Radio to initialize
        time.sleep(2.0)
        
        # Create message sender
        if WEBSOCKET_AVAILABLE:
            sender = SIRENAISMessageSender(args.websocket_port)
            if not sender.connect():
                print("❌ Failed to connect to GNU Radio websocket")
                tb.stop()
                tb.wait()
                return 1
            
            # Create test NMEA message
            nmea = create_test_nmea(args.mmsi, args.lat, args.lon, 
                                  args.speed, args.course, args.heading)
            
            if args.once:
                # Send one message and exit
                success = sender.send_nmea(nmea, "Test Vessel")
                if success:
                    print("✅ Message sent successfully")
                    time.sleep(1.0)  # Allow transmission to complete
                else:
                    print("❌ Failed to send message")
                
            elif args.continuous:
                # Continuous transmission
                print(f"🔄 Starting continuous transmission every {args.interval} seconds")
                print("Press Ctrl+C to stop")
                
                try:
                    while True:
                        success = sender.send_nmea(nmea, "Test Vessel")
                        if not success:
                            print("⚠️  Transmission failed, continuing...")
                        
                        time.sleep(args.interval)
                        
                except KeyboardInterrupt:
                    pass
            else:
                # Default: send one message and wait
                success = sender.send_nmea(nmea, "Test Vessel")
                if success:
                    print("✅ Message sent successfully")
                    print("🔄 GNU Radio flowgraph running - press Ctrl+C to stop")
                    tb.wait()  # Keep running until stopped
                else:
                    print("❌ Failed to send message")
            
            sender.close()
        else:
            print("⚠️  Websocket not available - GNU Radio flowgraph running without control")
            print("🔄 Press Ctrl+C to stop")
            tb.wait()
        
        # Stop GNU Radio
        tb.stop()
        tb.wait()
        print("✅ GNU Radio transmitter stopped")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
