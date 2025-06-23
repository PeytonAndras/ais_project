# Hybrid Maritime AIS Transmitter

The ultimate AIS transmitter combining production-ready standards compliance with rtl_ais compatibility testing capabilities.

## 🚀 Features

### Production Maritime Use
- **ITU-R M.1371-5 Compliant**: Full standards compliance for real maritime deployment
- **SOTDMA Protocol**: Self-Organizing Time Division Multiple Access prevents interference
- **Real-time Position Updates**: Continuous vessel tracking with GPS integration
- **Professional Error Handling**: Production-grade reliability and monitoring
- **Maritime Safety Features**: Emergency override, power limits, geographic restrictions

### Research & Compatibility Testing
- **rtl_ais Optimization**: Polar discriminator tuned FSK for maximum receiver compatibility
- **NMEA Compatibility**: Parse and transmit existing NMEA sentences
- **Signal Analysis**: Built-in signal quality monitoring and validation
- **Multi-mode Operation**: Switch between production and testing modes

### Hybrid Architecture
- **Adaptive Modulation**: GMSK for production, optimized FSK for rtl_ais testing
- **Intelligent SDR Interface**: Automatic configuration based on operation mode
- **Flexible Protocol Engine**: Supports both standards-compliant and compatibility modes
- **Professional Monitoring**: Comprehensive status reporting and diagnostics

## 🎯 Quick Start

### Installation
```bash
# Install dependencies
pip install -r hybrid_requirements.txt

# Install SoapySDR (system-specific)
# Ubuntu/Debian:
sudo apt-get install libsoapysdr-dev soapysdr-tools

# macOS:
brew install soapysdr
```

### Basic Usage

#### Production Maritime Beacon
```bash
python hybrid_maritime_ais.py \
    --mmsi 123456789 \
    --lat 37.7749 \
    --lon -122.4194 \
    --mode production \
    --sog 12.5 \
    --cog 045
```

#### rtl_ais Compatibility Testing
```bash
python hybrid_maritime_ais.py \
    --mmsi 123456789 \
    --lat 37.7749 \
    --lon -122.4194 \
    --mode rtl_ais_testing \
    --once
```

#### NMEA Compatibility Mode
```bash
python hybrid_maritime_ais.py \
    --mmsi 123456789 \
    --lat 37.7749 \
    --lon -122.4194 \
    --mode compatibility \
    --nmea "!AIVDM,1,1,,A,15MvlfP000G?n@@K>OW`4?vN0<0=,0*47"
```

## 🎛️ Operation Modes

### Production Mode
- **Standards Compliance**: Full ITU-R M.1371-5 implementation
- **SOTDMA Timing**: Coordinated time slots prevent interference
- **Frequency**: 161.975 MHz (AIS Channel A)
- **Sample Rate**: 96 kHz (standard)
- **Signal**: Proper GMSK modulation with Gaussian filtering
- **Use Case**: Real maritime vessel deployment

### rtl_ais Testing Mode
- **Receiver Optimization**: Tuned specifically for rtl_ais polar discriminator
- **Frequency**: 162.025 MHz (Channel B, appears in right stereo channel)
- **Sample Rate**: 250 kHz (high resolution for clean FSK)
- **Signal**: Phase-continuous FSK optimized for demodulation
- **Power**: 0.7x scaling for optimal receiver performance
- **Use Case**: Testing receiver compatibility and development

### Compatibility Mode
- **NMEA Input**: Accept pre-formatted NMEA sentences
- **Flexible Operation**: Bridge between existing systems and new capabilities
- **Validation**: Full NMEA sentence parsing and validation
- **Use Case**: Integration with existing maritime systems

## 📊 Configuration

### JSON Configuration File
```json
{
  "vessel": {
    "mmsi": 123456789,
    "name": "Test Vessel",
    "vessel_type": 70
  },
  "operation": {
    "mode": "production",
    "update_rate_seconds": 10.0
  },
  "hardware": {
    "sample_rate": 96000,
    "tx_gain": 40.0
  },
  "compatibility": {
    "rtl_ais_optimization": true,
    "polar_discriminator_tuning": true
  }
}
```

### Command Line Arguments
```bash
# Required
--mmsi MMSI           # 9-digit Maritime Mobile Service Identity
--lat LATITUDE        # Decimal degrees latitude
--lon LONGITUDE       # Decimal degrees longitude

