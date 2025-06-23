#!/usr/bin/env python3
"""
Configuration and Utilities for AIS Transmitter

This module provides configuration management, calibration utilities,
and helper functions for the AIS transmitter system.
"""

import json
import time
import math
import numpy as np
from typing import Dict, Any, Tuple, Optional
import logging

class AISConfig:
    """Configuration management for AIS transmitter"""
    
    DEFAULT_CONFIG = {
        # RF Parameters
        'sample_rate': 96000,
        'frequency_a': 161975000,  # AIS Channel A
        'frequency_b': 162025000,  # AIS Channel B
        'tx_gain': 30.0,
        'antenna': 'LNAW',
        
        # Protocol Parameters
        'symbol_rate': 9600,
        'bt_factor': 0.4,
        'samples_per_symbol': 10,
        
        # Timing Parameters
        'update_rate': 10.0,        # Position update rate in seconds
        'frame_duration': 60.0,     # SOTDMA frame duration
        'slots_per_frame': 2250,
        
        # Calibration
        'frequency_offset': 0.0,    # PPM correction
        'time_offset': 0.0,         # Time offset in seconds
        
        # Vessel Parameters
        'mmsi': 123456789,
        'vessel_name': 'TEST_VESSEL',
        'call_sign': 'TEST',
        'vessel_type': 37,          # Pleasure craft
        'dimensions': [10, 5, 2, 2], # to bow, stern, port, starboard
        
        # Position
        'latitude': 37.7749,
        'longitude': -122.4194,
        'speed_over_ground': 0.0,
        'course_over_ground': 0.0,
        'heading': 511,             # Not available
        'nav_status': 0,            # Under way using engine
        
        # Safety
        'max_power': 50.0,          # Maximum TX power in dB
        'enable_safety_limits': True,
        'require_gps_sync': False,
        
        # Logging
        'log_level': 'INFO',
        'log_file': None,
    }
    
    def __init__(self, config_file: Optional[str] = None):
        self.config = self.DEFAULT_CONFIG.copy()
        self.config_file = config_file
        
        if config_file:
            self.load_from_file(config_file)
    
    def load_from_file(self, filename: str):
        """Load configuration from JSON file"""
        try:
            with open(filename, 'r') as f:
                file_config = json.load(f)
            
            # Update config with file values
            self.config.update(file_config)
            logging.info(f"Loaded configuration from {filename}")
            
        except FileNotFoundError:
            logging.warning(f"Config file {filename} not found, using defaults")
        except json.JSONDecodeError as e:
            logging.error(f"Error parsing config file {filename}: {e}")
    
    def save_to_file(self, filename: str):
        """Save configuration to JSON file"""
        try:
            with open(filename, 'w') as f:
                json.dump(self.config, f, indent=2)
            logging.info(f"Saved configuration to {filename}")
        except Exception as e:
            logging.error(f"Error saving config to {filename}: {e}")
    
    def get(self, key: str, default=None):
        """Get configuration value"""
        return self.config.get(key, default)
    
    def set(self, key: str, value):
        """Set configuration value"""
        self.config[key] = value
        
        # Auto-save if config file specified
        if self.config_file:
            self.save_to_file(self.config_file)
    
    def validate(self) -> bool:
        """Validate configuration values"""
        errors = []
        
        # Validate MMSI
        mmsi = self.get('mmsi')
        if not (100000000 <= mmsi <= 999999999):
            errors.append(f"Invalid MMSI: {mmsi}")
        
        # Validate coordinates
        lat = self.get('latitude')
        lon = self.get('longitude')
        if not (-90 <= lat <= 90):
            errors.append(f"Invalid latitude: {lat}")
        if not (-180 <= lon <= 180):
            errors.append(f"Invalid longitude: {lon}")
        
        # Validate frequencies
        freq_a = self.get('frequency_a')
        freq_b = self.get('frequency_b')
        if freq_a not in [161975000, 162025000]:
            errors.append(f"Invalid frequency A: {freq_a}")
        if freq_b not in [161975000, 162025000]:
            errors.append(f"Invalid frequency B: {freq_b}")
        
        # Validate sample rate
        sample_rate = self.get('sample_rate')
        symbol_rate = self.get('symbol_rate')
        if sample_rate % symbol_rate != 0:
            errors.append(f"Sample rate {sample_rate} not compatible with symbol rate {symbol_rate}")
        
        if errors:
            for error in errors:
                logging.error(error)
            return False
        
        return True

