#!/usr/bin/env python3
"""
AIS Transmitter Application

Complete AIS transmitter that generates compliant AIS messages and transmits
them via LimeSDR. Designed to be compatible with rtl-ais and other AIS receivers.

Usage:
    python ais_transmitter.py --mmsi 123456789 --lat 37.7749 --lon -122.4194
"""

import argparse
import time
import signal
import sys
import threading
import logging
from typing import Optional
import numpy as np

from ais_protocol import AISPositionReport, AISProtocol, GMSKModulator
from limesdr_interface import LimeSDRTransmitter, SOTDMAController

class AISTransmitter:
    """Main AIS transmitter application"""
    
    def __init__(self, mmsi: int, latitude: float, longitude: float,
                 frequency: int = 161975000, sample_rate: int = 96000,
                 tx_gain: float = 30.0, update_rate: float = 10.0):
        """
        Initialize AIS transmitter
        
        Args:
            mmsi: Maritime Mobile Service Identity
            latitude: Latitude in decimal degrees
            longitude: Longitude in decimal degrees  
            frequency: Transmission frequency in Hz
            sample_rate: Sample rate in Hz
            tx_gain: Transmit gain in dB
            update_rate: Position update rate in seconds
        """
        self.mmsi = mmsi
        self.latitude = latitude
        self.longitude = longitude
        self.frequency = frequency
        self.update_rate = update_rate
        
        # Vessel motion parameters (for realistic simulation)
        self.speed_over_ground = 0.0  # knots
        self.course_over_ground = 0.0  # degrees
        self.heading = 511  # degrees (511 = not available)
        self.nav_status = 0  # Under way using engine
        
        # Initialize components
        self.protocol = AISProtocol()
        self.modulator = GMSKModulator(sample_rate=sample_rate, symbol_rate=9600)
        self.sdr = LimeSDRTransmitter(
            sample_rate=sample_rate,
            frequency=frequency,
            tx_gain=tx_gain
        )
        self.sotdma = SOTDMAController(mmsi=mmsi)
        
        # Control flags
        self.running = False
        self.tx_thread = None
        
        # Statistics
        self.packets_sent = 0
        self.last_transmission_time = 0
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        self.logger.info(f"AIS Transmitter initialized for MMSI {mmsi}")
        self.logger.info(f"Position: {latitude:.6f}, {longitude:.6f}")
        self.logger.info(f"Frequency: {frequency/1e6:.6f} MHz")
    
    def update_position(self, latitude: float, longitude: float):
        """Update vessel position"""
        self.latitude = latitude
        self.longitude = longitude
        self.logger.info(f"Position updated: {latitude:.6f}, {longitude:.6f}")
    
    def update_motion(self, sog: float, cog: float, heading: int = 511):
        """Update vessel motion parameters"""
        self.speed_over_ground = sog
        self.course_over_ground = cog
        self.heading = heading
        self.logger.info(f"Motion updated: SOG={sog:.1f}kn, COG={cog:.1f}°, HDG={heading}°")
    
    def set_nav_status(self, status: int):
        """Set navigation status"""
        status_names = {
            0: "Under way using engine",
            1: "At anchor",
            2: "Not under command", 
            3: "Restricted manoeuvrability",
            4: "Constrained by her draught",
            5: "Moored",
            6: "Aground",
            7: "Engaged in fishing",
            8: "Under way sailing",
            15: "Not defined"
        }
        self.nav_status = status
        self.logger.info(f"Navigation status: {status_names.get(status, 'Unknown')}")
    
    def create_position_message(self) -> AISPositionReport:
        """Create AIS position report message"""
        return AISPositionReport(
            mmsi=self.mmsi,
            latitude=self.latitude,
            longitude=self.longitude,
            sog=self.speed_over_ground,
            cog=self.course_over_ground,
            heading=self.heading,
            message_type=1,  # Position Report Class A
            nav_status=self.nav_status
        )
    
    def generate_transmission(self) -> np.ndarray:
        """Generate complete AIS transmission signal"""
        
        # Create message
        message = self.create_position_message()
        
        # Create packet with protocol
        packet_bits = self.protocol.create_packet(message)
        
        # Apply NRZI encoding
        nrzi_bits = self.protocol.nrzi_encode(packet_bits)
        
        # Reset modulator phase for clean transmission
        self.modulator.reset_phase()
        
        # Modulate to RF
        signal = self.modulator.modulate(nrzi_bits)
        
        # Add some padding/ramp-up samples at beginning and end
        ramp_samples = 100
        ramp_up = np.linspace(0, 1, ramp_samples)
        ramp_down = np.linspace(1, 0, ramp_samples)
        
        # Apply ramp to avoid spectral splatter
        signal[:ramp_samples] *= ramp_up
        signal[-ramp_samples:] *= ramp_down
        
        self.logger.debug(f"Generated signal: {len(signal)} samples, {len(packet_bits)} bits")
        
        return signal.astype(np.complex64)
    
    def transmit_once(self) -> bool:
        """Transmit a single AIS message"""
        try:
            # Generate signal
            signal = self.generate_transmission()
            
            # Check if hardware is available
            if not self.sdr.is_hardware_available():
                self.logger.warning("LimeSDR not available - saving signal to file instead")
                filename = f"ais_transmission_{int(time.time())}.cf32"
                success = self.sdr.save_signal_to_file(signal, filename)
                if success:
                    self.logger.info(f"Signal saved to {filename} for analysis")
                    self.packets_sent += 1
                    self.last_transmission_time = time.time()
                return success
            
            # Transmit via hardware
            success = self.sdr.transmit_signal(signal)
            
            if success:
                self.packets_sent += 1
                self.last_transmission_time = time.time()
                self.logger.info(f"Transmitted packet #{self.packets_sent}")
            else:
                self.logger.error("Transmission failed")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error during transmission: {e}")
            return False
    
    def start_continuous_transmission(self):
        """Start continuous transmission with SOTDMA timing"""
        if self.running:
            self.logger.warning("Transmission already running")
            return
        
        self.running = True
        self.tx_thread = threading.Thread(target=self._transmission_worker)
        self.tx_thread.daemon = True
        self.tx_thread.start()
        
        self.logger.info("Started continuous transmission")
    
    def _transmission_worker(self):
        """Worker thread for continuous transmission"""
        next_update_time = time.time()
        
        while self.running:
            try:
                current_time = time.time()
                
                # Check if it's time for next update
                if current_time >= next_update_time:
                    # Get next SOTDMA slot
                    slot_num, slot_time = self.sotdma.get_next_slot_time()
                    
                    # Generate signal
                    signal = self.generate_transmission()
                    
                    # Schedule transmission
                    self.sdr.schedule_transmission(signal, slot_time)
                    
                    # Update statistics
                    self.packets_sent += 1
                    self.last_transmission_time = slot_time
                    
                    self.logger.info(f"Scheduled packet #{self.packets_sent} for slot {slot_num}")
                    
                    # Schedule next update
                    next_update_time = current_time + self.update_rate
                
                # Sleep briefly
                time.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"Transmission worker error: {e}")
                time.sleep(1.0)
    
    def stop_transmission(self):
        """Stop continuous transmission"""
        if not self.running:
            return
        
        self.running = False
        
        if self.tx_thread:
            self.tx_thread.join(timeout=2.0)
        
        self.logger.info("Stopped transmission")
    
    def get_status(self) -> dict:
        """Get transmitter status"""
        return {
            'running': self.running,
            'packets_sent': self.packets_sent,
            'last_transmission': self.last_transmission_time,
            'mmsi': self.mmsi,
            'position': (self.latitude, self.longitude),
            'frequency': self.frequency
        }
    
    def close(self):
        """Clean shutdown"""
        self.stop_transmission()
        self.sdr.close()
        self.logger.info("AIS Transmitter closed")

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    print("\nShutting down AIS transmitter...")
    global transmitter
    if 'transmitter' in globals():
        transmitter.close()
    sys.exit(0)

