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
    
    def __init__(self, ship_manager):
        self.ship_manager = ship_manager
        self.transmission_controller = TransmissionController()
        self.simulation_active = False
        self.simulation_thread = None
        
    def start_simulation(self, signal_preset, interval=10, update_status_callback=None):
        """Start the ship simulation"""
        if self.simulation_active:
            return False
            
        self.simulation_active = True
        self.simulation_thread = threading.Thread(
            target=self._run_simulation,
            args=(signal_preset, interval, update_status_callback),
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
    
    def _run_simulation(self, signal_preset, interval, update_status_callback):
        """Run AIS ship simulation"""
        def update_status(msg):
            print(msg)
            if update_status_callback:
                update_status_callback(msg)
        
        last_move_time = datetime.now()
        
        try:
            update_status("Starting AIS ship simulation...")
            ships = self.ship_manager.get_ships()
            
            while self.simulation_active and ships:
                # Calculate elapsed time
                current_time = datetime.now()
                elapsed = (current_time - last_move_time).total_seconds()
                
                # Move all ships
                self.ship_manager.move_all_ships(elapsed)
                
                # Transmit AIS message for each ship
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
                    
                    update_status(f"Transmitting ship {i+1}/{len(ships)}: {ship.name} (MMSI: {ship.mmsi})")
                    
                    # Transmit
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

def start_simulation(signal_preset, interval=10, update_status_callback=None):
    """Start the ship simulation"""
    global _ship_simulation_active
    controller = get_simulation_controller()
    success = controller.start_simulation(signal_preset, interval, update_status_callback)
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
