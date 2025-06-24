# SIREN: Spoofed Identification & Real-time Emulation Node

## Custom Map and Offline Navigation Guide

This comprehensive guide covers the custom map functionality that allows you to upload nautical charts or any georeferenced maps for offline AIS simulation and navigation.

## Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Prerequisites](#prerequisites)
4. [Quick Start](#quick-start)
5. [Custom Map Setup](#custom-map-setup)
6. [Map Calibration](#map-calibration)
7. [Waypoint Selection](#waypoint-selection)
8. [Ship Simulation on Custom Maps](#ship-simulation-on-custom-maps)
9. [File Formats](#file-formats)
10. [Troubleshooting](#troubleshooting)
11. [Advanced Usage](#advanced-usage)
12. [Best Practices](#best-practices)

## Overview

The custom map functionality allows you to work completely offline with your own nautical charts, satellite imagery, or any georeferenced map. This is particularly useful for:

- **Offline Operations**: Work without internet connectivity
- **Classified/Restricted Areas**: Use official nautical charts for sensitive waters
- **High-Resolution Charts**: Use detailed charts for precise navigation
- **Training Scenarios**: Create specific training environments
- **Research**: Analyze historical charts or specialized mapping data

## Features

### 🗺️ Map Management
- **Upload Support**: PNG, JPG, JPEG, GIF, BMP, TIFF formats
- **Auto-Resize**: Large images automatically resized while maintaining aspect ratio
- **Zoom & Pan**: Navigate large charts with scrollable interface
- **Multiple Charts**: Switch between different map sources

### 🎯 Calibration System
- **Two-Point Minimum**: Basic linear interpolation for simple maps
- **Multi-Point Advanced**: Weighted interpolation for complex projections
- **Visual Feedback**: See calibration points directly on the map
- **Save/Load**: Preserve calibration data for reuse

### 🚢 Ship Integration
- **Real-Time Tracking**: Ships display on custom maps during simulation
- **Selected Ships Only**: Show only simulated vessels
- **Ship Information**: Click ships for detailed information
- **Track History**: Visual trails showing ship movement

### 🎯 Waypoint Selection
- **Interactive Selection**: Click on map to add waypoints
- **Ship Dialog Integration**: Use map for waypoint planning
- **Coordinate Display**: See exact lat/lon for selected points
- **Route Planning**: Build complex navigation routes

## Prerequisites

### Required Python Packages
```bash
pip install tkintermapview pillow
```

### System Requirements
- Python 3.8 or higher
- Tkinter (usually included with Python)
- At least 4GB RAM for large charts
- Graphics card supporting hardware acceleration (recommended)

### Optional Dependencies
```bash
# For enhanced image processing
pip install opencv-python

# For advanced coordinate transformations
pip install pyproj
```

## Quick Start

### 1. Launch Application
```bash
cd /path/to/nato_navy
python ais_main_modular.py
```

### 2. Switch to Custom Map Mode
1. Open the application
2. Go to the **Map View** tab
3. In the **Map Mode** dropdown, select "**custom**"
4. The custom map interface will appear

### 3. Upload Your First Map
1. Click **"Upload Map/Chart"**
2. Select your nautical chart or map image
3. The map will display in the interface
4. You're ready to calibrate!

## Custom Map Setup

### Supported File Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| PNG | `.png` | Best for charts with transparency |
| JPEG | `.jpg`, `.jpeg` | Good for satellite imagery |
| GIF | `.gif` | Supports animation (first frame used) |
| BMP | `.bmp` | Uncompressed, high quality |
| TIFF | `.tiff` | Professional cartographic standard |

### Image Preparation Tips

#### 1. Resolution Guidelines
- **Minimum**: 1024x768 pixels
- **Recommended**: 2000x2000 pixels or larger
- **Maximum**: Limited by available RAM

#### 2. Quality Considerations
- Use lossless formats (PNG, TIFF) for charts with text
- JPEG acceptable for satellite imagery
- Ensure coordinate markings are clearly visible
- Remove or crop unnecessary borders/legends

#### 3. File Size Optimization
```python
# Example: Resize large image while maintaining quality
from PIL import Image

# Open large chart
img = Image.open('large_chart.tiff')

# Resize to maximum 2000x2000 while maintaining aspect ratio
img.thumbnail((2000, 2000), Image.Resampling.LANCZOS)

# Save as PNG for best quality
img.save('optimized_chart.png', 'PNG')
```

## Map Calibration

Calibration is the process of telling the system where specific geographic coordinates are located on your map image.

### Basic Two-Point Calibration

This is the simplest method, suitable for small areas or charts with minimal projection distortion.

#### Step-by-Step Process:

1. **Start Calibration**
   - Click **"Calibrate Map"** button
   - Button text changes to **"Finish Calibration"**
   - Status shows: *"Click on map to set calibration points"*

2. **Select First Point**
   - Click on a location where you know the exact coordinates
   - Enter the latitude and longitude in the dialog
   - A red marker appears on the map

3. **Select Second Point**
   - Click on another location (preferably far from the first)
   - Enter its coordinates
   - Second red marker appears

4. **Finish Calibration**
   - Click **"Finish Calibration"**
   - System calculates the coordinate transformation
   - Status shows: *"Map calibrated with X points"*

#### Example Calibration Points:
```
Point 1: Harbor entrance
- Pixel: (234, 567)
- Coordinate: 41.234567, -70.123456

Point 2: Navigation buoy
- Pixel: (1456, 234)
- Coordinate: 41.245678, -70.098765
```

### Advanced Multi-Point Calibration

For better accuracy, especially with charts covering large areas or using complex projections.

#### Benefits:
- **Higher Accuracy**: Compensates for projection distortions
- **Better Coverage**: Works across entire chart area
- **Weighted Interpolation**: Closer points have more influence

#### Recommended Points:
- **Minimum**: 3 points forming a triangle
- **Optimal**: 4-6 points covering the chart area
- **Maximum**: 10 points (more doesn't significantly improve accuracy)

#### Point Selection Strategy:
```
Ideal 4-point layout:

Northwest    Northeast
    +           +
    |           |
    |   Chart   |
    |   Area    |
    +           +
Southwest    Southeast
```

### Calibration Accuracy Tips

#### 1. Point Selection
- Choose locations with **precise coordinate references**
- Use **navigation aids** (buoys, lighthouses, harbors)
- Avoid **estimated positions**
- Select points **well-distributed** across the chart

#### 2. Coordinate Sources
- **GPS waypoints** from actual navigation
- **Published coordinates** from nautical publications
- **Chart datums** (ensure datum consistency)
- **Known landmarks** with surveyed positions

#### 3. Quality Control
```python
# Verify calibration accuracy by testing known points
test_point = (41.240000, -70.110000)  # Known coordinate
pixel_x, pixel_y = custom_map.coord_to_pixel(test_point[0], test_point[1])
reverse_lat, reverse_lon = custom_map.pixel_to_coord(pixel_x, pixel_y)

# Check accuracy
error_lat = abs(test_point[0] - reverse_lat)
error_lon = abs(test_point[1] - reverse_lon)
print(f"Calibration error: {error_lat:.6f}°, {error_lon:.6f}°")
```

## Waypoint Selection

### From Ship Dialog

1. **Open Ship Management**
   - Click **"Add Ship"** or **"Edit Ship"**
   - Go to the **"Waypoints"** tab

2. **Use Custom Map Button**
   - Click **"Custom Map"** button
   - A dialog appears with instructions
   - Switch to the Map View tab (if not visible)

3. **Select Waypoint**
   - Click on desired location on the map
   - Waypoint is automatically added to ship's route
   - Confirmation message shows coordinates

### Direct Map Interaction

```python
# Example waypoint selection callback
def on_waypoint_selected(lat, lon):
    print(f"Selected waypoint: {lat:.6f}, {lon:.6f}")
    # Add to current ship or save for later use
    current_ship.add_waypoint(lat, lon)
```

### Waypoint Management

#### Adding Multiple Waypoints
1. Use the ship dialog's waypoint tab
2. Click **"Custom Map"** repeatedly for each waypoint
3. Or manually enter coordinates in the latitude/longitude fields

#### Waypoint Order
- Ships follow waypoints in the order they were added
- Use **"Remove"** to delete specific waypoints
- Use **"Clear All"** to start over

#### Maximum Waypoints
- **Limit**: 20 waypoints per ship
- **Recommendation**: 5-10 waypoints for realistic navigation
- **Performance**: More waypoints may slow simulation

## Ship Simulation on Custom Maps

### Ship Display

Ships appear as small blue circles with their names when simulation is running.

#### Visual Elements:
- **Blue Circle**: Ship position
- **Ship Name**: Text label next to ship
- **Selected Ships Only**: Only simulated ships appear
- **Real-Time Updates**: Positions update as ships move

### Simulation Workflow

1. **Load and Calibrate Map**
   - Upload your nautical chart
   - Calibrate with known coordinates
   - Save calibration for future use

2. **Configure Ships**
   - Add ships with starting positions
   - Set waypoints using the custom map
   - Configure speed and navigation parameters

3. **Start Simulation**
   - Select ships to simulate
   - Start simulation from Simulation tab
   - Switch to Map View to watch ships move

4. **Monitor Progress**
   - Ships move between waypoints
   - Track history shows ship paths
   - Click ships for real-time information

### Coordinate System Integration

The system automatically handles coordinate transformations between:
- **Pixel Coordinates**: X,Y position on image
- **Geographic Coordinates**: Latitude/Longitude
- **Ship Navigation**: Waypoint following and bearing calculation

## File Formats

### Calibration Files

Calibration data is saved in JSON format for easy sharing and backup.

#### Example Calibration File:
```json
{
  "map_file": "/path/to/chart.png",
  "calibration_points": [
    {
      "pixel": [234.5, 567.8],
      "coord": [41.234567, -70.123456]
    },
    {
      "pixel": [1456.2, 234.9],
      "coord": [41.245678, -70.098765]
    }
  ],
  "bounds": {
    "north": 41.245678,
    "south": 41.234567,
    "east": -70.098765,
    "west": -70.123456
  }
}
```

#### File Operations:
```python
# Save calibration
custom_map.save_calibration()  # Opens file dialog

# Load calibration
custom_map.load_calibration()  # Opens file dialog

# Programmatic access
with open('chart_calibration.json', 'r') as f:
    calibration_data = json.load(f)
```

### Map Files

#### Naming Convention:
```
chart_area_scale_date.format
Examples:
- boston_harbor_1_25000_2024.png
- chesapeake_bay_1_80000_2023.tiff
- training_area_alpha_1_10000.jpg
```

#### Organization Structure:
```
maps/
├── nautical_charts/
│   ├── east_coast/
│   │   ├── boston_harbor.png
│   │   └── boston_harbor_calibration.json
│   └── west_coast/
│       ├── san_francisco_bay.tiff
│       └── san_francisco_bay_calibration.json
├── satellite_imagery/
│   └── google_earth_exports/
└── training_charts/
    └── simulated_environments/
```

## Troubleshooting

### Common Issues

#### 1. Map Not Loading
**Symptoms**: Error dialog when uploading map
**Solutions**:
- Verify file format is supported
- Check file isn't corrupted
- Ensure sufficient memory available
- Try resizing image if very large

```bash
# Check file integrity
python -c "from PIL import Image; Image.open('chart.png').verify()"
```

#### 2. Calibration Inaccuracy
**Symptoms**: Ships appear in wrong locations
**Solutions**:
- Add more calibration points
- Verify coordinate accuracy
- Check coordinate datum consistency
- Recalibrate with better-distributed points

#### 3. Poor Performance
**Symptoms**: Slow map updates, laggy interface
**Solutions**:
- Reduce image size
- Close other applications
- Use PNG instead of uncompressed formats
- Limit number of ships being simulated

#### 4. Coordinate Conversion Errors
**Symptoms**: Ships appear far from expected positions
**Solutions**:
- Verify lat/lon format (decimal degrees)
- Check coordinate sign (N/S, E/W)
- Ensure datum consistency
- Test with known reference points

### Debug Mode

Enable debug output for troubleshooting:

```python
# In custom_map.py, add debug prints
def pixel_to_coord(self, pixel_x, pixel_y):
    print(f"DEBUG: Converting pixel ({pixel_x}, {pixel_y}) to coordinates")
    # ... existing code ...
    print(f"DEBUG: Result: {lat}, {lon}")
    return lat, lon
```

### Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| "Failed to load map" | File format/corruption | Try different format or file |
| "Insufficient Points" | Less than 2 calibration points | Add more calibration points |
| "Invalid Coordinates" | Bad lat/lon input | Check coordinate format |
| "Map not calibrated" | Trying to use uncalibrated map | Complete calibration first |

## Advanced Usage

### Custom Coordinate Systems

For specialized applications, you can extend the coordinate transformation system:

```python
# Example: UTM coordinate support
import pyproj

def coord_to_utm(lat, lon, zone):
    """Convert lat/lon to UTM coordinates"""
    proj = pyproj.Proj(proj='utm', zone=zone, ellps='WGS84')
    return proj(lon, lat)

def utm_to_coord(easting, northing, zone):
    """Convert UTM to lat/lon coordinates"""
    proj = pyproj.Proj(proj='utm', zone=zone, ellps='WGS84')
    return proj(easting, northing, inverse=True)
```

### Batch Calibration

For multiple charts with similar characteristics:

```python
# Batch calibration script
import json
import os

def batch_calibrate_charts(chart_directory, template_calibration):
    """Apply template calibration to multiple charts"""
    for chart_file in os.listdir(chart_directory):
        if chart_file.endswith(('.png', '.jpg', '.tiff')):
            # Create calibration file
            cal_file = chart_file.replace('.', '_calibration.')
            cal_file = cal_file.rsplit('_', 1)[0] + '_calibration.json'
            
            # Adapt template to current chart
            calibration = adapt_calibration_template(
                template_calibration, 
                chart_file
            )
            
            # Save calibration
            with open(cal_file, 'w') as f:
                json.dump(calibration, f, indent=2)
```

### Integration with External Data

#### GPS Track Import
```python
def import_gps_track(gpx_file):
    """Import GPS track as waypoints"""
    # Parse GPX file
    waypoints = []
    # ... GPX parsing code ...
    return waypoints
```

#### Chart Datum Conversion
```python
def convert_chart_datum(lat, lon, from_datum, to_datum):
    """Convert between chart datums"""
    # Use pyproj for accurate datum transformations
    transformer = pyproj.Transformer.from_crs(
        from_datum, to_datum, always_xy=True
    )
    return transformer.transform(lon, lat)
```

## Best Practices

### 1. Chart Selection
- **Use official nautical charts** when available
- **Match chart scale** to simulation area size
- **Ensure current editions** with latest updates
- **Consider chart datum** and projection

### 2. Calibration Strategy
- **Start with corner points** for basic coverage
- **Add intermediate points** for accuracy
- **Use prominent landmarks** for reference
- **Document calibration sources** for repeatability

### 3. File Management
- **Organize charts by region** or purpose
- **Save calibrations with descriptive names**
- **Back up calibration files** regularly
- **Version control** for shared environments

### 4. Performance Optimization
- **Optimize image sizes** before upload
- **Use appropriate file formats** for content type
- **Limit simultaneous ship count** on complex charts
- **Close unused applications** during simulation

### 5. Accuracy Verification
- **Test with known positions** after calibration
- **Cross-reference with GPS waypoints** when possible
- **Document accuracy limitations** for users
- **Regular recalibration** for critical applications

### 6. Training and Documentation
- **Create user guides** for specific chart sets
- **Document calibration procedures** for each chart
- **Train users on coordinate systems** and datums
- **Establish quality control** procedures

## Example Workflows

### Workflow 1: Preparing a Nautical Chart

1. **Acquire Chart**
   ```bash
   # Download from official source or scan paper chart
   # Ensure high resolution (300+ DPI for scanned charts)
   ```

2. **Prepare Image**
   ```python
   from PIL import Image
   
   # Open and optimize
   img = Image.open('raw_chart.tiff')
   img = img.convert('RGB')  # Remove unnecessary channels
   img.thumbnail((2000, 2000), Image.Resampling.LANCZOS)
   img.save('chart_optimized.png', 'PNG', optimize=True)
   ```

3. **Load and Calibrate**
   - Upload optimized image
   - Identify prominent navigation features
   - Add 4-6 calibration points
   - Save calibration file

4. **Verify Accuracy**
   - Test with known GPS waypoints
   - Check coordinate transformation accuracy
   - Document any limitations

### Workflow 2: Multi-Chart Training Environment

1. **Chart Collection**
   - Gather charts for training area
   - Ensure consistent datum and projection
   - Optimize all images to similar scale

2. **Standardized Calibration**
   - Create calibration template
   - Apply consistent methodology
   - Document reference standards

3. **Scenario Development**
   - Design ship routes using waypoints
   - Create realistic traffic patterns
   - Test scenarios thoroughly

4. **Deployment**
   - Package charts and calibrations
   - Create user documentation
   - Provide training on usage

### Workflow 3: Research Data Integration

1. **Data Preparation**
   ```python
   # Convert research data to map overlay
   import matplotlib.pyplot as plt
   
   # Create map from data
   plt.figure(figsize=(20, 20))
   plt.plot(lon_data, lat_data, 'b-')
   plt.xlim(lon_min, lon_max)
   plt.ylim(lat_min, lat_max)
   plt.savefig('research_map.png', dpi=300, bbox_inches='tight')
   ```

2. **Calibration**
   - Use data coordinate bounds for calibration
   - Add corner points with known coordinates
   - Verify transformation accuracy

3. **Analysis**
   - Run ship simulations over research area
   - Collect position and timing data
   - Export results for analysis

## Conclusion

The custom map functionality provides powerful offline capabilities for maritime AIS simulation and training. By following this guide, you can:

- Work completely offline with your own charts
- Achieve high accuracy through proper calibration
- Create realistic training scenarios
- Integrate with existing navigation workflows

For additional support or advanced features, consult the main application documentation or contact the development team.

---

**SIREN: Spoofed Identification & Real-time Emulation Node**  
*@ Peyton Andras @ Louisiana State University 2025*