def main():
    """Main application entry point"""
    parser = argparse.ArgumentParser(description='AIS Transmitter for LimeSDR')
    
    # Required arguments
    parser.add_argument('--mmsi', type=int, required=True,
                       help='Maritime Mobile Service Identity (9 digits)')
    parser.add_argument('--lat', '--latitude', type=float, required=True,
                       help='Latitude in decimal degrees')
    parser.add_argument('--lon', '--longitude', type=float, required=True,
                       help='Longitude in decimal degrees')
    
    # Optional arguments
    parser.add_argument('--freq', '--frequency', type=int, 
                       choices=[161975000, 162025000],
                       default=161975000,
                       help='Transmission frequency (161975000=AIS1, 162025000=AIS2)')
    parser.add_argument('--gain', type=float, default=30.0,
                       help='Transmit gain in dB (0-73)')
    parser.add_argument('--rate', '--update-rate', type=float, default=10.0,
                       help='Position update rate in seconds')
    parser.add_argument('--sog', '--speed', type=float, default=0.0,
                       help='Speed over ground in knots')
    parser.add_argument('--cog', '--course', type=float, default=0.0,
                       help='Course over ground in degrees')
    parser.add_argument('--heading', type=int, default=511,
                       help='True heading in degrees (511=not available)')
    parser.add_argument('--nav-status', type=int, default=0,
                       help='Navigation status (0=under way using engine)')
    parser.add_argument('--once', action='store_true',
                       help='Transmit once and exit')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose logging')
    
    args = parser.parse_args()
    
    # Validate MMSI
    if not (100000000 <= args.mmsi <= 999999999):
        print("Error: MMSI must be 9 digits")
        sys.exit(1)
    
    # Validate coordinates
    if not (-90 <= args.lat <= 90):
        print("Error: Latitude must be between -90 and 90 degrees")
        sys.exit(1)
    if not (-180 <= args.lon <= 180):
        print("Error: Longitude must be between -180 and 180 degrees")
        sys.exit(1)
    
    # Setup logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Install signal handler
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Create transmitter
        global transmitter
        transmitter = AISTransmitter(
            mmsi=args.mmsi,
            latitude=args.lat,
            longitude=args.lon,
            frequency=args.freq,
            tx_gain=args.gain,
            update_rate=args.rate
        )
        
        # Set motion parameters
        transmitter.update_motion(args.sog, args.cog, args.heading)
        transmitter.set_nav_status(args.nav_status)
        
        if args.once:
            # Single transmission
            print("Transmitting single AIS message...")
            success = transmitter.transmit_once()
            if success:
                print("Transmission completed successfully")
            else:
                print("Transmission failed")
                sys.exit(1)
        else:
            # Continuous transmission
            print(f"Starting continuous AIS transmission on {args.freq/1e6:.6f} MHz")
            print(f"MMSI: {args.mmsi}")
            print(f"Position: {args.lat:.6f}, {args.lon:.6f}")
            print(f"Update rate: {args.rate} seconds")
            print("Press Ctrl+C to stop")
            
            transmitter.start_continuous_transmission()
            
            # Keep main thread alive
            try:
                while True:
                    time.sleep(1)
                    status = transmitter.get_status()
                    if status['packets_sent'] > 0:
                        last_tx = time.ctime(status['last_transmission'])
                        print(f"\rPackets sent: {status['packets_sent']}, "
                              f"Last TX: {last_tx}", end='', flush=True)
            except KeyboardInterrupt:
                pass
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        if 'transmitter' in globals():
            transmitter.close()

if __name__ == "__main__":
    main()
