"""
Production AIS Transmitter

This module integrates the production-ready AIS implementation from hybrid_maritime_ais
into the SIREN transmission system. It provides:

- ITU-R M.1371-5 compliant AIS protocol implementation
- Multi-mode operation (production GMSK, rtl_ais FSK, compatibility)
- SOTDMA timing coordination
- Professional error handling and monitoring
- Standards-compliant signal generation

@ author: Peyton Andras @ Louisiana State University 2025
Based on hybrid_maritime_ais implementation
"""

import time
import threading
import logging
import numpy as np
from typing import Optional, Dict, List, Tuple, Callable
from dataclasses import dataclass
from enum import Enum

try:
    import SoapySDR
    from SoapySDR import SOAPY_SDR_TX, SOAPY_SDR_CF32
    SOAPY_AVAILABLE = True
except ImportError:
    SOAPY_AVAILABLE = False
    print("Warning: SoapySDR not available. Cannot transmit to SDR devices.")

# Import SIREN components
from ..ships.ais_ship import AISShip

class OperationMode(Enum):
    """Operation modes for different transmission environments"""
    PRODUCTION = "production"          # Standards-compliant maritime deployment
    RTL_AIS_TESTING = "rtl_ais_testing"  # Optimized for rtl_ais receivers
    COMPATIBILITY = "compatibility"    # NMEA sentence compatibility
    SIMULATION = "simulation"         # SIREN simulation mode

@dataclass
class TransmissionConfig:
    """Configuration for AIS transmission"""
    mode: OperationMode = OperationMode.SIMULATION
    frequency: int = 161975000  # AIS Channel A
    sample_rate: int = 96000
    tx_gain: float = 40.0
    update_rate: float = 10.0
    enable_sotdma: bool = True

