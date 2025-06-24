# SIREN: Spoofed Identification & Real-time Emulation Node

## Advanced AIS Maritime Simulation and Transmission System

**SIREN** is a comprehensive Automatic Identification System (AIS) simulation and transmission platform designed for maritime training, research, and cybersecurity applications. The system provides real-time ship simulation, AIS message generation, and SDR-based transmission capabilities with both online and offline mapping support.

---

## 🚢 Key Features

### Core Capabilities
- **Real-Time AIS Simulation**: Simulate multiple ships with realistic movement patterns and physics
- **SDR Transmission**: Broadcast standards-compliant AIS messages using Software Defined Radio
- **Interactive Mapping**: Support for both online maps (tkintermapview) and custom nautical charts
- **Waypoint Navigation**: Ships follow predefined routes with automatic course corrections and collision avoidance
- **Multi-Ship Management**: Handle fleets of vessels with individual configurations and behaviors
- **NMEA Message Generation**: Full AIS Type 1, 2, and 3 message compliance with proper encoding

### Advanced Features
- **Custom Map Support**: Upload and calibrate your own nautical charts for offline operation
- **Real-Time Visualization**: Ships move on maps synchronized with simulation timing
- **Selective Simulation**: Choose which ships to simulate and transmit independently
- **Signal Analysis**: Built-in transmission monitoring and signal quality assessment
- **Ship Tracking**: Historical trails, speed vectors, and real-time position updates
- **Modular Architecture**: Easily extensible with clean separation of concerns

---

### For SDR Transmission
- **SDR Hardware**: LimeSDR, HackRF, USRP, RTL-SDR (TX-capable), or compatible device
- **Drivers**: SoapySDR with appropriate device drivers installed
- **Licensing**: Appropriate radio operator license for transmissions (check local regulations)
- **Antenna**: VHF marine antenna tuned for 161.975 MHz and 162.025 MHz

### For Map Functionality
- **Internet**: Required for online maps (tkintermapview) - optional for custom maps
- **Display**: 1920x1080 minimum resolution recommended for full interface

---

## 🚀 Installation & Quick Start

### 1. Prerequisites & Installation

#### System Dependencies
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install python3-pip python3-venv git build-essential cmake

# macOS (requires Homebrew)
brew install python3 git cmake

# Windows: Install Python 3.8+ from python.org and Git
```


#### Create Virtual Environment (Recommended)
```bash
python3 -m venv siren_env
source siren_env/bin/activate  # On Windows: siren_env\Scripts\activate
```

#### Install Python Dependencies
```bash
# Core dependencies (required)
pip install tkintermapview pillow requests

# For SDR transmission (optional but recommended)
pip install numpy SoapySDR

# Development dependencies (optional)
pip install pytest matplotlib
```

#### Install SDR Drivers (For Transmission)
```bash
# Ubuntu/Debian
sudo apt-get install soapysdr-tools soapysdr-module-all

# macOS with Homebrew
brew install soapysdr

# Windows: Download SoapySDR installers from:
# https://github.com/pothosware/SoapySDR/wiki/WindowsInstall
```

### 2. First Launch & Basic Usage

#### Start SIREN
```bash
python ais_main_modular.py
```

#### Quick Test Sequence
1. **Add a Ship**: Click "Add Ship" button, enter basic details
2. **Add Waypoints**: In ship dialog, add waypoints by clicking on map
3. **Start Simulation**: Select ship(s) and click "Start Simulation"
4. **View Movement**: Switch to "Map View" tab to see ships moving
5. **Monitor AIS**: Check "AIS Messages" tab for transmitted data

#### Common Usage Scenarios

**Maritime Training Scenario**
```bash
# Load pre-configured training fleet
python ais_main_modular.py
# 1. Load "robust_ship_configs.json" via File menu
# 2. Select ships for training exercise
# 3. Start simulation with realistic timing (30-60 second intervals)
# 4. Monitor ship movements and AIS transmissions
```

**Research & Development Testing**
```bash
# Custom ship configuration for testing
python ais_main_modular.py
# 1. Create ships with specific MMSI ranges
# 2. Define precise waypoint routes
# 3. Use shorter intervals (5-10 seconds) for rapid testing
# 4. Enable transmission for signal analysis
```

**Cybersecurity Assessment**
```bash
# Controlled spoofing scenario (authorized environments only)
python ais_main_modular.py
# 1. Configure ships with target vessel parameters
# 2. Set up waypoints to simulate specific routes
# 3. Use custom maps for precise geographic context
# 4. Monitor for detection and response systems
```

### 3. Verify Installation
```bash
# Test core functionality
python test_modular.py

