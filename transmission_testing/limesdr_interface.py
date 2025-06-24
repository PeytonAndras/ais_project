#!/usr/bin/env python3
"""
LimeSDR Interface for AIS Transmission

This module provides a high-level interface to the LimeSDR for AIS transmission.
It handles all the SDR configuration, timing, and transmission details.
"""

import numpy as np
import time
import logging
from typing import Optional, Tuple, List
import threading
import queue

try:
    import SoapySDR
    from SoapySDR import SOAPY_SDR_TX, SOAPY_SDR_CF32
    SOAPY_AVAILABLE = True
except ImportError:
    SOAPY_AVAILABLE = False
    print("Warning: SoapySDR not available. Cannot transmit to LimeSDR.")

class LimeSDRTransmitter:
    """LimeSDR interface for AIS transmission"""
    
    # AIS frequency channels (Hz)
    AIS_CHANNEL_A = 161975000  # 161.975 MHz
    AIS_CHANNEL_B = 162025000  # 162.025 MHz
    
    def __init__(self, sample_rate: int = 96000, tx_gain: float = 40.0,
                 frequency: int = AIS_CHANNEL_A, antenna: str = "BAND2"):
        """
        Initialize LimeSDR transmitter
        
        Args:
            sample_rate: Sample rate in Hz (must be supported by LimeSDR)
            tx_gain: Transmit gain in dB (0-73 dB for LimeSDR)
            frequency: Transmit frequency in Hz (AIS_CHANNEL_A or AIS_CHANNEL_B)
            antenna: Antenna selection ("BAND1", "BAND2" for LimeSDR Mini)
        """
        self.sample_rate = sample_rate
        self.tx_gain = tx_gain
        self.frequency = frequency
        self.antenna = antenna
        
        self.sdr = None
        self.tx_stream = None
        self.is_transmitting = False
        
        # Transmission queue for SOTDMA timing
        self.tx_queue = queue.Queue()
        self.tx_thread = None
        self.stop_event = threading.Event()
        
        # Initialize logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        if not SOAPY_AVAILABLE:
            self.logger.error("SoapySDR not available. Cannot initialize LimeSDR.")
            return
        
        self._initialize_sdr()
    
    def _initialize_sdr(self):
        """Initialize and configure the LimeSDR"""
        try:
            # Find LimeSDR device
            results = SoapySDR.Device.enumerate()
            lime_device = None
            
            self.logger.info(f"Found {len(results)} SoapySDR devices")
            
            for i, device in enumerate(results):
                try:
                    # SoapySDRKwargs objects can be accessed like dictionaries
                    driver = device['driver'] if 'driver' in device else ''
                    name = device['name'] if 'name' in device else ''
                    label = device['label'] if 'label' in device else ''
                    
                    self.logger.info(f"  Device {i}: driver={driver}, name={name}, label={label}")
                    
                    # Check if this is a LimeSDR device
                    if ('lime' in driver.lower() or 
                        'lime' in name.lower() or 
                        'lime' in label.lower()):
                        lime_device = device
                        self.logger.info(f"Selected LimeSDR device: {device}")
                        break
                        
                except Exception as e:
                    self.logger.warning(f"Error accessing device {i}: {e}")
                    continue
            
            if lime_device is None:
                self.logger.error("No LimeSDR devices found")
                return
            
            # Create device
            self.sdr = SoapySDR.Device(lime_device)
            
            # Check available antennas
            available_antennas = self.sdr.listAntennas(SOAPY_SDR_TX, 0)
            self.logger.info(f"Available TX antennas: {available_antennas}")
            
            # Configure transmitter
            self.sdr.setSampleRate(SOAPY_SDR_TX, 0, self.sample_rate)
            self.sdr.setFrequency(SOAPY_SDR_TX, 0, self.frequency)
            self.sdr.setGain(SOAPY_SDR_TX, 0, self.tx_gain)
            
            # Set antenna - try different options for LimeSDR Mini
            try:
                self.sdr.setAntenna(SOAPY_SDR_TX, 0, self.antenna)
                self.logger.info(f"Antenna set to: {self.antenna}")
            except Exception as e:
                self.logger.warning(f"Failed to set antenna {self.antenna}: {e}")
                # Try alternative antenna names for LimeSDR Mini
                for alt_antenna in ["BAND2", "BAND1", "TX_PATH1", "TX_PATH2"]:
                    try:
                        self.sdr.setAntenna(SOAPY_SDR_TX, 0, alt_antenna)
                        self.antenna = alt_antenna
                        self.logger.info(f"Using alternative antenna: {alt_antenna}")
                        break
                    except:
                        continue
                else:
                    self.logger.warning("Could not set any antenna - using default")
            
            # Verify settings
            actual_rate = self.sdr.getSampleRate(SOAPY_SDR_TX, 0)
            actual_freq = self.sdr.getFrequency(SOAPY_SDR_TX, 0)
            actual_gain = self.sdr.getGain(SOAPY_SDR_TX, 0)
            
            self.logger.info(f"Sample rate: {actual_rate} Hz")
            self.logger.info(f"Frequency: {actual_freq/1e6:.6f} MHz")
            self.logger.info(f"TX Gain: {actual_gain} dB")
            
            # Enable and configure the TX path
            self._enable_tx_path()
            
            # Create TX stream
            self.tx_stream = self.sdr.setupStream(SOAPY_SDR_TX, SOAPY_SDR_CF32)
            
            self.logger.info("LimeSDR initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize LimeSDR: {e}")
            self.sdr = None
    
    def _enable_tx_path(self):
        """Enable and configure the TX hardware path"""
        try:
            # Enable the TX RF frontend - this is crucial for actual RF output!
            if hasattr(self.sdr, 'writeRegister'):
                # These are LMS7002M specific register writes to enable TX
                self.logger.info("Enabling TX RF frontend...")
                
                # Enable TX path in LMS7002M chip
                # Register 0x0020 - Enable TXPAD
                try:
                    self.sdr.writeRegister("LMS7002M", 0x0020, 0x0400)
                    self.logger.info("Enabled TXPAD")
                except Exception as e:
                    self.logger.warning(f"Could not write TXPAD register: {e}")
                
                # Register 0x0021 - Configure TX power
                try:
                    self.sdr.writeRegister("LMS7002M", 0x0021, 0x1F1F)  # Max power
                    self.logger.info("Set TX power to maximum")
                except Exception as e:
                    self.logger.warning(f"Could not write TX power register: {e}")
            
            # Try to enable TX using SoapySDR settings
            try:
                # Set frontend mapping - ensure TX channel 0 is mapped correctly
                if hasattr(self.sdr, 'setFrontendMapping'):
                    self.sdr.setFrontendMapping(SOAPY_SDR_TX, "A")
                    self.logger.info("Set TX frontend mapping to A")
            except Exception as e:
                self.logger.warning(f"Could not set frontend mapping: {e}")
            
            # Enable DC correction and IQ balance
            try:
                self.sdr.setDCOffsetMode(SOAPY_SDR_TX, 0, True)
                self.logger.info("Enabled DC offset correction")
            except Exception as e:
                self.logger.warning(f"Could not enable DC offset correction: {e}")
            
            try:
                self.sdr.setIQBalanceMode(SOAPY_SDR_TX, 0, True)
                self.logger.info("Enabled IQ balance correction")
            except Exception as e:
                self.logger.warning(f"Could not enable IQ balance correction: {e}")
            
            # Perform calibration if supported
            try:
                if hasattr(self.sdr, 'getHardwareTime'):
                    # Try to calibrate the TX path
                    result = self.sdr.calibrate(SOAPY_SDR_TX, 0, self.frequency, 10e6)
                    if result == 0:
                        self.logger.info("TX calibration successful")
                    else:
                        self.logger.warning(f"TX calibration returned: {result}")
            except Exception as e:
                self.logger.warning(f"Could not perform TX calibration: {e}")
            
            # Set specific LimeSDR settings
            try:
                # Enable TX LO (Local Oscillator)
                if hasattr(self.sdr, 'writeSetting'):
                    self.sdr.writeSetting("TX_LO_EN", "true")
                    self.logger.info("Enabled TX LO")
                    
                    # Enable TX PA (Power Amplifier)
                    self.sdr.writeSetting("TX_PA_EN", "true")
                    self.logger.info("Enabled TX PA")
                    
                    # Disable mute
                    self.sdr.writeSetting("TX_MUTE", "false")
                    self.logger.info("Disabled TX mute")
                    
            except Exception as e:
                self.logger.warning(f"Could not set LimeSDR-specific settings: {e}")
            
            self.logger.info("TX path configuration completed")
            
        except Exception as e:
            self.logger.error(f"Failed to enable TX path: {e}")
    
    def transmit_signal(self, signal: np.ndarray, timeout: float = 1.0) -> bool:
        """
        Transmit a signal immediately
        
        Args:
            signal: Complex baseband signal to transmit
            timeout: Timeout in seconds
            
        Returns:
            True if transmission successful, False otherwise
        """
        if not self.sdr or not self.tx_stream:
            self.logger.error("LimeSDR not initialized")
            return False
        
        try:
            # Ensure signal is in the right format (complex64)
            if signal.dtype != np.complex64:
                signal = signal.astype(np.complex64)
            
            # Activate stream
            self.sdr.activateStream(self.tx_stream)
            self.logger.info("TX stream activated")
            
            # Add some padding samples to ensure complete transmission
            padding_samples = int(0.001 * self.sample_rate)  # 1ms padding
            padded_signal = np.concatenate([
                np.zeros(padding_samples, dtype=np.complex64),
                signal,
                np.zeros(padding_samples, dtype=np.complex64)
            ])
            
            # Transmit signal in chunks if it's large
            chunk_size = 1024
            total_samples = len(padded_signal)
            transmitted = 0
            
            self.logger.info(f"Starting transmission of {total_samples} samples...")
            
            for i in range(0, total_samples, chunk_size):
                chunk = padded_signal[i:i+chunk_size]
                
                # Transmit chunk
                status = self.sdr.writeStream(self.tx_stream, [chunk], len(chunk), 
                                            timeoutUs=int(timeout * 1e6))
                
                if status.ret < 0:
                    self.logger.error(f"Write stream error: {status.ret}")
                    break
                
                transmitted += status.ret
                
                # Small delay to prevent buffer overrun
                time.sleep(0.001)
            
            # Wait for transmission to complete
            time.sleep(len(signal) / self.sample_rate + 0.1)
            
            # Deactivate stream
            self.sdr.deactivateStream(self.tx_stream)
            self.logger.info("TX stream deactivated")
            
            if transmitted < total_samples:
                self.logger.warning(f"Transmitted {transmitted}/{total_samples} samples")
            else:
                self.logger.info(f"Successfully transmitted {transmitted} samples")
            
            return transmitted > 0
            
        except Exception as e:
            self.logger.error(f"Transmission failed: {e}")
            try:
                self.sdr.deactivateStream(self.tx_stream)
            except:
                pass
            return False
    
    def schedule_transmission(self, signal: np.ndarray, slot_time: float):
        """
        Schedule a transmission for a specific SOTDMA slot
        
        Args:
            signal: Complex baseband signal to transmit
            slot_time: Absolute time when transmission should start (Unix timestamp)
        """
        if not self.tx_thread:
            self._start_tx_thread()
        
        self.tx_queue.put((signal, slot_time))
        self.logger.info(f"Scheduled transmission for {slot_time}")
    
    def _start_tx_thread(self):
        """Start the transmission thread for SOTDMA timing"""
        self.stop_event.clear()
        self.tx_thread = threading.Thread(target=self._tx_worker)
        self.tx_thread.daemon = True
        self.tx_thread.start()
        self.logger.info("Started transmission thread")
    
    def _tx_worker(self):
        """Worker thread for timed transmissions"""
        while not self.stop_event.is_set():
            try:
                # Get next transmission with timeout
                signal, slot_time = self.tx_queue.get(timeout=0.1)
                
                # Wait for transmission time
                current_time = time.time()
                wait_time = slot_time - current_time
                
                if wait_time > 0:
                    time.sleep(wait_time)
                elif wait_time < -0.1:  # More than 100ms late
                    self.logger.warning(f"Transmission late by {-wait_time:.3f}s")
                
                # Transmit
                self.transmit_signal(signal)
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Transmission thread error: {e}")
    
    def set_frequency(self, frequency: int):
        """Change transmission frequency"""
        if self.sdr:
            self.sdr.setFrequency(SOAPY_SDR_TX, 0, frequency)
            self.frequency = frequency
            actual_freq = self.sdr.getFrequency(SOAPY_SDR_TX, 0)
            self.logger.info(f"Frequency changed to: {actual_freq/1e6:.6f} MHz")
    
    def set_gain(self, gain: float):
        """Change transmission gain"""
        if self.sdr:
            self.sdr.setGain(SOAPY_SDR_TX, 0, gain)
            self.tx_gain = gain
            actual_gain = self.sdr.getGain(SOAPY_SDR_TX, 0)
            self.logger.info(f"TX Gain changed to: {actual_gain} dB")
    
    def get_ppm_error(self) -> float:
        """
        Get frequency error in PPM
        This should be calibrated using GPS or known reference
        """
        # TODO: Implement automatic calibration
        # For now, return 0 (assumes perfect crystal)
        return 0.0
    
    def calibrate_frequency(self, reference_freq: float, measured_freq: float):
        """
        Calibrate frequency using a known reference
        
        Args:
            reference_freq: Known reference frequency in Hz
            measured_freq: Measured frequency in Hz
        """
        ppm_error = (measured_freq - reference_freq) / reference_freq * 1e6
        self.logger.info(f"Calculated PPM error: {ppm_error:.2f} ppm")
        
        # Apply correction
        corrected_freq = self.frequency * (1 - ppm_error / 1e6)
        self.set_frequency(int(corrected_freq))
    
    def close(self):
        """Clean up and close the SDR"""
        # Stop transmission thread
        if self.tx_thread:
            self.stop_event.set()
            self.tx_thread.join(timeout=1.0)
        
        # Close SDR
        if self.sdr:
            if self.tx_stream:
                self.sdr.closeStream(self.tx_stream)
            self.sdr = None
        
        self.logger.info("LimeSDR closed")
    
    def __del__(self):
        """Destructor"""
        self.close()
    
    def is_hardware_available(self) -> bool:
        """Check if LimeSDR hardware is available"""
        return self.sdr is not None
    
    def save_signal_to_file(self, signal: np.ndarray, filename: str):
        """Save signal to file instead of transmitting (for testing)"""
        # Save as complex float32
        with open(filename, 'wb') as f:
            interleaved = np.empty(len(signal) * 2, dtype=np.float32)
            interleaved[0::2] = np.real(signal)
            interleaved[1::2] = np.imag(signal)
            interleaved.tofile(f)
        
        self.logger.info(f"Signal saved to {filename} for offline analysis")
        return True
    
    def get_antenna_options(self) -> List[str]:
        """Get available antenna options for this device"""
        if self.sdr:
            try:
                return self.sdr.listAntennas(SOAPY_SDR_TX, 0)
            except:
                return []
        return []

