# SIREN Offline Map Implementation

This implementation provides full offline map functionality for the SIREN maritime simulator webapp, allowing operation without internet connectivity once tiles are downloaded.

## 🚀 Quick Start

### 1. Download Map Tiles

First, download map tiles for your area of interest:

```bash
# Download tiles for Portugal coast (default area)
python3 download_tiles.py

# Download custom area (example: Mediterranean)
python3 download_tiles.py --north 44.0 --south 30.0 --east 20.0 --west -6.0 --min-zoom 8 --max-zoom 12

# Download with custom output directory
python3 download_tiles.py --output /path/to/tiles --max-zoom 16
```

### 2. Verify Downloaded Tiles

Verify tile integrity and get statistics:

```bash
# Basic verification
python3 verify_tiles.py

# Verify with storage calculation
python3 verify_tiles.py --storage

# Verify custom tiles directory
python3 verify_tiles.py --tiles-path /path/to/tiles
```

### 3. Test Offline Functionality

Open the test page to verify offline functionality:

```bash
# Start local server
python3 -m http.server 8000

# Open in browser
open http://localhost:8000/test_offline.html
```

### 4. Run SIREN Webapp

The main SIREN webapp now automatically supports offline maps:

```bash
# Open main webapp
open http://localhost:8000/siren.html
```

## 📁 Directory Structure

After downloading tiles, you'll have this structure:

```
siren-webapp-integrated/
├── tiles/                      # Downloaded map tiles
│   ├── openstreetmap/         # OSM tiles
│   │   ├── 8/                 # Zoom level 8
│   │   │   ├── 127/           # X coordinate
│   │   │   │   ├── 95.png     # Y coordinate tile
│   │   │   │   └── 96.png
│   │   │   └── 128/
│   │   ├── 9/                 # Zoom level 9
│   │   └── ...
│   ├── satellite/             # Satellite imagery tiles
│   ├── terrain/               # Terrain tiles
│   └── verification_report.json  # Verification results
├── download_tiles.py          # Tile downloader script
├── verify_tiles.py            # Tile verification script
├── test_offline.html          # Offline functionality test page
└── assets/
    └── siren-webapp.js        # Enhanced with offline support
```

## 🗺️ Map Layers

The implementation supports multiple map sources:

### Offline Layers (Cached)
- **OpenStreetMap**: Street maps with roads, cities, landmarks
- **Satellite**: High-resolution satellite imagery
- **Terrain**: Topographic maps with elevation data

### Online Layers (Fallback)
- **OpenStreetMap (Online)**: Live OSM tiles
- **Satellite (Online)**: Live satellite imagery
- **Terrain (Online)**: Live terrain data
- **Nautical (Online)**: Maritime navigation charts

## ⚙️ Configuration Options

### Download Script Options

```bash
python3 download_tiles.py --help
```

Options:
- `--north`, `--south`, `--east`, `--west`: Bounding box coordinates
- `--min-zoom`, `--max-zoom`: Zoom level range (8-14 recommended)
- `--output`: Output directory for tiles

### Zoom Level Guidelines

| Zoom Level | Coverage | Use Case | Tiles/Area |
|------------|----------|----------|------------|
| 8-10 | Regional | Overview, fleet tracking | ~100-1K |
| 11-12 | Local | Port approaches, coastal | ~1K-10K |
| 13-14 | Detailed | Harbor navigation | ~10K-100K |
| 15+ | Very detailed | Not recommended offline | 100K+ |

## 🔧 Features

### ✅ Implemented Features

- **Offline-first approach**: Prefers cached tiles over online
- **Automatic fallback**: Seamlessly switches between offline/online
- **Connection detection**: Visual indicators for online/offline status
- **Multiple map types**: Street, satellite, terrain maps
- **Error handling**: Graceful handling of missing tiles
- **Storage optimization**: Efficient tile storage and loading
- **Verification tools**: Integrity checking and statistics

### 🎯 Key Benefits

- **Zero internet dependency** once tiles are downloaded
- **Faster loading** from local cache
- **Reduced bandwidth** usage
- **Consistent performance** regardless of connection quality
- **Mission-critical reliability** for maritime operations

## 🧪 Testing

### Manual Testing

1. **Download test tiles**:
   ```bash
   python3 download_tiles.py --max-zoom 12
   ```

2. **Open test page**:
   ```bash
   python3 -m http.server 8000
   open http://localhost:8000/test_offline.html
   ```

3. **Test scenarios**:
   - Switch between map layers
   - Toggle offline mode
   - Add test ship markers
   - Verify tile loading in browser console

### Automated Verification

```bash
# Verify all downloaded tiles
python3 verify_tiles.py --storage

# Expected output: 
# ✅ All tiles verified successfully!
# 💾 Storage: XX.X MB (XXXX files)
```

## 🚨 Troubleshooting

### Common Issues

1. **"No Offline Tile" placeholders**:
   - Solution: Download tiles for the current map area
   - Check: `python3 verify_tiles.py`

2. **Tiles not loading**:
   - Check browser console for 404 errors
   - Verify tile directory structure
   - Ensure local server is running

3. **Slow tile downloading**:
   - Reduce zoom level range
   - Smaller geographic area
   - Check internet connection

4. **Large storage usage**:
   - Limit max zoom level (12-14 recommended)
   - Focus on operational areas only
   - Use `--storage` to estimate before downloading

### Browser Console Commands

```javascript
// Check current map state
console.log('Online:', navigator.onLine);
console.log('Current layer:', sirenApp.map._layers);

// Force refresh map
sirenApp.map.invalidateSize();

// Test offline mode
window.dispatchEvent(new Event('offline'));
```

## 📊 Storage Estimates

| Area | Zoom 8-12 | Zoom 8-14 | Zoom 8-16 |
|------|-----------|-----------|-----------|
| Small port (10km²) | ~50 MB | ~200 MB | ~800 MB |
| Coastal region (100km²) | ~200 MB | ~800 MB | ~3.2 GB |
| Large area (1000km²) | ~800 MB | ~3.2 GB | ~12.8 GB |

*Estimates for OpenStreetMap tiles only. Multiply by 3 for all tile types.*

## 🛡️ Security Considerations

- **Tile server respect**: Built-in delays to avoid overwhelming servers
- **User-Agent identification**: Identifies as SIREN Maritime Simulator
- **Error handling**: Graceful handling of server errors
- **Local storage only**: No external data transmission when offline

## 🔄 Updates

To update tiles for an area:

1. **Re-download** with same parameters (script skips existing tiles)
2. **Verify** updated tiles: `python3 verify_tiles.py`
3. **Clear browser cache** if needed for testing

## 📞 Support

For issues with the offline map implementation:

1. Check browser console for errors
2. Run `python3 verify_tiles.py` to check tile integrity
3. Test with `test_offline.html` for isolated testing
4. Check network connectivity indicators in the webapp

---

🚢 **Ready for offline maritime operations!**
