"""
Simulation Controller Module

Handles the ship simulation loop, timing, and coordination between
ship movement and AIS transmission. Enhanced with production-ready transmission.
"""

import time
import threading
from datetime import datetime
from ..protocol.ais_encoding import build_ais_payload, compute_checksum
from ..transmission.sdr_controller import (
    TransmissionController, 
    transmit_ships_production,
    start_continuous_transmission,
    stop_continuous_transmission,
    get_transmission_status,
    OperationMode
)

class SimulationController:
    """Controls the ship simulation and AIS transmission with production capabilities"""
    
    def __init__(self, ship_manager):
        self.ship_manager = ship_manager
        self.transmission_controller = TransmissionController()
        self.simulation_active = False
        self.simulation_thread = None
        self.use_production_transmission = True  # Default to production mode
        self.continuous_transmission = False
        
    def set_production_transmission(self, enabled: bool):
        """Enable or disable production transmission mode"""
        self.use_production_transmission = enabled
        self.transmission_controller.set_production_mode(enabled)
        
    def start_simulation(self, signal_preset, interval=10, update_status_callback=None, selected_ship_indices=None, continuous=False):
        """Start the ship simulation
        
        Args:
            signal_preset: Signal configuration for transmission
            interval: Time between simulation cycles
            update_status_callback: Callback for status updates
            selected_ship_indices: List of ship indices to simulate. If None, simulates all ships.
            continuous: If True, use continuous production transmission mode
        """
        if self.simulation_active:
            return False
            
        self.simulation_active = True
        self.continuous_transmission = continuous
        
        # If continuous mode and production transmission, start continuous transmission
        if continuous and self.use_production_transmission:
            ships = self.ship_manager.get_selected_ships(selected_ship_indices) if selected_ship_indices else self.ship_manager.get_ships()
            mode = self._get_operation_mode_from_preset(signal_preset)
            
            success = start_continuous_transmission(
                ships, 
                update_rate=interval,
                status_callback=update_status_callback,
                mode=mode,
                frequency=int(signal_preset.get('freq', 161975000)),
                tx_gain=signal_preset.get('gain', 40)
            )
            
            if not success:
                self.simulation_active = False
                return False
        
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
        
        # Stop continuous transmission if active
        if self.continuous_transmission:
            stop_continuous_transmission()
            
        if self.simulation_thread:
            self.simulation_thread.join(timeout=2.0)
    
    def get_transmission_status(self):
        """Get current transmission status"""
        return get_transmission_status()
    
    def _get_operation_mode_from_preset(self, signal_preset):
        """Convert signal preset to operation mode"""
        preset_mode = signal_preset.get('mode', 'production')
        
        mode_map = {
            'production': OperationMode.PRODUCTION,
            'rtl_ais_testing': OperationMode.RTL_AIS_TESTING,
            'compatibility': OperationMode.COMPATIBILITY,
            'legacy': OperationMode.SIMULATION
        }
        
        return mode_map.get(preset_mode, OperationMode.PRODUCTION)
    
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
            
            # Get ships to simulate
            if selected_ship_indices:
                ships = self.ship_manager.get_selected_ships(selected_ship_indices)
                update_status(f"Simulating {len(ships)} selected ships")
            else:
                ships = self.ship_manager.get_ships()
                selected_ship_indices = list(range(len(ships)))  # All ships
                update_status(f"Simulating all {len(ships)} ships")
            
            while self.simulation_active and ships:
                # Calculate elapsed time
                current_time = datetime.now()
                elapsed = (current_time - last_move_time).total_seconds()
                
                # Move only selected ships
                self.ship_manager.move_all_ships(elapsed, selected_ship_indices)
                
                # Update map after moving ships - show only selected ships
                self._trigger_map_update(selected_ship_indices)
                
                # Transmission handling
                if self.continuous_transmission and self.use_production_transmission:
                    # Continuous mode - transmission is handled automatically
                    # Just update status occasionally
                    if int(current_time.timestamp()) % 30 == 0:  # Every 30 seconds
                        status = get_transmission_status()
                        update_status(f"Continuous transmission: {status['packets_sent']} packets sent")
                else:
                    # Manual transmission mode
                    self._transmit_ships_manual(ships, signal_preset, update_status)
                
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
    
    def _transmit_ships_manual(self, ships, signal_preset, update_status):
        """Transmit ships manually using either production or legacy mode"""
        if self.use_production_transmission:
            # Use production transmitter for batch transmission
            try:
                mode = self._get_operation_mode_from_preset(signal_preset)
                success_count = transmit_ships_production(
                    ships, 
                    status_callback=update_status,
                    mode=mode,
                    frequency=int(signal_preset.get('freq', 161975000)),
                    tx_gain=signal_preset.get('gain', 40)
                )
                if success_count > 0:
                    update_status(f"Production transmission: {success_count}/{len(ships)} ships transmitted")
            except Exception as e:
                update_status(f"Production transmission error: {e}")
        else:
            # Use legacy transmission method
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

def start_simulation(signal_preset, interval=10, update_status_callback=None, selected_ship_indices=None, continuous=False):
    """Start the ship simulation with production or legacy transmission
    
    Args:
        signal_preset: Signal configuration for transmission
        interval: Time between simulation cycles
        update_status_callback: Callback for status updates
        selected_ship_indices: List of ship indices to simulate. If None, simulates all ships.
        continuous: If True, use continuous production transmission mode
    """
    global _ship_simulation_active
    controller = get_simulation_controller()
    success = controller.start_simulation(signal_preset, interval, update_status_callback, selected_ship_indices, continuous)
    if success:
        _ship_simulation_active = True
    return success

def set_production_transmission(enabled: bool):
    """Enable or disable production transmission mode"""
    controller = get_simulation_controller()
    controller.set_production_transmission(enabled)

def get_simulation_transmission_status():
    """Get transmission status from simulation controller"""
    controller = get_simulation_controller()
    return controller.get_transmission_status()

def stop_simulation():
    """Stop the ship simulation"""
    global _ship_simulation_active
    controller = get_simulation_controller()
    controller.stop_simulation()
    _ship_simulation_active = False

def is_simulation_active():
    """Check if simulation is currently active"""
    return _ship_simulation_active
