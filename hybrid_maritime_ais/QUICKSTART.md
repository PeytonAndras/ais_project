# Quick Start Guide - Hybrid Maritime AIS

Get up and running with the Hybrid Maritime AIS Transmitter in 5 minutes.

## 🚀 Installation

```bash
cd hybrid_maritime_ais
pip install -r requirements.txt
```

## ✅ Quick Test

Verify everything works (no hardware required):
```bash
python test.py
# Choose option 1 for quick test
```

## 🎯 Basic Usage

### Single Transmission
```bash
python hybrid_maritime_ais.py --mmsi 123456789 --lat 37.7749 --lon -122.4194 --once
```

### Continuous Beacon (Production)
```bash
python hybrid_maritime_ais.py --mmsi 123456789 --lat 37.7749 --lon -122.4194
```

### rtl_ais Testing
```bash
python hybrid_maritime_ais.py --mmsi 123456789 --lat 37.7749 --lon -122.4194 --mode rtl_ais_testing
```

## 🔧 Demo

See all features in action:
```bash
python demo.py
```

## 📖 Full Documentation

See [README.md](README.md) for complete documentation.

## ⚡ Key Features

- ✅ **Production Mode**: ITU-R M.1371-5 compliant
- ✅ **rtl_ais Mode**: Optimized for rtl_ais receivers  
- ✅ **NMEA Support**: Process existing NMEA sentences
- ✅ **Real-time Updates**: Dynamic position and motion
- ✅ **SOTDMA Timing**: Professional maritime coordination

## 🛠️ Requirements

- Python 3.7+
- LimeSDR (optional for testing)
- SoapySDR
- See requirements.txt for full list
