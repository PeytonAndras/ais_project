"""
Ship Manager Module

Handles ship configuration management, loading/saving ships,
and ship fleet operations.
"""

import json
import os
from .ais_ship import AISShip, create_sample_ships

# Global ship manager instance
_ship_manager = None
_ship_listbox_callback = None

class ShipManager:
    """Manages a fleet of AIS ships"""
    
    def __init__(self):
        self.ships = []
        self.config_file = "ship_configs.json"
        
    def load_ships(self):
        """Load ship configurations from file"""
        try:
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", self.config_file)
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    ship_data = json.load(f)
                    self.ships = [AISShip.from_dict(data) for data in ship_data]
                    return True
        except Exception as e:
            print(f"Error loading ship configurations: {e}")
        
        # Create sample ships if none loaded
        if not self.ships:
            self.ships = create_sample_ships()
        return False
    
    def save_ships(self):
        """Save ship configurations to file"""
        try:
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", self.config_file)
            with open(config_path, 'w') as f:
                json.dump([ship.to_dict() for ship in self.ships], f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving ship configurations: {e}")
            return False
    
    def add_ship(self, ship):
        """Add a ship to the fleet"""
        self.ships.append(ship)
        self.save_ships()
        self._notify_update()
    
    def remove_ship(self, index):
        """Remove a ship by index"""
        if 0 <= index < len(self.ships):
            del self.ships[index]
            self.save_ships()
            self._notify_update()
    
    def remove_ship_by_index(self, index):
        """Remove a ship by index (alias for remove_ship)"""
        return self.remove_ship(index)
    
    def update_ship(self, index, ship):
        """Update a ship at given index"""
        if 0 <= index < len(self.ships):
            self.ships[index] = ship
            self.save_ships()
            self._notify_update()
    
    def get_ships(self):
        """Get all ships"""
        return self.ships
    
    def get_ship(self, index):
        """Get a ship by index"""
        if 0 <= index < len(self.ships):
            return self.ships[index]
        return None
    
    def move_all_ships(self, elapsed_seconds, selected_indices=None):
        """Move ships based on elapsed time
        
        Args:
            elapsed_seconds: Time elapsed since last update
            selected_indices: List of ship indices to move. If None, moves all ships.
        """
        if selected_indices is None:
            # Move all ships if no selection specified
            for ship in self.ships:
                ship.move(elapsed_seconds)
        else:
            # Only move selected ships
            for index in selected_indices:
                if 0 <= index < len(self.ships):
                    self.ships[index].move(elapsed_seconds)
    
    def get_selected_ships(self, selected_indices):
        """Get only the selected ships for transmission
        
        Args:
            selected_indices: List of ship indices to get
            
        Returns:
            List of selected ship objects
        """
        if not selected_indices:
            return []
        
        selected_ships = []
        for index in selected_indices:
            if 0 <= index < len(self.ships):
                selected_ships.append(self.ships[index])
        return selected_ships
    
    def _notify_update(self):
        """Notify UI of ship updates"""
        if _ship_listbox_callback:
            _ship_listbox_callback(self.ships)

def get_ship_manager():
    """Get the global ship manager instance"""
    global _ship_manager
    if _ship_manager is None:
        _ship_manager = ShipManager()
        _ship_manager.load_ships()
    return _ship_manager

def get_ship_configs():
    """Get all ship configurations"""
    return get_ship_manager().get_ships()

def save_ship_configs():
    """Save ship configurations"""
    return get_ship_manager().save_ships()

def add_ship_config(ship):
    """Add a ship configuration"""
    get_ship_manager().add_ship(ship)

def remove_ship_config(index):
    """Remove a ship configuration by index"""
    get_ship_manager().remove_ship(index)

def update_ship_config(index, ship):
    """Update a ship configuration"""
    get_ship_manager().update_ship(index, ship)

def update_ship_listbox_callback(callback):
    """Set the callback for ship listbox updates"""
    global _ship_listbox_callback
    _ship_listbox_callback = callback
