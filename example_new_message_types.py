#!/usr/bin/env python3
"""
Example script showing how to generate different AIS message types
for the ships defined in ship_configs.json
"""

import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'siren'))

from siren.protocol.ais_encoding import create_nmea_sentence
from siren.ships.ais_ship import AISShip

def load_ship_configs():
    """Load ship configurations from JSON file"""
    with open('ship_configs.json', 'r') as f:
        ship_data = json.load(f)
    return [AISShip.from_dict(data) for data in ship_data]

def generate_messages_for_ship(ship):
    """Generate different message types for a ship"""
    print(f"\n🚢 {ship.name} (MMSI: {ship.mmsi})")
    print("-" * 50)
    
    # Type 1: Position Report
    type1_fields = ship.get_ais_fields()
    nmea1 = create_nmea_sentence(type1_fields)
    print(f"Type 1 (Position): {nmea1}")
    
    # Type 5: Static and Voyage Data
    type5_fields = ship.get_type5_fields()
    nmea5 = create_nmea_sentence(type5_fields)
    print(f"Type 5 (Static/Voyage): {nmea5}")
    
    # Type 18: Class B Position Report (for smaller vessels)
    if ship.ship_type in [30, 37]:  # Fishing vessels and pleasure craft
        type18_fields = ship.get_type18_fields()
        nmea18 = create_nmea_sentence(type18_fields)
        print(f"Type 18 (Class B): {nmea18}")

def generate_base_station_example():
    """Generate a Type 4 base station report example"""
    print(f"\n🏗️ Base Station Example")
    print("-" * 50)
    
    fields = {
        'msg_type': 4,
        'repeat': 0,
        'mmsi': 2000001,  # Base station MMSI format
        'year': 2025,
        'month': 6,
        'day': 24,
        'hour': 12,
        'minute': 0,
        'second': 0,
        'accuracy': 1,
        'lon': -9.20,  # Near our ship area
        'lat': 39.55,
        'epfd_type': 1,
        'raim': 0,
        'radio_status': 0
    }
    
    nmea4 = create_nmea_sentence(fields)
    print(f"Type 4 (Base Station): {nmea4}")

def generate_aid_to_navigation_example():
    """Generate a Type 21 aid-to-navigation report example"""
    print(f"\n🔆 Aid-to-Navigation Example")
    print("-" * 50)
    
    fields = {
        'msg_type': 21,
        'repeat': 0,
        'mmsi': 992123456,  # Aid-to-navigation MMSI format
        'aid_type': 5,      # Light without sectors
        'name': 'CASCAIS LIGHTHOUSE',
        'accuracy': 1,
        'lon': -9.4204,    # Cascais lighthouse coordinates
        'lat': 38.6917,
        'dim_to_bow': 15,
        'dim_to_stern': 15,
        'dim_to_port': 10,
        'dim_to_starboard': 10,
        'epfd_type': 1,
        'timestamp': 60,
        'off_position': 0,
        'aton_status': 0,
        'raim': 0,
        'virtual_aid': 0,
        'assigned': 0
    }
    
    nmea21 = create_nmea_sentence(fields)
    print(f"Type 21 (Aid-to-Nav): {nmea21}")

if __name__ == "__main__":
    print("🌊 AIS Message Generation Examples")
    print("Using ships from ship_configs.json")
    print("=" * 60)
    
    try:
        ships = load_ship_configs()
        
        # Generate messages for each ship
        for ship in ships[:3]:  # Show first 3 ships to avoid cluttering
            generate_messages_for_ship(ship)
        
        # Generate infrastructure examples
        generate_base_station_example()
        generate_aid_to_navigation_example()
        
        print(f"\n=" * 60)
        print("📡 All message types generated successfully!")
        print("\nMessage Type Summary:")
        print("• Type 1: Real-time position updates")
        print("• Type 4: Base station time/position reference")  
        print("• Type 5: Ship static data and voyage information")
        print("• Type 18: Class B transponder position reports")
        print("• Type 21: Navigation aids (lighthouses, buoys, etc.)")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
