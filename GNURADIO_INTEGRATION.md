# GNU Radio Integration for SIREN

This document describes how to integrate the proven GNU Radio AIS transmission method (from ais-simulator.py) into your SIREN project.

## Overview

The GNU Radio integration provides a working AIS transmission method that has been tested successfully with rtl_ais over-the-air transmission. This implementation is based on the proven `ais-simulator.py` that uses:

- GNU Radio flowgraph with `gr-ais_simulator` blocks
- LimeSDR with `gr-osmosdr` 
- GMSK modulation with BT=0.4
- Websocket interface for message injection

## Quick Start

### 1. Install Dependencies

Run the automated setup script:

```bash
cd /path/to/nato_navy
./setup_gnuradio.sh
```

Or install manually:

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install gnuradio gr-osmosdr gr-ais
pip3 install websocket-client

# Arch Linux
sudo pacman -S gnuradio gnuradio-osmosdr
yay -S gr-ais
pip3 install websocket-client

# macOS
brew install gnuradio gr-osmosdr
pip3 install websocket-client
```

### 2. Test Standalone Transmitter

```bash
# Single test transmission
python3 siren_gnuradio_transmitter.py --mmsi 123456789 --lat 39.5 --lon -9.2 --once

# Continuous transmission every 10 seconds
python3 siren_gnuradio_transmitter.py --mmsi 123456789 --lat 39.5 --lon -9.2 --continuous --interval 10

# Use Channel B
python3 siren_gnuradio_transmitter.py --mmsi 123456789 --lat 39.5 --lon -9.2 --channel B
```

### 3. Integration with SIREN

To use GNU Radio transmission in the main SIREN application:

```python
from siren.transmission.siren_gnuradio_integration import create_siren_transmitter

# Create GNU Radio-based transmitter
tx = create_siren_transmitter(prefer_gnuradio=True, channel='A')

# Start transmitter
tx.start()

# Transmit a ship
success = tx.transmit_ship(ship)

# Continuous transmission
tx.start_continuous_transmission(ships, update_rate=10.0)

# Stop when done
tx.stop()
```

## Architecture

The GNU Radio integration consists of several components:

### Core Components

1. **`siren_gnuradio_transmitter.py`** - Standalone transmitter script
2. **`siren/transmission/gnuradio_transmitter.py`** - GNU Radio transmitter class
3. **`siren/transmission/siren_gnuradio_integration.py`** - SIREN integration layer
4. **`siren/config/gnuradio_config.py`** - Configuration management
5. **`setup_gnuradio.sh`** - Automated installation script

### GNU Radio Flowgraph

The transmitter creates a GNU Radio flowgraph that exactly matches `ais-simulator.py`:

```
Websocket PDU → PDU to Stream → AIS Frame Builder → GMSK Mod → Power Scale → LimeSDR
```

- **Websocket PDU**: Receives AIS messages via websocket
- **AIS Frame Builder**: `ais_simulator.bitstring_to_frame()`
- **GMSK Modulator**: `digital.gmsk_mod()` with BT=0.4
- **LimeSDR Sink**: `osmosdr.sink()` with driver=lime

### Message Flow

1. SIREN ships generate AIS fields using `ship.get_ais_fields()`
2. Fields converted to NMEA using `create_nmea_sentence()`
3. NMEA payload extracted and sent via websocket to GNU Radio
4. GNU Radio processes message through AIS frame builder
5. GMSK modulation and transmission via LimeSDR

## Configuration

### GNU Radio Settings

Default configuration (matches ais-simulator.py):

```python
GNURADIO_CONFIG = {
    'channel': 'A',          # AIS Channel A (161.975MHz) or B (162.025MHz)
    'sample_rate': 8000000,  # 8 MHz sample rate
    'bit_rate': 9600,        # AIS standard bit rate
    'tx_gain': 42,           # RF gain (dB)
    'bb_gain': 30,           # Baseband gain (dB)
    'ppm': 0,                # Frequency correction
    'websocket_port': 52002, # Communication port
    'power_scaling': 0.9,    # Signal scaling factor
    'gmsk_bt': 0.4          # GMSK BT parameter
}
```

### LimeSDR Settings

The transmitter uses these LimeSDR parameters (matching ais-simulator.py):

```python
osmosdr_sink.set_sample_rate(8000000)
osmosdr_sink.set_center_freq(161975000)  # Channel A
osmosdr_sink.set_gain(42, 0)
osmosdr_sink.set_bb_gain(30, 0)
osmosdr_sink.set_antenna("BAND1", 0)
```

## Integration Options

### 1. Standalone Mode

Use `siren_gnuradio_transmitter.py` directly:

```bash
python3 siren_gnuradio_transmitter.py --mmsi 123456789 --lat 39.5 --lon -9.2
```

### 2. SIREN Integration

Use the integrated transmitter in SIREN:

```python
# In your SIREN application
from siren.transmission.siren_gnuradio_integration import SIRENGnuRadioTransmitter

