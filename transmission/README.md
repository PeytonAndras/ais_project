# AIS Transmitter for LimeSDR

A complete, standards-compliant AIS (Automatic Identification System) transmitter for LimeSDR that generates signals fully compatible with rtl-ais and other AIS receivers.

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Test without hardware
python test_basic.py

# 3. Single transmission (with LimeSDR connected)
python ais_transmitter.py --mmsi 123456789 --lat 37.7749 --lon -122.4194 --once
```

## 📖 Documentation

- **[📘 User Guide](USER_GUIDE.md)** - Complete installation, setup, and usage guide
- **[⚡ Quick Reference](QUICK_REFERENCE.md)** - Essential commands and troubleshooting
- **[🔧 Project Summary](PROJECT_SUMMARY.md)** - Technical implementation details

## ✨ Features

- **🎯 Standards Compliant**: Full ITU-R M.1371-5 AIS specification
- **📡 GMSK Modulation**: Proper Gaussian Minimum Shift Keying (BT=0.4)
- **⏱️ SOTDMA Protocol**: Self-Organizing Time Division Multiple Access
- **🔧 LimeSDR Support**: Native support via SoapySDR
- **✅ Validation Tools**: Comprehensive testing against rtl-ais
- **🔄 Real-time Transmission**: Continuous AIS beacon capability
- **⚙️ Configurable**: Extensive configuration options
- **🛡️ Safety Features**: Built-in power limits and test modes

## 🎛️ Basic Usage

### Single Transmission
```bash
python ais_transmitter.py --mmsi 123456789 --lat 37.7749 --lon -122.4194 --once
```

### Continuous Beacon
```bash
python ais_transmitter.py --mmsi 123456789 --lat 37.7749 --lon -122.4194
```

### With Vessel Motion
```bash
python ais_transmitter.py \
    --mmsi 123456789 \
    --lat 37.7749 \
    --lon -122.4194 \
    --sog 12.5 \
    --cog 045 \
    --heading 047
```

### Save to File (No Hardware)
```bash
python ais_transmitter.py --mmsi 123456789 --lat 37.7749 --lon -122.4194 --output signal.iq --once
```

## 🔧 Installation

### System Requirements
- Python 3.7+
- LimeSDR Mini or LimeSDR USB
- SoapySDR with LimeSuite drivers
- VHF antenna (161-162 MHz)

### Quick Installation
```bash
# Install LimeSuite (varies by OS - see User Guide for details)
# Ubuntu/Debian:
sudo apt install limesuite liblimesuite-dev

# Install Python dependencies
pip install -r requirements.txt

# Test installation
python test_basic.py
```

### Verify Hardware
```bash
# Check LimeSDR detection
SoapySDRUtil --find

# Test hardware connection
python debug_hardware.py
```

## 🧪 Testing & Validation

### Software Tests (No Hardware Required)
```bash
# Basic functionality test
python test_basic.py

# Signal analysis and validation
python signal_analysis.py

# Complete demonstration
python demo.py
```

### Hardware Tests (LimeSDR Required)
```bash
# Hardware diagnostics
python debug_hardware.py

# RF output test
python test_cw_simple.py

# Live AIS transmission test
python ais_transmitter.py --mmsi 123456789 --lat 37.7749 --lon -122.4194 --once
```

## 🔍 Monitoring Reception

### With rtl-ais
```bash
# Terminal 1: Transmit
python ais_transmitter.py --mmsi 123456789 --lat 37.7749 --lon -122.4194

# Terminal 2: Receive (with RTL-SDR)
rtl_ais -f 161975000 -s 48000 -g 40
```

### With SDR Software
Monitor **161.975 MHz** (AIS Channel A) using:
- CubicSDR, SDR#, GQRX, or similar
- NFM mode, 25 kHz bandwidth
- You should see AIS packet bursts
## 📁 Project Structure

```
transmitter/
├── ais_protocol.py          # Core AIS protocol implementation
├── ais_transmitter.py       # Main application
├── limesdr_interface.py     # LimeSDR/SoapySDR interface
├── ais_validator.py         # Signal validation tools
├── ais_utils.py            # Configuration utilities
├── signal_analysis.py       # Signal analysis tools
├── test_basic.py           # Basic functionality tests
├── debug_hardware.py       # Hardware diagnostics
├── test_cw_simple.py       # RF output verification
├── demo.py                 # Complete demonstration
├── requirements.txt         # Python dependencies
├── USER_GUIDE.md           # Complete user guide
├── QUICK_REFERENCE.md      # Quick reference
└── README.md              # This file
```

## ⚡ Troubleshooting

### Common Issues

| Problem | Quick Fix |
|---------|-----------|
| No LimeSDR detected | `python reset_limesdr.py` |
| No RF output | `python force_enable_tx.py` |
| Import errors | `pip install -r requirements.txt` |
| Permission denied | Add user to dialout group (Linux) |

See [Quick Reference](QUICK_REFERENCE.md) for more solutions.

## ⚠️ Legal and Safety

### Important Warnings
- **🏛️ Maritime license may be required** for AIS transmission
- **📡 Use only assigned MMSI numbers** (not test numbers) for real maritime use
- **🔌 Test with RF dummy load first**
- **📏 Follow local power restrictions** (typically 2W max)
- **🚫 Don't interfere with maritime traffic**

### Test Guidelines
- Use MMSI `123456789` for testing
- Start with low power (30 dB gain)
- Test in RF-shielded environment when possible
- Monitor for interference

## 🔬 Technical Specifications

### Signal Parameters
- **Frequencies**: 161.975 MHz (AIS1), 162.025 MHz (AIS2)
- **Modulation**: GMSK with BT=0.4
- **Data Rate**: 9600 bps
- **Sample Rate**: 96 kHz
- **Packet Duration**: ~23.3 ms

### Protocol Compliance
- **Standard**: ITU-R M.1371-5
- **Message Types**: 1, 2, 3, 4, 18 (Position Reports, Base Station)
- **Encoding**: NRZI with HDLC bit stuffing
- **Error Detection**: CRC-16 CCITT
- **Multiple Access**: SOTDMA (2250 slots/60s frame)

## 🎯 Validation Results

The implementation has been thoroughly validated:

```
✅ Packet Structure: VALID (Training + Start + Data + CRC + End)
✅ NRZI Encoding: PASS (Correctly implemented and reversible)  
✅ GMSK Signal: VALID (Continuous phase, proper bandwidth)
✅ Bit Stuffing: PASS (HDLC compliant with valid CRC-16)
✅ Timing: GOOD (Perfect 9600 bps symbol timing)
✅ Overall Assessment: FULLY COMPLIANT with AIS specification
```

## 🤝 Contributing

Contributions welcome! Please:
1. Read the User Guide first
2. Test your changes thoroughly  
3. Follow existing code style
4. Update documentation as needed

## 📄 License

See the LICENSE file for details. This implementation is for educational and licensed maritime use only.

---

**📖 For complete setup and usage instructions, see the [User Guide](USER_GUIDE.md)!**
