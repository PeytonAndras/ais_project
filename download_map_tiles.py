#!/usr/bin/env python3
"""
Map Tile Download Utility
=========================

Standalone utility for downloading and managing local OpenStreetMap tiles
for the SIREN maritime simulation system.

Usage:
    python download_map_tiles.py --area portugal --zoom 1-12
    python download_map_tiles.py --area atlantic --zoom 1-10
    python download_map_tiles.py --custom 42.0 36.0 -10.0 -6.0 --zoom 1-12
    python download_map_tiles.py --info
    python download_map_tiles.py --clear

@ author: Peyton Andras @ Louisiana State University 2025
"""

import argparse
import sys
import os
from pathlib import Path

# Add the siren package to the path
sys.path.insert(0, str(Path(__file__).parent))

def main():
    parser = argparse.ArgumentParser(description="Download and manage local map tiles for SIREN")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--area", choices=["portugal", "atlantic"], 
                      help="Download predefined area")
    group.add_argument("--custom", nargs=4, metavar=("NORTH", "SOUTH", "WEST", "EAST"), 
                      type=float, help="Download custom bounding box")
    group.add_argument("--info", action="store_true", 
                      help="Show cache information")
    group.add_argument("--clear", action="store_true", 
                      help="Clear tile cache")
    
    parser.add_argument("--zoom", default="1-10", 
                       help="Zoom level range (e.g., '1-12' or '8')")
    parser.add_argument("--cache-dir", default="map_cache",
                       help="Cache directory path")
    
    args = parser.parse_args()
    
    try:
        from siren.map.local_tiles import LocalTileManager, download_portugal_area, download_atlantic_area
        
        # Initialize tile manager
        tile_manager = LocalTileManager(args.cache_dir)
        
        if args.info:
            show_cache_info(tile_manager)
        elif args.clear:
            clear_cache(tile_manager)
        elif args.area:
            download_predefined_area(tile_manager, args.area)
        elif args.custom:
            download_custom_area(tile_manager, args.custom, args.zoom)
            
    except ImportError as e:
        print(f"Error importing SIREN modules: {e}")
        print("Make sure you're running this from the SIREN project directory.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

def show_cache_info(tile_manager):
    """Display cache information"""
    print("=== Map Tile Cache Information ===")
    
    cache_info = tile_manager.get_cache_info()
    print(f"Total tiles: {cache_info['total_tiles']}")
    print(f"Total size: {cache_info['total_size_mb']:.1f} MB")
    
    if cache_info['zoom_distribution']:
        print("\nZoom level distribution:")
        for zoom, count in sorted(cache_info['zoom_distribution'].items()):
            print(f"  Zoom {zoom}: {count} tiles")
    else:
        print("No cached tiles found.")

def clear_cache(tile_manager):
    """Clear the tile cache"""
    print("=== Clearing Map Tile Cache ===")
    
    cache_info = tile_manager.get_cache_info()
    if cache_info['total_tiles'] == 0:
        print("Cache is already empty.")
        return
    
    response = input(f"This will delete {cache_info['total_tiles']} tiles ({cache_info['total_size_mb']:.1f} MB). Continue? (y/N): ")
    if response.lower() in ['y', 'yes']:
        if tile_manager.clear_cache():
            print("Cache cleared successfully.")
        else:
            print("Failed to clear cache.")
    else:
        print("Cache clear cancelled.")

def download_predefined_area(tile_manager, area):
    """Download a predefined area"""
    print(f"=== Downloading {area.title()} Area ===")
    
    def progress_callback(progress, downloaded, total):
        print(f"\rProgress: {progress:.1f}% ({downloaded}/{total} tiles)", end="")
    
    if area == "portugal":
        from siren.map.local_tiles import download_portugal_area
        download_portugal_area(tile_manager, progress_callback)
    elif area == "atlantic":
        from siren.map.local_tiles import download_atlantic_area
        download_atlantic_area(tile_manager, progress_callback)
    
    print("\nDownload complete!")

def download_custom_area(tile_manager, bounds, zoom_str):
    """Download a custom area"""
    north, south, west, east = bounds
    
    # Parse zoom range
    if '-' in zoom_str:
        min_zoom, max_zoom = map(int, zoom_str.split('-'))
    else:
        min_zoom = max_zoom = int(zoom_str)
    
    print(f"=== Downloading Custom Area ===")
    print(f"Bounds: N={north}, S={south}, W={west}, E={east}")
    print(f"Zoom levels: {min_zoom}-{max_zoom}")
    
    def progress_callback(progress, downloaded, total):
        print(f"\rProgress: {progress:.1f}% ({downloaded}/{total} tiles)", end="")
    
    tile_manager.download_area(
        north, south, east, west,
        min_zoom, max_zoom,
        progress_callback=progress_callback
    )
    
    print("\nDownload complete!")

if __name__ == "__main__":
    main()