class SOTDMAController:
    """SOTDMA (Self-Organizing Time Division Multiple Access) Controller
    
    Manages slot timing for AIS transmissions according to ITU-R M.1371-5
    """
    
    # SOTDMA timing constants
    FRAME_DURATION = 60.0  # seconds
    SLOTS_PER_FRAME = 2250
    SLOT_DURATION = FRAME_DURATION / SLOTS_PER_FRAME  # ~26.667 ms
    
    def __init__(self, mmsi: int):
        self.mmsi = mmsi
        self.current_slot = 0
        self.slot_increment = self._calculate_slot_increment()
        
        # Initialize to GPS time (simplified - should use actual GPS)
        self.frame_start_time = self._get_frame_start_time()
        
        self.logger = logging.getLogger(__name__)
    
    def _calculate_slot_increment(self) -> int:
        """Calculate slot increment based on MMSI"""
        # Simplified algorithm - real implementation should follow ITU spec
        return (self.mmsi % 1237) + 1
    
    def _get_frame_start_time(self) -> float:
        """Get the start time of the current SOTDMA frame"""
        # Simplified - should be synchronized to GPS time
        current_time = time.time()
        return current_time - (current_time % self.FRAME_DURATION)
    
    def get_next_slot_time(self) -> Tuple[int, float]:
        """
        Get the next transmission slot number and absolute time
        
        Returns:
            Tuple of (slot_number, absolute_time)
        """
        # Calculate next slot
        self.current_slot = (self.current_slot + self.slot_increment) % self.SLOTS_PER_FRAME
        
        # Calculate absolute time
        current_frame_start = self._get_frame_start_time()
        slot_time = current_frame_start + (self.current_slot * self.SLOT_DURATION)
        
        # If slot time is in the past, move to next frame
        if slot_time < time.time():
            current_frame_start += self.FRAME_DURATION
            slot_time = current_frame_start + (self.current_slot * self.SLOT_DURATION)
        
        self.logger.debug(f"Next slot: {self.current_slot} at {slot_time}")
        
        return self.current_slot, slot_time
    
    def reserve_slot(self, slot_number: int) -> float:
        """
        Reserve a specific slot for transmission
        
        Args:
            slot_number: Slot number (0-2249)
            
        Returns:
            Absolute time for the slot
        """
        current_frame_start = self._get_frame_start_time()
        slot_time = current_frame_start + (slot_number * self.SLOT_DURATION)
        
        # If slot time is in the past, move to next frame
        if slot_time < time.time():
            current_frame_start += self.FRAME_DURATION
            slot_time = current_frame_start + (slot_number * self.SLOT_DURATION)
        
        return slot_time

def main():
    """Test the LimeSDR interface"""
    
    if not SOAPY_AVAILABLE:
        print("SoapySDR not available - cannot test LimeSDR interface")
        return
    
    # Create transmitter
    tx = LimeSDRTransmitter(
        sample_rate=96000,
        frequency=LimeSDRTransmitter.AIS_CHANNEL_A,
        tx_gain=30.0  # Low gain for testing
    )
    
    # Create test signal (1 second of 1 kHz sine wave)
    t = np.linspace(0, 1, 96000)
    test_signal = 0.1 * np.exp(1j * 2 * np.pi * 1000 * t)  # 1 kHz complex sine
    
    # Test immediate transmission
    print("Testing immediate transmission...")
    success = tx.transmit_signal(test_signal.astype(np.complex64))
    print(f"Transmission {'succeeded' if success else 'failed'}")
    
    # Test SOTDMA controller
    sotdma = SOTDMAController(mmsi=123456789)
    slot_num, slot_time = sotdma.get_next_slot_time()
    print(f"Next SOTDMA slot: {slot_num} at {time.ctime(slot_time)}")
    
    # Clean up
    tx.close()

if __name__ == "__main__":
    main()