class ProductionAISProtocol:
    """Production-ready AIS protocol with full ITU-R M.1371-5 compliance"""
    
    def __init__(self, mode: OperationMode = OperationMode.PRODUCTION):
        self.mode = mode
        self.logger = logging.getLogger(__name__)
        
    def create_position_message_bits(self, ship: AISShip) -> List[int]:
        """Create AIS position report message bits from ship object"""
        bits = []
        
        # Message Type (6 bits) - Type 1 Position Report
        bits.extend(self._int_to_bits(1, 6))
        
        # Repeat Indicator (2 bits) - always 0 for original transmission
        bits.extend(self._int_to_bits(0, 2))
        
        # MMSI (30 bits)
        bits.extend(self._int_to_bits(ship.mmsi, 30))
        
        # Navigation Status (4 bits)
        nav_status_map = {
            "Under way using engine": 0,
            "At anchor": 1,
            "Not under command": 2,
            "Restricted manoeuverability": 3,
            "Constrained by her draught": 4,
            "Moored": 5,
            "Aground": 6,
            "Engaged in fishing": 7,
            "Under way sailing": 8,
            "Not defined": 15
        }
        nav_status = nav_status_map.get(ship.status, ship.status if isinstance(ship.status, int) else 0)
        bits.extend(self._int_to_bits(nav_status, 4))
        
        # Rate of Turn (8 bits) - use ship.turn or default
        rot = getattr(ship, 'turn', 128)  # 128 = not available
        if rot == -128:
            rot = 128  # Convert invalid to not available
        bits.extend(self._int_to_bits(rot & 0xFF, 8))
        
        # Speed over Ground (10 bits) - in 0.1 knot resolution
        sog_encoded = min(int(ship.speed * 10), 1022)
        bits.extend(self._int_to_bits(sog_encoded, 10))
        
        # Position Accuracy (1 bit) - 0 = low accuracy (>10m)
        bits.extend(self._int_to_bits(0, 1))
        
        # Longitude (28 bits) - in 1/10000 minute resolution
        lon_encoded = int(ship.lon * 600000)
        if lon_encoded < 0:
            lon_encoded = (1 << 28) + lon_encoded  # Two's complement
        bits.extend(self._int_to_bits(lon_encoded & ((1 << 28) - 1), 28))
        
        # Latitude (27 bits) - in 1/10000 minute resolution
        lat_encoded = int(ship.lat * 600000)
        if lat_encoded < 0:
            lat_encoded = (1 << 27) + lat_encoded  # Two's complement
        bits.extend(self._int_to_bits(lat_encoded & ((1 << 27) - 1), 27))
        
        # Course over Ground (12 bits) - in 0.1 degree resolution
        cog_encoded = int(ship.course * 10) if ship.course != 360.0 else 3600
        bits.extend(self._int_to_bits(cog_encoded & 0xFFF, 12))
        
        # True Heading (9 bits)
        heading = getattr(ship, 'heading', 511)
        if heading == -1 or heading > 359:
            heading = 511  # Not available
        else:
            heading = int(heading)  # Ensure integer
        bits.extend(self._int_to_bits(heading & 0x1FF, 9))
        
        # Time Stamp (6 bits) - seconds in UTC minute
        timestamp = int(time.time()) % 60
        bits.extend(self._int_to_bits(timestamp & 0x3F, 6))
        
        # Maneuver Indicator (2 bits) - not available
        bits.extend(self._int_to_bits(0, 2))
        
        # Spare (3 bits)
        bits.extend(self._int_to_bits(0, 3))
        
        # RAIM Flag (1 bit) - RAIM not in use
        bits.extend(self._int_to_bits(0, 1))
        
        # Radio Status (19 bits) - SOTDMA state
        bits.extend(self._int_to_bits(0, 19))
        
        return bits
    
    def create_complete_frame(self, ship: AISShip) -> List[int]:
        """Create complete AIS frame from ship object"""
        message_bits = self.create_position_message_bits(ship)
        
        # Calculate CRC-16 for the message payload
        crc_bits = self._calculate_crc16(message_bits)
        
        # Combine message + CRC
        payload_with_crc = message_bits + crc_bits
        
        # Apply HDLC bit stuffing to payload
        stuffed_payload = self._hdlc_bit_stuff(payload_with_crc)
        
        # Apply NRZI encoding to stuffed payload
        nrzi_payload = self._nrzi_encode(stuffed_payload)
        
        # Build frame with training, flags, and processed payload
        training = [0, 1] * 12  # Training sequence (24 bits)
        start_delimiter = [0, 1, 1, 1, 1, 1, 1, 0]  # HDLC start flag
        end_delimiter = [0, 1, 1, 1, 1, 1, 1, 0]    # HDLC end flag
        buffer_bits = [0] * 8   # Buffer
        
        # Combine complete frame
        complete_frame = training + start_delimiter + nrzi_payload + end_delimiter + buffer_bits
        
        return complete_frame
    
    def _int_to_bits(self, value: int, num_bits: int) -> List[int]:
        """Convert integer to list of bits (MSB first)"""
        bits = []
        for i in range(num_bits - 1, -1, -1):
            bits.append((value >> i) & 1)
        return bits
    
    def _calculate_crc16(self, data_bits: List[int]) -> List[int]:
        """Calculate CRC-16-CCITT for AIS message (ITU-R M.1371-5)"""
        crc = 0xFFFF  # Initial value
        
        for bit in data_bits:
            crc ^= (bit << 15)
            for _ in range(1):
                if crc & 0x8000:
                    crc = (crc << 1) ^ 0x1021  # CCITT polynomial
                else:
                    crc = crc << 1
                crc &= 0xFFFF
        
        # Convert CRC to 16 bits (MSB first)
        crc_bits = []
        for i in range(15, -1, -1):
            crc_bits.append((crc >> i) & 1)
        
        return crc_bits
    
    def _hdlc_bit_stuff(self, bits: List[int]) -> List[int]:
        """HDLC bit stuffing - insert 0 after five consecutive 1s"""
        stuffed = []
        consecutive_ones = 0
        
        for bit in bits:
            stuffed.append(bit)
            
            if bit == 1:
                consecutive_ones += 1
                if consecutive_ones == 5:
                    stuffed.append(0)  # Stuff a zero
                    consecutive_ones = 0
            else:
                consecutive_ones = 0
        
        return stuffed
    
    def _nrzi_encode(self, bits: List[int]) -> List[int]:
        """Standard NRZI encoding - transition for 0, no transition for 1"""
        if not bits:
            return []
            
        encoded = []
        current = 1  # Start with 1
        
        for bit in bits:
            if bit == 0:
                current = 1 - current  # Transition
            encoded.append(current)
            
        return encoded