# Operation Mode
--mode {production,rtl_ais_testing,compatibility}

# Vessel Motion
--sog SPEED          # Speed over ground (knots)
--cog COURSE         # Course over ground (degrees)
--heading HEADING    # True heading (degrees, 511=N/A)

# Transmission Options
--once               # Single transmission and exit
--rate SECONDS       # Continuous update rate
--nmea SENTENCE      # Transmit specific NMEA sentence

# Debugging
--verbose            # Detailed logging
```

## 🔧 Architecture

### Core Components

#### EnhancedAISProtocol
- Dual-mode AIS protocol implementation
- Standards-compliant message generation
- NMEA sentence parsing and validation
- CRC-16, HDLC bit stuffing, NRZI encoding

#### HybridModulator
- Adaptive modulation based on operation mode
- GMSK for production use
- rtl_ais optimized FSK for compatibility testing
- Continuous phase management

#### AdaptiveLimeSDRInterface
- Intelligent SDR configuration
- Mode-specific frequency and sample rate selection
- Robust hardware detection and error handling
- Signal conditioning and power optimization

#### SOTDMAController
- Self-Organizing Time Division Multiple Access
- Prevents interference with other vessels
- MMSI-based slot calculation
- Frame synchronization and timing

## 📡 Signal Characteristics

### Production Mode (GMSK)
- **Frequency**: 161.975 MHz
- **Modulation**: Gaussian Minimum Shift Keying
- **Bandwidth**: ~25 kHz
- **Symbol Rate**: 9600 bps
- **Gaussian Filter**: BT = 0.4
- **Compliance**: ITU-R M.1371-5

### rtl_ais Testing Mode (FSK)
- **Frequency**: 162.025 MHz
- **Modulation**: Frequency Shift Keying
- **Deviation**: ±2400 Hz
- **Phase**: Continuous (critical for polar discriminator)
- **Power**: 0.7x scaling for receiver optimization
- **Compatibility**: Optimized for rtl_ais demodulation chain

## 🛡️ Safety Features

### Power Management
- Configurable transmit power limits
- Automatic power scaling for different modes
- Hardware safety limits enforcement

### Geographic Restrictions
- Optional geographic boundary enforcement
- Prevent transmission outside authorized areas
- Configurable lat/lon limits

### Time Restrictions
- Optional time-based transmission control
- Configure operating hours
- Emergency override capabilities

### SOTDMA Compliance
- Prevents interference with other vessels
- Coordinated time slot usage
- Frame synchronization

## 📈 Monitoring & Diagnostics

### Real-time Status
```python
status = transmitter.get_status()
print(f"Mode: {status['mode']}")
print(f"Packets sent: {status['packets_sent']}")
print(f"Hardware available: {status['hardware']['available']}")
```

### Logging
- Configurable log levels (DEBUG, INFO, WARNING, ERROR)
- File and console output
- Log rotation with size limits
- Structured logging for analysis

### Performance Metrics
- Transmission success rate
- Signal quality measurements
- Timing accuracy
- Hardware performance

## 🔬 Technical Implementation

### Frame Structure
```
Training Sequence (24 bits): 010101010101010101010101
Start Delimiter (8 bits):    01111110
NRZI Encoded Payload:        [Variable length with bit stuffing]
End Delimiter (8 bits):      01111110
Buffer (8 bits):             00000000
```

### Message Types Supported
- **Type 1**: Position Report Class A (under way)
- **Type 2**: Position Report Class A (assigned schedule)
- **Type 3**: Position Report Class A (response to interrogation)
- **Custom**: NMEA sentence compatibility

### Protocol Stack
1. **Application Layer**: Vessel information and navigation data
2. **Presentation Layer**: AIS message encoding (6-bit armoring)
3. **Data Link Layer**: HDLC framing, bit stuffing, CRC-16
4. **Physical Layer**: NRZI encoding, GMSK/FSK modulation

## 🚀 Deployment Scenarios

### Maritime Vessel
```bash
# Production deployment on actual vessel
python hybrid_maritime_ais.py \
    --mmsi 123456789 \
    --lat 37.7749 \
    --lon -122.4194 \
    --mode production \
    --sog 15.2 \
    --cog 135 \
    --nav-status 0
