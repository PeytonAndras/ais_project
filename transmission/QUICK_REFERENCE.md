# AIS Transmitter Quick Reference

## Essential Commands

### First Time Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Test installation
python test_basic.py

# Check hardware
SoapySDRUtil --find
```

### Basic Transmission
```bash
# Single transmission
python ais_transmitter.py --mmsi 123456789 --lat 37.7749 --lon -122.4194 --once

# Continuous beacon (10 second interval)
python ais_transmitter.py --mmsi 123456789 --lat 37.7749 --lon -122.4194

# Save to file instead of transmitting
python ais_transmitter.py --mmsi 123456789 --lat 37.7749 --lon -122.4194 --output signal.iq --once
```

### Testing & Debugging
```bash
# Basic functionality test (no hardware needed)
python test_basic.py

# Signal analysis and validation
python signal_analysis.py

# Hardware diagnostics
python debug_hardware.py

# CW test for RF output verification
python test_cw_simple.py

# Force enable TX if no RF output
python force_enable_tx.py

# Reset LimeSDR connection
python reset_limesdr.py
```

## Common Parameters

### Position & Motion
```bash
--lat 37.7749              # Latitude (decimal degrees)
--lon -122.4194            # Longitude (decimal degrees)
--sog 12.5                 # Speed over ground (knots)
--cog 045                  # Course over ground (degrees)
--heading 047              # True heading (degrees)
```

### Hardware Settings
```bash
--frequency 161975000      # AIS Channel A (default)
--frequency 162025000      # AIS Channel B
--gain 30                  # TX gain in dB (0-64)
--antenna BAND2            # Antenna selection (LimeSDR Mini)
```

### Timing & Control
```bash
--interval 10.0            # Transmission interval (seconds)
--once                     # Single transmission only
--duration 300             # Run for 5 minutes then stop
```

## Configuration File Template

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
    "interval": 10.0,
    "antenna": "BAND2"
}
```

Use with: `python ais_transmitter.py --config config.json`

## Troubleshooting Quick Fixes

### No LimeSDR Detected
```bash
# Check connection
SoapySDRUtil --find

# Reset USB
python reset_limesdr.py

# Linux: Add user to dialout group
sudo usermod -a -G dialout $USER
```

### No RF Output
```bash
# Check with CW test
python test_cw_simple.py

# Force enable TX
python force_enable_tx.py

# Check hardware diagnostics
python debug_hardware.py
```

### Import Errors
```bash
# Install missing dependencies
pip install numpy scipy matplotlib SoapySDR

# Check Python version (need 3.7+)
python --version
```

## Monitoring Reception

### With RTL-SDR
```bash
# Terminal 1: Transmit
python ais_transmitter.py --mmsi 123456789 --lat 37.7749 --lon -122.4194

# Terminal 2: Receive (if rtl-ais installed)
rtl_ais -f 161975000 -s 48000 -g 40
```

### With SDR Software
- **Frequency**: 161.975 MHz or 162.025 MHz
- **Bandwidth**: 25 kHz
- **Mode**: NFM or Raw I/Q
- **Sample Rate**: 48 kHz or higher

## Safety Checklist

### Before First Use
- [ ] Read legal requirements for your country
- [ ] Obtain proper maritime license if needed
- [ ] Use test MMSI numbers (123456789)
- [ ] Connect RF dummy load for testing
- [ ] Start with low power (30 dB gain)

### Before Maritime Use
- [ ] Obtain official MMSI number
- [ ] Verify compliance with local regulations
- [ ] Test reception with known receiver
- [ ] Calibrate frequency accuracy
- [ ] Set appropriate power level

## Default Test Settings

| Parameter | Value | Notes |
|-----------|-------|-------|
| MMSI | 123456789 | Test range |
| Frequency | 161.975 MHz | AIS Channel A |
| TX Gain | 30 dB | Safe test level |
| Interval | 10 seconds | Class B rate |
| Sample Rate | 96 kHz | Standard |
| Antenna | BAND2 | LimeSDR Mini |

## File Outputs

### Signal Files
```bash
# Create IQ file for analysis
python ais_transmitter.py --mmsi 123456789 --lat 37.7749 --lon -122.4194 --output test.iq --once

# Analyze saved signal
python signal_analysis.py --file test.iq
```

### Log Files
- Application logs: Console output
- Error logs: `transmitter.log` (if configured)
- Signal analysis: Console reports

## Quick Problem Resolution

| Problem | Quick Fix |
|---------|-----------|
| "No devices found" | `python reset_limesdr.py` |
| "Device busy" | Unplug/replug LimeSDR |
| "Import error" | `pip install -r requirements.txt` |
| "No RF output" | `python force_enable_tx.py` |
| "Permission denied" | Run as admin or add to dialout group |
| "Stream failed" | Reduce gain, check USB |

## Signal Verification

### Expected Results
- **Signal Analysis**: All tests should PASS
- **CW Test**: Strong carrier at 161.975 MHz  
- **AIS Reception**: Decoded position reports
- **Hardware Test**: Successful TX calibration

### Key Indicators
- ✅ "TX calibration finished"
- ✅ "Successfully transmitted X samples"  
- ✅ "All validation tests PASSED"
- ✅ Receiver shows AIS messages

---

**Remember**: Always test with dummy load first and follow maritime regulations!

For detailed information, see the complete USER_GUIDE.md file.
