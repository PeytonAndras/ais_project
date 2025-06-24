# Extended AIS Message Types Documentation

## Overview

The SIREN AIS Generator has been extended to support additional AIS message types beyond the original Type 1 position reports. The following message types are now fully implemented:

## Implemented Message Types

### Type 1, 2, 3 - Position Report Class A ✅
**Usage**: Real-time vessel position, course, and speed reporting
**Fields**: MMSI, position, course, speed, navigation status, rate of turn
**Frequency**: Every 2-10 seconds while underway

### Type 4 - Base Station Report ✅  
**Usage**: Shore-based AIS stations providing UTC time and position reference
**Fields**: MMSI, UTC date/time, position, EPFD type
**Frequency**: Every 10 seconds

### Type 5 - Static and Voyage Related Data ✅
**Usage**: Ship identification, dimensions, voyage information
**Fields**: MMSI, call sign, vessel name, ship type, dimensions, destination, ETA
**Frequency**: Every 6 minutes

### Type 18 - Standard Class B Position Report ✅
**Usage**: Position reports from Class B transponders (smaller vessels)
**Fields**: MMSI, position, course, speed (simplified compared to Class A)
**Frequency**: Variable, typically 30 seconds to 3 minutes

### Type 21 - Aid-to-Navigation Report ✅
**Usage**: Position and status of navigation aids (buoys, lighthouses, beacons)
**Fields**: MMSI, aid type, name, position, dimensions, status
**Frequency**: Every 3 minutes

## How to Use

### In the GUI Application

1. **Start the application**: `python siren_main.py`
2. **Select message type**: Use the dropdown in the AIS Generator tab
3. **Fill in fields**: The form will update with relevant fields for the selected type
4. **Generate message**: Click "Generate Message" to create the NMEA sentence
5. **Transmit**: Select signal preset and transmit

### Programmatically

```python
from siren.protocol.ais_encoding import create_nmea_sentence

# Type 1 - Position Report
type1_fields = {
    'msg_type': 1,
    'mmsi': 123456789,
    'nav_status': 0,
    'lon': -74.0060,
    'lat': 40.7128,
    'sog': 12.5,
    'cog': 90.0,
    # ... other fields
}

# Type 4 - Base Station
type4_fields = {
    'msg_type': 4,
    'mmsi': 2000001,
    'year': 2025,
    'month': 6,
    'day': 24,
    'hour': 12,
    'minute': 0,
    'second': 0,
    'lon': -74.0060,
    'lat': 40.7128,
    # ... other fields
}

# Type 5 - Static/Voyage Data
type5_fields = {
    'msg_type': 5,
    'mmsi': 123456789,
    'vessel_name': 'MY VESSEL',
    'ship_type': 70,  # Cargo
    'destination': 'NEW YORK',
    'eta_month': 12,
    'eta_day': 25,
    # ... other fields
}

# Generate NMEA sentences
nmea1 = create_nmea_sentence(type1_fields)
nmea4 = create_nmea_sentence(type4_fields)
nmea5 = create_nmea_sentence(type5_fields)
```

### With Ship Objects

```python
from siren.ships.ais_ship import AISShip

ship = AISShip(name="Test Vessel", mmsi=123456789, ...)

# Get different message types
type1_fields = ship.get_ais_fields()        # Position report
type5_fields = ship.get_type5_fields()      # Static/voyage data  
type18_fields = ship.get_type18_fields()    # Class B position
```

## Field Reference

### Common Fields

| Field | Description | Range/Format |
|-------|-------------|--------------|
| `mmsi` | Maritime Mobile Service Identity | 9-digit number |
| `lon` | Longitude in decimal degrees | -180.0 to 180.0 |
| `lat` | Latitude in decimal degrees | -90.0 to 90.0 |
| `accuracy` | Position accuracy | 0=low (>10m), 1=high (<10m) |
| `timestamp` | UTC second when report generated | 0-59, 60=not available |
| `repeat` | Repeat indicator | Usually 0 |

### Message Type Specific Fields

#### Type 4 (Base Station)
- `year`, `month`, `day`, `hour`, `minute`, `second`: UTC date/time
- `epfd_type`: Electronic Position Fixing Device (1=GPS)
- `radio_status`: Communication state

#### Type 5 (Static/Voyage) 
- `vessel_name`: Ship name (up to 20 characters)
- `call_sign`: Radio call sign (up to 7 characters)
- `ship_type`: Vessel type code (30=Fishing, 70=Cargo, etc.)
- `dim_to_bow/stern/port/starboard`: Ship dimensions in meters
- `destination`: Destination port (up to 20 characters)
- `eta_month/day/hour/minute`: Estimated Time of Arrival

#### Type 18 (Class B)
- `cs_unit`: CS Unit flag
- `display`: Display capability
- `dsc`: DSC capability  
- `band`: Frequency band capability
- `msg22`: Message 22 capability

#### Type 21 (Aid-to-Navigation)
- `aid_type`: Type of navigation aid (1=Reference point, 5=Light, etc.)
- `name`: Name of the aid (up to 20 characters)
- `off_position`: Whether aid is off position
- `aton_status`: Aid-to-navigation status
- `virtual_aid`: Whether this is a virtual aid

## Navigation Status Codes

| Code | Description |
|------|-------------|
| 0 | Under way using engine |
| 1 | At anchor |
| 2 | Not under command |
| 3 | Restricted manoeuverability |
| 5 | Moored |
| 7 | Engaged in fishing |
| 8 | Under way sailing |
| 15 | Not defined |

## Ship Type Codes

| Code | Description |
|------|-------------|
| 30 | Fishing |
| 35 | Military ops |
| 37 | Pleasure craft |
| 70 | Cargo |
| 71 | Cargo, hazardous category A |
| 72 | Cargo, hazardous category B |
| 80 | Tanker |

## MMSI Allocation

| Range | Usage |
|-------|-------|
| 001000000-009999999 | Shore-based stations |
| 200000000-799999999 | Ship stations |
| 970000000-970999999 | Search and rescue transponders |
| 990000000-999999999 | Aids to navigation |

## Testing

Run the test scripts to verify functionality:

```bash
# Test all message types
python test_new_message_types.py

# Generate examples with ship data
python example_new_message_types.py
```

## Transmission Considerations

- **Legal compliance**: Only transmit on authorized frequencies
- **Power levels**: Use appropriate power for your location
- **Interference**: Monitor for existing AIS traffic
- **Timing**: Follow proper SOTDMA timing intervals
- **Content**: Ensure message content is realistic and safe

## Future Enhancements

Additional message types that could be implemented:
- Type 6: Binary Addressed Message
- Type 8: Binary Broadcast Message  
- Type 14: Safety Related Broadcast
- Type 19: Extended Class B Position Report
- Type 24: Static Data Report

Each requires specific field definitions and encoding logic following ITU-R M.1371-5 standard.
