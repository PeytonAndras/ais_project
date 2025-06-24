# SIREN: Spoofed Identification & Real-time Emulation Node

## Advanced AIS Maritime Simulation and Transmission System

**SIREN** is a comprehensive Automatic Identification System (AIS) simulation and transmission platform designed for maritime training, research, and cybersecurity applications. The system provides real-time ship simulation, AIS message generation, and SDR-based transmission capabilities with both online and offline mapping support.

---

## 🚢 Features Overview

### Core Capabilities
- **Real-Time AIS Simulation**: Simulate multiple ships with realistic movement patterns
- **SDR Transmission**: Broadcast AIS messages using Software Defined Radio
- **Interactive Mapping**: Online maps with tkintermapview or custom nautical charts
- **Waypoint Navigation**: Ships follow predefined routes with automatic course corrections
- **Multi-Ship Management**: Handle fleets of vessels with individual configurations
- **NMEA Message Generation**: Standards-compliant AIS Type 1, 2, and 3 messages

### Advanced Features
- **Custom Map Support**: Upload and calibrate your own nautical charts for offline operation
- **Real-Time Visualization**: Ships move on maps synchronized with simulation
- **Selective Simulation**: Choose which ships to simulate and transmit
- **Signal Presets**: Pre-configured transmission parameters for different scenarios
- **Ship Tracking**: Historical trails and real-time position updates
- **Fullscreen Mode**: Immersive interface for training and demonstration

---

## 📋 System Requirements

### Minimum Requirements
- **OS**: Windows 10, macOS 10.14, or Linux (Ubuntu 18.04+)
- **Python**: 3.8 or higher
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 2GB free space
- **Graphics**: Hardware-accelerated graphics recommended

### For SDR Transmission
- **SDR Hardware**: LimeSDR, HackRF, USRP, or compatible device
- **Drivers**: SoapySDR with appropriate device drivers
- **Licensing**: Appropriate radio operator license for transmissions

### For Map Functionality
- **Internet**: Required for online maps (optional for custom maps)
- **Display**: 1920x1080 minimum resolution recommended

---

## 🚀 Quick Start

### 1. Installation

#### Clone Repository
```bash
git clone https://github.com/your-org/nato_navy.git
cd nato_navy
```

#### Install Dependencies
```bash
# Essential packages
pip install tkintermapview pillow

# Optional SDR support
pip install SoapySDR

# All dependencies
pip install -r requirements.txt
```

#### For SDR Hardware Support
```bash
# Ubuntu/Debian
sudo apt-get install soapysdr-tools soapysdr-module-all

# macOS with Homebrew
brew install soapysdr

# Windows
# Download SoapySDR installers from official website
```

### 2. First Launch
```bash
python ais_main_modular.py
```

### 3. Basic Ship Simulation
1. **Add Ships**: Click "Add Ship" to create vessels
2. **Set Waypoints**: Use the waypoints tab to plan routes
3. **Start Simulation**: Select ships and click "Start Simulation"
4. **View on Map**: Switch to Map View tab to see ships moving

---

## 🗺️ Map Modes

### Online Maps (Default)
- **Requires Internet**: Live tile downloads from OpenStreetMap
- **Global Coverage**: Worldwide mapping capability
- **Real-Time Updates**: Latest satellite imagery and chart updates
- **Search Function**: Find locations by name or coordinates

### Custom Maps (Offline)
- **Upload Charts**: Use your own nautical charts or satellite imagery
- **Offline Operation**: No internet required after setup
- **High Precision**: Use official nautical charts for accuracy
- **Calibration System**: Map pixel coordinates to real-world positions

**📖 For detailed custom map instructions, see [CUSTOM_MAP_GUIDE.md](CUSTOM_MAP_GUIDE.md)**

---

## 🛠️ Configuration

### Ship Configuration

Ships are defined in `ship_configs.json` or `robust_ship_configs.json`:

```json
{
  "name": "MV Atlantic Explorer",
  "mmsi": 123456789,
  "lat": 41.234567,
  "lon": -70.123456,
  "speed": 12.5,
  "course": 045,
  "heading": 045,
  "status": "Under way using engine",
  "ship_type": "Cargo",
  "length": 200,
  "width": 25,
  "destination": "Port of Boston",
  "waypoints": [
    [41.240000, -70.110000],
    [41.250000, -70.095000]
  ]
}
```

### Signal Presets

Transmission parameters in signal configuration:

```python
signal_presets = [
    {
        "name": "AIS Channel A (161.975 MHz)",
        "frequency": 161975000,
        "sample_rate": 2000000,
        "gain": 30,
        "channel": "A"
    },
    {
        "name": "AIS Channel B (162.025 MHz)", 
        "frequency": 162025000,
        "sample_rate": 2000000,
        "gain": 30,
        "channel": "B"
    }
]
```

