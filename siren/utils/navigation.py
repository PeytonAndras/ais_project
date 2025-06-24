"""
Utilities Module - Helper Functions
===================================

This module contains utility functions used throughout the application.
"""

import math

def haversine(lat1, lon1, lat2, lon2):
    """Calculate the great circle distance between two points in kilometers"""
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371  # Radius of earth in kilometers
    return c * r

def calculate_initial_compass_bearing(point1, point2):
    """Calculate the initial compass bearing between two points"""
    lat1, lon1 = point1
    lat2, lon2 = point2
    
    # Convert decimal degrees to radians
    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)
    lon_diff = math.radians(lon2 - lon1)
    
    # Calculate bearing
    x = math.sin(lon_diff) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1) * math.cos(lat2) * math.cos(lon_diff))
    
    initial_bearing = math.atan2(x, y)
    initial_bearing = math.degrees(initial_bearing)
    
    # Normalize to 0-360
    bearing = (initial_bearing + 360) % 360
    
    return bearing