# Test production integration (if SDR available)
python test_production_integration.py

# Validate SDR hardware detection (optional)
SoapySDRUtil --find

# Check Python environment
python -c "
import sys
print(f'Python: {sys.version}')
try:
    import tkintermapview, PIL, requests
    print('✅ Core dependencies: OK')
    try:
        import SoapySDR, numpy
        print('✅ SDR dependencies: OK')
    except ImportError as e:
        print(f'⚠️  SDR dependencies missing: {e}')
except ImportError as e:
    print(f'❌ Core dependencies missing: {e}')
"
```


## 🔧 Advanced Integration: Hybrid Maritime AIS

SIREN integrates with a production-ready maritime AIS system in `hybrid_maritime_ais/` for real-world deployment.

### Production System Features
- **ITU-R M.1371-5 Compliance**: Full maritime standards compliance
- **SOTDMA Protocol**: Self-Organizing Time Division Multiple Access
- **Multi-mode Operation**: Production (GMSK), testing (FSK), emergency modes
- **Command-line Interface**: Direct vessel beacon transmission

### Usage Examples
```bash
cd hybrid_maritime_ais/

# Production maritime beacon
python hybrid_maritime_ais.py \
    --mmsi 123456789 --lat 41.7749 --lon -70.4194 \
    --mode production --sog 12.5 --cog 045 --rate 10

# Emergency beacon (higher transmission rate)
python hybrid_maritime_ais.py \
    --mmsi 123456789 --lat 41.7749 --lon -70.4194 \
    --mode emergency --nav-status 7 --rate 5

# Testing mode (rtl_ais compatible)
python hybrid_maritime_ais.py \
    --mmsi 123456789 --lat 41.7749 --lon -70.4194 \
    --mode rtl_ais_testing --once
```

### System Comparison
| Feature | SIREN (Simulation) | Hybrid (Production) |
|---------|-------------------|-------------------|
| **Purpose** | Multi-vessel simulation & training | Single-vessel deployment |
| **Interface** | GUI with waypoint management | Command-line operation |
| **Compliance** | Development/testing focus | Full ITU maritime standards |
| **Use Case** | Training, testing, R&D | Live vessel tracking |
---

## 🗺️ Map System

### Online Maps (Default Mode)
- **Live Tile Loading**: Real-time download from OpenStreetMap
- **Global Coverage**: Worldwide mapping with zoom levels 1-19
- **Geocoding**: Search locations by name or coordinates
- **Requirements**: Internet connection for tile downloads

### Custom Maps (Offline Mode)
- **Upload Charts**: Import nautical charts, satellite imagery, or custom maps
- **Calibration System**: Map image pixels to real-world coordinates
- **Offline Operation**: No internet required after initial setup
- **High Precision**: Use official charts for navigation accuracy

#### Custom Map Setup
1. **Prepare Image**: PNG/JPG format, reasonable resolution
2. **Calibration**: Define 2+ reference points with known coordinates
3. **Upload**: Use "Upload Custom Map" in interface
4. **Verify**: Test coordinate conversion accuracy
---

## ⚙️ Configuration Guide

### Ship Configuration Files

Ships are defined in JSON format (`ship_configs.json` or `robust_ship_configs.json`):

```json
{
  "ships": [
    {
      "name": "MV Atlantic Explorer",
      "mmsi": 123456789,
      "lat": 41.234567,
      "lon": -70.123456,
      "speed": 12.5,
      "course": 045.0,
      "heading": 045.0,
      "status": "Under way using engine",
      "ship_type": "Cargo",
      "length": 200,
      "width": 25,
      "draft": 8.5,
      "destination": "Port of Boston",
      "waypoints": [
        [41.240000, -70.110000],
        [41.250000, -70.095000],
        [41.260000, -70.080000]
      ]
    }
  ]
}
```

### SDR Transmission Settings

Configure transmission parameters in the application:

```python
# AIS Channel A (Primary)
frequency = 161975000  # Hz
sample_rate = 2000000  # 2 MHz
gain = 30             # dB (adjust based on hardware)

