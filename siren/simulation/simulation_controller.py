"""
Simulation Controller Module

Handles the ship simulation loop, timing, and coordination between
ship movement and AIS transmission.
"""

import time
import threading
from datetime import datetime
from ..protocol.ais_encoding import build_ais_payload, compute_checksum
from ..transmission.sdr_controller import TransmissionController

class SimulationController:
    """Controls the ship simulation and AIS transmission"""
    
    def __init__(self, ship_manager, transmission_method="SoapySDR"):
        self.ship_manager = ship_manager
        self.transmission_method = transmission_method
        self.transmission_controller = None
        self.gnuradio_controller = None
        self.simulation_active = False
        self.simulation_thread = None
        
        # Initialize the appropriate transmission controller
        self._init_transmission_controller()
        
    def _init_transmission_controller(self):
        """Initialize the appropriate transmission controller based on method"""
        if self.transmission_method == "GNU Radio":
            try:
                from ..transmission.siren_gnuradio_integration import SIRENGnuRadioTransmitter
                self.gnuradio_controller = SIRENGnuRadioTransmitter(use_gnuradio=True)
                print(f"Initialized GNU Radio transmission controller")
            except Exception as e:
                print(f"Failed to initialize GNU Radio controller: {e}")
                # Fallback to SoapySDR
                self.transmission_method = "SoapySDR"
                self.transmission_controller = TransmissionController()
        else:
            # Default to SoapySDR
            self.transmission_controller = TransmissionController()
            
    def set_transmission_method(self, method):
        """Change the transmission method"""
        if method != self.transmission_method:
            self.transmission_method = method
            self._init_transmission_controller()
        
    def start_simulation(self, signal_preset, interval=10, update_status_callback=None, selected_ship_indices=None, transmission_method="SoapySDR"):
        """Start the ship simulation
        
        Args:
            signal_preset: Signal configuration for transmission
            interval: Time between simulation cycles
            update_status_callback: Callback for status updates
            selected_ship_indices: List of ship indices to simulate. If None, simulates all ships.
            transmission_method: Either "GNU Radio" or "SoapySDR"
        """
        if self.simulation_active:
            # Stop current simulation before starting new one
            self.stop_simulation()
            
        # Set transmission method if different
        if transmission_method != self.transmission_method:
            self.set_transmission_method(transmission_method)
            
        self.simulation_active = True
        self.simulation_thread = threading.Thread(
            target=self._run_simulation,
            args=(signal_preset, interval, update_status_callback, selected_ship_indices),
            daemon=True
        )
        self.simulation_thread.start()
        return True
    
    def stop_simulation(self):
        """Stop the ship simulation"""
        self.simulation_active = False
        if self.simulation_thread:
            self.simulation_thread.join(timeout=2.0)
    
    def is_running(self):
        """Check if simulation is running"""
        return self.simulation_active
    
    def _trigger_map_update(self, selected_ship_indices=None):
        """Trigger a map update in a thread-safe manner
        
        Args:
            selected_ship_indices: List of ship indices to display on map
        """
        try:
            # Import here to avoid circular imports
            from ..map.visualization import update_ships_on_map
            update_ships_on_map(selected_ship_indices)
        except Exception as e:
            print(f"Error updating map: {e}")
    
    def _run_simulation(self, signal_preset, interval, update_status_callback, selected_ship_indices=None):
        """Run AIS ship simulation"""
        def update_status(msg):
            print(msg)
            if update_status_callback:
                update_status_callback(msg)
        
        last_move_time = datetime.now()
        
        try:
            update_status("Starting AIS ship simulation...")
            
            while self.simulation_active:
                # Get fresh ship references each cycle to pick up live updates
                if selected_ship_indices:
                    ships = self.ship_manager.get_selected_ships(selected_ship_indices)
                    if not ships:  # No ships to simulate
                        update_status("No ships to simulate")
                        break
                else:
                    ships = self.ship_manager.get_ships()
                    selected_ship_indices = list(range(len(ships)))  # All ships
                    if not ships:  # No ships available
                        update_status("No ships available")
                        break
                
                # Calculate elapsed time
                current_time = datetime.now()
                elapsed = (current_time - last_move_time).total_seconds()
                
                # Move only selected ships
                self.ship_manager.move_all_ships(elapsed, selected_ship_indices)
                
                # Update map after moving ships - show only selected ships
                self._trigger_map_update(selected_ship_indices)
                
                # Transmit AIS message for each selected ship
                for i, ship in enumerate(ships):
                    if not self.simulation_active:
                        break
                        
                    # Create NMEA message
                    fields = ship.get_ais_fields()
                    payload, fill = build_ais_payload(fields)
                    
                    # Alternate channels
                    channel = 'A' if i % 2 == 0 else 'B'
                    sentence = f"AIVDM,1,1,,{channel},{payload},{fill}"
                    cs = compute_checksum(sentence)
                    full_sentence = f"!{sentence}*{cs}"
                    
                    update_status(f"Transmitting ship {i+1}/{len(ships)}: {ship.name} (MMSI: {ship.mmsi}) via {self.transmission_method}")
                    
                    # Transmit using the appropriate controller
                    if self.transmission_method == "GNU Radio" and self.gnuradio_controller:
                        try:
                            success = self.gnuradio_controller.transmit_ship(ship)
                            if not success:
                                update_status(f"GNU Radio transmission failed for {ship.name}")
                        except Exception as e:
                            update_status(f"GNU Radio error for {ship.name}: {e}")
                    else:
                        # Use SoapySDR controller
                        if self.transmission_controller:
                            self.transmission_controller.transmit_signal(signal_preset, full_sentence, update_status)
                    
                    # Delay between ships
                    time.sleep(0.5)
                
                # Save move time
                last_move_time = current_time
                
                # Wait for interval
                for _ in range(int(interval * 10)):
                    if not self.simulation_active:
                        break
                    time.sleep(0.1)
                    
        except Exception as e:
            update_status(f"Simulation error: {e}")
        finally:
            self.simulation_active = False
            update_status("Simulation stopped")

# Global simulation controller instance
_simulation_controller = None
_ship_simulation_active = False

def get_simulation_controller():
    """Get the global simulation controller instance"""
    global _simulation_controller
    if _simulation_controller is None:
        from ..ships.ship_manager import get_ship_manager
        _simulation_controller = SimulationController(get_ship_manager())
    return _simulation_controller

def start_simulation(signal_preset, interval=10, update_status_callback=None, selected_ship_indices=None, transmission_method="SoapySDR"):
    """Start the ship simulation
    
    Args:
        signal_preset: Signal configuration for transmission
        interval: Time between simulation cycles
        update_status_callback: Callback for status updates
        selected_ship_indices: List of ship indices to simulate. If None, simulates all ships.
        transmission_method: Either "GNU Radio" or "SoapySDR"
    """
    global _ship_simulation_active
    controller = get_simulation_controller()
    success = controller.start_simulation(signal_preset, interval, update_status_callback, selected_ship_indices, transmission_method)
    if success:
        _ship_simulation_active = True
    return success

def stop_simulation():
    """Stop the ship simulation"""
    global _ship_simulation_active
    controller = get_simulation_controller()
    controller.stop_simulation()
    _ship_simulation_active = False

def is_simulation_active():
    """Check if simulation is currently active"""
    return _ship_simulation_active
