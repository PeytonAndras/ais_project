#!/usr/bin/env python3
"""
Simple test script to check if the ship dialog buttons are working
"""

import tkinter as tk
from tkinter import ttk
import sys
import os

# Add the project root to the path
sys.path.insert(0, '/Users/peytonandras/Projects/nato_navy')

try:
    from siren.ships.ais_ship import AISShip
    from siren.ui.ship_dialogs import ShipDialog
    
    def test_dialog():
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        
        # Create a test ship
        test_ship = AISShip(
            name="Test Ship",
            mmsi=123456789,
            ship_type=70,
            lat=40.0,
            lon=-74.0,
            speed=10,
            course=90
        )
        
        # Test with simulation context
        simulation_context = {
            'is_simulating': True,
            'is_ship_in_simulation': True,
            'ship_index': 0,
            'update_callback': lambda idx, ship: print(f"Update callback called for ship {idx}: {ship.name}")
        }
        
        print("Creating dialog with simulation context...")
        dialog = ShipDialog(root, "Test Edit Dialog", ship=test_ship, simulation_context=simulation_context)
        
        root.mainloop()
    
    if __name__ == "__main__":
        test_dialog()
        
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running from the correct directory")