# AIS Channel B (Secondary)
frequency = 162025000  # Hz
# AIS Channel B (Secondary)
frequency = 162025000  # Hz
sample_rate = 2000000  # 2 MHz
gain = 30             # dB
```

### Signal Presets Available
- **AIS_STANDARD**: Default configuration for testing
- **AIS_HIGH_POWER**: Increased gain for range testing  
- **AIS_PRECISION**: Lower power for controlled environments

---

## 🎮 User Interface Guide

### Main Application Window

#### Tabs Overview
1. **Ship Simulation**: Manage fleet, add/edit vessels, start simulation
2. **Transmission Log**: Monitor AIS messages and transmission status
3. **Map View**: Interactive mapping with real-time ship visualization
4. **Signal Config**: Configure SDR transmission parameters

#### Interface Features
- **Fullscreen Mode**: Press `F11` for immersive view
- **Resizable Panels**: Adjust interface layout for different screens
- **Status Indicators**: Real-time feedback on simulation and transmission state

### Ship Simulation Tab

#### Ship Management
- **Ship List**: View all configured vessels with MMSI, position, and status
- **Add Ship**: Create new vessel with comprehensive parameter dialog
- **Edit Ship**: Modify existing ship configuration and waypoints
- **Delete Ship**: Remove vessels from simulation fleet

#### Ship Configuration Dialog
```
Basic Info:       Navigation:           Physical:
- Name           - Latitude            - Ship Type
- MMSI           - Longitude           - Length/Beam
- Destination    - Course/Speed        - Status
- Flag Country   - Heading             - Turn Rate

Waypoints:
- Interactive map for waypoint selection
- Manual coordinate entry
- Up to 20 waypoints per ship
- Automatic route planning
```

#### Simulation Controls
- **Signal Preset**: Choose transmission configuration
- **Simulation Interval**: Set update frequency (1-60 seconds)
- **Ship Selection**: Choose which ships to simulate
- **Real-time Status**: Monitor simulation progress

### Map View Tab

#### Online Mode (Default)
- **Live Maps**: OpenStreetMap, Google Normal/Satellite
- **Global Coverage**: Worldwide mapping with zoom levels 1-19
- **Search Function**: Find locations by name or coordinates
- **Real-time Updates**: Live ship tracking and movement

#### Custom Mode (Offline)
- **Upload Charts**: Import nautical charts or custom imagery
- **Calibration System**: Define coordinate reference points
- **Offline Operation**: No internet required after setup
- **Precision Navigation**: Use official charts for accuracy

#### Map Controls
```
Track Management:    Display Options:     Navigation:
- History Length     - Ship Names         - Pan/Zoom
- Show/Hide Trails   - Speed Vectors      - Center on Fleet
- Clear All Tracks   - Waypoint Markers   - Search Locations
```

---

## 🔧 Advanced Technical Details

### AIS Message Structure

SIREN generates ITU-R M.1371-5 compliant AIS messages:

```
Message Type 1/2/3 (Position Report):
┌─────────────────────────────────────────────────────────┐
│ Field           │ Bits │ Description                    │
├─────────────────────────────────────────────────────────┤
│ Message Type    │ 6    │ 1, 2, or 3                    │
│ Repeat          │ 2    │ Repeat indicator               │
│ MMSI            │ 30   │ Maritime Mobile Service ID     │
│ Navigation      │ 4    │ Navigation status              │
│ Rate of Turn    │ 8    │ Turn rate indicator            │
│ Speed over Grd  │ 10   │ Speed in 1/10 knot units      │
│ Position Accur  │ 1    │ Position accuracy flag         │
│ Longitude       │ 28   │ Longitude in 1/10000 minutes   │
│ Latitude        │ 27   │ Latitude in 1/10000 minutes    │
│ Course over Grd │ 12   │ Course in 1/10 degree units   │
│ True Heading    │ 9    │ Heading in degrees             │
│ Time Stamp      │ 6    │ UTC second                     │
│ Special Maneuv  │ 2    │ Special maneuver indicator     │
│ Spare           │ 3    │ Spare bits                     │
│ RAIM flag       │ 1    │ RAIM flag                      │
│ Radio Status    │ 19   │ Radio status                   │
└─────────────────────────────────────────────────────────┘
Total: 168 bits
```

### Waypoint Navigation System

#### Navigation Mathematics
```python
# Great-circle distance calculation (Haversine formula)
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0  # Earth's radius in kilometers
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return R * c