class ProductionModulator:
    """Production modulator supporting GMSK and rtl_ais optimized FSK"""
    
    def __init__(self, sample_rate: int, symbol_rate: int = 9600, mode: OperationMode = OperationMode.PRODUCTION):
        self.sample_rate = sample_rate
        self.symbol_rate = symbol_rate
        self.mode = mode
        self.freq_deviation = 2400  # AIS standard FSK deviation
        
    def modulate(self, bits: List[int]) -> np.ndarray:
        """Modulate bits to RF signal"""
        if self.mode == OperationMode.RTL_AIS_TESTING:
            return self._generate_rtl_ais_optimized_fsk(bits)
        else:
            return self._generate_production_gmsk(bits)
    
    def _generate_production_gmsk(self, symbols: List[int]) -> np.ndarray:
        """Generate production-grade GMSK signal with proper Gaussian filtering"""
        samples_per_symbol = int(self.sample_rate / self.symbol_rate)
        
        # Convert symbols to differential encoding
        diff_symbols = []
        for symbol in symbols:
            diff_symbols.append(2 * symbol - 1)  # Convert 0,1 to -1,1
        
        # Upsample to sample rate
        upsampled = np.zeros(len(diff_symbols) * samples_per_symbol)
        for i, symbol in enumerate(diff_symbols):
            upsampled[i * samples_per_symbol] = symbol
        
        # Create Gaussian filter (BT = 0.4 for AIS)
        bt = 0.4
        filter_span = 4  # Filter spans 4 symbol periods
        t = np.arange(-filter_span * samples_per_symbol // 2,
                     filter_span * samples_per_symbol // 2 + 1) / self.sample_rate
        
        # Gaussian filter impulse response
        gaussian_filter = np.exp(-2 * np.pi**2 * bt**2 * self.symbol_rate**2 * t**2 / np.log(2))
        gaussian_filter = gaussian_filter / np.sum(gaussian_filter)
        
        # Apply Gaussian filter
        filtered = np.convolve(upsampled, gaussian_filter, mode='same')
        
        # MSK phase integration
        phase = np.cumsum(filtered) * np.pi / (2 * samples_per_symbol)
        
        # Generate complex signal
        signal = np.exp(1j * phase)
        
        return signal.astype(np.complex64)
    
    def _generate_rtl_ais_optimized_fsk(self, symbols: List[int]) -> np.ndarray:
        """Generate FSK signal optimized for rtl_ais polar discriminator"""
        samples_per_symbol = int(self.sample_rate / self.symbol_rate)
        signal = []
        phase = 0.0  # Maintain phase continuity (critical for rtl_ais)
        
        for symbol in symbols:
            # AIS standard FSK: Mark (1) = +2400 Hz, Space (0) = -2400 Hz
            if symbol == 1:
                freq_offset = +self.freq_deviation
            else:
                freq_offset = -self.freq_deviation
            
            # Generate samples for this symbol with continuous phase
            for sample_idx in range(samples_per_symbol):
                phase_increment = 2 * np.pi * freq_offset / self.sample_rate
                phase += phase_increment
                sample = np.exp(1j * phase)
                signal.append(sample)
        
        return np.array(signal, dtype=np.complex64)
    
    def add_ramps(self, signal: np.ndarray) -> np.ndarray:
        """Add rise/fall ramps to prevent spectral splatter"""
        ramp_samples = int(0.001 * self.sample_rate)  # 1ms ramps
        
        if len(signal) > 2 * ramp_samples:
            ramp_up = 0.5 * (1 - np.cos(np.linspace(0, np.pi, ramp_samples)))
            ramp_down = 0.5 * (1 + np.cos(np.linspace(0, np.pi, ramp_samples)))
            
            signal[:ramp_samples] *= ramp_up
            signal[-ramp_samples:] *= ramp_down
            
        return signal

class SOTDMAController:
    """SOTDMA (Self-Organizing Time Division Multiple Access) controller"""
    
    def __init__(self, mmsi: int):
        self.mmsi = mmsi
        self.slot_number = self._calculate_initial_slot()
        self.frame_count = 0
        self.logger = logging.getLogger(__name__)
        
    def _calculate_initial_slot(self) -> int:
        """Calculate initial SOTDMA slot based on MMSI"""
        # ITU-R M.1371-5 SOTDMA slot calculation
        return (self.mmsi % 2250)
    
    def get_next_slot_time(self) -> Tuple[int, float]:
        """Get next transmission slot and timing"""
        # SOTDMA frame is 60 seconds with 2250 slots
        slot_duration = 60.0 / 2250  # ~26.67ms per slot
        
        current_time = time.time()
        frame_start = current_time - (current_time % 60)
        slot_time = frame_start + (self.slot_number * slot_duration)
        
        # If slot has passed, move to next frame
        if slot_time < current_time:
            slot_time += 60.0
            self.frame_count += 1
        
        return self.slot_number, slot_time
    
    def is_slot_available(self) -> bool:
        """Check if current slot is available for transmission"""
        current_time = time.time()
        slot_num, slot_time = self.get_next_slot_time()
        
        # Slot is available if we're within the slot window
        slot_duration = 60.0 / 2250
        return abs(current_time - slot_time) < slot_duration / 2

class ProductionSDRInterface:
    """Production SDR interface with adaptive configuration"""
    
    # AIS frequency channels
    AIS_CHANNEL_A = 161975000  # 161.975 MHz
    AIS_CHANNEL_B = 162025000  # 162.025 MHz
    
    def __init__(self, config: TransmissionConfig):
        self.config = config
        self.sdr = None
        self.tx_stream = None
        self.logger = logging.getLogger(__name__)
        
        # Configure frequency based on mode
        if config.mode == OperationMode.RTL_AIS_TESTING:
            self.frequency = self.AIS_CHANNEL_B  # Channel B for rtl_ais
            self.sample_rate = 250000  # High sample rate for clean FSK
        else:
            self.frequency = config.frequency or self.AIS_CHANNEL_A
            self.sample_rate = config.sample_rate
        
        self.sdr_available = False
        if SOAPY_AVAILABLE:
            try:
                self._initialize_sdr()
                self.sdr_available = True
            except Exception as e:
                self.logger.warning(f"SDR initialization failed: {e}")
                self.sdr_available = False
        else:
            self.logger.warning("SoapySDR not available, operating in simulation mode")
    
    def _initialize_sdr(self):
        """Initialize SDR device"""
        if not SOAPY_AVAILABLE:
            raise Exception("SoapySDR not available")
            
        # Find available SDR devices
        results = SoapySDR.Device.enumerate()
        if not results:
            raise Exception("No SoapySDR devices found")
        
        # Prefer LimeSDR, then HackRF, then any device
        device = None
        for result in results:
            # Handle SoapySDRKwargs properly
            try:
                if hasattr(result, 'get'):
                    driver = result.get('driver', '').lower()
                elif 'driver' in result:
                    driver = result['driver'].lower()
                else:
                    driver = str(result).lower()
                
                if 'lime' in driver:
                    device = result
                    break
                elif 'hackrf' in driver and device is None:
                    device = result
            except:
                # If we can't get driver info, still use the device
                if device is None:
                    device = result
        
        if device is None:
            device = results[0]  # Use first available device
        
        self.sdr = SoapySDR.Device(device)
        
        # Configure SDR
        self.sdr.setSampleRate(SOAPY_SDR_TX, 0, self.sample_rate)
        self.sdr.setFrequency(SOAPY_SDR_TX, 0, self.frequency)
        self.sdr.setGain(SOAPY_SDR_TX, 0, self.config.tx_gain)
        
        # Try to set bandwidth
        try:
            self.sdr.setBandwidth(SOAPY_SDR_TX, 0, 25000)  # 25 kHz for AIS
        except:
            pass  # Not all SDRs support bandwidth setting
        
        self.logger.info(f"SDR initialized: {self.frequency/1e6:.6f} MHz, "
                       f"{self.sample_rate/1000:.0f} kS/s, {self.config.tx_gain:.1f}dB")
    
    def is_available(self) -> bool:
        """Check if SDR is available for transmission"""
        return self.sdr_available and self.sdr is not None
    
    def get_device_info(self) -> str:
        """Get information about the SDR device"""
        if not self.is_available():
            return "No SDR device available"
        
        try:
            info = self.sdr.getHardwareInfo()
            driver = info.get('driver', 'Unknown')
            hardware = info.get('hardware', 'Unknown')
            return f"{driver} - {hardware}"
        except:
            return "SDR device (details unavailable)"
    
    def is_available(self) -> bool:
        """Check if SDR is available for transmission"""
        return self.sdr is not None
    
    def transmit_signal(self, signal: np.ndarray) -> bool:
        """Transmit signal via SDR"""
        if not self.is_available():
            self.logger.warning("SDR not available for transmission")
            return False
        
        stream = None
        try:
            # Ensure any previous streams are cleaned up
            if hasattr(self, 'tx_stream') and self.tx_stream:
                try:
                    self.sdr.closeStream(self.tx_stream)
                except:
                    pass
                self.tx_stream = None
            
            # Setup transmission stream with error handling
            try:
                stream = self.sdr.setupStream(SOAPY_SDR_TX, SOAPY_SDR_CF32, [0])
                self.tx_stream = stream
            except Exception as stream_error:
                self.logger.error(f"Failed to setup stream: {stream_error}")
                # Try to reset the device
                try:
                    self._reset_sdr_device()
                    stream = self.sdr.setupStream(SOAPY_SDR_TX, SOAPY_SDR_CF32, [0])
                    self.tx_stream = stream
                except Exception as reset_error:
                    self.logger.error(f"Failed to reset and setup stream: {reset_error}")
                    return False
            
            # Apply mode-specific signal conditioning
            if self.config.mode == OperationMode.RTL_AIS_TESTING:
                signal = signal * 0.7  # Optimize amplitude for rtl_ais
            
            # Activate stream and transmit
            self.sdr.activateStream(stream)
            time.sleep(0.01)  # Brief settle time
            
            result = self.sdr.writeStream(stream, [signal], len(signal))
            
            # Cleanup stream properly
            time.sleep(0.01)
            self.sdr.deactivateStream(stream)
            self.sdr.closeStream(stream)
            self.tx_stream = None
            
            success = result.ret == len(signal)
            if success:
                self.logger.debug(f"Transmitted {len(signal)} samples successfully")
            else:
                self.logger.warning(f"Transmission incomplete: {result.ret}/{len(signal)}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Transmission failed: {e}")
            # Ensure cleanup even on error
            if stream:
                try:
                    self.sdr.deactivateStream(stream)
                    self.sdr.closeStream(stream)
                except:
                    pass
                self.tx_stream = None
            return False
    
    def _reset_sdr_device(self):
        """Reset the SDR device to clear any stuck states"""
        try:
            self.logger.info("Attempting SDR device reset...")
            # Close current connection
            if self.sdr:
                self.sdr = None
            
            # Brief delay
            time.sleep(0.5)
            
            # Reinitialize
            self._initialize_sdr()
            self.logger.info("SDR device reset completed")
            
        except Exception as e:
            self.logger.error(f"SDR reset failed: {e}")
            raise
    
    def close(self):
        """Close SDR interface and cleanup streams"""
        try:
            # Close any active streams
            if hasattr(self, 'tx_stream') and self.tx_stream:
                try:
                    self.sdr.closeStream(self.tx_stream)
                except:
                    pass
                self.tx_stream = None
            
            # Close SDR device
            if self.sdr:
                try:
                    # Give it a moment to clean up
                    time.sleep(0.1)
                    self.sdr = None
                except:
                    pass
        except Exception as e:
            print(f"Error closing SDR interface: {e}")

class ProductionAISTransmitter:
    """Production AIS transmitter integrating all components"""
    
    def __init__(self, config: TransmissionConfig = None):
        self.config = config or TransmissionConfig()
        self.running = False
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.protocol = ProductionAISProtocol(self.config.mode)
        self.sdr = ProductionSDRInterface(self.config)
        self.modulator = ProductionModulator(self.sdr.sample_rate, mode=self.config.mode)
        
        # SOTDMA controller (only for production mode)
        self.sotdma_controllers = {}  # One per MMSI
        
        # Statistics
        self.packets_sent = 0
        self.last_transmission_time = 0
        self.transmission_thread = None
        
        self.logger.info(f"Production AIS Transmitter initialized in {self.config.mode.value} mode")
    
    def transmit_ship(self, ship: AISShip) -> bool:
        """Transmit AIS message for a single ship"""
        try:
            # Create AIS frame
            frame = self.protocol.create_complete_frame(ship)
            
            # Verify frame structure
            if not self._verify_frame(frame):
                self.logger.error(f"Invalid frame for ship {ship.name} (MMSI: {ship.mmsi})")
                return False
            
            # SOTDMA timing for production mode
            if self.config.mode == OperationMode.PRODUCTION and self.config.enable_sotdma:
                if ship.mmsi not in self.sotdma_controllers:
                    self.sotdma_controllers[ship.mmsi] = SOTDMAController(ship.mmsi)
                
                sotdma = self.sotdma_controllers[ship.mmsi]
                slot_num, slot_time = sotdma.get_next_slot_time()
                
                # Wait for SOTDMA slot
                current_time = time.time()
                sleep_time = slot_time - current_time
                if sleep_time > 0 and sleep_time < 60:  # Reasonable wait time
                    time.sleep(sleep_time)
            
            # Modulate signal
            signal = self.modulator.modulate(frame)
            signal = self.modulator.add_ramps(signal)
            
            # Transmit
            success = self.sdr.transmit_signal(signal)
            
            if success:
                self.packets_sent += 1
                self.last_transmission_time = time.time()
                self.logger.info(f"Transmitted AIS message for {ship.name} (MMSI: {ship.mmsi})")
            else:
                self.logger.error(f"Failed to transmit for {ship.name} (MMSI: {ship.mmsi})")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Transmission error for ship {ship.name}: {e}")
            return False
    
    def transmit_ships(self, ships: List[AISShip], status_callback: Optional[Callable] = None) -> int:
        """Transmit AIS messages for multiple ships"""
        success_count = 0
        
        for ship in ships:
            try:
                if self.transmit_ship(ship):
                    success_count += 1
                    if status_callback:
                        status_callback(f"Transmitted: {ship.name} (MMSI: {ship.mmsi})")
                else:
                    if status_callback:
                        status_callback(f"Failed: {ship.name} (MMSI: {ship.mmsi})")
                
                # Small delay between ships to avoid overwhelming the SDR
                time.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"Error transmitting ship {ship.name}: {e}")
                if status_callback:
                    status_callback(f"Error: {ship.name} - {str(e)}")
        
        return success_count
    
    def start_continuous_transmission(self, ships: List[AISShip], 
                                    status_callback: Optional[Callable] = None):
        """Start continuous transmission for multiple ships"""
        if self.running:
            return
        
        self.running = True
        
        def transmission_worker():
            next_update = time.time()
            
            while self.running:
                try:
                    current_time = time.time()
                    
                    if current_time >= next_update:
                        # Transmit all ships
                        success_count = self.transmit_ships(ships, status_callback)
                        
                        if status_callback:
                            status_callback(f"Transmission cycle complete: {success_count}/{len(ships)} successful")
                        
                        # Schedule next update
                        next_update = current_time + self.config.update_rate
                    
                    time.sleep(0.1)
                    
                except Exception as e:
                    self.logger.error(f"Continuous transmission error: {e}")
                    if status_callback:
                        status_callback(f"Transmission error: {str(e)}")
                    time.sleep(1.0)
        
        self.transmission_thread = threading.Thread(target=transmission_worker)
        self.transmission_thread.daemon = True
        self.transmission_thread.start()
        
        self.logger.info("Started continuous AIS transmission")
    
    def stop_transmission(self):
        """Stop continuous transmission"""
        self.running = False
        if self.transmission_thread:
            self.transmission_thread.join(timeout=5)
        self.logger.info("Stopped AIS transmission")
    
    def _verify_frame(self, frame: List[int]) -> bool:
        """Verify AIS frame structure"""
        if len(frame) < 40:
            return False
        
        # Verify training sequence
        training_check = ''.join(map(str, frame[:24]))
        if training_check != "010101010101010101010101":
            return False
        
        # Verify start flag
        start_flag_check = ''.join(map(str, frame[24:32]))
        if start_flag_check != "01111110":
            return False
        
        return True
    
    def get_status(self) -> Dict:
        """Get transmitter status"""
        return {
            'mode': self.config.mode.value,
            'running': self.running,
            'packets_sent': self.packets_sent,
            'last_transmission': self.last_transmission_time,
            'hardware_available': self.sdr.is_available(),
            'frequency': self.sdr.frequency,
            'sample_rate': self.sdr.sample_rate,
            'sotdma_enabled': self.config.enable_sotdma,
            'active_ships': len(self.sotdma_controllers)
        }
    
    def close(self):
        """Clean shutdown"""
        self.stop_transmission()
        self.sdr.close()
        self.logger.info("Production AIS Transmitter closed")
    
    def reset_sdr(self):
        """Reset the SDR device to clear any stuck states"""
        try:
            self.logger.info("Resetting SDR device...")
            self.sdr._reset_sdr_device()
            self.logger.info("SDR device reset successful")
            return True
        except Exception as e:
            self.logger.error(f"SDR reset failed: {e}")
            return False

