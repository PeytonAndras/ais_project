#!/usr/bin/env python3
"""
SIREN Offline Map Tile Downloader
Downloads map tiles for offline use in the SIREN maritime simulator
"""

import requests
import os
import time
import math
import argparse
from urllib.parse import urlparse

class TileDownloader:
    def __init__(self, base_path="tiles"):
        self.base_path = base_path
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'SIREN Maritime Simulator/1.0'
        })
    
    def deg2num(self, lat_deg, lon_deg, zoom):
        """Convert latitude/longitude to tile numbers"""
        lat_rad = math.radians(lat_deg)
        n = 2.0 ** zoom
        x_tile = int((lon_deg + 180.0) / 360.0 * n)
        y_tile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
        return (x_tile, y_tile)
    
    def download_area(self, north, south, east, west, min_zoom, max_zoom, tile_sources):
        """Download tiles for a specified area"""
        print(f"Downloading tiles for area:")
        print(f"  North: {north}, South: {south}")
        print(f"  East: {east}, West: {west}")
        print(f"  Zoom levels: {min_zoom} to {max_zoom}")
        
        total_tiles = 0
        downloaded_tiles = 0
        skipped_tiles = 0
        
        for source_name, source_url in tile_sources.items():
            print(f"\n📡 Downloading {source_name} tiles...")
            source_path = os.path.join(self.base_path, source_name.lower().replace(' ', '_'))
            
            for zoom in range(min_zoom, max_zoom + 1):
                # Calculate tile bounds correctly
                min_x, max_y = self.deg2num(north, west, zoom)
                max_x, min_y = self.deg2num(south, east, zoom)
                
                # Ensure coordinates are in correct order
                if min_x > max_x:
                    min_x, max_x = max_x, min_x
                if min_y > max_y:
                    min_y, max_y = max_y, min_y
                
                tile_count = (max_x - min_x + 1) * (max_y - min_y + 1)
                print(f"  📊 Zoom {zoom}: {tile_count} tiles (x: {min_x}-{max_x}, y: {min_y}-{max_y})")
                
                for x in range(min_x, max_x + 1):
                    for y in range(min_y, max_y + 1):
                        total_tiles += 1
                        
                        # Handle different URL patterns
                        if '{s}' in source_url:
                            subdomains = ['a', 'b', 'c']
                            subdomain = subdomains[x % len(subdomains)]
                            tile_url = source_url.format(z=zoom, x=x, y=y, s=subdomain)
                        else:
                            tile_url = source_url.format(z=zoom, x=x, y=y)
                        
                        tile_path = os.path.join(source_path, str(zoom), str(x), f"{y}.png")
                        
                        # Create directory if it doesn't exist
                        os.makedirs(os.path.dirname(tile_path), exist_ok=True)
                        
                        # Skip if tile already exists
                        if os.path.exists(tile_path) and os.path.getsize(tile_path) > 0:
                            skipped_tiles += 1
                            continue
                        
                        try:
                            response = self.session.get(tile_url, timeout=15)
                            response.raise_for_status()
                            
                            # Check if we got a valid image
                            if len(response.content) > 0:
                                with open(tile_path, 'wb') as f:
                                    f.write(response.content)
                                
                                downloaded_tiles += 1
                                if downloaded_tiles % 50 == 0:
                                    print(f"    ✅ Downloaded {downloaded_tiles} tiles...")
                            
                            # Be nice to tile servers
                            time.sleep(0.1)
                            
                        except Exception as e:
                            print(f"    ❌ Error downloading {tile_url}: {e}")
                            continue
        
        print(f"\n🎉 Download complete!")
        print(f"  📥 Downloaded: {downloaded_tiles} new tiles")
        print(f"  ⏭️  Skipped: {skipped_tiles} existing tiles")
        print(f"  📊 Total processed: {total_tiles} tiles")

def main():
    parser = argparse.ArgumentParser(description='Download map tiles for SIREN offline use')
    parser.add_argument('--north', type=float, default=40.2, help='Northern boundary (latitude)')
    parser.add_argument('--south', type=float, default=38.8, help='Southern boundary (latitude)')
    parser.add_argument('--east', type=float, default=-8.0, help='Eastern boundary (longitude)')
    parser.add_argument('--west', type=float, default=-10.0, help='Western boundary (longitude)')
    parser.add_argument('--min-zoom', type=int, default=8, help='Minimum zoom level')
    parser.add_argument('--max-zoom', type=int, default=14, help='Maximum zoom level')
    parser.add_argument('--output', type=str, default='tiles', help='Output directory for tiles')
    
    args = parser.parse_args()
    
    # Define tile sources
    tile_sources = {
        'openstreetmap': 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
        'satellite': 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        'terrain': 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Terrain_Base/MapServer/tile/{z}/{y}/{x}',
    }
    
    # Add nautical charts if available (requires different handling)
    # 'nautical': 'https://tileservice.charts.noaa.gov/tiles/50000_1/{z}/{x}/{y}.png'
    
    print("🗺️  SIREN Offline Map Tile Downloader")
    print("=" * 50)
    
    downloader = TileDownloader(args.output)
    downloader.download_area(
        args.north, args.south, args.east, args.west,
        args.min_zoom, args.max_zoom, tile_sources
    )
    
    print(f"\n📁 Tiles saved to: {os.path.abspath(args.output)}")
    print("🚢 Ready for offline SIREN operation!")

if __name__ == "__main__":
    main()