# Initial compass bearing calculation
def calculate_bearing(point1, point2):
    lat1, lon1 = radians(point1[0]), radians(point1[1])
    lat2, lon2 = radians(point2[0]), radians(point2[1])
    dlon = lon2 - lon1
    
    y = sin(dlon) * cos(lat2)
    x = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlon)
    bearing = atan2(y, x)
    return (degrees(bearing) + 360) % 360
```

#### Waypoint Detection & Progression
- **Detection Radius**: 1.1km (configurable via `waypoint_radius`)
- **Course Updates**: Automatic bearing calculation to next waypoint
- **Position Updates**: Mercator projection with latitude correction
- **Physics Model**: Constant speed with realistic turn rates

### SDR Transmission Pipeline

#### Signal Generation Process
```
1. AIS Data → Binary Encoding → 6-bit ASCII → NMEA Sentence
2. NMEA → HDLC Framing → Bit Stuffing → NRZI Encoding  
3. NRZI → GMSK Modulation → Digital Filter → DAC Output
4. Baseband → RF Upconversion → Antenna Transmission
```

#### Supported Hardware
| Device | Driver | Frequency Range | Sample Rate | TX Power |
|--------|--------|----------------|-------------|----------|
| **HackRF One** | `hackrf` | 1MHz - 6GHz | 8-20 MHz | 10-63 dB |
| **LimeSDR** | `limesuite` | 100kHz - 3.8GHz | 0.1-61.44 MHz | Variable |
| **USRP B200** | `uhd` | 70MHz - 6GHz | Up to 56 MHz | Software controlled |
| **PlutoSDR** | `plutosdr` | 325MHz - 3.8GHz | Up to 20 MHz | -89 to 0 dBm |

---

## 🧪 Testing & Validation

### Built-in Test Suite

Run comprehensive tests to verify functionality:

```bash
# Test waypoint navigation
python test_waypoint_navigation.py

# Test AIS message encoding
python -c "
from siren.protocol.ais_encoding import build_ais_payload
fields = {'msg_type': 1, 'mmsi': 123456789, 'lat': 41.0, 'lon': -70.0}
payload, fill = build_ais_payload(fields)
print(f'AIS Payload: {payload}')
"

# Test SDR hardware (if available)
SoapySDRUtil --find
```

### Manual Testing Procedures

#### 1. Ship Movement Validation
```bash
# Create test ship with waypoints
# Start simulation with 5-second intervals
# Verify ships move toward waypoints
# Check course changes at waypoint transitions
```

#### 2. AIS Message Validation
```bash
# Monitor transmitted messages with AIS receiver
# Verify MMSI, position, course, speed accuracy
# Check message timing and channel alternation
# Validate NMEA checksum calculation
```

#### 3. Map Integration Testing
```bash
# Online maps: Test with different zoom levels
# Custom maps: Upload and calibrate test chart
# Waypoint selection: Click-to-add functionality
# Ship tracking: Real-time position updates
```

### Performance Benchmarks

| Operation | Target | Typical Performance |
|-----------|--------|-------------------|
| **Ship Movement Calculation** | <5ms per ship | ~1ms average |
| **AIS Message Generation** | <10ms per message | ~2ms average |
| **Map Update Rate** | 10+ FPS | 30+ FPS typical |
| **SDR Transmission Latency** | <50ms | ~20ms average |
| **Waypoint Detection** | <1ms | ~0.3ms average |

---

## 🛡️ Security, Safety & Legal

### Regulatory Compliance

**CRITICAL**: AIS transmission is regulated by maritime and telecommunications law.

#### Legal Requirements
- **Radio License**: Amateur radio, maritime mobile, or experimental license required
- **Frequency Authorization**: AIS frequencies (161.975/162.025 MHz) are protected
- **Geographic Compliance**: Check local regulations before transmission
- **Power Limits**: Adhere to jurisdictional RF power restrictions

#### Safe Operation Guidelines
```python
SAFE_OPERATION = {
    'environment': 'RF-shielded lab or anechoic chamber',
    'power_level': 'Minimum necessary for testing',
    'coordination': 'Notify maritime authorities of testing',
    'monitoring': 'Watch for interference with real traffic',
    'duration': 'Limit transmission time to testing needs'
}
```

### Security Research Applications
- **Vulnerability Assessment**: Study AIS security weaknesses
- **Spoofing Detection**: Develop detection algorithms
- **Maritime Cybersecurity**: Train security professionals
- **Protocol Analysis**: Research AIS protocol implementations

### Ethical Use Guidelines
✅ **Acceptable Uses:**
- Academic research and education
- Cybersecurity training and awareness
- Maritime safety system testing
- Protocol development and debugging

❌ **Prohibited Uses:**
- Interference with live maritime traffic
- Identity spoofing for malicious purposes
- Disruption of navigation safety systems
- Commercial operation without proper licensing

---

## 🔍 Troubleshooting Guide

### Installation Issues

#### Python Dependencies
```bash
# Check Python version
python --version  # Requires 3.8+

