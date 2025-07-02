"""
SIREN GNU Radio Integration

This module integrates the GNU Radio AIS transmitter into the main SIREN system,
providing a working transmission method based on the proven ais-simulator.py approach.

@ author: Peyton Andras @ Louisiana State University 2025
"""

import logging
import time
from typing import Optional, List, Callable, Dict, Any

from .gnuradio_transmitter import GnuRadioAISTransmitter, GnuRadioTransmissionController
from .production_transmitter import ProductionAISTransmitter, TransmissionConfig, OperationMode
from ..ships.ais_ship import AISShip


class SIRENGnuRadioTransmitter:
    """
    Main SIREN transmitter with GNU Radio integration
    
    This class provides a unified interface that can use either:
    1. GNU Radio method (proven working with ais-simulator)
    2. Original SoapySDR method (fallback)
    """
    
    def __init__(self, use_gnuradio: bool = True, **kwargs):
        """Initialize SIREN transmitter with GNU Radio integration
        
        Args:
            use_gnuradio: If True, use GNU Radio method. If False, use SoapySDR
            **kwargs: Configuration parameters
        """
        self.logger = logging.getLogger(__name__)
        self.use_gnuradio = use_gnuradio
        
        # GNU Radio configuration
        self.channel = kwargs.get('channel', 'A')
        self.sample_rate = kwargs.get('sample_rate', 8000000)  # 8 MHz for GNU Radio
        self.bit_rate = kwargs.get('bit_rate', 9600)
        self.tx_gain = kwargs.get('tx_gain', 42)
        self.bb_gain = kwargs.get('bb_gain', 30)
        self.ppm = kwargs.get('ppm', 0)
        self.websocket_port = kwargs.get('websocket_port', 52002)
        
        # Initialize transmitters
        self.gnuradio_tx = None
        self.soapy_tx = None
        self.controller = None
        
        if self.use_gnuradio:
            self._init_gnuradio()
        else:
            self._init_soapy()
        
        self.running = False
        self.packets_sent = 0
        
    def _init_gnuradio(self):
        """Initialize GNU Radio transmitter"""
        try:
            self.gnuradio_tx = GnuRadioAISTransmitter(
                channel=self.channel,
                sample_rate=self.sample_rate,
                bit_rate=self.bit_rate,
                tx_gain=self.tx_gain,
                bb_gain=self.bb_gain,
                ppm=self.ppm,
                websocket_port=self.websocket_port
            )
            self.controller = GnuRadioTransmissionController(self.gnuradio_tx)
            self.logger.info("GNU Radio transmitter initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize GNU Radio transmitter: {e}")
            self.logger.info("Falling back to SoapySDR transmitter")
            self.use_gnuradio = False
            self._init_soapy()
    
    def _init_soapy(self):
        """Initialize SoapySDR transmitter (fallback)"""
        try:
            config = TransmissionConfig(
                mode=OperationMode.PRODUCTION,
                frequency=161975000 if self.channel == 'A' else 162025000,
                sample_rate=96000,  # Different sample rate for SoapySDR
                tx_gain=float(self.tx_gain),
                update_rate=10.0
            )
            self.soapy_tx = ProductionAISTransmitter(config)
            self.logger.info("SoapySDR transmitter initialized as fallback")
        except Exception as e:
            self.logger.error(f"Failed to initialize SoapySDR transmitter: {e}")
            raise RuntimeError("No transmitter method available")
    
    def start(self):
        """Start the transmitter"""
        if self.running:
            return
        
        try:
            if self.use_gnuradio and self.gnuradio_tx:
                self.gnuradio_tx.start()
                self.logger.info("GNU Radio transmitter started")
            elif self.soapy_tx:
                # SoapySDR doesn't need explicit start
                self.logger.info("SoapySDR transmitter ready")
            
            self.running = True
            
        except Exception as e:
            self.logger.error(f"Failed to start transmitter: {e}")
            raise
    
    def stop(self):
        """Stop the transmitter"""
        if not self.running:
            return
        
        self.running = False
        
        # Stop continuous transmission
        if self.controller:
            self.controller.stop_transmission()
        
        # Stop transmitters
        if self.use_gnuradio and self.gnuradio_tx:
            self.gnuradio_tx.stop()
            self.logger.info("GNU Radio transmitter stopped")
        
        # SoapySDR transmitter doesn't need explicit stop
        
    def transmit_ship(self, ship: AISShip) -> bool:
        """Transmit AIS message for a single ship"""
        if not self.running:
            self.logger.error("Transmitter not started")
            return False
        
        try:
            if self.use_gnuradio and self.gnuradio_tx:
                success = self.gnuradio_tx.transmit_ship(ship)
            elif self.soapy_tx:
                success = self.soapy_tx.transmit_ship(ship)
            else:
                self.logger.error("No transmitter available")
                return False
            
            if success:
                self.packets_sent += 1
                
            return success
            
        except Exception as e:
            self.logger.error(f"Error transmitting ship {ship.name}: {e}")
            return False
    
    def transmit_ships(self, ships: List[AISShip], 
                      status_callback: Optional[Callable] = None) -> int:
        """Transmit AIS messages for multiple ships"""
        if not self.running:
            self.logger.error("Transmitter not started")
            return 0
        
        try:
            if self.use_gnuradio and self.gnuradio_tx:
                count = self.gnuradio_tx.transmit_ships(ships, status_callback)
            elif self.soapy_tx:
                count = self.soapy_tx.transmit_ships(ships, status_callback)
            else:
                self.logger.error("No transmitter available")
                return 0
            
            self.packets_sent += count
            return count
            
        except Exception as e:
            self.logger.error(f"Error transmitting ships: {e}")
            return 0
    
    def start_continuous_transmission(self, ships: List[AISShip], 
                                    update_rate: float = 10.0,
                                    status_callback: Optional[Callable] = None):
        """Start continuous transmission for multiple ships"""
        if not self.running:
            self.logger.error("Transmitter not started")
            return
        
        try:
            if self.use_gnuradio and self.controller:
                self.controller.start_continuous_transmission(
                    ships, update_rate, status_callback
                )
                self.logger.info(f"Started continuous GNU Radio transmission for {len(ships)} ships")
            elif self.soapy_tx:
                self.soapy_tx.start_continuous_transmission(ships, status_callback)
                self.logger.info(f"Started continuous SoapySDR transmission for {len(ships)} ships")
            else:
                self.logger.error("No transmitter available for continuous transmission")
                
        except Exception as e:
            self.logger.error(f"Failed to start continuous transmission: {e}")
    
    def stop_continuous_transmission(self):
        """Stop continuous transmission"""
        try:
            if self.use_gnuradio and self.controller:
                self.controller.stop_transmission()
            elif self.soapy_tx:
                self.soapy_tx.stop_transmission()
                
            self.logger.info("Stopped continuous transmission")
            
        except Exception as e:
            self.logger.error(f"Error stopping continuous transmission: {e}")
    
    def update_ships(self, ships: List[AISShip]):
        """Update the ships being transmitted"""
        try:
            if self.use_gnuradio and self.controller:
                self.controller.update_ships(ships)
            # SoapySDR transmitter updates ships automatically
            
        except Exception as e:
            self.logger.error(f"Error updating ships: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get transmitter status"""
        base_status = {
            'running': self.running,
            'packets_sent': self.packets_sent,
            'method': 'GNU Radio' if self.use_gnuradio else 'SoapySDR',
            'channel': self.channel
        }
        
        if self.use_gnuradio and self.gnuradio_tx:
            gnuradio_status = self.gnuradio_tx.get_status()
            base_status.update(gnuradio_status)
        elif self.soapy_tx:
            soapy_status = self.soapy_tx.get_status()
            base_status.update(soapy_status)
        
        return base_status
    
    def reset(self):
        """Reset transmitter state"""
        try:
            was_running = self.running
            
            if was_running:
                self.stop()
            
            self.packets_sent = 0
            
            if self.use_gnuradio and self.gnuradio_tx:
                self.gnuradio_tx.reset()
            elif self.soapy_tx:
                self.soapy_tx.reset_sdr()
            
            if was_running:
                self.start()
                
        except Exception as e:
            self.logger.error(f"Error resetting transmitter: {e}")
    
    def is_available(self) -> bool:
        """Check if transmitter is available"""
        if self.use_gnuradio and self.gnuradio_tx:
            return self.gnuradio_tx.is_available()
        elif self.soapy_tx:
            return True  # Assume SoapySDR is available if initialized
        return False


def create_siren_transmitter(prefer_gnuradio: bool = True, **kwargs) -> SIRENGnuRadioTransmitter:
    """
    Factory function to create the best available SIREN transmitter
    
    Args:
        prefer_gnuradio: If True, try GNU Radio first, then fall back to SoapySDR
        **kwargs: Configuration parameters
    
    Returns:
        SIRENGnuRadioTransmitter instance
    """
    return SIRENGnuRadioTransmitter(use_gnuradio=prefer_gnuradio, **kwargs)


# Example usage and testing
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO, 
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Create test ship
    from ..ships.ais_ship import AISShip
    
    test_ship = AISShip(
        name="GNU Radio Test Vessel",
        mmsi=123456789,
        ship_type=70,
        lat=39.5,
        lon=-9.2,
        course=90,
        speed=10
    )
    
    # Test GNU Radio transmitter
    try:
        tx = create_siren_transmitter(prefer_gnuradio=True, channel='A')
        tx.start()
        
        print("Transmitting test message...")
        success = tx.transmit_ship(test_ship)
        print(f"Transmission {'successful' if success else 'failed'}")
        
        print("Status:", tx.get_status())
        
        tx.stop()
        print("Test completed")
        
    except Exception as e:
        print(f"Test failed: {e}")