---

## 🎮 User Interface Guide

### Main Application Window

#### Tabs Overview
1. **Ship Management**: Add, edit, and configure vessels
2. **Simulation**: Control simulation parameters and start/stop
3. **Map View**: Interactive mapping with ship visualization
4. **Signal**: Configure transmission parameters (if SDR available)

#### Fullscreen Mode
- **Toggle**: Press `F11` or `Escape`
- **Custom Title Bar**: SIREN branding with window controls
- **Optimized Layout**: Larger fonts and better spacing

### Ship Management Tab

#### Ship List
- **View All Ships**: See configured vessels with key parameters
- **Selection**: Choose ships for simulation
- **Quick Info**: MMSI, speed, course displayed in list

#### Ship Operations
- **Add Ship**: Create new vessel with full configuration
- **Edit Ship**: Modify existing ship parameters
- **Delete Ship**: Remove ships from configuration
- **Save/Load**: Persist configurations to file

### Simulation Tab

#### Controls
- **Signal Preset**: Choose transmission channel and parameters
- **Interval**: Set time between simulation cycles (1-60 seconds)
- **Ship Selection**: Only selected ships will be simulated
- **Start/Stop**: Control simulation state

#### Status Display
- **Simulation Log**: Real-time status messages
- **Ship Count**: Number of ships being simulated
- **Transmission Status**: SDR transmission feedback

### Map View Tab

#### Online Mode Features
- **Location Search**: Find places by name or coordinates
- **Map Types**: OpenStreetMap, Google Normal, Google Satellite
- **Zoom Controls**: Mouse wheel or touch gestures
- **Ship Markers**: Real-time position indicators

#### Custom Mode Features
- **Upload Maps**: Load nautical charts or satellite imagery
- **Calibration**: Map pixel coordinates to geographic positions
- **Waypoint Selection**: Click map to add navigation waypoints
- **Offline Operation**: No internet required

#### Map Controls Panel
- **Track History**: Set number of position points to remember
- **Show Tracks**: Toggle ship trail visibility
- **Center on Ships**: Automatically frame all vessels
- **Clear Tracks**: Remove all historical position data

---

## 🔧 Advanced Configuration

### Environment Variables
```bash
# Set custom configuration directory
export AIS_CONFIG_DIR=/path/to/custom/configs

# Enable debug logging
export AIS_DEBUG=1

# Set default map mode
export AIS_MAP_MODE=custom
```

### Custom Ship Types

Add new ship types by editing the ship type configuration:

```python
SHIP_TYPES = {
    "Custom Research Vessel": 50,
    "Navy Destroyer": 60,
    "Submarine": 70,
    "Research Platform": 80
}
```

### Navigation Behavior

Ships follow waypoints with these behaviors:
- **Automatic Course Calculation**: Bearing computed between waypoints
- **Speed Control**: Maintains configured speed between points
- **Waypoint Tolerance**: Reaches waypoint when within 0.001° (≈100m)
- **Route Completion**: Stops at final waypoint or cycles if configured

---

## 🛡️ Security and Legal Considerations

### Legal Requirements
- **Radio License**: SDR transmission requires appropriate amateur radio or maritime license
- **Frequency Authorization**: Ensure legal authority to transmit on AIS frequencies
- **Geographic Restrictions**: Some areas prohibit AIS spoofing or simulation

### Safety Guidelines
- **Test Environment**: Use only in controlled, isolated environments
- **Power Levels**: Keep transmission power minimal to avoid interference
- **Coordination**: Inform maritime authorities of testing activities
- **Monitoring**: Watch for interference with real maritime traffic

### Security Applications
- **Cybersecurity Training**: Demonstrate AIS vulnerabilities
- **Research**: Study maritime communication security
- **Defense**: Evaluate detection and mitigation techniques
- **Education**: Teach maritime communication protocols

---

## 🔍 Troubleshooting

### Common Issues

#### Application Won't Start
```bash
# Check Python version
python --version  # Should be 3.8+

# Verify dependencies
pip list | grep -i tkinter
pip list | grep -i pillow

# Run with debug output
python ais_main_modular.py --debug
```

#### Map Not Loading
```bash
# Test internet connection for online maps
ping tile.openstreetmap.org

# Verify tkintermapview installation
python -c "import tkintermapview; print('OK')"

# Switch to custom map mode if online fails
# Use Map Mode dropdown in interface
```

#### SDR Issues
```bash
# Test SoapySDR installation
SoapySDRUtil --find

# List available devices
SoapySDRUtil --probe

# Check device permissions (Linux)
sudo usermod -a -G plugdev $USER  # Logout/login required
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
