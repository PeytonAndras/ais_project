#!/usr/bin/env python3
"""
SIREN Offline Tile Verification Script
Verifies the integrity and structure of downloaded map tiles
"""

import os
import json
from PIL import Image
import argparse

def verify_tile_structure(tiles_path="tiles"):
    """Verify the structure and integrity of downloaded tiles"""
    
    if not os.path.exists(tiles_path):
        print(f"❌ Tiles directory not found: {tiles_path}")
        return False
    
    print("🔍 SIREN Offline Tile Verification")
    print("=" * 50)
    
    tile_types = []
    total_tiles = 0
    valid_tiles = 0
    corrupt_tiles = 0
    
    # Scan for tile types
    for item in os.listdir(tiles_path):
        item_path = os.path.join(tiles_path, item)
        if os.path.isdir(item_path):
            tile_types.append(item)
    
    if not tile_types:
        print(f"❌ No tile directories found in {tiles_path}")
        return False
    
    print(f"📁 Found tile types: {', '.join(tile_types)}\n")
    
    verification_report = {
        "tile_types": {},
        "summary": {
            "total_tiles": 0,
            "valid_tiles": 0,
            "corrupt_tiles": 0,
            "zoom_levels": set()
        }
    }
    
    for tile_type in tile_types:
        print(f"🗺️  Verifying {tile_type} tiles...")
        type_path = os.path.join(tiles_path, tile_type)
        
        type_stats = {
            "zoom_levels": {},
            "total_tiles": 0,
            "valid_tiles": 0,
            "corrupt_tiles": 0
        }
        
        # Check zoom levels
        zoom_levels = []
        for item in os.listdir(type_path):
            item_path = os.path.join(type_path, item)
            if os.path.isdir(item_path) and item.isdigit():
                zoom_levels.append(int(item))
        
        zoom_levels.sort()
        
        for zoom in zoom_levels:
            zoom_path = os.path.join(type_path, str(zoom))
            zoom_stats = {
                "x_ranges": {},
                "total_tiles": 0,
                "valid_tiles": 0,
                "corrupt_tiles": 0
            }
            
            # Check X directories
            x_dirs = []
            for item in os.listdir(zoom_path):
                item_path = os.path.join(zoom_path, item)
                if os.path.isdir(item_path) and item.isdigit():
                    x_dirs.append(int(item))
            
            x_dirs.sort()
            
            for x in x_dirs:
                x_path = os.path.join(zoom_path, str(x))
                
                # Count Y tiles
                y_files = []
                for item in os.listdir(x_path):
                    if item.endswith('.png'):
                        y_files.append(item)
                
                x_tiles = 0
                x_valid = 0
                x_corrupt = 0
                
                for y_file in y_files:
                    tile_path = os.path.join(x_path, y_file)
                    x_tiles += 1
                    total_tiles += 1
                    
                    # Verify tile integrity
                    try:
                        with Image.open(tile_path) as img:
                            # Check if image can be loaded and has reasonable dimensions
                            if img.size[0] == 256 and img.size[1] == 256:
                                x_valid += 1
                                valid_tiles += 1
                            else:
                                x_corrupt += 1
                                corrupt_tiles += 1
                                print(f"    ⚠️  Invalid size: {tile_path} ({img.size})")
                    except Exception as e:
                        x_corrupt += 1
                        corrupt_tiles += 1
                        print(f"    ❌ Corrupt tile: {tile_path} - {e}")
                
                zoom_stats["x_ranges"][x] = {
                    "total": x_tiles,
                    "valid": x_valid,
                    "corrupt": x_corrupt,
                    "y_range": [int(f.replace('.png', '')) for f in y_files if f.endswith('.png')]
                }
                
                zoom_stats["total_tiles"] += x_tiles
                zoom_stats["valid_tiles"] += x_valid
                zoom_stats["corrupt_tiles"] += x_corrupt
            
            type_stats["zoom_levels"][zoom] = zoom_stats
            type_stats["total_tiles"] += zoom_stats["total_tiles"]
            type_stats["valid_tiles"] += zoom_stats["valid_tiles"]
            type_stats["corrupt_tiles"] += zoom_stats["corrupt_tiles"]
            
            verification_report["summary"]["zoom_levels"].add(zoom)
            
            print(f"    📊 Zoom {zoom}: {zoom_stats['total_tiles']} tiles ({zoom_stats['valid_tiles']} valid, {zoom_stats['corrupt_tiles']} corrupt)")
        
        verification_report["tile_types"][tile_type] = type_stats
        verification_report["summary"]["total_tiles"] += type_stats["total_tiles"]
        verification_report["summary"]["valid_tiles"] += type_stats["valid_tiles"]
        verification_report["summary"]["corrupt_tiles"] += type_stats["corrupt_tiles"]
        
        print(f"  ✅ {tile_type}: {type_stats['total_tiles']} total tiles")
        print(f"     Valid: {type_stats['valid_tiles']}, Corrupt: {type_stats['corrupt_tiles']}")
        print()
    
    # Convert set to list for JSON serialization
    verification_report["summary"]["zoom_levels"] = sorted(list(verification_report["summary"]["zoom_levels"]))
    
    # Summary
    print("📋 VERIFICATION SUMMARY")
    print("-" * 30)
    print(f"Total tile types: {len(tile_types)}")
    print(f"Zoom levels: {', '.join(map(str, verification_report['summary']['zoom_levels']))}")
    print(f"Total tiles: {verification_report['summary']['total_tiles']}")
    print(f"Valid tiles: {verification_report['summary']['valid_tiles']}")
    print(f"Corrupt tiles: {verification_report['summary']['corrupt_tiles']}")
    
    if verification_report['summary']['corrupt_tiles'] == 0:
        print("🎉 All tiles verified successfully!")
        success = True
    else:
        print(f"⚠️  {verification_report['summary']['corrupt_tiles']} corrupt tiles found")
        success = False
    
    # Save verification report
    report_file = os.path.join(tiles_path, 'verification_report.json')
    with open(report_file, 'w') as f:
        json.dump(verification_report, f, indent=2)
    
    print(f"\n📄 Verification report saved to: {report_file}")
    
    return success

def estimate_storage_size(tiles_path="tiles"):
    """Estimate total storage size of tiles"""
    total_size = 0
    file_count = 0
    
    for root, dirs, files in os.walk(tiles_path):
        for file in files:
            if file.endswith('.png'):
                file_path = os.path.join(root, file)
                total_size += os.path.getsize(file_path)
                file_count += 1
    
    # Convert bytes to human readable format
    for unit in ['B', 'KB', 'MB', 'GB']:
        if total_size < 1024.0:
            break
        total_size /= 1024.0
    
    print(f"💾 Storage: {total_size:.1f} {unit} ({file_count} files)")

def main():
    parser = argparse.ArgumentParser(description='Verify SIREN offline map tiles')
    parser.add_argument('--tiles-path', type=str, default='tiles', help='Path to tiles directory')
    parser.add_argument('--storage', action='store_true', help='Calculate storage usage')
    
    args = parser.parse_args()
    
    try:
        if args.storage:
            estimate_storage_size(args.tiles_path)
        
        success = verify_tile_structure(args.tiles_path)
        
        if success:
            print("\n🚢 Tiles ready for offline SIREN operation!")
        else:
            print("\n⚠️  Some issues found. Check the report for details.")
            
    except KeyboardInterrupt:
        print("\n⏹️  Verification cancelled by user")
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")

if __name__ == "__main__":
    main()