# Verify critical packages
python -c "import tkinter; print('tkinter: OK')"
python -c "import tkintermapview; print('maps: OK')"
python -c "from PIL import Image; print('images: OK')"

# Install missing packages
pip install tkintermapview pillow requests
```

#### SDR Driver Issues
```bash
# Test SoapySDR installation
SoapySDRUtil --find

# List available devices
SoapySDRUtil --probe

# Check device permissions (Linux)
sudo usermod -a -G plugdev $USER  # Logout/login required
```

### Common Issues & Quick Fixes

#### Application Won't Start
```bash
# Check Python version
python --version  # Must be 3.8+

# Verify tkinter installation
python -c "import tkinter; tkinter.Tk().destroy(); print('tkinter: OK')"

# Check for conflicting packages
pip list | grep -i tk
```

#### Ships Not Moving
- **Verify Selection**: Ensure ships are selected in the ship list
- **Check Waypoints**: Ships need waypoints to have movement destinations
- **Simulation Status**: Confirm "Start Simulation" was clicked
- **Interval Setting**: Very high intervals (>300s) may appear static

#### Map Display Issues
```bash
# Online maps: Check internet connection
curl -I https://tile.openstreetmap.org/1/0/0.png

# Custom maps: Verify image format and calibration
file your_custom_map.png  # Should show valid image format
```

#### SDR Transmission Problems
```bash
# Check device permissions (Linux/macOS)
groups $USER | grep -E "(plugdev|dialout)"

# Verify device detection
SoapySDRUtil --probe="driver=hackrf"  # Replace with your device

# Test signal generation (without transmission)
python -c "
from siren.transmission.production_transmitter import ProductionTransmitter
tx = ProductionTransmitter()
print('✅ Transmitter initialized successfully')
"
```

#### Ship Simulation Problems
- **Ships Not Moving**: Check waypoint configuration and simulation selection
- **Wrong Positions**: Verify latitude/longitude format (decimal degrees)
- **Performance Issues**: Reduce number of simulated ships or map complexity

### Debug Mode

Enable detailed logging:
```python
# In ais_main_modular.py, add:
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Log Files

Application logs are written to:
- **Windows**: `%APPDATA%\SIREN\logs\`
- **macOS**: `~/Library/Logs/SIREN/`
- **Linux**: `~/.local/share/SIREN/logs/`

---

## 📁 Project Structure

### Core Application Files
```
nato_navy/
├── ais_main_modular.py          # Main application entry point
├── ship_configs.json            # Default ship configurations
├── robust_ship_configs.json     # Extended ship fleet configurations
└── README.md                    # This comprehensive guide

