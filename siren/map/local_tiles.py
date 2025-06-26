"""
Local Map Tiles Module - Offline Map Support
============================================

Handles loading and management of locally stored OpenStreetMap tiles
for offline operation of the SIREN maritime simulation system.

@ author: Peyton Andras @ Louisiana State University 2025
"""

import os
import sqlite3
import math
import urllib.request
import urllib.parse
import time
from pathlib import Path

class LocalTileManager:
    """Manages local storage and retrieval of map tiles"""
    
    def __init__(self, cache_dir="map_cache"):
        """Initialize the local tile manager
        
        Args:
            cache_dir: Directory to store cached tiles
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Database file for tile metadata
        self.db_path = self.cache_dir / "tiles.db"
        self.init_database()
        
        # Tile server URLs
        self.tile_servers = {
            "openstreetmap": "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
            "openstreetmap_b": "https://b.tile.openstreetmap.org/{z}/{x}/{y}.png", 
            "openstreetmap_c": "https://c.tile.openstreetmap.org/{z}/{x}/{y}.png"
        }
        
        # Rate limiting for downloads
        self.last_download_time = 0
        self.min_download_interval = 0.1  # 100ms between downloads
        
    def init_database(self):
        """Initialize the SQLite database for tile metadata"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS tiles (
                        z INTEGER,
                        x INTEGER, 
                        y INTEGER,
                        server TEXT,
                        filename TEXT,
                        download_date TEXT,
                        file_size INTEGER,
                        PRIMARY KEY (z, x, y, server)
                    )
                """)
                conn.commit()
        except Exception as e:
            print(f"Error initializing tile database: {e}")
    
    def deg2num(self, lat_deg, lon_deg, zoom):
        """Convert lat/lon to tile coordinates"""
        lat_rad = math.radians(lat_deg)
        n = 2.0 ** zoom
        x = int((lon_deg + 180.0) / 360.0 * n)
        y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
        return (x, y)
    
    def num2deg(self, x, y, zoom):
        """Convert tile coordinates to lat/lon"""
        n = 2.0 ** zoom
        lon_deg = x / n * 360.0 - 180.0
        lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
        lat_deg = math.degrees(lat_rad)
        return (lat_deg, lon_deg)
    
    def get_tile_path(self, z, x, y, server="openstreetmap"):
        """Get the local file path for a tile"""
        filename = f"{server}_z{z}_x{x}_y{y}.png"
        return self.cache_dir / filename
    
    def is_tile_cached(self, z, x, y, server="openstreetmap"):
        """Check if a tile is available in local cache"""
        tile_path = self.get_tile_path(z, x, y, server)
        return tile_path.exists()
    
    def download_tile(self, z, x, y, server="openstreetmap"):
        """Download a single tile from the server"""
        if server not in self.tile_servers:
            raise ValueError(f"Unknown tile server: {server}")
            
        # Rate limiting
        current_time = time.time()
        time_since_last = current_time - self.last_download_time
        if time_since_last < self.min_download_interval:
            time.sleep(self.min_download_interval - time_since_last)
        
        url = self.tile_servers[server].format(z=z, x=x, y=y)
        tile_path = self.get_tile_path(z, x, y, server)
        
        try:
            # Create request with proper headers
            req = urllib.request.Request(url)
            req.add_header('User-Agent', 'SIREN-AIS-System/1.0 (Maritime Research Tool)')
            
            # Download the tile
            with urllib.request.urlopen(req, timeout=10) as response:
                tile_data = response.read()
                
            # Save to file
            with open(tile_path, 'wb') as f:
                f.write(tile_data)
            
            # Update database
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO tiles 
                    (z, x, y, server, filename, download_date, file_size)
                    VALUES (?, ?, ?, ?, ?, datetime('now'), ?)
                """, (z, x, y, server, tile_path.name, len(tile_data)))
                conn.commit()
            
            self.last_download_time = time.time()
            return True
            
        except Exception as e:
            print(f"Error downloading tile {z}/{x}/{y}: {e}")
            return False
    
    def download_area(self, north, south, east, west, min_zoom=1, max_zoom=10, 
                      server="openstreetmap", progress_callback=None):
        """Download tiles for a specific geographic area
        
        Args:
            north, south, east, west: Bounding box coordinates
            min_zoom, max_zoom: Zoom level range
            server: Tile server to use
            progress_callback: Function to call with progress updates
        """
        total_tiles = 0
        downloaded_tiles = 0
        
        # Calculate total number of tiles
        for zoom in range(min_zoom, max_zoom + 1):
            x_min, y_max = self.deg2num(north, west, zoom)
            x_max, y_min = self.deg2num(south, east, zoom)
            total_tiles += (x_max - x_min + 1) * (y_max - y_min + 1)
        
        print(f"Downloading {total_tiles} tiles for zoom levels {min_zoom}-{max_zoom}")
        
        # Download tiles
        for zoom in range(min_zoom, max_zoom + 1):
            x_min, y_max = self.deg2num(north, west, zoom)
            x_max, y_min = self.deg2num(south, east, zoom)
            
            for x in range(x_min, x_max + 1):
                for y in range(y_min, y_max + 1):
                    if not self.is_tile_cached(zoom, x, y, server):
                        if self.download_tile(zoom, x, y, server):
                            downloaded_tiles += 1
                        else:
                            print(f"Failed to download tile {zoom}/{x}/{y}")
                    else:
                        downloaded_tiles += 1
                    
                    # Progress callback
                    if progress_callback:
                        progress = (downloaded_tiles / total_tiles) * 100
                        progress_callback(progress, downloaded_tiles, total_tiles)
        
        print(f"Download complete: {downloaded_tiles}/{total_tiles} tiles")
        return downloaded_tiles, total_tiles
    
    def get_local_tile_server_url(self):
        """Get a file:// URL template for local tiles"""
        # Return a template that tkintermapview can use
        cache_path = str(self.cache_dir.absolute())
        return f"file://{cache_path}/openstreetmap_z{{z}}_x{{x}}_y{{y}}.png"
    
    def get_cached_tile_count(self):
        """Get the number of cached tiles"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM tiles")
                return cursor.fetchone()[0]
        except Exception:
            return 0
    
    def get_cache_info(self):
        """Get information about the tile cache"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Total tiles
                cursor = conn.execute("SELECT COUNT(*) FROM tiles")
                total_tiles = cursor.fetchone()[0]
                
                # Total size
                cursor = conn.execute("SELECT SUM(file_size) FROM tiles")
                total_size = cursor.fetchone()[0] or 0
                
                # Zoom level distribution
                cursor = conn.execute("SELECT z, COUNT(*) FROM tiles GROUP BY z ORDER BY z")
                zoom_distribution = dict(cursor.fetchall())
                
                return {
                    "total_tiles": total_tiles,
                    "total_size_mb": total_size / (1024 * 1024),
                    "zoom_distribution": zoom_distribution
                }
        except Exception as e:
            print(f"Error getting cache info: {e}")
            return {"total_tiles": 0, "total_size_mb": 0, "zoom_distribution": {}}
    
    def clear_cache(self):
        """Clear all cached tiles"""
        try:
            # Remove all tile files
            for tile_file in self.cache_dir.glob("*.png"):
                tile_file.unlink()
            
            # Clear database
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM tiles")
                conn.commit()
            
            print("Tile cache cleared")
            return True
        except Exception as e:
            print(f"Error clearing cache: {e}")
            return False


def download_portugal_area(tile_manager, progress_callback=None):
    """Download tiles for the Portugal coastal area (default map region)"""
    # Portugal bounding box (approximate)
    north = 42.0   # Northern boundary
    south = 36.0   # Southern boundary  
    west = -10.0   # Western boundary
    east = -6.0    # Eastern boundary
    
    print("Downloading tiles for Portugal coastal area...")
    return tile_manager.download_area(
        north, south, east, west,
        min_zoom=1, max_zoom=12,
        progress_callback=progress_callback
    )


def download_atlantic_area(tile_manager, progress_callback=None):
    """Download tiles for a larger Atlantic area"""
    # Larger Atlantic area
    north = 45.0
    south = 35.0
    west = -15.0
    east = -5.0
    
    print("Downloading tiles for Atlantic area...")
    return tile_manager.download_area(
        north, south, east, west,
        min_zoom=1, max_zoom=10,
        progress_callback=progress_callback
    )


# Global tile manager instance
_tile_manager = None

def get_tile_manager():
    """Get or create the global tile manager instance"""
    global _tile_manager
    if _tile_manager is None:
        _tile_manager = LocalTileManager()
    return _tile_manager