class GPSSimulator:
    """GPS time and position simulator for testing"""
    
    def __init__(self, start_lat: float, start_lon: float):
        self.start_lat = start_lat
        self.start_lon = start_lon
        self.start_time = time.time()
        
        # Simulate movement
        self.speed = 0.0  # knots
        self.course = 0.0  # degrees
        
    def set_motion(self, speed: float, course: float):
        """Set simulated vessel motion"""
        self.speed = speed
        self.course = course
    
    def get_position(self) -> Tuple[float, float]:
        """Get current simulated position"""
        if self.speed == 0:
            return self.start_lat, self.start_lon
        
        # Calculate movement
        elapsed_time = time.time() - self.start_time
        distance_nm = (self.speed * elapsed_time) / 3600.0  # nautical miles
        
        # Convert to lat/lon offset
        lat_offset = distance_nm * math.cos(math.radians(self.course)) / 60.0
        lon_offset = distance_nm * math.sin(math.radians(self.course)) / (60.0 * math.cos(math.radians(self.start_lat)))
        
        return self.start_lat + lat_offset, self.start_lon + lon_offset
    
    def get_gps_time(self) -> float:
        """Get GPS time (simplified - just UTC)"""
        return time.time()

class FrequencyCalibrator:
    """Frequency calibration utilities"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def measure_frequency_error(self, reference_freq: float, measured_freq: float) -> float:
        """Calculate frequency error in PPM"""
        ppm_error = (measured_freq - reference_freq) / reference_freq * 1e6
        return ppm_error
    
    def generate_calibration_tone(self, frequency: float, duration: float, 
                                sample_rate: int = 96000) -> np.ndarray:
        """Generate calibration tone for frequency measurement"""
        t = np.linspace(0, duration, int(sample_rate * duration))
        tone = 0.5 * np.exp(1j * 2 * np.pi * frequency * t)
        return tone.astype(np.complex64)
    
    def estimate_ppm_from_ais_signals(self, known_frequency: float, 
                                    measured_frequency: float) -> float:
        """Estimate PPM error from AIS signal measurements"""
        ppm_error = self.measure_frequency_error(known_frequency, measured_frequency)
        self.logger.info(f"Estimated PPM error: {ppm_error:.2f} ppm")
        return ppm_error

class SignalAnalyzer:
    """Signal analysis utilities"""
    
    @staticmethod
    def calculate_power_db(signal: np.ndarray) -> float:
        """Calculate signal power in dB"""
        power_linear = np.mean(np.abs(signal)**2)
        if power_linear > 0:
            return 10 * np.log10(power_linear)
        else:
            return -np.inf
    
    @staticmethod
    def calculate_peak_to_average_ratio(signal: np.ndarray) -> float:
        """Calculate peak-to-average power ratio"""
        avg_power = np.mean(np.abs(signal)**2)
        peak_power = np.max(np.abs(signal)**2)
        if avg_power > 0:
            return 10 * np.log10(peak_power / avg_power)
        else:
            return np.inf
    
    @staticmethod
    def measure_frequency_spectrum(signal: np.ndarray, sample_rate: int) -> Tuple[np.ndarray, np.ndarray]:
        """Calculate frequency spectrum"""
        fft_data = np.fft.fftshift(np.fft.fft(signal))
        frequencies = np.fft.fftshift(np.fft.fftfreq(len(signal), 1/sample_rate))
        return frequencies, 20 * np.log10(np.abs(fft_data) + 1e-12)
    
    @staticmethod
    def find_spectral_peak(signal: np.ndarray, sample_rate: int) -> float:
        """Find frequency of spectral peak"""
        frequencies, spectrum = SignalAnalyzer.measure_frequency_spectrum(signal, sample_rate)
        peak_idx = np.argmax(spectrum)
        return frequencies[peak_idx]

class PacketLogger:
    """Log AIS packets for analysis"""
    
    def __init__(self, log_file: Optional[str] = None):
        self.log_file = log_file
        self.packet_count = 0
        self.logger = logging.getLogger(__name__)
    
    def log_packet(self, packet_data: dict):
        """Log packet transmission details"""
        self.packet_count += 1
        
        log_entry = {
            'packet_id': self.packet_count,
            'timestamp': time.time(),
            'human_time': time.ctime(),
            **packet_data
        }
        
        if self.log_file:
            try:
                with open(self.log_file, 'a') as f:
                    f.write(json.dumps(log_entry) + '\n')
            except Exception as e:
                self.logger.error(f"Error writing to log file: {e}")
        
        self.logger.info(f"Packet #{self.packet_count}: MMSI={packet_data.get('mmsi')}")

class SOTDMASlotCalculator:
    """Advanced SOTDMA slot calculation"""
    
    def __init__(self, mmsi: int):
        self.mmsi = mmsi
        self.slot_increment = self._calculate_slot_increment()
        self.nominal_increment = self._calculate_nominal_increment()
    
    def _calculate_slot_increment(self) -> int:
        """Calculate slot increment based on MMSI (simplified)"""
        # Real implementation should follow ITU-R M.1371-5 Annex 2
        return (self.mmsi % 1237) + 1
    
    def _calculate_nominal_increment(self) -> int:
        """Calculate nominal increment for reporting rate"""
        # Simplified - should be based on vessel type and speed
        return 750  # Default for Class A vessels
    
    def get_reporting_interval(self, speed_knots: float, nav_status: int) -> float:
        """Get reporting interval based on speed and status"""
        
        # ITU-R M.1371-5 Table 5
        if nav_status in [1, 5]:  # At anchor or moored
            return 180.0  # 3 minutes
        elif nav_status == 6:  # Aground
            return 180.0  # 3 minutes
        elif speed_knots == 0:
            return 180.0  # 3 minutes when not moving
        elif speed_knots <= 2:
            return 10.0   # 10 seconds
        elif speed_knots <= 14:
            return 10.0   # 10 seconds
        elif speed_knots <= 20:
            return 6.0    # 6 seconds
        elif speed_knots <= 23:
            return 3.33   # 2 seconds
        else:
            return 2.0    # 2 seconds
    
    def calculate_next_slot(self, current_slot: int, speed: float, nav_status: int) -> int:
        """Calculate next transmission slot"""
        # Simplified algorithm
        increment = self.slot_increment
        
        # Adjust based on reporting rate
        interval = self.get_reporting_interval(speed, nav_status)
        slots_per_interval = int(interval / (60.0 / 2250))  # Convert to slots
        
        if slots_per_interval < increment:
            increment = slots_per_interval
        
        return (current_slot + increment) % 2250

def create_default_config_file(filename: str = "ais_config.json"):
    """Create a default configuration file"""
    config = AISConfig()
    config.save_to_file(filename)
    print(f"Created default configuration file: {filename}")

def main():
    """Utilities main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='AIS Transmitter Utilities')
    parser.add_argument('--create-config', metavar='FILE',
                       help='Create default configuration file')
    parser.add_argument('--validate-config', metavar='FILE',
                       help='Validate configuration file')
    parser.add_argument('--calibration-tone', nargs=3, metavar=('FREQ', 'DURATION', 'FILE'),
                       help='Generate calibration tone (freq_hz duration_sec output_file)')
    
    args = parser.parse_args()
    
    if args.create_config:
        create_default_config_file(args.create_config)
    
    elif args.validate_config:
        config = AISConfig(args.validate_config)
        if config.validate():
            print("Configuration is valid")
        else:
            print("Configuration has errors")
            exit(1)
    
    elif args.calibration_tone:
        freq, duration, filename = args.calibration_tone
        calibrator = FrequencyCalibrator()
        tone = calibrator.generate_calibration_tone(float(freq), float(duration))
        
        # Save as raw complex float32
        with open(filename, 'wb') as f:
            raw_data = np.empty(len(tone) * 2, dtype=np.float32)
            raw_data[0::2] = np.real(tone)
            raw_data[1::2] = np.imag(tone)
            raw_data.tofile(f)
        
        print(f"Generated {float(duration)}s calibration tone at {float(freq)}Hz: {filename}")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