├── siren/                       # Modular SIREN system
│   ├── __init__.py
│   ├── config/                  # Configuration management
│   │   ├── settings.py
│   │   └── __init__.py
│   ├── protocol/                # AIS protocol implementation
│   │   ├── ais_encoding.py      # AIS message encoding
│   │   └── __init__.py
│   ├── ships/                   # Ship simulation
│   │   ├── ais_ship.py          # Individual ship class
│   │   ├── ship_manager.py      # Fleet management
│   │   └── __init__.py
│   ├── transmission/            # SDR transmission
│   │   ├── production_transmitter.py  # Production AIS transmission
│   │   ├── sdr_controller.py    # SDR device management
│   │   └── __init__.py
│   ├── simulation/              # Simulation engine  
│   │   ├── simulation_controller.py  # Simulation management
│   │   └── __init__.py
│   ├── map/                     # Mapping and visualization
│   │   ├── visualization.py     # Map display and ship tracking
│   │   ├── custom_map.py        # Custom chart support
│   │   └── __init__.py
│   ├── ui/                      # User interface
│   │   ├── main_window.py       # Primary GUI window
│   │   ├── ship_dialogs.py      # Ship configuration dialogs
│   │   └── __init__.py
│   └── utils/                   # Utility functions
│       ├── navigation.py        # Navigation calculations
│       └── __init__.py

├── hybrid_maritime_ais/         # Production AIS system
│   ├── hybrid_maritime_ais.py   # Command-line AIS transmitter
│   ├── maritime_ais_config.json # Production configuration
│   ├── requirements.txt         # Production dependencies
│   └── README.md               # Production system guide

├── transmission/                # Legacy transmission modules
│   ├── ais_protocol.py         # Low-level AIS implementation
│   ├── ais_transmitter.py      # Direct SDR transmission
│   └── requirements.txt        # Transmission dependencies

└── debug/                      # Development and testing
    ├── maritime_decoder.py     # AIS message decoder
    └── maritime_transmitter.py # Testing transmitter
```

### Key Dependencies
```
Core (Required):
- tkintermapview  # Interactive mapping
- pillow         # Image processing  
- requests       # HTTP/geocoding

SDR Transmission (Optional):
- SoapySDR       # SDR abstraction layer
- numpy          # Signal processing

Development (Optional):
- pytest         # Unit testing
- matplotlib     # Signal visualization
```

---

## 🧪 Testing and Validation

### Unit Tests
```bash
# Run basic tests
python -m pytest test_modular.py

# Test ship movement
python test_ship_movement.py

# Validate AIS message generation
python test_ais_encoding.py
```

### Integration Tests
```bash
# Test full simulation workflow
python integration_test.py

# Validate map functionality
python test_map_integration.py
```

### Performance Benchmarks
```bash
# Ship simulation performance
python benchmark_simulation.py

# Memory usage analysis
python benchmark_memory.py
```

---

## ⚡ Quick Reference

### Essential Commands
```bash
# Start application
python ais_main_modular.py

# Run tests
python test_modular.py
python test_production_integration.py

# Check SDR devices
SoapySDRUtil --find

# Production AIS transmission
cd hybrid_maritime_ais/
python hybrid_maritime_ais.py --mmsi 123456789 --lat 41.0 --lon -70.0
```

### Default Configuration
```python
# AIS Frequencies
AIS_CHANNEL_A = 161975000  # Hz (Primary)
AIS_CHANNEL_B = 162025000  # Hz (Secondary)

# Ship Defaults
DEFAULT_SPEED = 10.0       # knots
DEFAULT_COURSE = 0.0       # degrees (North)
WAYPOINT_RADIUS = 1.1      # km (detection threshold)

# Simulation Settings
MIN_INTERVAL = 1           # seconds
MAX_INTERVAL = 3600        # seconds (1 hour)
DEFAULT_INTERVAL = 30      # seconds
```

### File Locations
```bash
# Configuration
ship_configs.json                    # Default ships
robust_ship_configs.json            # Extended fleet
siren/config/settings.py            # System settings

# Transmission
siren/transmission/production_transmitter.py  # Main transmitter
hybrid_maritime_ais/hybrid_maritime_ais.py   # Production CLI

# Maps & UI
siren/map/visualization.py          # Map display
siren/ui/main_window.py             # Main interface
```

---

## 📚 API Reference

### Core Classes

#### `AISShip`
```python
class AISShip:
    def __init__(self, name, mmsi, lat, lon, **kwargs):
        """Initialize ship with basic parameters"""
    
    def move(self, elapsed_time):
        """Update ship position based on elapsed time"""
    
    def get_ais_fields(self):
        """Generate AIS message fields"""