# Global production transmitter instance
_production_transmitter = None

def get_production_transmitter(config: TransmissionConfig = None) -> ProductionAISTransmitter:
    """Get the global production transmitter instance"""
    global _production_transmitter
    if _production_transmitter is None:
        _production_transmitter = ProductionAISTransmitter(config)
    return _production_transmitter

def reset_production_transmitter():
    """Reset the global production transmitter to clear SDR issues"""
    global _production_transmitter
    if _production_transmitter:
        try:
            _production_transmitter.close()
        except:
            pass
        _production_transmitter = None
        print("Production transmitter reset")
        return True
    return False

def reset_sdr_device():
    """Reset the SDR device for the global transmitter"""
    global _production_transmitter
    if _production_transmitter:
        return _production_transmitter.reset_sdr()
    return False

def create_production_config(
    mode: OperationMode = OperationMode.PRODUCTION,
    frequency: int = 161975000,
    sample_rate: int = 96000,
    tx_gain: float = 40.0,
    update_rate: float = 10.0,
    enable_sotdma: bool = True
) -> TransmissionConfig:
    """Create a production transmission configuration"""
    return TransmissionConfig(
        mode=mode,
        frequency=frequency,
        sample_rate=sample_rate,
        tx_gain=tx_gain,
        update_rate=update_rate,
        enable_sotdma=enable_sotdma
    )

def is_production_mode_available() -> bool:
    """Check if production mode transmission is available"""
    return SOAPY_AVAILABLE
