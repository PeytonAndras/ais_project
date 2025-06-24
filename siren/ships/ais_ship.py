"""
Ship Simulation Module

Contains the AISShip class and related navigation utilities.
Handles ship movement, waypoint navigation, and AIS field generation.
"""

import math
from datetime import datetime
from ..utils.navigation import haversine, calculate_initial_compass_bearing

class AISShip:
    """Class representing a simulated AIS ship with position and movement"""
    
    def __init__(self, name, mmsi, ship_type, length=30, beam=10, 
                lat=40.7128, lon=-74.0060, course=90, speed=8, 
                status=0, turn=0, destination=""):
        self.name = name
        self.mmsi = mmsi
        self.ship_type = ship_type
        self.length = length
        self.beam = beam
        self.lat = lat
        self.lon = lon
        self.course = course  # degrees
        self.speed = speed    # knots
        self.status = status  # navigation status
        self.turn = turn      # rate of turn
        self.destination = destination
        self.accuracy = 1     # position accuracy (1=high)
        self.heading = course # heading initially matches course
        
        # New attributes for waypoint navigation
        self.waypoints = []  # List of (lat, lon) tuples
        self.current_waypoint = -1  # Index of current target waypoint
        self.waypoint_radius = 0.01  # ~1km radius to consider waypoint reached
    
    def move(self, elapsed_seconds):
        """Move the ship based on speed and course"""
        if self.speed <= 0:
            return
            
        # Convert speed to position change
        lat_factor = math.cos(math.radians(self.lat))
        hours = elapsed_seconds / 3600
        distance_nm = self.speed * hours
        
        # Calculate position change
        dy = distance_nm * math.cos(math.radians(self.course)) / 60
        dx = distance_nm * math.sin(math.radians(self.course)) / (60 * lat_factor)
        
        # Update position
        self.lat += dy
        self.lon += dx
        
        # Apply turn rate
        if self.turn != 0:
            rot_deg_min = self.turn / 4.0
            course_change = rot_deg_min * (elapsed_seconds / 60.0)
            self.course = (self.course + course_change) % 360
            self.heading = round(self.course)
        
        # Check waypoint navigation
        self.check_waypoint_reached()
    
    def check_waypoint_reached(self):
        """Check and handle reaching of waypoints"""
        if self.current_waypoint == -1 or self.current_waypoint >= len(self.waypoints):
            return  # No valid waypoint to check
        
        target_wp = self.waypoints[self.current_waypoint]
        distance_to_wp = haversine(self.lat, self.lon, target_wp[0], target_wp[1])
        
        # Convert waypoint_radius from degrees to kilometers (rough approximation)
        radius_km = self.waypoint_radius * 111.0  # 1 degree ≈ 111 km
        
        if distance_to_wp <= radius_km:
            # Waypoint reached
            print(f"Waypoint {self.current_waypoint+1} reached: {target_wp}")
            self.current_waypoint += 1  # Move to next waypoint
            
            if self.current_waypoint < len(self.waypoints):
                # Set course to next waypoint
                next_wp = self.waypoints[self.current_waypoint]
                self.course = calculate_initial_compass_bearing((self.lat, self.lon), next_wp)
                print(f"Course set to next waypoint {self.current_waypoint+1}: {self.course}°")
            else:
                print("All waypoints reached")
    
    def get_ais_fields(self):
        """Get fields for AIS message construction"""
        timestamp = datetime.now().second % 60
        
        return {
            'msg_type': 1,
            'repeat': 0,
            'mmsi': self.mmsi,
            'nav_status': self.status,
            'rot': self.turn,
            'sog': self.speed,
            'accuracy': self.accuracy,
            'lon': self.lon,
            'lat': self.lat,
            'cog': self.course,
            'hdg': self.heading,
            'timestamp': timestamp
        }
        
    def to_dict(self):
        """Convert to dictionary for serialization"""
        return self.__dict__
    
    @classmethod
    def from_dict(cls, data):
        """Create ship from dictionary"""
        ship = cls(
            name=data.get('name', 'Unknown'),
            mmsi=data.get('mmsi', 0),
            ship_type=data.get('ship_type', 0),
            length=data.get('length', 30),
            beam=data.get('beam', 10),
            lat=data.get('lat', 0),
            lon=data.get('lon', 0),
            course=data.get('course', 0),
            speed=data.get('speed', 0),
            status=data.get('status', 0),
            turn=data.get('turn', 0),
            destination=data.get('destination', '')
        )
        ship.accuracy = data.get('accuracy', 1)
        ship.heading = data.get('heading', ship.course)
        ship.waypoints = data.get('waypoints', [])
        ship.current_waypoint = data.get('current_waypoint', -1)
        ship.waypoint_radius = data.get('waypoint_radius', 0.01)
        
        # If ship has waypoints and current_waypoint is valid, set course to first waypoint
        if ship.waypoints and 0 <= ship.current_waypoint < len(ship.waypoints):
            target_wp = ship.waypoints[ship.current_waypoint]
            ship.course = calculate_initial_compass_bearing((ship.lat, ship.lon), target_wp)
            ship.heading = round(ship.course)
        
        return ship

def create_sample_ships():
    """Create sample ship configurations"""
    # Sample ships in New York Harbor
    return [
        AISShip("Cargo Vessel 1", 366123001, 70, 100, 20, 40.7028, -74.0160, 45, 8, 0),
        AISShip("Tanker 2", 366123002, 80, 120, 25, 40.7050, -74.0180, 90, 5, 0),
        AISShip("Passenger 3", 366123003, 60, 80, 15, 40.6980, -74.0100, 270, 10, 0),
        AISShip("Tug 4", 366123004, 50, 30, 10, 40.7000, -74.0120, 180, 4, 0),
        AISShip("Ferry 5", 366123005, 60, 40, 12, 40.7060, -74.0140, 0, 12, 0)
    ]
