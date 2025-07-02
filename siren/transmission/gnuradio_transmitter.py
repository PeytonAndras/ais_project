"""
GNU Radio AIS Transmitter for SIREN

This module integrates the proven GNU Radio AIS transmission method
into the SIREN system. Based on the working ais-simulator.py that uses
gr-ais_simulator blocks and osmosdr for LimeSDR transmission.

@ author: Peyton Andras @ Louisiana State University 2025
Based on ais-simulator.py (Embyte & Pastus, Mictronics)
"""

import time
import threading
import logging
import queue
import json
import socket
from typing import Optional, Dict, List, Callable
from dataclasses import dataclass
from enum import Enum

try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    websocket = None

try:
    from gnuradio import blocks
    from gnuradio import digital
    from gnuradio import gr, pdu
    from gnuradio import ais_simulator
    import osmosdr
    GNURADIO_AVAILABLE = True
except ImportError as e:
    GNURADIO_AVAILABLE = False
    print(f"Warning: GNU Radio not available: {e}")
    print("Install with: sudo apt-get install gnuradio gr-osmosdr gr-ais")

# Import SIREN components
from ..ships.ais_ship import AISShip
from ..protocol.ais_encoding import create_nmea_sentence

class GnuRadioAISTransmitter:
    """GNU Radio-based AIS transmitter using gr-ais_simulator blocks"""
    
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
            raise RuntimeError("GNU Radio not available. Install gnuradio, gr-osmosdr, and gr-ais.")
        
        if not WEBSOCKET_AVAILABLE:
            raise RuntimeError("WebSocket client not available. Install with: pip install websocket-client")
        
        self.channel = channel
        self.sample_rate = sample_rate
        self.bit_rate = bit_rate
        self.tx_gain = tx_gain
        self.bb_gain = bb_gain
        self.ppm = ppm
        self.websocket_port = websocket_port
        
        # Calculate frequency
        channel_id = 0 if channel == "A" else 1
        self.frequency = 161975000 + 50000 * channel_id
        
        self.logger = logging.getLogger(__name__)
        self.running = False
        self.top_block = None
        self.message_queue = queue.Queue()
        self.packets_sent = 0
        
        # Websocket for sending data to GNU Radio
        self.websocket_url = f"ws://localhost:{websocket_port}"
        self.ws = None
        
        self.logger.info(f"GNU Radio AIS transmitter initialized")
        self.logger.info(f"Channel: {channel} ({self.frequency/1e6:.3f} MHz)")
        self.logger.info(f"Sample rate: {sample_rate/1e6:.1f} MHz")
        
    def _create_top_block(self):
        """Create GNU Radio flowgraph (top block)"""
        
        class AISTopBlock(gr.top_block):
            def __init__(self, channel_id, sample_rate, bit_rate, tx_gain, bb_gain, ppm, ws_port):
                gr.top_block.__init__(self, 'SIREN AIS Transmitter')
                
                # Calculate frequency
                frequency = 161975000 + 50000 * channel_id
                
                # LimeSDR Sink
                self.osmosdr_sink = osmosdr.sink(args="driver=lime,antenna=BAND1")
                self.osmosdr_sink.set_sample_rate(sample_rate)
                self.osmosdr_sink.set_freq_corr(ppm, 0)
                self.osmosdr_sink.set_center_freq(frequency, 0)
                self.osmosdr_sink.set_gain(tx_gain, 0)
                self.osmosdr_sink.set_bb_gain(bb_gain, 0)
                self.osmosdr_sink.set_antenna("BAND1", 0)
                
                # GMSK Modulator
                self.gmsk_mod = digital.gmsk_mod(
                    samples_per_symbol=int(sample_rate / bit_rate),
                    bt=0.4,
                    verbose=False,
                    log=False,
                )
                
                # Websocket PDU source
                self.websocket_pdu = ais_simulator.websocket_pdu("0.0.0.0", str(ws_port))
                
                # PDU to tagged stream converter
                self.pdu_to_stream = pdu.pdu_to_tagged_stream(gr.types.byte_t, 'packet_len')
                
                # Power scaling
                self.multiply_const = blocks.multiply_const_vcc((0.9, ))
                
                # AIS frame builder
                self.ais_frame_builder = ais_simulator.bitstring_to_frame(True, 'packet_len')
                
                # Connect the flowgraph
                self.msg_connect((self.websocket_pdu, 'out'), (self.pdu_to_stream, 'pdus'))
                self.connect((self.pdu_to_stream, 0), (self.ais_frame_builder, 0))
                self.connect((self.ais_frame_builder, 0), (self.gmsk_mod, 0))
                self.connect((self.gmsk_mod, 0), (self.multiply_const, 0))
                self.connect((self.multiply_const, 0), (self.osmosdr_sink, 0))
        
        channel_id = 0 if self.channel == "A" else 1
        return AISTopBlock(channel_id, self.sample_rate, self.bit_rate, 
                          self.tx_gain, self.bb_gain, self.ppm, self.websocket_port)
    
    def start(self):
        """Start the GNU Radio transmitter"""
        if self.running:
            return
        
        try:
            # Create and start GNU Radio flowgraph
            self.top_block = self._create_top_block()
            self.top_block.start()
            
            # Wait a moment for GNU Radio to initialize
            time.sleep(2.0)
            
            # Connect to websocket
            self._connect_websocket()
            
            self.running = True
            self.logger.info("GNU Radio AIS transmitter started")
            
        except Exception as e:
            self.logger.error(f"Failed to start GNU Radio transmitter: {e}")
            if self.top_block:
                self.top_block.stop()
                self.top_block.wait()
            raise
    
    def stop(self):
        """Stop the GNU Radio transmitter"""
        if not self.running:
            return
        
        self.running = False
        
        # Close websocket
        if self.ws:
            try:
                self.ws.close()
            except:
                pass
            self.ws = None
        
        # Stop GNU Radio
        if self.top_block:
            self.top_block.stop()
            self.top_block.wait()
            self.top_block = None
        
        self.logger.info("GNU Radio AIS transmitter stopped")
    
    def _connect_websocket(self):
        """Connect to GNU Radio websocket interface"""
        max_retries = 10
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                self.ws = websocket.create_connection(self.websocket_url, timeout=5)
                self.logger.info(f"Connected to GNU Radio websocket on port {self.websocket_port}")
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    self.logger.debug(f"Websocket connection attempt {attempt + 1} failed, retrying...")
                    time.sleep(retry_delay)
                else:
                    raise RuntimeError(f"Failed to connect to GNU Radio websocket: {e}")
    
    def transmit_ship(self, ship: AISShip) -> bool:
        """Transmit AIS message for a single ship"""
        try:
            # Generate AIS fields from ship
            ais_fields = ship.get_ais_fields()
            
            # Create NMEA sentence using SIREN's protocol module
            nmea_sentence = create_nmea_sentence(ais_fields)
            
            if not nmea_sentence:
                self.logger.error(f"Failed to create NMEA sentence for ship {ship.name}")
                return False
            
            # Send NMEA sentence to GNU Radio via websocket
            return self._send_nmea_to_gnuradio(nmea_sentence, ship.name)
            
        except Exception as e:
            self.logger.error(f"Error transmitting ship {ship.name}: {e}")
            return False
    
    def _send_nmea_to_gnuradio(self, nmea_sentence: str, ship_name: str = "Unknown") -> bool:
        """Send NMEA sentence to GNU Radio via websocket"""
        if not self.ws or not self.running:
            self.logger.error("GNU Radio transmitter not running or websocket not connected")
            return False
        
        try:
            # Import payload conversion function
            from ..protocol.ais_encoding import payload_to_bitstring, extract_payload_from_nmea
            
            # Extract payload from NMEA sentence
            payload, fill_bits = extract_payload_from_nmea(nmea_sentence)
            if payload is None:
                self.logger.error(f"Failed to extract payload from NMEA sentence: {nmea_sentence}")
                return False
            
            # Convert AIS payload to binary bit string
            # This matches what the original ais-simulator web interface sends
            bit_string = payload_to_bitstring(payload)
            if not bit_string:
                self.logger.error(f"Failed to convert payload to bit string: {payload}")
                return False
            
            # Send raw binary bit string to GNU Radio websocket
            # This is what the GNU Radio flowgraph expects (not JSON)
            self.ws.send(bit_string)
            
            self.packets_sent += 1
            self.logger.info(f"Transmitted AIS message for {ship_name} (packet #{self.packets_sent})")
            self.logger.debug(f"NMEA: {nmea_sentence}")
            self.logger.debug(f"Payload: {payload}")
            self.logger.debug(f"Bit string ({len(bit_string)} bits): {bit_string[:50]}{'...' if len(bit_string) > 50 else ''}")
            
            return True
                
        except Exception as e:
            self.logger.error(f"Failed to send message to GNU Radio: {e}")
            # Try to reconnect websocket
            try:
                self._connect_websocket()
            except:
                pass
            return False
    
    def transmit_ships(self, ships: List[AISShip], 
                      status_callback: Optional[Callable] = None) -> int:
        """Transmit AIS messages for multiple ships"""
        if not self.running:
            self.logger.error("Transmitter not started")
            return 0
        
        success_count = 0
        
        for ship in ships:
            try:
                if self.transmit_ship(ship):
                    success_count += 1
                    if status_callback:
                        status_callback(f"✅ Transmitted: {ship.name} (MMSI: {ship.mmsi})")
                else:
                    if status_callback:
                        status_callback(f"❌ Failed: {ship.name} (MMSI: {ship.mmsi})")
                
                # Small delay between ships to avoid overwhelming the system
                time.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"Error transmitting ship {ship.name}: {e}")
                if status_callback:
                    status_callback(f"❌ Error: {ship.name} - {str(e)}")
        
        return success_count
    
    def get_status(self) -> Dict:
        """Get transmitter status"""
        return {
            'running': self.running,
            'packets_sent': self.packets_sent,
            'channel': self.channel,
            'frequency': self.frequency,
            'sample_rate': self.sample_rate,
            'websocket_connected': self.ws is not None,
            'gnuradio_available': GNURADIO_AVAILABLE
        }
    
    def reset(self):
        """Reset transmitter state"""
        was_running = self.running
        if was_running:
            self.stop()
        
        self.packets_sent = 0
        
        if was_running:
            self.start()
    
    @classmethod
    def is_available(cls) -> bool:
        """Check if GNU Radio transmitter is available"""
        return GNURADIO_AVAILABLE and WEBSOCKET_AVAILABLE
    
    @classmethod
    def check_dependencies(cls) -> Dict[str, bool]:
        """Check availability of all dependencies"""
        return {
            'gnuradio': GNURADIO_AVAILABLE,
            'websocket': WEBSOCKET_AVAILABLE,
            'overall': GNURADIO_AVAILABLE and WEBSOCKET_AVAILABLE
        }


