"""
Transmission Module

Handles SDR transmission using HackRF, LimeSDR, and other SoapySDR devices.
Contains transmission logic and device management from the original implementation.
"""

import time
import numpy as np
from ..signal.modulation import create_ais_signal
from ..protocol.ais_encoding import char_to_sixbit

try:
    import SoapySDR
    SOAPY_SDR_TX = getattr(SoapySDR, "SOAPY_SDR_TX", "TX")
    SOAPY_SDR_CF32 = getattr(SoapySDR, "SOAPY_SDR_CF32", "CF32")
    SDR_AVAILABLE = True
except ImportError:
    SDR_AVAILABLE = False

class TransmissionController:
    """Controls SDR transmission operations"""
    
    def __init__(self):
        self.sdr = None
        self.tx_stream = None
        
    def is_available(self):
        """Check if SDR transmission is available"""
        return SDR_AVAILABLE
    
    def transmit_signal(self, signal_preset, nmea_sentence=None, status_callback=None):
        """Transmit a signal using HackRF or LimeSDR"""
        if not SDR_AVAILABLE:
            message = "SoapySDR not available. Install with: pip install soapysdr"
            if status_callback:
                status_callback(message)
            return False
        
        def update_status(msg):
            print(msg)
            if status_callback:
                status_callback(msg)
        
        try:
            # Add detailed logging of the exact message being transmitted
            if nmea_sentence:
                update_status("=" * 50)
                update_status(f"TRANSMITTING EXACT SENTENCE: {nmea_sentence}")
                
                # Log binary representation too
                if "AIVDM" in nmea_sentence:
                    parts = nmea_sentence.split(',')
                    if len(parts) >= 6:
                        payload = parts[5]
                        update_status(f"Payload: {payload}")
                        
                        # Show each character and its 6-bit representation
                        bits_log = "Bit representation: "
                        for char in payload:
                            try:
                                bits = char_to_sixbit(char)
                                bits_log += f"[{char}:{bits}] "
                            except ValueError as e:
                                bits_log += f"[{char}:ERROR] "
                        update_status(bits_log)
                update_status("=" * 50)
            
            update_status(f"Preparing to transmit {signal_preset['name']}...")
            
            # Find SDR devices
            devices = self._find_sdr_devices(update_status)
            if not devices:
                raise RuntimeError("No SDR devices found")
            
            # Initialize the SDR
            self.sdr = self._initialize_sdr(devices[0], update_status)
            
            # Configure SDR parameters
            self._configure_sdr(signal_preset, update_status)
            
            # Create signal for transmission
            if signal_preset["modulation"] == "GMSK" and nmea_sentence:
                signal = create_ais_signal(nmea_sentence, 2e6)
                update_status("Created AIS signal with GMSK modulation")
            else:
                update_status("Error: No valid signal to transmit")
                return False
            
            # Debug signal stats
            print(f"Signal stats: min={np.min(np.abs(signal)):.3f}, max={np.max(np.abs(signal)):.3f}, len={len(signal)}")
            
            # Setup transmission stream
            update_status("Setting up transmission stream...")
            self.tx_stream = self.sdr.setupStream(SOAPY_SDR_TX, SOAPY_SDR_CF32, [0])
            self.sdr.activateStream(self.tx_stream)
            
            # Transmit
            update_status("Transmitting signal...")
            status = self.sdr.writeStream(self.tx_stream, [signal], len(signal))
            update_status(f"Transmission status: {status}")
            
            # Cleanup
            self._cleanup_transmission(update_status)
            
            update_status(f"Successfully transmitted on {signal_preset['freq']/1e6} MHz")
            return True
            
        except Exception as e:
            error_msg = f"Transmission Error: {str(e)}"
            update_status(error_msg)
            
            recovery_msg = """
Try these recovery steps:
1. Unplug the SDR and wait 10 seconds
2. Plug it back into a different USB port
3. Run these commands in the terminal:
   hackrf_info
   hackrf_transfer -R   (This resets the device)

If problems persist, try restarting your computer.
"""
            update_status(recovery_msg)
            return False
    
    def _find_sdr_devices(self, update_status):
        """Find available SDR devices"""
        devices = []
        try:
            # Try HackRF
            hackrf_devices = SoapySDR.Device.enumerate({'driver': 'hackrf'})
            if hackrf_devices:
                devices = hackrf_devices
                update_status(f"Found {len(hackrf_devices)} HackRF device(s)")
            
            # Try LimeSDR if no HackRF
            if not devices:
                lime_devices = SoapySDR.Device.enumerate({'driver': 'lime'})
                if lime_devices:
                    devices = lime_devices
                    update_status(f"Found {len(lime_devices)} LimeSDR device(s)")
            
            # Try generic enumeration
            if not devices:
                devices = SoapySDR.Device.enumerate()
                update_status(f"Found {len(devices)} generic SDR device(s)")
                
        except Exception as e:
            update_status(f"Error finding SDR: {str(e)}")
            
        return devices
    
    def _initialize_sdr(self, device_info, update_status):
        """Initialize SDR device"""
        try:
            try:
                sdr = SoapySDR.Device(device_info)
            except AttributeError:
                # Fall back to makeDevice for older versions
                sdr = SoapySDR.makeDevice(device_info)
            update_status("SDR initialized successfully")
            return sdr
        except Exception as e:
            update_status(f"Failed to initialize SDR: {str(e)}")
            # Try generic driver
            try:
                sdr = SoapySDR.Device({'driver': 'hackrf'})
            except AttributeError:
                sdr = SoapySDR.makeDevice({'driver': 'hackrf'})
            update_status("SDR initialized with generic driver")
            return sdr
    
    def _configure_sdr(self, signal_preset, update_status):
        """Configure SDR parameters"""
        center_freq = signal_preset["freq"]
        sample_rate = 2e6
        tx_gain = signal_preset["gain"]
        
        update_status(f"Configuring: {center_freq/1e6} MHz, Gain: {tx_gain} dB...")
        
        # Set basic parameters
        self.sdr.setSampleRate(SOAPY_SDR_TX, 0, sample_rate)
        self.sdr.setFrequency(SOAPY_SDR_TX, 0, center_freq)
        
        # Set gain - handle different SDR types
        try:
            gain_names = self.sdr.listGains(SOAPY_SDR_TX, 0)
            print(f"Available gain elements: {gain_names}")
            
            # Try individual gain elements
            if 'AMP' in gain_names:
                amp_value = 14 if tx_gain > 30 else 0
                self.sdr.setGain(SOAPY_SDR_TX, 0, 'AMP', amp_value)
                print(f"Set AMP gain to {amp_value}")
                
            if 'VGA' in gain_names:
                vga_value = min(47, max(0, tx_gain))
                self.sdr.setGain(SOAPY_SDR_TX, 0, 'VGA', vga_value)
                print(f"Set VGA gain to {vga_value}")
                
        except Exception as e:
            # Fallback to overall gain
            print(f"Could not set individual gains: {e}")
            self.sdr.setGain(SOAPY_SDR_TX, 0, tx_gain)
            print(f"Set overall gain to {tx_gain}")
        
        # Try setting bandwidth if supported
        try:
            self.sdr.setBandwidth(SOAPY_SDR_TX, 0, 1.75e6)
        except Exception as bw_e:
            update_status(f"Note: Cannot set bandwidth ({str(bw_e)})")
    
    def _cleanup_transmission(self, update_status):
        """Clean up after transmission"""
        update_status("Cleaning up...")
        time.sleep(1.0)  # Allow time to finish
        
        if self.tx_stream:
            self.sdr.deactivateStream(self.tx_stream)
            self.sdr.closeStream(self.tx_stream)
            self.tx_stream = None
        
        # Force Python garbage collection
        if self.sdr:
            del self.sdr
            self.sdr = None
        time.sleep(0.5)

# Signal configuration presets
SIGNAL_PRESETS = [
    {"name": "AIS Channel A", "freq": 161.975e6, "gain": 70, "modulation": "GMSK", "sdr_type": "hackrf"},
    {"name": "AIS Channel B", "freq": 162.025e6, "gain": 65, "modulation": "GMSK", "sdr_type": "hackrf"},
]

# Global transmission controller instance
_transmission_controller = None

def get_transmission_controller():
    """Get the global transmission controller instance"""
    global _transmission_controller
    if _transmission_controller is None:
        _transmission_controller = TransmissionController()
    return _transmission_controller

def get_signal_presets():
    """Get available signal presets"""
    return SIGNAL_PRESETS

def transmit_signal(signal_preset, nmea_sentence=None, status_callback=None):
    """Global function to transmit a signal"""
    controller = get_transmission_controller()
    return controller.transmit_signal(signal_preset, nmea_sentence, status_callback)

def is_sdr_available():
    """Check if SDR support is available"""
    return SDR_AVAILABLE