tx = SIRENGnuRadioTransmitter(use_gnuradio=True, channel='A')
tx.start()
tx.transmit_ship(ship)
```

### 3. Hybrid Mode

The integration automatically falls back to SoapySDR if GNU Radio fails:

```python
# Will try GNU Radio first, fall back to SoapySDR
tx = create_siren_transmitter(prefer_gnuradio=True)
```

## Testing and Validation

### 1. Dependency Check

```bash
python3 -c "
from gnuradio import gr, blocks, digital, ais_simulator
import osmosdr
import websocket
print('✅ All dependencies available')
"
```

### 2. Hardware Test

```bash
# Test LimeSDR detection
SoapySDRUtil --find="driver=lime"

# Test GNU Radio with LimeSDR
python3 siren_gnuradio_transmitter.py --mmsi 999999001 --lat 0 --lon 0 --once
```

### 3. Signal Verification

Use rtl_ais or another AIS receiver to verify transmitted signals:

```bash
# Receive on AIS Channel A
rtl_ais -n -h 127.0.0.1 -p 10110 -d 0 -f 161975000 -s 250000
```

## Troubleshooting

### Common Issues

1. **GNU Radio Import Error**
   ```
   Solution: Install gnuradio, gr-osmosdr, gr-ais packages
   ```

2. **LimeSDR Not Found**
   ```
   Solution: Check USB connection, install LimeSDR drivers
   ```

3. **Websocket Connection Failed**
   ```
   Solution: Check port 52002 is available, install websocket-client
   ```

4. **Permission Denied (LimeSDR)**
   ```
   Solution: Add user to plugdev group, install udev rules
   ```

### Debug Commands

```bash
# Check GNU Radio version
python3 -c "import gnuradio; print(gnuradio.version())"

# Test LimeSDR
LimeUtil --find

# Check websocket
netstat -ln | grep 52002
```

## Advantages of GNU Radio Method

1. **Proven Working**: Based on successfully tested ais-simulator.py
2. **Standards Compliance**: Uses proper AIS frame building blocks
3. **Hardware Compatibility**: Well-tested with LimeSDR
4. **Modular Design**: Clean separation between GNU Radio and SIREN
5. **Fallback Support**: Can fall back to SoapySDR if needed

## Performance

- **Transmission Rate**: Up to several messages per second
- **Frequency Accuracy**: Excellent with proper PPM calibration  
- **Signal Quality**: Clean GMSK with proper BT=0.4 filtering
- **Compatibility**: Tested with rtl_ais and other AIS receivers

## Security and Legal

⚠️ **Important Warnings:**

- Use test MMSI numbers (999999xxx) for development
- Ensure proper radio licensing for your jurisdiction
- Test in RF-shielded environment initially
- Follow maritime radio regulations
- Coordinate with maritime authorities for testing

## Next Steps

1. Run `./setup_gnuradio.sh` to install dependencies
2. Test with `siren_gnuradio_transmitter.py` 
3. Integrate into your SIREN application
4. Validate with AIS receivers
5. Deploy for your specific use case

For more information, see the main SIREN documentation and the original ais-simulator.py project.
