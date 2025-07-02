# Simple GNU Radio Integration for SIREN

This document describes the **simple GNU Radio integration** approach for SIREN, which bypasses complex GNU Radio Python bindings by using the proven `ais-simulator.py` websocket interface.

## Overview

Instead of trying to integrate GNU Radio blocks directly into SIREN (which requires complex dependencies like `gr-ais` and `gr-osmosdr`), this approach:

1. **Uses ais-simulator.py as a GNU Radio backend** - it handles all GNU Radio complexity
2. **SIREN sends AIS bitstrings via websocket** - simple, cross-platform communication
3. **ais-simulator handles RF transmission** - proven working implementation

## Architecture

```
SIREN UI → Simple Transmitter → WebSocket → ais-simulator.py → GNU Radio → SDR → RF
```

- **SIREN**: Generates ship data and AIS messages using `pyais`
- **Simple Transmitter**: Converts to bitstrings and sends via websocket
- **ais-simulator.py**: Receives bitstrings and transmits via GNU Radio flowgraph
- **GNU Radio**: Handles GMSK modulation and SDR output

## Quick Start

### 1. Setup (One-time)

```bash
# Run the setup script
python3 simple_gnuradio_setup.py

# Or install dependencies manually
pip install websocket-client pyais
```

### 2. Start GNU Radio Backend

```bash
# In one terminal - start the GNU Radio flowgraph
cd ais-simulator
python3 ais-simulator.py

# This creates a websocket server on port 52002
# Leave this running during transmission
```

### 3. Use SIREN with GNU Radio

```bash
# In another terminal - start SIREN
python3 siren_main.py
```

In SIREN GUI:
1. Go to **Ship Simulation** tab
2. Select **"GNU Radio (Simple)"** as transmission method
3. Choose AIS channel (A or B)
4. Select ships to simulate
5. Click **"Start Simulation"**

SIREN will connect to the GNU Radio websocket and start transmitting!

## Testing

### Test the Integration

```bash
# Test with a single ship
python3 simple_gnuradio_test.py --test single --mmsi 123456789 --lat 39.5 --lon -9.2

# Test continuous transmission
python3 simple_gnuradio_test.py --test continuous --duration 30

# Test multiple ships
python3 simple_gnuradio_test.py --test multiple --ships 3
```

### Verify RF Transmission

Use an AIS receiver to verify transmission:

```bash
# With rtl_ais
rtl_ais -n

# With dump1090 in AIS mode
# Or any other AIS receiver software
```

## Benefits of This Approach

✅ **Simple dependencies**: Only needs `websocket-client` and `pyais`  
✅ **Cross-platform**: Works on any system that can run Python  
✅ **Proven reliable**: Uses the working ais-simulator.py implementation  
✅ **Easy debugging**: Can monitor websocket traffic  
✅ **No complex builds**: No need to compile GNU Radio blocks  

## Files Created

- `siren/transmission/simple_gnuradio.py` - Main transmitter implementation
- `siren/config/simple_gnuradio_config.py` - Configuration management
- `simple_gnuradio_test.py` - Test script
- `simple_gnuradio_setup.py` - Setup script
- GUI integration in `siren/ui/main_window.py`

## Troubleshooting

### Connection Issues

**Problem**: "Failed to connect to GNU Radio"  
**Solution**: Make sure `ais-simulator.py` is running first

```bash
cd ais-simulator
python3 ais-simulator.py
# Should show: "Websocket server listening on port 52002"
```

### Port Issues

**Problem**: "Connection refused" or port conflicts  
**Solution**: Check if port 52002 is available

```bash
# Check if port is in use
lsof -i :52002

# Use different port if needed (modify both ais-simulator and SIREN config)
```

### No RF Output

**Problem**: Websocket connects but no RF transmission  
**Solution**: Check GNU Radio dependencies on the ais-simulator system

```bash
# Make sure GNU Radio is properly installed
gnuradio-config-info --version

# Check for required blocks
python3 -c "from gnuradio import ais_simulator; print('gr-ais available')"
python3 -c "import osmosdr; print('gr-osmosdr available')"
```

### AIS Encoding Issues

**Problem**: Invalid AIS messages  
**Solution**: Check MMSI and coordinate formats

```python
# MMSI must be 9 digits
mmsi = 123456789  # ✅ Valid

# Coordinates must be in decimal degrees
latitude = 39.5    # ✅ Valid
longitude = -9.2   # ✅ Valid (negative for west)
```

## Advanced Configuration

### Custom Websocket Port

```python
# In SIREN GUI, or modify config files
websocket_port = 52003  # Custom port

# Must match ais-simulator.py startup:
python3 ais-simulator.py --port 52003
```

### Custom Transmission Interval

```python
# In SIREN GUI
transmission_interval = 5  # Send every 5 seconds
```

### Multiple Channels

Run multiple ais-simulator instances for different channels:

```bash
# Terminal 1 - Channel A
cd ais-simulator
python3 ais-simulator.py --channel A --port 52002

# Terminal 2 - Channel B  
cd ais-simulator
python3 ais-simulator.py --channel B --port 52003
```

## Comparison with Complex Integration

| Feature | Simple Integration | Complex Integration |
|---------|-------------------|-------------------|
| Dependencies | `websocket-client`, `pyais` | `gnuradio`, `gr-ais`, `gr-osmosdr` |
| Setup | `pip install` | System packages + compilation |
| Cross-platform | ✅ Works everywhere | ❌ Linux/x86 mainly |
| Debugging | ✅ Easy websocket monitoring | ❌ Complex GNU Radio debugging |
| Reliability | ✅ Uses proven ais-simulator | ❌ Custom integration |
| Performance | ✅ Efficient websocket | ✅ Direct GNU Radio |

## Contributing

To extend this integration:

1. Modify `simple_gnuradio.py` for new features
2. Update configuration in `simple_gnuradio_config.py`
3. Add tests to `simple_gnuradio_test.py`
4. Update this documentation

The simple approach makes it easy to add features without dealing with GNU Radio complexity!