class GnuRadioTransmissionController:
    """Controller for continuous GNU Radio AIS transmission"""
    
    def __init__(self, transmitter: GnuRadioAISTransmitter):
        self.transmitter = transmitter
        self.running = False
        self.transmission_thread = None
        self.ships = []
        self.update_rate = 10.0  # seconds
        self.status_callback = None
        self.logger = logging.getLogger(__name__)
    
    def start_continuous_transmission(self, ships: List[AISShip], 
                                    update_rate: float = 10.0,
                                    status_callback: Optional[Callable] = None):
        """Start continuous transmission for multiple ships"""
        if self.running:
            return
        
        self.ships = ships
        self.update_rate = update_rate
        self.status_callback = status_callback
        self.running = True
        
        def transmission_worker():
            next_update = time.time()
            
            while self.running:
                try:
                    current_time = time.time()
                    
                    if current_time >= next_update:
                        # Transmit all ships
                        success_count = self.transmitter.transmit_ships(
                            self.ships, self.status_callback
                        )
                        
                        if self.status_callback:
                            self.status_callback(f"📊 Transmitted {success_count}/{len(self.ships)} ships")
                        
                        # Schedule next update
                        next_update = current_time + self.update_rate
                    
                    time.sleep(0.1)
                    
                except Exception as e:
                    self.logger.error(f"Transmission worker error: {e}")
                    time.sleep(1.0)
        
        self.transmission_thread = threading.Thread(target=transmission_worker, daemon=True)
        self.transmission_thread.start()
        
        self.logger.info(f"Started continuous GNU Radio AIS transmission for {len(ships)} ships")
    
    def stop_transmission(self):
        """Stop continuous transmission"""
        self.running = False
        if self.transmission_thread:
            self.transmission_thread.join(timeout=2.0)
        self.logger.info("Stopped continuous GNU Radio AIS transmission")
    
    def update_ships(self, ships: List[AISShip]):
        """Update the ships being transmitted"""
        self.ships = ships
        self.logger.info(f"Updated transmission fleet to {len(ships)} ships")
    
    def update_rate_setting(self, rate: float):
        """Update transmission rate"""
        self.update_rate = rate
        self.logger.info(f"Updated transmission rate to {rate} seconds")