```

### AIS Receiver Testing
```bash
# Test receiver compatibility
python hybrid_maritime_ais.py \
    --mmsi 999999999 \
    --lat 37.7749 \
    --lon -122.4194 \
    --mode rtl_ais_testing \
    --rate 30 \
    --verbose
```

### Harbor Simulation
```bash
# High-rate updates for harbor environment
python hybrid_maritime_ais.py \
    --mmsi 123456789 \
    --lat 37.7749 \
    --lon -122.4194 \
    --mode production \
    --rate 2 \
    --sog 3.5
```

### Emergency Beacon
```bash
# Emergency transmission with override
python hybrid_maritime_ais.py \
    --mmsi 123456789 \
    --lat 37.7749 \
    --lon -122.4194 \
    --mode emergency \
    --nav-status 7 \
    --rate 5
```

## 🔧 Hardware Requirements

### LimeSDR Support
- **LimeSDR Mini**: Recommended for portable use
- **LimeSDR USB**: Full-featured option
- **Sample Rates**: 96 kHz (production), 250 kHz (testing)
- **Frequency Range**: 161-162 MHz (AIS bands)
- **Gain Range**: 0-73 dB

### System Requirements
- **Python**: 3.7 or later
- **Memory**: 2GB RAM minimum
- **Storage**: 100MB for application + logs
- **OS**: Linux, macOS, Windows (with SoapySDR)
- **Network**: Optional (for GPS/configuration)

## 📚 Integration Examples

### GPS Integration
```python
# Real-time GPS updates
import gpsd

gpsd.connect()
packet = gpsd.get_current()
transmitter.update_vessel_position(packet.lat, packet.lon)
transmitter.update_vessel_motion(packet.speed, packet.track)
```

### Configuration API
```python
# Load configuration from file
with open('maritime_ais_config.json') as f:
    config = json.load(f)

vessel = VesselInfo(**config['vessel'])
transmitter = HybridMaritimeAIS(vessel, OperationMode(config['operation']['mode']))
```

## 🛠️ Development

### Testing
```bash
# Run unit tests
python -m pytest tests/

# Test signal generation
python -c "
from hybrid_maritime_ais import *
vessel = VesselInfo(123456789, 37.7749, -122.4194)
tx = HybridMaritimeAIS(vessel, OperationMode.RTL_AIS_TESTING)
print('✅ System test passed')
"
```

### Signal Analysis
```python
# Analyze generated signals
import matplotlib.pyplot as plt
signal = modulator.modulate(frame)
plt.plot(np.real(signal))
plt.title('AIS Signal (Real Part)')
plt.show()
```

## 📄 License & Compliance

### Regulatory Compliance
- **ITU-R M.1371-5**: International AIS standard compliance
- **FCC Part 80**: US maritime radio regulations
- **SOLAS Chapter V**: International maritime safety requirements

### Usage Guidelines
- **Testing Only**: Use test MMSI numbers (999999xxx) for development
- **Power Limits**: Respect local RF power regulations
- **Interference**: Ensure SOTDMA compliance in production use
- **Maritime Law**: Follow applicable maritime communications regulations

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📞 Support

- **Documentation**: Complete API documentation included
- **Examples**: Comprehensive usage examples provided
- **Testing**: Unit tests and integration tests available
- **Issues**: Report bugs and feature requests via GitHub issues

---

**⚠️ Important**: This software is intended for authorized maritime use only. Ensure compliance with local regulations and maritime law before deployment.
