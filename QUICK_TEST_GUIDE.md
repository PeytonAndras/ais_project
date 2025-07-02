# Quick SIREN GNU Radio Test Guide

## Prerequisites
1. Your GNU Radio .grc flowgraph should be running and listening on port 52002
2. SIREN code transferred to your GNU Radio machine

## Quick Test Steps

### 1. **Setup Checklist (30 seconds)**
```bash
python gnuradio_checklist.py
```
This checks all dependencies and verifies your GNU Radio setup.

### 2. **Websocket Test (10 seconds)**
```bash
python quick_gnuradio_test.py
```
This tests the websocket connection and sends a test bitstring.

### 3. **Single Transmission Test (15 seconds)**
```bash
python siren_gnuradio_transmitter.py --mmsi 123456789 --lat 39.5 --lon -9.2 --once
```
This sends one real AIS message through the complete SIREN pipeline.

### 4. **Continuous Transmission Test**
```bash
python siren_gnuradio_transmitter.py --mmsi 123456789 --lat 39.5 --lon -9.2 --continuous --interval 10
```
This sends AIS messages every 10 seconds. Press Ctrl+C to stop.

## Expected Output

### Successful transmission should show:
```
🚢 SIREN GNU Radio AIS Transmitter
📡 Channel: A (161.975 MHz)
⚡ Sample rate: 8.0 MHz
🚀 Starting GNU Radio flowgraph...
✅ Connected to GNU Radio websocket on port 52002
📡 Transmitted AIS message for Test Vessel (packet #1)
🔧 NMEA: !AIVDM,1,1,,A,11mg=5@0?`wEpd0FVR8?wjmH0000,0*60
✅ Message sent successfully
```

## Troubleshooting

### "GNU Radio not available"
- Install: `sudo apt-get install gnuradio gr-osmosdr gr-ais`
- Install: `pip install websocket-client pyais`

### "Websocket connection failed"
- Make sure your .grc flowgraph is running
- Check it's listening on port 52002
- Verify with: `netstat -ln | grep 52002`

### "Failed to extract payload"
- Check SIREN modules: `python -c "from siren.protocol.ais_encoding import payload_to_bitstring; print('OK')"`

### "SIREN modules not available"
- Run from the correct directory (where siren/ folder exists)
- Check Python path: `python -c "import sys; print(sys.path)"`

## What's Different from Original

The key change is that SIREN now sends **binary bitstrings** to the GNU Radio websocket, not JSON:

```python
# OLD (doesn't work):
ws.send(json.dumps({"payload": "11mg=5@0..."}))

# NEW (works with your .grc):
ws.send("000001000001110101101111...")  # Raw binary bits
```

This matches exactly what your working ais-simulator web interface sends.

## Full SIREN Integration

Once basic transmission works, you can use the full SIREN UI:

```bash
# Start SIREN with GNU Radio transmission
python siren_main.py --transmission gnuradio
```

The UI will show a "GNU Radio" option in the transmission method dropdown.