```

#### `ShipManager`
```python
class ShipManager:
    def add_ship(self, ship):
        """Add ship to managed fleet"""
    
    def move_all_ships(self, elapsed, selected_indices=None):
        """Move selected ships based on elapsed time"""
    
    def get_selected_ships(self, indices):
        """Get ships by index list"""
```

#### `MapVisualization`
```python
class MapVisualization:
    def update_map(self, force=False, selected_ship_indices=None):
        """Update ship positions on map"""
    
    def set_selected_ships(self, selected_ship_indices):
        """Set which ships to display"""
```

### Utility Functions

#### AIS Encoding
```python
def build_ais_payload(fields):
    """Generate AIS binary payload from ship data"""

def compute_checksum(sentence):
    """Calculate NMEA sentence checksum"""
```

#### Navigation
```python
def calculate_initial_compass_bearing(lat1, lon1, lat2, lon2):
    """Calculate bearing between two points"""

def move_towards_waypoint(ship, waypoint, elapsed_time):
    """Move ship towards target waypoint"""
```

---

## 🤝 Contributing

### Development Setup
```bash
# Clone repository
git clone https://github.com/your-org/nato_navy.git
cd nato_navy

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows

# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

### Code Style
- **PEP 8**: Follow Python style guidelines
- **Type Hints**: Use type annotations where appropriate
- **Docstrings**: Document all public functions and classes
- **Testing**: Write tests for new functionality

### Submission Process
1. **Fork Repository**: Create personal fork
2. **Feature Branch**: Create branch for changes
3. **Documentation**: Update relevant documentation
4. **Testing**: Ensure all tests pass
5. **Pull Request**: Submit with clear description

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

### Third-Party Licenses
- **tkintermapview**: MIT License
- **Pillow**: HPND License
- **SoapySDR**: Boost Software License

---

## 📞 Support

### Documentation
- **User Guide**: This README
- **Custom Maps**: [CUSTOM_MAP_GUIDE.md](CUSTOM_MAP_GUIDE.md)
- **API Documentation**: `/docs/api/`
- **Examples**: `/examples/` directory

### Community
- **Issues**: [GitHub Issues](https://github.com/your-org/nato_navy/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/nato_navy/discussions)
- **Wiki**: [Project Wiki](https://github.com/your-org/nato_navy/wiki)

### Academic Support
- **Institution**: Louisiana State University
- **Author**: Peyton Andras
- **Research Group**: Maritime Cybersecurity Lab
- **Email**: research@example.edu

---

## 🎯 Roadmap

### Version 2.0 (Planned)
- **Enhanced AIS Messages**: Support for Type 4, 5, and other message types
- **Multi-Frequency**: Simultaneous transmission on multiple channels
- **Weather Integration**: Dynamic weather effects on ship movement
- **Collision Avoidance**: Realistic ship behavior near other vessels

### Version 2.1 (Future)
- **3D Visualization**: Three-dimensional ship representation
- **Tidal Effects**: Current and tide influence on ship movement
- **Harbor Simulation**: Detailed port and harbor operations
- **Multi-User**: Collaborative simulation environments

### Long-Term Goals
- **Machine Learning**: AI-driven ship behavior patterns
- **Cloud Integration**: Web-based simulation platform
- **VR/AR Support**: Immersive visualization capabilities
- **Real-World Integration**: Interface with actual AIS networks

---

## 🏆 Acknowledgments

### Project Contributors
- **Lead Developer**: Peyton Andras, Louisiana State University
- **Maritime Expertise**: [Maritime Industry Partners]
- **Cybersecurity Research**: [Academic Collaborators]
- **Testing and Validation**: [Student Research Teams]

### Open Source Libraries
- **tkintermapview**: Interactive mapping capabilities
- **Pillow**: Image processing and manipulation
- **SoapySDR**: Software Defined Radio abstraction
- **tkinter**: Cross-platform GUI framework

### Research Support
- **Louisiana State University**: Academic institutional support
- **Maritime Industry**: Real-world validation and requirements
- **Cybersecurity Community**: Security testing and feedback

---

**SIREN: Spoofed Identification & Real-time Emulation Node**  
*Advanced Maritime AIS Simulation Platform*  
*© 2025 Louisiana State University*
