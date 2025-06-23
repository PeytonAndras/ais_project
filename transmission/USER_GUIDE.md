# AIS Transmitter User Guide

## Table of Contents
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Hardware Setup](#hardware-setup)
- [Basic Usage](#basic-usage)
- [Advanced Features](#advanced-features)
- [Testing and Validation](#testing-and-validation)
- [Troubleshooting](#troubleshooting)
- [Legal and Safety](#legal-and-safety)
- [Technical Reference](#technical-reference)

## Quick Start

### Prerequisites
- LimeSDR Mini or LimeSDR USB
- Python 3.7 or higher
- SoapySDR and LimeSuite drivers
- VHF antenna for 161-162 MHz

### 5-Minute Test
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Test without hardware
python test_basic.py

# 3. Test with LimeSDR (if connected)
python ais_transmitter.py --mmsi 123456789 --lat 37.7749 --lon -122.4194 --once
```

## Installation

### System Requirements
- **Operating System**: Windows, Linux, or macOS
- **Python**: 3.7 or higher
- **RAM**: 512 MB minimum
- **USB**: USB 3.0 port (recommended for LimeSDR)

### Software Installation

#### 1. Install LimeSuite
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install limesuite liblimesuite-dev

# macOS with Homebrew
brew install limesuite

# Windows: Download from LimeMicro website
```

#### 2. Install Python Dependencies
```bash
# Full installation (with all features)
pip install -r requirements.txt

# Minimal installation (testing only)
pip install -r requirements_minimal.txt
```

#### 3. Verify Installation
```bash
# Check SoapySDR installation
SoapySDRUtil --find

# Test basic functionality
python test_basic.py
```

## Hardware Setup

### LimeSDR Connection

#### 1. Connect LimeSDR
1. Connect LimeSDR to USB 3.0 port
2. Wait for drivers to install (Windows)
3. Verify connection: `SoapySDRUtil --find`

#### 2. Antenna Connection
- **LimeSDR Mini**: Use SMA connector for TX
- **LimeSDR USB**: Use SMA connector marked "TX"
- **Frequency**: 161-162 MHz (VHF marine band)
- **Antenna**: Marine VHF antenna or appropriate test antenna

#### 3. Test Hardware
```bash
# Quick hardware test
python debug_hardware.py

# RF output test (monitor with receiver)
python test_cw_simple.py
```

### Safety Considerations
⚠️ **IMPORTANT**: Always test with a dummy load first!
- Use 50Ω RF dummy load for initial testing
- Keep power levels low (start with default 30dB gain)
- Test in RF-shielded environment when possible

## Basic Usage

### Command Line Interface

#### Single Transmission
```bash
# Basic position report
python ais_transmitter.py --mmsi 123456789 --lat 37.7749 --lon -122.4194 --once

# With vessel details
python ais_transmitter.py \
    --mmsi 123456789 \
    --lat 37.7749 \
    --lon -122.4194 \
    --sog 12.5 \
    --cog 045 \
    --heading 047 \
    --once
```

#### Continuous Transmission
```bash
# Basic beacon (transmits every 10 seconds)
python ais_transmitter.py --mmsi 123456789 --lat 37.7749 --lon -122.4194

# Moving vessel simulation
python ais_transmitter.py \
    --mmsi 123456789 \
    --lat 37.7749 \
    --lon -122.4194 \
    --sog 15.0 \
    --cog 090 \
    --course-change 1.0 \
    --speed-change 0.1
```

### Configuration File

Create `config.json`:
```json
{
    "mmsi": 123456789,
    "vessel_name": "Test Vessel",
    "latitude": 37.7749,
    "longitude": -122.4194,
    "speed_over_ground": 12.5,
    "course_over_ground": 45.0,
    "true_heading": 47,
    "frequency": 161975000,
    "tx_gain": 30.0,
    "interval": 10.0
}
```

Use with:
```bash
python ais_transmitter.py --config config.json
```

### All Command Line Options

```bash
python ais_transmitter.py --help

# Key options:
--mmsi          MMSI number (required)
--lat/--lon     Position coordinates (required)
--sog           Speed over ground (knots)
--cog           Course over ground (degrees)
--heading       True heading (degrees)
--frequency     Frequency (161975000 or 162025000)
--gain          TX gain in dB (0-64)
--interval      Transmission interval (seconds)
--once          Single transmission only
--config        Configuration file
--output        Save signal to file instead of transmitting
```

## Advanced Features

### SOTDMA Timing
The transmitter automatically handles SOTDMA (Self-Organizing Time Division Multiple Access) timing:

```python
# Custom SOTDMA configuration
python ais_transmitter.py \
    --mmsi 123456789 \
    --lat 37.7749 \
    --lon -122.4194 \
    --sotdma-slot 150  # Specific slot number
```

### Signal Analysis
```bash
# Analyze generated signal
python signal_analysis.py

# Validate protocol compliance
python ais_validator.py
```

### Frequency Calibration
```bash
# Measure frequency error
python ais_transmitter.py --mmsi 123456789 --lat 37.7749 --lon -122.4194 --calibrate

# Apply PPM correction
python ais_transmitter.py --mmsi 123456789 --lat 37.7749 --lon -122.4194 --ppm-correction 2.5
```

### Custom Message Types
```python
# In Python script
from ais_protocol import AISProtocol

protocol = AISProtocol()

# Create custom Type 4 (Base Station Report)
message = protocol.create_base_station_report(
    mmsi=123456789,
    timestamp=datetime.utcnow(),
    latitude=37.7749,
    longitude=-122.4194
)

signal = protocol.generate_gmsk_signal(message)
```

## Testing and Validation

### Signal Quality Tests

#### 1. Basic Functionality
```bash
python test_basic.py
```
Tests protocol implementation without hardware.

#### 2. Signal Analysis
```bash
python signal_analysis.py
```
Analyzes signal properties:
- GMSK modulation parameters
- Timing accuracy
- Protocol compliance
- Spectrum analysis

#### 3. Hardware Tests
```bash
# Hardware connectivity
python debug_hardware.py

# RF output verification
python test_cw_simple.py

# Force TX enable (if needed)
python force_enable_tx.py
```

### Reception Testing

#### With rtl-ais
```bash
# In one terminal - transmit
python ais_transmitter.py --mmsi 123456789 --lat 37.7749 --lon -122.4194

# In another terminal - receive (if you have RTL-SDR)
rtl_ais -f 161975000 -s 48000 -g 40
```

#### With SDR Software
Use SDR software like:
- **CubicSDR**: General purpose SDR software
- **SDR#**: Windows SDR software  
- **GQRX**: Linux/macOS SDR software

Monitor 161.975 MHz for AIS signals.

### File Output Testing
```bash
# Generate signal file
python ais_transmitter.py \
    --mmsi 123456789 \
    --lat 37.7749 \
    --lon -122.4194 \
    --output test_signal.iq \
    --once

# Analyze the file
python signal_analysis.py --file test_signal.iq
```

## Troubleshooting

### Hardware Issues

#### LimeSDR Not Detected
```bash
# Check USB connection
lsusb | grep Lime  # Linux
system_profiler SPUSBDataType | grep Lime  # macOS

# Check SoapySDR
SoapySDRUtil --find

# Reset connection
python reset_limesdr.py
```

#### No RF Output
1. **Check antenna connection**
2. **Verify frequency** (161.975 MHz)
3. **Increase gain** (try 50-60 dB)
4. **Test with spectrum analyzer**
5. **Run force_enable_tx.py**

#### USB Connection Problems
- Try different USB port
- Use USB 3.0 port if available
- Check USB cable quality
- Restart computer
- Update LimeSuite drivers

### Software Issues

#### Import Errors
```bash
# Install missing dependencies
pip install numpy scipy matplotlib

# For SoapySDR issues
pip install SoapySDR
```

#### Permission Errors (Linux)
```bash
# Add user to dialout group
sudo usermod -a -G dialout $USER
# Logout and login again
```

#### Python Version Issues
- Requires Python 3.7+
- Check: `python --version`
- Use virtual environment if needed

### Signal Issues

#### No Signal Received
1. **Check frequency** (161.975 MHz vs 162.025 MHz)
2. **Verify receiver gain**
3. **Check antenna orientation**
4. **Test with stronger signal**

#### Poor Signal Quality
1. **Check antenna SWR**
2. **Reduce interference sources**
3. **Verify cable connections**
4. **Calibrate frequency**

### Common Error Messages

#### "Device is busy"
- Another program using LimeSDR
- Restart LimeSuite software
- Unplug and reconnect LimeSDR

#### "No LimeSDR devices found"
- Check USB connection
- Install/update drivers
- Run as administrator (Windows)

#### "Stream activation failed"
- Reduce sample rate
- Check USB bandwidth
- Restart application

## Legal and Safety

### Legal Requirements ⚠️

#### Maritime Licensing
- **AIS transmission requires maritime license**
- **Use only assigned MMSI numbers**
- **Comply with local regulations**
- **Maritime Mobile Service license often required**

#### Frequency Allocation
- 161.975 MHz (AIS Channel A)
- 162.025 MHz (AIS Channel B)
- **VHF Maritime Mobile Service only**
- **No amateur radio use**

#### Power Restrictions
- **Typical limit: 2 watts**
- **Class A: 12.5 watts maximum**
- **Class B: 2 watts maximum**
- **Check local regulations**

### Safety Guidelines

#### RF Safety
- **Use dummy load for testing**
- **Keep antennas away from people**
- **Follow SAR guidelines**
- **Use minimum necessary power**

#### Maritime Safety
- **Don't interfere with real maritime traffic**
- **Use test MMSI ranges**
- **Test in RF-shielded environment**
- **Follow collision avoidance rules**

#### Testing Guidelines
- **Use MMSI 123456789 for testing**
- **Test on land with dummy load**
- **Monitor for interference**
- **Stop if causing problems**

### Recommended Test Procedures

1. **Bench Testing**: Use dummy load and spectrum analyzer
2. **Laboratory Testing**: RF-shielded room with controlled environment
3. **Limited Range Testing**: Low power with close-range receiver
4. **Maritime Testing**: Only with proper licensing and coordination

## Technical Reference

### Signal Specifications

#### GMSK Modulation
- **Symbol Rate**: 9600 bps
- **BT Product**: 0.4
- **Deviation**: ±2400 Hz
- **Sample Rate**: 96 kHz (10 samples/symbol)

#### AIS Packet Structure
```
Training Sequence (24 bits) + Start Flag (8 bits) + Data (168 bits) + CRC (16 bits) + End Flag (8 bits)
Total: 224 bits = 23.33 ms transmission time
```

#### Frequencies
- **Channel A**: 161.975 MHz (87B)
- **Channel B**: 162.025 MHz (88B)
- **Channel spacing**: 25 kHz

### Protocol Details

#### SOTDMA Frame Structure
- **Frame Duration**: 60 seconds
- **Total Slots**: 2250
- **Slot Duration**: 26.67 ms
- **Guard Time**: 200 µs

#### Message Types Supported
- **Type 1**: Position Report Class A
- **Type 2**: Position Report Class A (Assigned schedule)
- **Type 3**: Position Report Class A (Response to interrogation)
- **Type 4**: Base Station Report
- **Type 18**: Standard Class B Position Report

### Performance Specifications

#### Timing Accuracy
- **Symbol timing**: ±0.01%
- **Frame timing**: ±1 ms
- **SOTDMA timing**: ±200 µs

#### Signal Quality
- **EVM**: <5% (typical <2%)
- **Spurious emissions**: <-40 dBc
- **Frequency accuracy**: ±10 ppm (±1.6 kHz at VHF)

### API Reference

#### AISProtocol Class
```python
protocol = AISProtocol()
message = protocol.create_position_report(mmsi, lat, lon, sog, cog, heading)
signal = protocol.generate_gmsk_signal(message)
```

#### LimeSDRTransmitter Class
```python
transmitter = LimeSDRTransmitter(frequency=161975000, tx_gain=30.0)
transmitter.transmit_signal(signal)
```

#### AISTransmitter Class
```python
ais = AISTransmitter(mmsi=123456789, lat=37.7749, lon=-122.4194)
ais.start_continuous_transmission(interval=10.0)
```

---

## Support and Contact

For technical support:
1. Check this user guide
2. Review troubleshooting section
3. Run diagnostic scripts
4. Check GitHub issues/discussions

**Remember**: Always follow maritime regulations and safety guidelines when using AIS equipment!

---

*This user guide covers all aspects of the AIS transmitter system. For the latest updates and additional documentation, refer to the project repository.*
