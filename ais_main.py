#!/usr/bin/env python3
"""
@ author: Peyton Andras @ Louisiana State University 2025

this is the new implementation of the entire main program UI, 

still has the old : transmission, and ship simulation
however it is the old encoding/decoding and transmission code.. leaving untouched until proper
tranmission code is achieved


AIS NMEA Generator & Transmitter
- Generate AIS messages with proper encoding
- Transmit using HackRF or other SoapySDR devices
- Simulate vessel movements with AIS position reporting
- Visualize ship movements on interactive map
"""
import tkinter as tk          
from tkinter import ttk, messagebox, scrolledtext
import numpy as np            
import time
import threading
import json
import os
from datetime import datetime, timedelta
import math
import webbrowser  # For opening fallback map if needed
import tempfile

# Add map visualization libraries
try:
    import tkintermapview  # Main map widget
    tkintermapview.TkinterMapView.USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    MAP_VIEW_AVAILABLE = True
    print("tkintermapview imported successfully")
except ImportError as e:
    MAP_VIEW_AVAILABLE = False
    print(f"tkintermapview import error: {e}. Map functionality will be limited.")
    print("Install with: pip install tkintermapview")

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
    print("PIL imported successfully")
except ImportError:
    PIL_AVAILABLE = False
    print("PIL import error. Ship icons will be basic. Install with: pip install pillow")

### SDR CONFIGURATION ###
try:
    import SoapySDR
    SOAPY_SDR_TX = getattr(SoapySDR, "SOAPY_SDR_TX", "TX")
    SOAPY_SDR_CF32 = getattr(SoapySDR, "SOAPY_SDR_CF32", "CF32")
    SDR_AVAILABLE = True
    print("SoapySDR imported successfully")
except ImportError as e:
    print(f"SoapySDR import error: {e}")
    SDR_AVAILABLE = False

### AIS MESSAGE ENCODING FUNCTIONS ###
def sixbit_to_char(val):
    """Convert 6-bit value to AIS ASCII character"""
    if val < 0 or val > 63:
        raise ValueError("6-bit value out of range")
    return chr(val + 48 if val < 40 else val + 56)

def char_to_sixbit(char):
    """Convert AIS 6-bit ASCII character to bits"""
    val = ord(char)
    if val >= 48 and val < 88:
        val -= 48
    elif val >= 96 and val < 128:
        val -= 56
    else:
        raise ValueError(f"Invalid AIS character: {char}")
    
    # Convert to 6 bits
    return [(val >> 5) & 1, (val >> 4) & 1, (val >> 3) & 1, 
            (val >> 2) & 1, (val >> 1) & 1, val & 1]

def compute_checksum(sentence):
    """Compute NMEA checksum (XOR of all characters)"""
    cs = 0
    for c in sentence:
        cs ^= ord(c)
    return f"{cs:02X}"

def build_ais_payload(fields):
    """Build AIS payload from message fields"""
    bits = []
    
    # Helper function to add bits to the message
    def add(value, length):
        for i in range(length - 1, -1, -1):
            bits.append((value >> i) & 1)
    
    # Add all required fields for position report
    add(fields['msg_type'], 6)   # Message type
    add(fields['repeat'], 2)     # Repeat indicator
    add(fields['mmsi'], 30)      # MMSI (ship ID)
    add(fields['nav_status'], 4) # Navigation status
    add(fields['rot'] & 0xFF, 8) # Rate of Turn
    
    # Speed over ground (1/10 knots)
    add(int(fields['sog'] * 10) & 0x3FF, 10)
    
    # Position accuracy
    add(fields['accuracy'], 1)
    
    # Longitude (1/10000 minute)
    lon_minutes = fields['lon'] * 60
    lon_value = int(lon_minutes * 10000)
    if lon_value < 0:
        lon_value = (1 << 28) + lon_value  # Two's complement
    add(int(lon_value) & ((1 << 28) - 1), 28)
    
    # Latitude (1/10000 minute)
    lat_minutes = fields['lat'] * 60
    lat_value = int(lat_minutes * 10000)
    if lat_value < 0:
        lat_value = (1 << 27) + lat_value  # Two's complement
    add(int(lat_value) & ((1 << 27) - 1), 27)
    
    # Course over ground (1/10 degrees)
    add(int(fields['cog'] * 10) & 0xFFF, 12)
    
    # True heading
    if fields['hdg'] == -1:  # Not available
        add(511, 9)
    else:
        add(int(fields['hdg']) & 0x1FF, 9)
    
    # Timestamp
    add(int(fields['timestamp']) & 0x3F, 6)
    
    # Spare bits
    add(0, 8)
    
    # Pad to 6-bit boundary
    fill = (6 - (len(bits) % 6)) % 6
    for _ in range(fill): 
        bits.append(0)
    
    # Convert binary data to 6-bit ASCII
    payload = ''.join(sixbit_to_char(int(''.join(str(b) for b in bits[i:i+6]), 2))
                      for i in range(0, len(bits), 6))
    
    return payload, fill

### SIGNAL GENERATION FUNCTIONS ###
# Signal configuration presets
SIGNAL_PRESETS = [
    {"name": "AIS Channel A", "freq": 161.975e6, "gain": 70, "modulation": "GMSK", "sdr_type": "hackrf"},
    {"name": "AIS Channel B", "freq": 162.025e6, "gain": 65, "modulation": "GMSK", "sdr_type": "hackrf"},
]

def calculate_crc(bits):
    """Calculate CRC-16-CCITT for AIS message correctly at bit level"""
    poly = 0x1021
    crc = 0xFFFF
    
    for bit in bits:
        # Correctly process one bit at a time
        crc ^= (bit << 15)
        crc = (crc << 1) ^ poly if crc & 0x8000 else crc << 1
        crc &= 0xFFFF
    
    return [(crc >> i) & 1 for i in range(15, -1, -1)]

def haversine(lat1, lon1, lat2, lon2):
    """Calculate the great circle distance between two points in kilometers"""
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371  # Radius of earth in kilometers
    return c * r

def calculate_initial_compass_bearing(point1, point2):
    """Calculate the initial compass bearing between two points"""
    lat1, lon1 = point1
    lat2, lon2 = point2
    
    # Convert decimal degrees to radians
    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)
    lon_diff = math.radians(lon2 - lon1)
    
    # Calculate bearing
    x = math.sin(lon_diff) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1) * math.cos(lat2) * math.cos(lon_diff))
    
    initial_bearing = math.atan2(x, y)
    initial_bearing = math.degrees(initial_bearing)
    
    # Normalize to 0-360
    bearing = (initial_bearing + 360) % 360
    
    return bearing

def create_ais_signal(nmea_sentence, sample_rate=2e6, repetitions=6):
    """Create a properly modulated AIS signal from NMEA sentence"""
    # Extract payload from NMEA sentence
    parts = nmea_sentence.split(',')
    if len(parts) < 6:
        raise ValueError("Invalid NMEA sentence")
    
    payload = parts[5]
    print(f"Creating AIS signal from payload: {payload}")
    
    # Convert 6-bit ASCII to bits
    bits = []
    for char in payload:
        char_bits = char_to_sixbit(char)
        bits.extend(char_bits)
    
    # Calculate and append CRC
    crc_bits = calculate_crc(bits)
    bits.extend(crc_bits)
    print(f"Added CRC bits: {crc_bits}")
    
    # Create HDLC frame with flags and bit stuffing
    start_flag = [0, 1, 1, 1, 1, 1, 1, 0]
    stuffed_bits = []
    consecutive_ones = 0
    
    # Start flag
    stuffed_bits.extend(start_flag)
    
    # Training sequence
    stuffed_bits.extend([0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1])
    
    # Log bit stuffing process
    print(f"Original bits length: {len(bits)}")
    
    # Add data bits with bit stuffing
    for i, bit in enumerate(bits):
        if bit == 1:
            consecutive_ones += 1
        else:
            consecutive_ones = 0
            
        stuffed_bits.append(bit)
        
        # After 5 consecutive ones, insert a 0
        if consecutive_ones == 5:
            stuffed_bits.append(0)
            consecutive_ones = 0
            print(f"Bit stuffing: Added zero after position {i}")
    
    # End flag
    stuffed_bits.extend(start_flag)
    
    print(f"After bit stuffing: length={len(stuffed_bits)}")
    
    # NRZI encoding
    nrzi_bits = []
    # Initialize with last bit of training sequence for better sync
    current_level = stuffed_bits[24] if len(stuffed_bits) > 24 else 0
    
    for bit in stuffed_bits:
        if bit == 0:
            current_level = 1 - current_level
        nrzi_bits.append(current_level)
    
    # GMSK modulation
    bit_rate = 9600.0  # AIS bit rate
    samples_per_bit = int(sample_rate / bit_rate)
    num_samples = len(nrzi_bits) * samples_per_bit
    
    # Create Gaussian filter with proper BT product
    bt = 0.4  # AIS BT product (standard value)
    filter_length = 4
    t = np.arange(-filter_length/2, filter_length/2, 1/samples_per_bit)
    h = np.sqrt(2*np.pi/np.log(2)) * bt * np.exp(-2*np.pi**2*bt**2*t**2/np.log(2))
    h = h / np.sum(h)
    
    # Upsample bits
    upsampled = np.zeros(num_samples)
    for i, bit in enumerate(nrzi_bits):
        upsampled[i*samples_per_bit] = 2*bit - 1
    
    # Apply Gaussian filter
    filtered = np.convolve(upsampled, h, 'same')
    
    # MSK modulation
    phase = np.cumsum(filtered) * np.pi / samples_per_bit
    
    # Generate I/Q samples
    i_samples = np.cos(phase)
    q_samples = np.sin(phase)
    iq_samples = i_samples + 1j * q_samples
    
    # Add pre-emphasis for better reception
    emphasis = np.exp(-1j * np.pi * 0.25)
    iq_samples *= emphasis
    
    # Normalize and scale
    max_amp = np.max(np.abs(iq_samples))
    if max_amp > 0:
        iq_samples = iq_samples / max_amp * 0.9
    
    # Repeat the signal
    return np.tile(iq_samples * 1.0, repetitions)

### SHIP SIMULATION ###
class AISShip:
    """Class representing a simulated AIS ship with position and movement"""
    def __init__(self, name, mmsi, ship_type, length=30, beam=10, 
                lat=40.7128, lon=-74.0060, course=90, speed=8, 
                status=0, turn=0, destination=""):
        self.name = name
        self.mmsi = mmsi
        self.ship_type = ship_type
        self.length = length
        self.beam = beam
        self.lat = lat
        self.lon = lon
        self.course = course  # degrees
        self.speed = speed    # knots
        self.status = status  # navigation status
        self.turn = turn      # rate of turn
        self.destination = destination
        self.accuracy = 1     # position accuracy (1=high)
        self.heading = course # heading initially matches course
        
        # New attributes for waypoint navigation
        self.waypoints = []  # List of (lat, lon) tuples
        self.current_waypoint = -1  # Index of current target waypoint
        self.waypoint_radius = 0.01  # ~1km radius to consider waypoint reached
    
    def move(self, elapsed_seconds):
        """Move the ship based on speed and course"""
        if self.speed <= 0:
            return
            
        # Convert speed to position change
        lat_factor = math.cos(math.radians(self.lat))
        hours = elapsed_seconds / 3600
        distance_nm = self.speed * hours
        
        # Calculate position change
        dy = distance_nm * math.cos(math.radians(self.course)) / 60
        dx = distance_nm * math.sin(math.radians(self.course)) / (60 * lat_factor)
        
        # Update position
        self.lat += dy
        self.lon += dx
        
        # Apply turn rate
        if self.turn != 0:
            rot_deg_min = self.turn / 4.0
            course_change = rot_deg_min * (elapsed_seconds / 60.0)
            self.course = (self.course + course_change) % 360
            self.heading = round(self.course)
        
        # Check waypoint navigation
        self.check_waypoint_reached()
    
    def check_waypoint_reached(self):
        """Check and handle reaching of waypoints"""
        if self.current_waypoint == -1 or self.current_waypoint >= len(self.waypoints):
            return  # No valid waypoint to check
        
        target_wp = self.waypoints[self.current_waypoint]
        distance_to_wp = haversine(self.lat, self.lon, target_wp[0], target_wp[1])
        
        if distance_to_wp <= self.waypoint_radius:
            # Waypoint reached
            print(f"Waypoint {self.current_waypoint+1} reached: {target_wp}")
            self.current_waypoint += 1  # Move to next waypoint
            
            if self.current_waypoint < len(self.waypoints):
                # Set course to next waypoint
                next_wp = self.waypoints[self.current_waypoint]
                self.course = calculate_initial_compass_bearing((self.lat, self.lon), next_wp)
                print(f"Course set to next waypoint {self.current_waypoint+1}: {self.course}°")
            else:
                print("All waypoints reached")
    
    def get_ais_fields(self):
        """Get fields for AIS message construction"""
        timestamp = datetime.now().second % 60
        
        return {
            'msg_type': 1,
            'repeat': 0,
            'mmsi': self.mmsi,
            'nav_status': self.status,
            'rot': self.turn,
            'sog': self.speed,
            'accuracy': self.accuracy,
            'lon': self.lon,
            'lat': self.lat,
            'cog': self.course,
            'hdg': self.heading,
            'timestamp': timestamp
        }
        
    def to_dict(self):
        """Convert to dictionary for serialization"""
        return self.__dict__
    
    @classmethod
    def from_dict(cls, data):
        """Create ship from dictionary"""
        ship = cls(
            name=data.get('name', 'Unknown'),
            mmsi=data.get('mmsi', 0),
            ship_type=data.get('ship_type', 0),
            length=data.get('length', 30),
            beam=data.get('beam', 10),
            lat=data.get('lat', 0),
            lon=data.get('lon', 0),
            course=data.get('course', 0),
            speed=data.get('speed', 0),
            status=data.get('status', 0),
            turn=data.get('turn', 0),
            destination=data.get('destination', '')
        )
        ship.accuracy = data.get('accuracy', 1)
        ship.heading = data.get('heading', ship.course)
        return ship

# Global ship configuration
SHIP_CONFIGS = []
ship_simulation_active = False
simulation_thread = None

def save_ship_configs():
    """Save ship configurations to file"""
    try:
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ship_configs.json")
        with open(config_path, 'w') as f:
            json.dump([ship.to_dict() for ship in SHIP_CONFIGS], f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving ship configurations: {e}")
        return False

def load_ship_configs():
    """Load ship configurations from file"""
    global SHIP_CONFIGS
    try:
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ship_configs.json")
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                SHIP_CONFIGS = [AISShip.from_dict(data) for data in json.load(f)]
                return True
    except Exception as e:
        print(f"Error loading ship configurations: {e}")
    
    # Create sample ships if none loaded
    if not SHIP_CONFIGS:
        create_sample_ships()
    return False

def create_sample_ships():
    """Create sample ship configurations"""
    global SHIP_CONFIGS
    
    # Sample ships in New York Harbor
    SHIP_CONFIGS = [
        AISShip("Cargo Vessel 1", 366123001, 70, 100, 20, 40.7028, -74.0160, 45, 8, 0),
        AISShip("Tanker 2", 366123002, 80, 120, 25, 40.7050, -74.0180, 90, 5, 0),
        AISShip("Passenger 3", 366123003, 60, 80, 15, 40.6980, -74.0100, 270, 10, 0),
        AISShip("Tug 4", 366123004, 50, 30, 10, 40.7000, -74.0120, 180, 4, 0),
        AISShip("Ferry 5", 366123005, 60, 40, 12, 40.7060, -74.0140, 0, 12, 0)
    ]

### TRANSMISSION FUNCTIONS ###
def transmit_signal(signal_preset, nmea_sentence=None, status_callback=None):
    """Transmit a signal using HackRF or LimeSDR"""
    if not SDR_AVAILABLE:
        message = "SoapySDR not available. Install with: pip install soapysdr"
        if status_callback:
            status_callback(message)
        else:
            messagebox.showerror("Error", message)
        return False
    
    def update_status(msg):
        print(msg)
        if status_callback:
            status_callback(msg)
    
    try:
        # Add detailed logging of the exact message being transmitted
        if nmea_sentence:
            update_status("=" * 50)
            update_status(f"TRANSMITTING EXACT SENTENCE: {nmea_sentence}")
            
            # Log binary representation too
            if "AIVDM" in nmea_sentence:
                parts = nmea_sentence.split(',')
                if len(parts) >= 6:
                    payload = parts[5]
                    update_status(f"Payload: {payload}")
                    
                    # Show each character and its 6-bit representation
                    bits_log = "Bit representation: "
                    for char in payload:
                        try:
                            bits = char_to_sixbit(char)
                            bits_log += f"[{char}:{bits}] "
                        except ValueError as e:
                            bits_log += f"[{char}:ERROR] "
                    update_status(bits_log)
            update_status("=" * 50)
        
        update_status(f"Preparing to transmit {signal_preset['name']}...")
        
        # Find SDR devices
        devices = []
        try:
            # Try HackRF
            hackrf_devices = SoapySDR.Device.enumerate({'driver': 'hackrf'})
            if hackrf_devices:
                devices = hackrf_devices
                update_status(f"Found {len(hackrf_devices)} HackRF device(s)")
            
            # Try LimeSDR if no HackRF
            if not devices:
                lime_devices = SoapySDR.Device.enumerate({'driver': 'lime'})
                if lime_devices:
                    devices = lime_devices
                    update_status(f"Found {len(lime_devices)} LimeSDR device(s)")
            
            # Try generic enumeration
            if not devices:
                devices = SoapySDR.Device.enumerate()
                update_status(f"Found {len(devices)} generic SDR device(s)")
                
            if not devices:
                raise RuntimeError("No SDR devices found")
        except Exception as e:
            update_status(f"Error finding SDR: {str(e)}")
            raise
        
        # Initialize the SDR
        try:
            try:
                sdr = SoapySDR.Device(devices[0])
            except AttributeError:
                # Fall back to makeDevice for older versions
                sdr = SoapySDR.makeDevice(devices[0])
            update_status("SDR initialized successfully")
        except Exception as e:
            update_status(f"Failed to initialize SDR: {str(e)}")
            # Try generic driver
            try:
                sdr = SoapySDR.Device({'driver': 'hackrf'})
            except AttributeError:
                sdr = SoapySDR.makeDevice({'driver': 'hackrf'})
            update_status("SDR initialized with generic driver")
        
        # Configure SDR parameters
        center_freq = signal_preset["freq"]
        sample_rate = 2e6
        tx_gain = signal_preset["gain"]
        
        update_status(f"Configuring: {center_freq/1e6} MHz, Gain: {tx_gain} dB...")
        
        # Set basic parameters
        sdr.setSampleRate(SOAPY_SDR_TX, 0, sample_rate)
        sdr.setFrequency(SOAPY_SDR_TX, 0, center_freq)
        
        # Set gain - handle different SDR types
        try:
            gain_names = sdr.listGains(SOAPY_SDR_TX, 0)
            print(f"Available gain elements: {gain_names}")
            
            # Try individual gain elements
            if 'AMP' in gain_names:
                amp_value = 14 if tx_gain > 30 else 0
                sdr.setGain(SOAPY_SDR_TX, 0, 'AMP', amp_value)
                print(f"Set AMP gain to {amp_value}")
                
            if 'VGA' in gain_names:
                vga_value = min(47, max(0, tx_gain))
                sdr.setGain(SOAPY_SDR_TX, 0, 'VGA', vga_value)
                print(f"Set VGA gain to {vga_value}")
                
        except Exception as e:
            # Fallback to overall gain
            print(f"Could not set individual gains: {e}")
            sdr.setGain(SOAPY_SDR_TX, 0, tx_gain)
            print(f"Set overall gain to {tx_gain}")
        
        # Try setting bandwidth if supported
        try:
            sdr.setBandwidth(SOAPY_SDR_TX, 0, 1.75e6)
        except Exception as bw_e:
            update_status(f"Note: Cannot set bandwidth ({str(bw_e)})")
        
        # Create signal for transmission
        if signal_preset["modulation"] == "GMSK" and nmea_sentence:
            signal = create_ais_signal(nmea_sentence, sample_rate)
            update_status("Created AIS signal with GMSK modulation")
        else:
            update_status("Error: No valid signal to transmit")
            return False
        
        # Debug signal stats
        print(f"Signal stats: min={np.min(np.abs(signal)):.3f}, max={np.max(np.abs(signal)):.3f}, len={len(signal)}")
        
        # Setup transmission stream
        update_status("Setting up transmission stream...")
        tx_stream = sdr.setupStream(SOAPY_SDR_TX, SOAPY_SDR_CF32, [0])
        sdr.activateStream(tx_stream)
        
        # Transmit
        update_status("Transmitting signal...")
        status = sdr.writeStream(tx_stream, [signal], len(signal))
        update_status(f"Transmission status: {status}")
        
        # Cleanup
        update_status("Cleaning up...")
        time.sleep(1.0)  # Allow time to finish
        
        sdr.deactivateStream(tx_stream)
        sdr.closeStream(tx_stream)
        
        # Force Python garbage collection
        del sdr
        time.sleep(0.5)
        
        update_status(f"Successfully transmitted on {center_freq/1e6} MHz")
        return True
        
    except Exception as e:
        error_msg = f"Transmission Error: {str(e)}"
        update_status(error_msg)
        
        recovery_msg = """
Try these recovery steps:
1. Unplug the SDR and wait 10 seconds
2. Plug it back into a different USB port
3. Run these commands in the terminal:
   hackrf_info
   hackrf_transfer -R   (This resets the device)

If problems persist, try restarting your computer.
"""
        update_status(recovery_msg)
        return False

def run_ship_simulation(signal_preset, interval=10, update_status_callback=None):
    """Run AIS ship simulation"""
    global ship_simulation_active
    ship_simulation_active = True
    
    def update_status(msg):
        print(msg)
        if update_status_callback:
            update_status_callback(msg)
    
    last_move_time = datetime.now()
    
    try:
        update_status("Starting AIS ship simulation...")
        
        while ship_simulation_active and SHIP_CONFIGS:
            # Calculate elapsed time
            current_time = datetime.now()
            elapsed = (current_time - last_move_time).total_seconds()
            
            # Move all ships
            for ship in SHIP_CONFIGS:
                ship.move(elapsed)
            
            # Transmit AIS message for each ship
            for i, ship in enumerate(SHIP_CONFIGS):
                if not ship_simulation_active:
                    break
                    
                # Create NMEA message
                fields = ship.get_ais_fields()
                payload, fill = build_ais_payload(fields)
                
                # Alternate channels
                channel = 'A' if i % 2 == 0 else 'B'
                sentence = f"AIVDM,1,1,,{channel},{payload},{fill}"
                cs = compute_checksum(sentence)
                full_sentence = f"!{sentence}*{cs}"
                
                update_status(f"Transmitting ship {i+1}/{len(SHIP_CONFIGS)}: {ship.name} (MMSI: {ship.mmsi})")
                
                # Transmit
                transmit_signal(signal_preset, full_sentence, update_status)
                
                # Delay between ships
                time.sleep(0.5)
            
            # Save move time
            last_move_time = current_time
            
            # Wait until next cycle
            if ship_simulation_active:
                update_status(f"Waiting {interval} seconds until next transmission...")
                time.sleep(interval)
    
    except Exception as e:
        update_status(f"Error in ship simulation: {e}")
    finally:
        ship_simulation_active = False
        update_status("Ship simulation stopped")

def update_ship_listbox():
    """Update the ship listbox with current configurations"""
    ship_listbox.delete(0, tk.END)
    
    for i, ship in enumerate(SHIP_CONFIGS):
        ship_listbox.insert(i, f"{ship.name} (MMSI: {ship.mmsi}) - {ship.speed} kts, {ship.course}°")

### GUI SETUP ###
# Create main window
root = tk.Tk()
root.title("AIS NMEA Generator & Transmitter")
root.minsize(800, 600)

# Main frame
main_frame = ttk.Frame(root, padding=10)
main_frame.pack(fill=tk.BOTH, expand=True)

# Create tabbed interface
notebook = ttk.Notebook(main_frame)
notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

# ----- Tab 1: AIS Message Generator -----
ais_frame = ttk.Frame(notebook, padding=10)
notebook.add(ais_frame, text="AIS Generator")

# Left side - Input parameters
input_frame = ttk.LabelFrame(ais_frame, text="Message Parameters", padding=10)
input_frame.grid(row=0, column=0, sticky=(tk.N, tk.W, tk.E, tk.S), padx=5, pady=5)

# Create input fields
labels = ["Message Type", "Repeat", "MMSI", "Nav Status",
          "ROT (-127..127)", "SOG (knots)", "Accuracy (0/1)",
          "Longitude (°)", "Latitude (°)", "COG (°)",
          "Heading (°)", "Timestamp (s)"]
vars_ = []
for i, lbl in enumerate(labels):
    ttk.Label(input_frame, text=lbl).grid(column=0, row=i, sticky=tk.W, padx=5, pady=2)
    var = tk.StringVar(value="0")
    entry = ttk.Entry(input_frame, textvariable=var, width=15)
    entry.grid(column=1, row=i, sticky=tk.W, padx=5, pady=2)
    vars_.append(var)

# Assign variables
(msg_type_var, repeat_var, mmsi_var, nav_status_var,
 rot_var, sog_var, acc_var, lon_var,
 lat_var, cog_var, hdg_var, ts_var) = vars_

# Default values
msg_type_var.set("1")
repeat_var.set("0")
mmsi_var.set("366123456")
nav_status_var.set("0")
lon_var.set("-74.0060")
lat_var.set("40.7128")
sog_var.set("10.0")
cog_var.set("90.0")

# Generate button
gen_btn = ttk.Button(input_frame, text="Generate Message", command=lambda: generate())
gen_btn.grid(column=0, row=len(labels)+1, columnspan=2, pady=10)

# Right side - Output
output_frame = ttk.LabelFrame(ais_frame, text="Message Output", padding=10)
output_frame.grid(row=0, column=1, sticky=(tk.N, tk.W, tk.E, tk.S), padx=5, pady=5)

# Output fields
ttk.Label(output_frame, text="AIS Payload:").grid(column=0, row=0, sticky=tk.W, pady=5)
payload_var = tk.StringVar()
ttk.Entry(output_frame, textvariable=payload_var, width=40).grid(column=0, row=1, sticky=(tk.W, tk.E))

ttk.Label(output_frame, text="Fill Bits:").grid(column=0, row=2, sticky=tk.W, pady=5)
fill_var = tk.StringVar()
ttk.Entry(output_frame, textvariable=fill_var, width=5).grid(column=0, row=3, sticky=tk.W)

ttk.Label(output_frame, text="NMEA Sentence:").grid(column=0, row=4, sticky=tk.W, pady=5)
nmea_var = tk.StringVar()
ttk.Entry(output_frame, textvariable=nmea_var, width=60).grid(column=0, row=5, sticky=(tk.W, tk.E))

# Signal selection
signal_frame = ttk.LabelFrame(output_frame, text="Transmission Signal", padding=10)
signal_frame.grid(column=0, row=6, sticky=(tk.W, tk.E), pady=10)

# Listbox for signal selection
signal_listbox = tk.Listbox(signal_frame, height=5)
signal_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# Add scroll bar
scrollbar = ttk.Scrollbar(signal_frame, orient="vertical", command=signal_listbox.yview)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
signal_listbox.configure(yscrollcommand=scrollbar.set)

# Populate the signal listbox
for i, preset in enumerate(SIGNAL_PRESETS):
    signal_listbox.insert(i, f"{preset['name']} ({preset['freq']/1e6} MHz)")
signal_listbox.selection_set(0)

# Edit signal button
edit_btn = ttk.Button(output_frame, text="Edit Signal Settings", command=lambda: edit_signal_preset())
edit_btn.grid(column=0, row=7, sticky=tk.W, pady=5)

# Transmit button
tx_btn = ttk.Button(output_frame, text="Transmit Message", command=lambda: transmit())
tx_btn.grid(column=0, row=8, sticky=(tk.W, tk.E), pady=10)
if not SDR_AVAILABLE:
    tx_btn.config(state="disabled")

# --- AIS Message Type Reference Panel ---
ais_type_frame = ttk.LabelFrame(ais_frame, text="AIS Message Types Reference", padding=10)
ais_type_frame.grid(row=0, column=2, sticky=(tk.N, tk.W, tk.E, tk.S), padx=10, pady=5)

ais_type_text = tk.Text(ais_type_frame, width=38, height=22, wrap=tk.WORD)
ais_type_text.pack(fill=tk.BOTH, expand=True)

ais_type_text.insert(tk.END, """\
AIS Message Types (for 'Message Type' input):

1 - Position Report Class A
2 - Position Report Class A (Assigned schedule)
3 - Position Report Class A (Response to interrogation)
4 - Base Station Report
5 - Static and Voyage Related Data
6 - Binary Addressed Message
7 - Binary Acknowledge
8 - Binary Broadcast Message
9 - Standard SAR Aircraft Position Report
10 - UTC/Date Inquiry
11 - UTC/Date Response
12 - Addressed Safety Related Message
13 - Safety Related Acknowledge
14 - Safety Related Broadcast Message
15 - Interrogation
16 - Assignment Mode Command
17 - GNSS Broadcast Binary Message
18 - Standard Class B CS Position Report
19 - Extended Class B Equipment Position Report
20 - Data Link Management
21 - Aid-to-Navigation Report
22 - Channel Management
23 - Group Assignment Command
24 - Static Data Report (Class B)
25 - Single Slot Binary Message
26 - Multiple Slot Binary Message
27 - Long Range AIS Broadcast Message

For most ship position reports, use type 1, 2, 3, 18, or 19.
""")
ais_type_text.config(state=tk.DISABLED)

# ----- Tab 2: Transmission Log -----
log_frame = ttk.Frame(notebook, padding=10)
notebook.add(log_frame, text="Transmission Log")

# Text area for logs
log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, width=80, height=20)
log_text.pack(fill=tk.BOTH, expand=True)
log_text.configure(state='disabled')

# ----- Tab 3: Ship Simulation -----
sim_frame = ttk.Frame(notebook, padding=10)
notebook.add(sim_frame, text="Ship Simulation")

# Left side - Ship list
ship_list_frame = ttk.LabelFrame(sim_frame, text="Ships", padding=10)
ship_list_frame.grid(row=0, column=0, sticky=(tk.N, tk.W, tk.E, tk.S), padx=5, pady=5)

# Ship selection listbox
ship_listbox = tk.Listbox(ship_list_frame, height=15, selectmode=tk.MULTIPLE)
ship_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# Add scroll bar
ship_scrollbar = ttk.Scrollbar(ship_list_frame, orient="vertical", command=ship_listbox.yview)
ship_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
ship_listbox.configure(yscrollcommand=ship_scrollbar.set)

# Ship control buttons
ship_control_frame = ttk.Frame(ship_list_frame)
ship_control_frame.pack(fill=tk.X, pady=10)

# Add/Edit/Delete buttons
add_ship_btn = ttk.Button(ship_control_frame, text="Add Ship", command=lambda: add_new_ship())
add_ship_btn.pack(side=tk.LEFT, padx=5)

edit_ship_btn = ttk.Button(ship_control_frame, text="Edit Ship", command=lambda: edit_selected_ship())
edit_ship_btn.pack(side=tk.LEFT, padx=5)

delete_ship_btn = ttk.Button(ship_control_frame, text="Delete Ship", command=lambda: delete_selected_ships())
delete_ship_btn.pack(side=tk.LEFT, padx=5)

# Right side - Simulation controls
sim_control_frame = ttk.LabelFrame(sim_frame, text="Simulation Controls", padding=10)
sim_control_frame.grid(row=0, column=1, sticky=(tk.N, tk.W, tk.E, tk.S), padx=5, pady=5)

# Channel selection
ttk.Label(sim_control_frame, text="AIS Channel:").grid(row=0, column=0, sticky=tk.W, pady=5)
sim_channel_var = tk.StringVar(value="0")
ttk.Combobox(sim_control_frame, textvariable=sim_channel_var, 
             values=["0", "1"]).grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5)

# Interval setting
ttk.Label(sim_control_frame, text="Interval (seconds):").grid(row=1, column=0, sticky=tk.W, pady=5)
sim_interval_var = tk.StringVar(value="10")
ttk.Entry(sim_control_frame, textvariable=sim_interval_var, width=5).grid(row=1, column=1, sticky=(tk.W, tk.E))

# Start/Stop buttons
start_sim_btn = ttk.Button(sim_control_frame, text="Start Simulation", command=lambda: start_ship_simulation())
start_sim_btn.grid(row=2, column=0, columnspan=2, pady=10)

stop_sim_btn = ttk.Button(sim_control_frame, text="Stop Simulation", command=lambda: stop_ship_simulation())
stop_sim_btn.grid(row=3, column=0, columnspan=2, pady=10)
stop_sim_btn.config(state=tk.DISABLED)

def start_ship_simulation():
    """Start the ship simulation"""
    global ship_simulation_active, simulation_thread
    
    if ship_simulation_active:
        messagebox.showinfo("Already Running", "Simulation is already running")
        return
    
    # Get simulation parameters
    channel_idx = int(sim_channel_var.get())
    if channel_idx < 0 or channel_idx >= len(SIGNAL_PRESETS):
        messagebox.showerror("Error", "Invalid channel selection")
        return
    
    try:
        interval = int(sim_interval_var.get())
        if interval < 1:
            raise ValueError("Interval must be at least 1 second")
    except ValueError as e:
        messagebox.showerror("Invalid Interval", str(e))
        return
    
    # Get selected signal preset
    signal_preset = SIGNAL_PRESETS[channel_idx]
    
    # Update UI
    sim_status_var.set("Simulation Running...")
    start_sim_btn.config(state=tk.DISABLED)
    stop_sim_btn.config(state=tk.NORMAL)
    
    # Clear log
    sim_log_text.configure(state='normal')
    sim_log_text.delete(1.0, tk.END)
    sim_log_text.configure(state='disabled')
    
    # Update log function
    def update_sim_log(msg):
        sim_log_text.configure(state='normal')
        sim_log_text.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')}: {msg}\n")
        sim_log_text.see(tk.END)
        sim_log_text.configure(state='disabled')
    
    # Start simulation thread
    simulation_thread = threading.Thread(
        target=run_ship_simulation, 
        args=(signal_preset, interval, update_sim_log),
        daemon=True
    )
    simulation_thread.start()

# Simulation log
sim_log_frame = ttk.LabelFrame(sim_control_frame, text="Simulation Log", padding=10)
sim_log_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)

sim_log_text = scrolledtext.ScrolledText(sim_log_frame, wrap=tk.WORD, width=40, height=10)
sim_log_text.pack(fill=tk.BOTH, expand=True)
sim_log_text.configure(state='disabled')

# Status indicator
sim_status_var = tk.StringVar(value="Ready")
ttk.Label(sim_control_frame, textvariable=sim_status_var).grid(row=5, column=0, columnspan=2, pady=5)

# Status bar
status_var = tk.StringVar()
status_var.set("Ready" if SDR_AVAILABLE else "SDR support not available")
ttk.Label(main_frame, textvariable=status_var, relief=tk.SUNKEN, anchor=tk.W).pack(side=tk.BOTTOM, fill=tk.X)

# ----- Tab 4: Map Visualization -----
map_frame = ttk.Frame(notebook, padding=10)
notebook.add(map_frame, text="Map View")

# --- Map Search Bar ---
if MAP_VIEW_AVAILABLE:
    search_frame = ttk.Frame(map_frame)
    search_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 5))
    search_var = tk.StringVar()
    ttk.Label(search_frame, text="Search Location:").pack(side=tk.LEFT, padx=5)
    search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
    search_entry.pack(side=tk.LEFT, padx=5)
    def do_search(*args):
        query = search_var.get().strip()
        if not query:
            return
        # Try to parse as lat,lon first
        try:
            if ',' in query:
                lat, lon = map(float, query.split(','))
                map_widget.set_position(lat, lon)
                map_widget.set_zoom(12)
                return
        except Exception:
            pass
        # Otherwise, use geocoding
        try:
            result = map_widget.set_address(query)
            if result:
                map_widget.set_zoom(12)
        except Exception as e:
            messagebox.showerror("Search Error", f"Could not find location: {e}")
    ttk.Button(search_frame, text="Go", command=do_search).pack(side=tk.LEFT, padx=5)
    search_entry.bind('<Return>', lambda event: do_search())

# Ship tracking variables
ship_markers = {}  # Dictionary to store ship markers on map
ship_tracks = {}   # Dictionary to store historical positions for each ship
track_lines = {}   # Dictionary to store the polyline objects for ship tracks

# Split map frame into two parts: map and control panel
map_container = ttk.Frame(map_frame)
map_container.grid(row=1, column=0, sticky=(tk.N, tk.W, tk.E, tk.S))  # <-- row=1 so search bar is above

map_control_panel = ttk.LabelFrame(map_frame, text="Map Controls", padding=10)
map_control_panel.grid(row=1, column=1, sticky=(tk.N, tk.W, tk.S), padx=5)

# Make the map expand with window resizing
map_frame.columnconfigure(0, weight=1)
map_frame.rowconfigure(1, weight=1)  # <-- row=1 for map
map_container.columnconfigure(0, weight=1)
map_container.rowconfigure(0, weight=1)

if MAP_VIEW_AVAILABLE:
    # Create the map widget (ONLY ONCE)
    map_widget = tkintermapview.TkinterMapView(map_container, width=600, height=400, corner_radius=0)
    map_widget.grid(row=0, column=0, sticky=(tk.N, tk.W, tk.E, tk.S))
    
    # Set default position (Portugal)
    map_widget.set_tile_server("https://a.tile.openstreetmap.org/{z}/{x}/{y}.png")    
    map_widget.set_position(39.5, -9.25)  # Portugal area
    map_widget.set_zoom(8)
else:
    # Fallback if map widget is not available
    map_fallback_frame = ttk.LabelFrame(map_container, text="Map Not Available", padding=20)
    map_fallback_frame.grid(row=0, column=0, sticky=(tk.N, tk.W, tk.E, tk.S))
    
    ttk.Label(map_fallback_frame, text="tkintermapview module is required for the map display.").pack(pady=10)
    ttk.Label(map_fallback_frame, text="Install using: pip install tkintermapview").pack(pady=5)
    
    def open_browser_map():
        # Open a web-based map as fallback
        webbrowser.open("https://www.openstreetmap.org/#map=12/40.7128/-74.0060")
    
    ttk.Button(map_fallback_frame, text="Open Map in Browser", command=open_browser_map).pack(pady=20)

# Map control elements
ttk.Label(map_control_panel, text="Tracking Options:").grid(row=0, column=0, sticky=tk.W, pady=5)

# Track history length
ttk.Label(map_control_panel, text="Track History:").grid(row=1, column=0, sticky=tk.W, pady=5)
track_history_var = tk.StringVar(value="20")
track_history_entry = ttk.Entry(map_control_panel, textvariable=track_history_var, width=5)
track_history_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
ttk.Label(map_control_panel, text="points").grid(row=1, column=2, sticky=tk.W)

# Track display toggle
show_tracks_var = tk.BooleanVar(value=True)
show_tracks_check = ttk.Checkbutton(map_control_panel, text="Show Tracks", variable=show_tracks_var)
show_tracks_check.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=5)

# Define track visibility toggle function
def toggle_track_visibility():
    """Toggle visibility of ship tracks on map"""
    if not MAP_VIEW_AVAILABLE:
        return
        
    show_tracks = show_tracks_var.get()
    
    for mmsi, track_line in track_lines.items():
        if not show_tracks and track_line:
            # Hide track
            map_widget.delete(track_line)
            track_lines[mmsi] = None
        elif show_tracks and not track_line and mmsi in ship_tracks and len(ship_tracks[mmsi]) > 1:
            # Show track
            track_line = map_widget.set_path(
                ship_tracks[mmsi],
                width=2,
                color=f"#{mmsi % 0xFFFFFF:06x}"
            )
            track_lines[mmsi] = track_line

# Map type selection
ttk.Label(map_control_panel, text="Map Type:").grid(row=3, column=0, sticky=tk.W, pady=10)
map_type_var = tk.StringVar(value="OpenStreetMap")
if MAP_VIEW_AVAILABLE:
    map_type_combo = ttk.Combobox(map_control_panel, textvariable=map_type_var, 
                                 values=["OpenStreetMap", "Google Normal", "Google Satellite"])
    map_type_combo.grid(row=3, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=10)
    
    def change_map_type(event=None):
        selected = map_type_var.get()
        if selected == "OpenStreetMap":
            map_widget.set_tile_server("https://a.tile.openstreetmap.org/{z}/{x}/{y}.png")
        elif selected == "Google Normal":
            map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=m&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)
        elif selected == "Google Satellite":
            map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)
    
    map_type_combo.bind("<<ComboboxSelected>>", change_map_type)
else:
    ttk.Combobox(map_control_panel, textvariable=map_type_var, 
                values=["OpenStreetMap"], state="disabled").grid(row=3, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=10)

# Center map button
def center_map_on_ships():
    if not MAP_VIEW_AVAILABLE or not SHIP_CONFIGS:
        return
        
    # Calculate the center and bounds of all ships
    lats = [ship.lat for ship in SHIP_CONFIGS]
    lons = [ship.lon for ship in SHIP_CONFIGS]
    
    if not lats or not lons:
        return
        
    # Calculate center
    center_lat = sum(lats) / len(lats)
    center_lon = sum(lons) / len(lons)
    
    # Calculate zoom level based on spread
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    
    # Set position and appropriate zoom
    map_widget.set_position(center_lat, center_lon)
    
    # If ships are far apart, adjust zoom to fit all
    if max(max_lat - min_lat, (max_lon - min_lon) * math.cos(math.radians(center_lat))) > 0.1:
        map_widget.fit_bounding_box((min_lat, min_lon), (max_lat, max_lon))
    else:
        map_widget.set_zoom(12)  # Default zoom if ships are close together

ttk.Button(map_control_panel, text="Center on Ships", command=center_map_on_ships).grid(
    row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)

# Clear tracks button
def clear_all_tracks():
    if not MAP_VIEW_AVAILABLE:
        return
        
    for mmsi, track_line in track_lines.items():
        if track_line:
            map_widget.delete(track_line)
    
    track_lines.clear()
    
    for mmsi in ship_tracks:
        ship_tracks[mmsi] = []
        
    update_map(force=True)

ttk.Button(map_control_panel, text="Clear All Tracks", command=clear_all_tracks).grid(
    row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)

# Ship information display
ship_info_frame = ttk.LabelFrame(map_control_panel, text="Selected Ship Info", padding=10)
ship_info_frame.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=15)

ship_info_text = tk.Text(ship_info_frame, width=25, height=8, wrap=tk.WORD)
ship_info_text.pack(fill=tk.BOTH, expand=True)
ship_info_text.insert(tk.END, "Click on a ship to view details")
ship_info_text.config(state=tk.DISABLED)

# --- MID to Country Mapping and Flag Extraction ---
MID_TO_COUNTRY = {
    201: "Albania", 202: "Andorra", 203: "Austria", 204: "Azores", 205: "Belgium",
    206: "Belarus", 207: "Bulgaria", 209: "Cyprus", 210: "Cyprus", 211: "Germany",
    212: "Cyprus", 213: "Georgia", 214: "Moldova", 215: "Malta", 218: "Germany",
    219: "Denmark", 220: "Denmark", 224: "Spain", 225: "Spain", 226: "France",
    227: "France", 228: "France", 229: "Malta", 230: "Finland", 231: "Faeroe Islands",
    232: "United Kingdom", 233: "United Kingdom", 234: "United Kingdom", 235: "United Kingdom",
    236: "Gibraltar", 237: "Greece", 238: "Croatia", 239: "Greece", 240: "Greece",
    241: "Greece", 242: "Morocco", 243: "Hungary", 244: "Netherlands", 245: "Netherlands",
    246: "Netherlands", 247: "Italy", 248: "Malta", 249: "Malta", 250: "Ireland",
    251: "Iceland", 252: "Liechtenstein", 253: "Luxembourg", 254: "Monaco", 255: "Portugal",
    256: "Malta", 257: "Norway", 258: "Norway", 259: "Norway", 261: "Poland",
    262: "Montenegro", 263: "Portugal", 264: "Romania", 265: "Sweden", 266: "Sweden",
    267: "Slovakia", 268: "San Marino", 269: "Switzerland", 270: "Czech Republic",
    271: "Turkey", 272: "Ukraine", 273: "Russia", 274: "Macedonia", 275: "Latvia",
    276: "Estonia", 277: "Lithuania", 278: "Slovenia", 279: "Serbia", 301: "Anguilla",
    303: "Alaska (USA)", 304: "Antigua and Barbuda", 305: "Antigua and Barbuda", 306: "Aruba",
    307: "Netherlands Antilles", 308: "Bahamas", 309: "Bahamas", 310: "Bermuda",
    311: "Bahamas", 312: "Belize", 314: "Barbados", 316: "Canada", 319: "Cayman Islands",
    321: "Costa Rica", 325: "Dominica", 327: "Dominican Republic", 329: "Guadeloupe",
    330: "Grenada", 331: "Greenland", 332: "Guatemala", 334: "Honduras", 336: "Haiti",
    338: "United States", 339: "Jamaica", 341: "Saint Kitts and Nevis", 343: "Saint Lucia",
    345: "Mexico", 348: "Montserrat", 350: "Nicaragua", 351: "Panama", 352: "Panama",
    353: "Panama", 354: "Panama", 355: "Panama", 356: "Panama", 357: "Panama",
    358: "Puerto Rico", 359: "Saint Vincent and the Grenadines", 361: "Trinidad and Tobago",
    362: "Trinidad and Tobago", 364: "Turks and Caicos Islands", 366: "United States",
    367: "United States", 368: "United States", 369: "United States", 370: "Panama",
    371: "Panama", 372: "Panama", 373: "Panama", 374: "Panama", 375: "Saint Pierre and Miquelon",
    376: "Saint Vincent and the Grenadines", 377: "Saint Vincent and the Grenadines",
    378: "British Virgin Islands", 379: "United States Virgin Islands", 401: "Afghanistan",
    # ... (add more as needed)
}

def get_flag_from_mmsi(mmsi):
    try:
        mid = int(str(mmsi)[:3])
        return MID_TO_COUNTRY.get(mid, "Unknown")
    except Exception:
        return "Unknown"

# Create ship icons if PIL is available
ship_icon = None
ship_icon_selected = None

if PIL_AVAILABLE and MAP_VIEW_AVAILABLE:
    # Create a simple ship icon (triangle pointing in direction of travel)
    def create_ship_icon(color="blue", size=20):
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        # Draw a ship-like triangle
        draw.polygon([(size//2, 0), (0, size), (size, size)], fill=color)
        return ImageTk.PhotoImage(img)
    
    # Create standard and selected ship icons
    ship_icon = create_ship_icon(color="blue", size=24)
    ship_icon_selected = create_ship_icon(color="red", size=24)

# Function to update the map with current ship positions
def update_map(force=False):
    if not MAP_VIEW_AVAILABLE:
        return
        
    # Get track history length
    try:
        max_track_points = max(1, min(100, int(track_history_var.get())))
    except ValueError:
        max_track_points = 20  # Default value
    
    # Update each ship's position on the map
    for ship in SHIP_CONFIGS:
        mmsi = ship.mmsi
        
        # Add current position to track history
        if mmsi not in ship_tracks:
            ship_tracks[mmsi] = []
        
        # Add position to track if it has changed
        last_position = ship_tracks[mmsi][-1] if ship_tracks[mmsi] else None
        current_position = (ship.lat, ship.lon)
        
        if not last_position or last_position != current_position or force:
            ship_tracks[mmsi].append(current_position)
            
            # Limit track history
            while len(ship_tracks[mmsi]) > max_track_points:
                ship_tracks[mmsi].pop(0)
            
            # Update or create ship marker
            if mmsi in ship_markers:
                # Update existing marker
                ship_markers[mmsi].position = current_position
                
                # Also update the ship marker's rotation if supported
                if hasattr(ship_markers[mmsi], 'set_marker_text_color'):
                    ship_markers[mmsi].text = f"{ship.name}\n{ship.speed}kn"
            else:
                # Create new marker
                marker_text = f"{ship.name}\n{ship.speed}kn"
                marker = map_widget.set_marker(
                    ship.lat, ship.lon,
                    text=marker_text,
                    icon=ship_icon
                )
                
                # Store ship reference in marker for click handler
                marker.ship_ref = ship
                
                # Add click event to show ship details
                def make_click_handler(ship_obj, marker_obj):
                    def on_marker_click(marker=None):  # Accept an optional parameter
                        # Update ship info display
                        ship_info_text.config(state=tk.NORMAL)
                        ship_info_text.delete(1.0, tk.END)
                        
                        # Format ship info
                        info = (
                            f"Name: {ship_obj.name}\n"
                            f"MMSI: {ship_obj.mmsi}\n"
                            f"Position: {ship_obj.lat:.5f}, {ship_obj.lon:.5f}\n"
                            f"Course: {ship_obj.course}°\n"
                            f"Speed: {ship_obj.speed} knots\n"
                            f"Status: {ship_obj.status}\n"
                        )
                        ship_info_text.insert(tk.END, info)
                        ship_info_text.config(state=tk.DISABLED)
                        
                        # Reset all markers first
                        for mmsi_key, m in ship_markers.items():
                            # Set all markers back to default
                            if PIL_AVAILABLE and ship_icon:
                                try:
                                    m.icon = ship_icon  # Reset icon
                                    m.icon_anchor = None  # Reset anchor if needed
                                except:
                                    pass  # If any error occurs, just continue
                        
                        # Now highlight the selected marker
                        if PIL_AVAILABLE and ship_icon_selected:
                            try:
                                marker_obj.icon = ship_icon_selected
                            except:
                                pass
                                
                        # Force a redraw of the map widget
                        if MAP_VIEW_AVAILABLE:
                            map_widget.update_idletasks()
                    
                    return on_marker_click
                
                marker.command = make_click_handler(ship, marker)
                ship_markers[mmsi] = marker
            
            # Update ship track polyline if enabled
            if show_tracks_var.get() and len(ship_tracks[mmsi]) > 1:
                # Delete existing track line if it exists
                if mmsi in track_lines and track_lines[mmsi]:
                    map_widget.delete(track_lines[mmsi])
                
                # Create new track line
                track_line = map_widget.set_path(
                    ship_tracks[mmsi],
                    width=2,
                    color=f"#{mmsi % 0xFFFFFF:06x}"  # Generate color based on MMSI
                )
                track_lines[mmsi] = track_line
            elif not show_tracks_var.get() and mmsi in track_lines and track_lines[mmsi]:
                # Hide track if track display is disabled
                map_widget.delete(track_lines[mmsi])
                track_lines[mmsi] = None

# Add update_map to the ship simulation process
original_run_ship_simulation = run_ship_simulation

def enhanced_run_ship_simulation(*args, **kwargs):
    """Wrapper around original run_ship_simulation to add map updates"""
    global ship_simulation_active
    ship_simulation_active = True
    
    def map_update_thread():
        while ship_simulation_active:
            # Update map on UI thread
            root.after(0, update_map)
            time.sleep(1)  # Update map once per second
    
    # Start map update thread
    if MAP_VIEW_AVAILABLE:
        threading.Thread(target=map_update_thread, daemon=True).start()
    
    # Run original simulation
    original_run_ship_simulation(*args, **kwargs)

# Replace the original function with our enhanced version
run_ship_simulation = enhanced_run_ship_simulation

# Additional enhancements to hook into existing UI actions

def start_ship_simulation_with_map():
    """Enhanced version that updates the map too"""
def enhanced_stop_ship_simulation():
    """Enhanced version that updates the map"""
    global ship_simulation_active
    ship_simulation_active = False
    
    original_stop_ship_simulation()
    
    if MAP_VIEW_AVAILABLE:
        # Clear markers from map when simulation stops
        for marker in ship_markers.values():
            map_widget.delete(marker)
        ship_markers.clear()

def stop_ship_simulation():
    """Stop the ship simulation"""
    global ship_simulation_active
    ship_simulation_active = False
    
    sim_status_var.set("Simulation Stopped")
    start_sim_btn.config(state=tk.NORMAL)
    stop_sim_btn.config(state=tk.DISABLED)
    
    # Reload ship configs
    load_ship_configs()
    update_ship_listbox()
        
    show_tracks = show_tracks_var.get()
    for mmsi, track_line in track_lines.items():
        if not show_tracks and track_line:
            # Hide track
            map_widget.delete(track_line)
            track_lines[mmsi] = None
        elif show_tracks and not track_line and mmsi in ship_tracks and len(ship_tracks[mmsi]) > 1:
            # Show track
            track_line = map_widget.set_path(
                ship_tracks[mmsi],
                width=2,
                color=f"#{mmsi % 0xFFFFFF:06x}"
            )
            track_lines[mmsi] = track_line

# Connect toggle function
show_tracks_check.config(command=toggle_track_visibility)

# Initialize map with current ship positions if available
if MAP_VIEW_AVAILABLE and SHIP_CONFIGS:
    root.after(1000, update_map)  # Update map soon after startup
    root.after(1500, center_map_on_ships)  # Center map after initialization

# Make sure we clear everything when exiting
def original_stop_ship_simulation():
    """Stop the ship simulation"""
    global ship_simulation_active
    ship_simulation_active = False
    
    sim_status_var.set("Simulation Stopped")
    start_sim_btn.config(state=tk.NORMAL)
    stop_sim_btn.config(state=tk.DISABLED)
    
    # Reload ship configs
    load_ship_configs()
    update_ship_listbox()

def enhanced_stop_ship_simulation():
    """Enhanced version that updates the map"""
    global ship_simulation_active
    ship_simulation_active = False
    
    original_stop_ship_simulation()
    
    if MAP_VIEW_AVAILABLE:
        # Clear markers from map when simulation stops
        for marker in ship_markers.values():
            map_widget.delete(marker)
        ship_markers.clear()

# Update geometry weights for resizing
root.grid_rowconfigure(0, weight=1)
root.grid_columnconfigure(0, weight=1)

# Define functions that were referenced in button commands
def generate():
    """Generate AIS message from GUI input fields"""
    try:
        # Collect field values
        fields = {
            'msg_type': int(msg_type_var.get()),
            'repeat': int(repeat_var.get()),
            'mmsi': int(mmsi_var.get()),
            'nav_status': int(nav_status_var.get()),
            'rot': int(rot_var.get()),
            'sog': float(sog_var.get()),
            'accuracy': int(acc_var.get()),
            'lon': float(lon_var.get()),
            'lat': float(lat_var.get()),
            'cog': float(cog_var.get()),
            'hdg': int(hdg_var.get()),
            'timestamp': int(ts_var.get())
        }
        
        # Build payload
        payload, fill = build_ais_payload(fields)
        payload_var.set(payload)
        fill_var.set(str(fill))
        
        # Create NMEA sentence
        channel = 'A'
        sentence = f"AIVDM,1,1,,{channel},{payload},{fill}"
        cs = compute_checksum(sentence)
        full_sentence = f"!{sentence}*{cs}"
        nmea_var.set(full_sentence)
    except Exception as e:
        messagebox.showerror("Error", str(e))

def transmit():
    """Transmit generated AIS message"""
    nmea_sentence = nmea_var.get()
    if not nmea_sentence:
        messagebox.showerror("Error", "Generate an AIS message first")
        return
    
    # Get selected signal preset
    selected_index = signal_listbox.curselection()
    if not selected_index:
        messagebox.showerror("Error", "Select a signal type")
        return
    
    selected_preset = SIGNAL_PRESETS[selected_index[0]]
    
    # Confirm transmission
    if messagebox.askyesno("Transmit", 
                          f"Transmit AIS message using {selected_preset['name']}?\n"
                          f"Frequency: {selected_preset['freq']/1e6} MHz\n\n"
                          "Ensure you have proper authorization to transmit."):
        
        # Update function for log
        def update_log(msg):
            log_text.configure(state='normal')
            log_text.insert(tk.END, f"{msg}\n")
            log_text.see(tk.END)
            log_text.configure(state='disabled')
            status_var.set(f"Last action: {msg}")
        
        # Start transmission thread
        threading.Thread(
            target=transmit_signal, 
            args=(selected_preset, nmea_sentence, update_log),
            daemon=True
        ).start()

def edit_signal_preset():
    """Edit a signal preset"""
    selected_index = signal_listbox.curselection()
    if not selected_index:
        messagebox.showerror("Error", "Select a signal to edit")
        return
        
    idx = selected_index[0]
    preset = SIGNAL_PRESETS[idx]
    
    # Create edit dialog
    edit_window = tk.Toplevel(root)
    edit_window.title(f"Edit {preset['name']}")
    edit_window.geometry("300x200")
    
    # Create form
    frame = ttk.Frame(edit_window, padding=10)
    frame.pack(fill=tk.BOTH, expand=True)
    
    # Add form fields
    ttk.Label(frame, text="Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
    name_var = tk.StringVar(value=preset["name"])
    ttk.Entry(frame, textvariable=name_var).grid(row=0, column=1, sticky=(tk.W, tk.E))
    
    ttk.Label(frame, text="Frequency (MHz):").grid(row=1, column=0, sticky=tk.W, pady=5)
    freq_var = tk.StringVar(value=str(preset["freq"]/1e6))
    ttk.Entry(frame, textvariable=freq_var).grid(row=1, column=1, sticky=(tk.W, tk.E))
    
    ttk.Label(frame, text="Gain (0-70):").grid(row=2, column=0, sticky=tk.W, pady=5)
    gain_var = tk.StringVar(value=str(preset["gain"]))
    ttk.Entry(frame, textvariable=gain_var).grid(row=2, column=1, sticky=(tk.W, tk.E))
    
    ttk.Label(frame, text="Modulation:").grid(row=3, column=0, sticky=tk.W, pady=5)
    mod_var = tk.StringVar(value=preset["modulation"])
    ttk.Combobox(frame, textvariable=mod_var, 
                values=["GMSK"]).grid(row=3, column=1)
    
    # Save function
    def save_changes():
        try:
            # Validate inputs
            freq_mhz = float(freq_var.get())
            gain = int(gain_var.get())
            
            if gain < 0 or gain > 70:
                raise ValueError("Gain must be between 0 and 70")
                
            if freq_mhz <= 0:
                raise ValueError("Frequency must be positive")
                
            # Update preset
            SIGNAL_PRESETS[idx] = {
                "name": name_var.get(),
                "freq": freq_mhz * 1e6,
                "gain": gain,
                "modulation": mod_var.get(),
                "sdr_type": preset.get("sdr_type", "hackrf")
            }
            
            # Update listbox
            signal_listbox.delete(idx)
            signal_listbox.insert(idx, f"{name_var.get()} ({freq_mhz} MHz)")
            signal_listbox.selection_set(idx)
            
            edit_window.destroy()
            
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))

    # Add buttons
    btn_frame = ttk.Frame(frame)
    btn_frame.grid(row=4, column=0, columnspan=2, pady=10)
    
    ttk.Button(btn_frame, text="Save", command=save_changes).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Cancel", command=edit_window.destroy).pack(side=tk.LEFT)

def add_new_ship():
    """Add a new ship to the simulation"""
    ship_dialog = tk.Toplevel(root)
    ship_dialog.title("Add New Ship")
    ship_dialog.attributes("-fullscreen", True)
    
    main_frame = ttk.Frame(ship_dialog, padding=10)
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    ship_notebook = ttk.Notebook(main_frame)
    ship_notebook.pack(fill=tk.BOTH, expand=True, pady=5)
    
    # Tab 1: Basic ship info
    basic_frame = ttk.Frame(ship_notebook, padding=10)
    ship_notebook.add(basic_frame, text="Basic Info")
    
    fields = [
        ("Name:", "ship_name", "Vessel 1"),
        ("MMSI:", "mmsi", "366000001"),
        ("Ship Type (0-99):", "ship_type", "70"),
        ("Length (m):", "length", "100"),
        ("Beam (m):", "beam", "20"),
        ("Latitude (°):", "lat", "40.7128"),
        ("Longitude (°):", "lon", "-74.0060"),
        ("Course (°):", "course", "90"),
        ("Speed (knots):", "speed", "8"),
        ("Nav Status (0-15):", "status", "0"),
        ("Rate of Turn:", "turn", "0"),
        ("Destination:", "dest", "NEW YORK")
    ]
    vars_dict = {}
    flag_var = None  # Add this before the loop
    for i, (label_text, var_name, default) in enumerate(fields):
        ttk.Label(basic_frame, text=label_text).grid(row=i, column=0, sticky=tk.W, pady=5)
        var = tk.StringVar(value=default)
        vars_dict[var_name] = var
        ttk.Entry(basic_frame, textvariable=var).grid(row=i, column=1, sticky=(tk.W, tk.E), pady=5)
        # --- Flag display next to MMSI ---
        if var_name == "mmsi":
            flag_var = tk.StringVar(value=get_flag_from_mmsi(default))
            def update_flag_var(*args):
                flag_var.set(get_flag_from_mmsi(vars_dict["mmsi"].get()))
            vars_dict["mmsi"].trace_add("write", lambda *a: update_flag_var())
            ttk.Label(basic_frame, text="Flag:").grid(row=i, column=2, sticky=tk.W, pady=5)
            ttk.Label(basic_frame, textvariable=flag_var).grid(row=i, column=3, sticky=tk.W, pady=5)

    # Tab 2: Waypoints
    waypoints_frame = ttk.Frame(ship_notebook, padding=10)
    ship_notebook.add(waypoints_frame, text="Waypoints")
    
    waypoints_list_frame = ttk.LabelFrame(waypoints_frame, text="Waypoint List")
    waypoints_list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
    
    waypoints_table_frame = ttk.Frame(waypoints_list_frame)
    waypoints_table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    waypoints_list = ttk.Treeview(waypoints_table_frame, columns=("ID", "Latitude", "Longitude"), 
                                  show="headings", height=10)
    waypoints_list.heading("ID", text="Waypoint")
    waypoints_list.heading("Latitude", text="Latitude")
    waypoints_list.heading("Longitude", text="Longitude")
    waypoints_list.column("ID", width=80)
    waypoints_list.column("Latitude", width=120)
    waypoints_list.column("Longitude", width=120)
    waypoints_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
    waypoints_scroll = ttk.Scrollbar(waypoints_table_frame, orient="vertical", command=waypoints_list.yview)
    waypoints_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    waypoints_list.configure(yscrollcommand=waypoints_scroll.set)
    
    waypoints = []
    waypoint_markers = []  # <-- FIX: define before use
    
    waypoints_action_frame = ttk.Frame(waypoints_list_frame)
    waypoints_action_frame.pack(fill=tk.X, pady=5)
    
    waypoint_lat_var = tk.StringVar()
    waypoint_lon_var = tk.StringVar()
    
    ttk.Label(waypoints_action_frame, text="Latitude:").pack(side=tk.LEFT, padx=5)
    ttk.Entry(waypoints_action_frame, textvariable=waypoint_lat_var, width=10).pack(side=tk.LEFT, padx=5)
    ttk.Label(waypoints_action_frame, text="Longitude:").pack(side=tk.LEFT, padx=5)
    ttk.Entry(waypoints_action_frame, textvariable=waypoint_lon_var, width=10).pack(side=tk.LEFT, padx=5)

    if MAP_VIEW_AVAILABLE:
        waypoint_map_frame = ttk.LabelFrame(waypoints_frame, text="Pick Waypoint on Map", padding=5)
        waypoint_map_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        waypoint_map = tkintermapview.TkinterMapView(waypoint_map_frame, width=400, height=250, corner_radius=0)
        waypoint_map.pack(fill=tk.BOTH, expand=True)
        try:
            lat0 = float(waypoint_lat_var.get()) if waypoint_lat_var.get() else 39.5
            lon0 = float(waypoint_lon_var.get()) if waypoint_lon_var.get() else -9.25
        except Exception:
            lat0, lon0 = 39.5, -9.25
        waypoint_map.set_position(lat0, lon0)
        waypoint_map.set_zoom(10)
        waypoint_marker = [None]
        def on_waypoint_map_click(coords):
            lat, lon = coords
            waypoint_lat_var.set(f"{lat:.6f}")
            waypoint_lon_var.set(f"{lon:.6f}")
            if waypoint_marker[0]:
                waypoint_map.delete(waypoint_marker[0])
            waypoint_marker[0] = waypoint_map.set_marker(lat, lon, text="Waypoint")
            sim_status_var.set("Ready")
        waypoint_map.add_left_click_map_command(on_waypoint_map_click)
        def center_waypoint_map():
            try:
                lat = float(waypoint_lat_var.get())
                lon = float(waypoint_lon_var.get())
                waypoint_map.set_position(lat, lon)
            except Exception:
                pass
        ttk.Button(waypoints_action_frame, text="Center Map", command=center_waypoint_map).pack(side=tk.LEFT, padx=5)
        # Draw existing waypoints as markers
        for i, wp in enumerate(waypoints):
            marker = waypoint_map.set_marker(wp[0], wp[1], text=f"WP {i+1}")
            waypoint_markers.append(marker)
    else:
        ttk.Label(waypoints_frame, text="Map not available. Install tkintermapview for map picking.").pack(pady=10)

    def add_waypoint():
        try:
            lat = float(waypoint_lat_var.get())
            lon = float(waypoint_lon_var.get())
            if lat < -90 or lat > 90:
                raise ValueError("Latitude must be between -90 and 90")
            if lon < -180 or lon > 180:
                raise ValueError("Longitude must be between -180 and 180")
            waypoints.append((lat, lon))
            waypoints_list.insert("", "end", values=(f"WP {len(waypoints)}", f"{lat:.6f}", f"{lon:.6f}"))
            waypoint_lat_var.set("")
            waypoint_lon_var.set("")
            if MAP_VIEW_AVAILABLE:
                marker = waypoint_map.set_marker(lat, lon, text=f"WP {len(waypoints)}")
                waypoint_markers.append(marker)
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))

    def remove_waypoint():
        selected = waypoints_list.selection()
        if not selected:
            messagebox.showerror("Error", "Select a waypoint to remove")
            return
        item = waypoints_list.item(selected[0])
        wp_id = item['values'][0]
        try:
            index = int(wp_id.split(" ")[1]) - 1
            if 0 <= index < len(waypoints):
                waypoints.pop(index)
                waypoints_list.delete(*waypoints_list.get_children())
                if MAP_VIEW_AVAILABLE:
                    for m in waypoint_markers:
                        waypoint_map.delete(m)
                    waypoint_markers.clear()
                    for i, wp in enumerate(waypoints):
                        marker = waypoint_map.set_marker(wp[0], wp[1], text=f"WP {i+1}")
                        waypoint_markers.append(marker)
                for i, wp in enumerate(waypoints):
                    waypoints_list.insert("", "end", values=(f"WP {i+1}", f"{wp[0]:.6f}", f"{wp[1]:.6f}"))
        except (ValueError, IndexError) as e:
            messagebox.showerror("Error", f"Could not remove waypoint: {str(e)}")
    def clear_waypoints():
        if messagebox.askyesno("Confirm", "Remove all waypoints?"):
            waypoints.clear()
            waypoints_list.delete(*waypoints_list.get_children())
            if MAP_VIEW_AVAILABLE:
                for m in waypoint_markers:
                    waypoint_map.delete(m)
                waypoint_markers.clear()

    # --- Ship Type Reference Panel for Dialog ---

    reference_frame = ttk.Frame(basic_frame)
    reference_frame.grid(row=len(fields)+1, column=0, columnspan=4, sticky=tk.W, padx=0, pady=(10, 0))

    ship_type_frame = ttk.LabelFrame(reference_frame, text="Ship Type Codes Reference", padding=10)
    ship_type_frame.pack(side=tk.LEFT, padx=(0, 10), pady=0, anchor="n")

    ttk.Label(ship_type_frame, text="Common AIS Ship Types:", font=("Segoe UI", 11, "bold")).pack(anchor=tk.W, pady=5)

    ship_type_scroll = tk.Scrollbar(ship_type_frame)
    ship_type_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    ship_type_text = tk.Text(
        ship_type_frame, wrap=tk.WORD, yscrollcommand=ship_type_scroll.set,
        height=12, width=18, font=("Segoe UI", 11), relief=tk.FLAT, borderwidth=0,
    )
    ship_type_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
    ship_type_scroll.config(command=ship_type_text.yview)
    ship_type_text.config(state=tk.NORMAL)
    ship_type_text.delete(1.0, tk.END)
    ship_type_text.insert(tk.END, """\
20 - Wing in ground (WIG)
30 - Fishing
31 - Towing
32 - Towing (long)
33 - Dredging or underwater ops
34 - Diving ops
35 - Military ops
36 - Sailing
37 - Pleasure craft
40 - High speed craft (HSC)
50 - Pilot vessel
51 - Search and rescue vessel
52 - Tug
53 - Port tender
54 - Anti-pollution
55 - Law enforcement
60 - Passenger
70 - Cargo
80 - Tanker
90 - Other type

(0 = Not available, 99 = Other)
""")
    ship_type_text.config(state=tk.DISABLED)

    # --- Navigation Status Codes Reference (Improved UI) ---
    nav_status_frame = ttk.LabelFrame(reference_frame, text="Navigation Status Codes Reference", padding=(12, 8))
    nav_status_frame.pack(side=tk.LEFT, padx=(0, 0), pady=0, anchor="n")

    ttk.Label(nav_status_frame, text="Common AIS Navigation Status Codes:", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 6))

    nav_status_scroll = tk.Scrollbar(nav_status_frame)
    nav_status_text = tk.Text(
        nav_status_frame, width=25, height=12, wrap=tk.WORD,
        font=("Segoe UI", 11), relief=tk.FLAT, borderwidth=0,
        yscrollcommand=nav_status_scroll.set
    )
    nav_status_scroll.config(command=nav_status_text.yview)
    nav_status_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
    nav_status_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    nav_status_text.insert(tk.END, """\
0 - Under way using engine
1 - At anchor
2 - Not under command
3 - Restricted manoeuverability
4 - Constrained by her draught
5 - Moored
6 - Aground
7 - Engaged in fishing
8 - Under way sailing
9 - Reserved for HSC
10 - Reserved for WIG
11 - Reserved
12 - Reserved
13 - Reserved
14 - AIS-SART/MOB-AIS/EPIRB-AIS
15 - Not defined (default)
""")
    nav_status_text.config(state=tk.DISABLED)


    ttk.Button(waypoints_action_frame, text="Add", command=add_waypoint).pack(side=tk.LEFT, padx=5)
    ttk.Button(waypoints_action_frame, text="Remove", command=remove_waypoint).pack(side=tk.LEFT, padx=5)
    ttk.Button(waypoints_action_frame, text="Clear All", command=clear_waypoints).pack(side=tk.LEFT, padx=5)
    ttk.Label(waypoints_frame, text="Note: Ship will follow waypoints in order. Max 20 waypoints.", wraplength=400).pack(pady=10)
    # Save function
    def save_ship():
        try:
            # Validate inputs
            mmsi = int(vars_dict["mmsi"].get())
            if mmsi < 200000000 or mmsi > 999999999:
                raise ValueError("MMSI must be 9 digits")
                
            lat = float(vars_dict["lat"].get())
            if lat < -90 or lat > 90:
                raise ValueError("Latitude must be -90 to 90")
                
            lon = float(vars_dict["lon"].get())
            if lon < -180 or lon > 180:
                raise ValueError("Longitude must be -180 to 180")
            
            # Create ship
            new_ship = AISShip(
                name=vars_dict["ship_name"].get(),
                mmsi=int(vars_dict["mmsi"].get()),
                ship_type=int(vars_dict["ship_type"].get()),
                length=float(vars_dict["length"].get()),
                beam=float(vars_dict["beam"].get()),
                lat=lat,
                lon=lon,
                course=float(vars_dict["course"].get()),
                speed=float(vars_dict["speed"].get()),
                status=int(vars_dict["status"].get()),
                turn=int(vars_dict["turn"].get()),
                destination=vars_dict["dest"].get()
            )
            
            # Add waypoints to the ship
            if waypoints:
                new_ship.waypoints = waypoints.copy()
                # Set current waypoint to first waypoint
                new_ship.current_waypoint = 0
                # Optionally set initial course toward first waypoint
                if len(waypoints) > 0:
                    first_wp = waypoints[0]
                    bearing = calculate_initial_compass_bearing((lat, lon), first_wp)
                    new_ship.course = bearing
                    new_ship.heading = round(bearing)
            
            # Add to configuration
            SHIP_CONFIGS.append(new_ship)
            update_ship_listbox()
            save_ship_configs()
            ship_dialog.destroy()
            
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))
    
    # Bottom button frame
    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(fill=tk.X, pady=10)
    
    ttk.Button(btn_frame, text="Save Ship", command=save_ship, 
              padding=(20, 10)).pack(side=tk.LEFT, padx=10)
    ttk.Button(btn_frame, text="Cancel", command=ship_dialog.destroy, 
              padding=(20, 10)).pack(side=tk.LEFT, padx=10)
    
    # Set layout weights
    basic_frame.columnconfigure(1, weight=1)

def delete_selected_ships():
    """Delete selected ships from the configuration"""
    selected = ship_listbox.curselection()
    if not selected:
        messagebox.showerror("Error", "Select ship(s) to delete")
        return
    
    # Confirm deletion
    if messagebox.askyesno("Confirm Delete", 
                          f"Delete {len(selected)} selected ship(s)?"):
        # Delete in reverse order to avoid index shifts
        for index in sorted(selected, reverse=True):
            del SHIP_CONFIGS[index]
        
        update_ship_listbox()
        save_ship_configs()

def edit_selected_ship():
    """Edit an existing ship"""
    selected = ship_listbox.curselection()
    if not selected:
        messagebox.showerror("Error", "Select a ship to edit")
        return
    
    ship_index = selected[0]
    ship = SHIP_CONFIGS[ship_index]
    
    # Create dialog
    ship_dialog = tk.Toplevel(root)
    ship_dialog.title(f"Edit: {ship.name}")
    ship_dialog.attributes("-fullscreen", True)
    
    main_frame = ttk.Frame(ship_dialog, padding=10)
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    ship_notebook = ttk.Notebook(main_frame)
    ship_notebook.pack(fill=tk.BOTH, expand=True, pady=5)
    
    basic_frame = ttk.Frame(ship_notebook, padding=10)
    ship_notebook.add(basic_frame, text="Basic Info")
    
    fields = [
        ("Name:", "ship_name", ship.name),
        ("MMSI:", "mmsi", str(ship.mmsi)),
        ("Ship Type (0-99):", "ship_type", str(ship.ship_type)),
        ("Length (m):", "length", str(ship.length)),
        ("Beam (m):", "beam", str(ship.beam)),
        ("Latitude (°):", "lat", str(ship.lat)),
        ("Longitude (°):", "lon", str(ship.lon)),
        ("Course (°):", "course", str(ship.course)),
        ("Speed (knots):", "speed", str(ship.speed)),
        ("Nav Status (0-15):", "status", str(ship.status)),
        ("Rate of Turn:", "turn", str(ship.turn)),
        ("Destination:", "dest", ship.destination)
    ]
    vars_dict = {}
    flag_var = None  # Add this before the loop
    for i, (label_text, var_name, default) in enumerate(fields):
        ttk.Label(basic_frame, text=label_text).grid(row=i, column=0, sticky=tk.W, pady=5)
        var = tk.StringVar(value=default)
        vars_dict[var_name] = var
        ttk.Entry(basic_frame, textvariable=var).grid(row=i, column=1, sticky=(tk.W, tk.E), pady=5)
        # --- Flag display next to MMSI ---
        if var_name == "mmsi":
            flag_var = tk.StringVar(value=get_flag_from_mmsi(default))
            def update_flag_var(*args):
                flag_var.set(get_flag_from_mmsi(vars_dict["mmsi"].get()))
            vars_dict["mmsi"].trace_add("write", lambda *a: update_flag_var())
            ttk.Label(basic_frame, text="Flag:").grid(row=i, column=2, sticky=tk.W, pady=5)
            ttk.Label(basic_frame, textvariable=flag_var).grid(row=i, column=3, sticky=tk.W, pady=5)
            
    
    # Tab 2: Waypoints
    waypoints_frame = ttk.Frame(ship_notebook, padding=10)
    ship_notebook.add(waypoints_frame, text="Waypoints")
    
    waypoints_list_frame = ttk.LabelFrame(waypoints_frame, text="Waypoint List")
    waypoints_list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
    
    waypoints_table_frame = ttk.Frame(waypoints_list_frame)
    waypoints_table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    waypoints_list = ttk.Treeview(waypoints_table_frame, columns=("ID", "Latitude", "Longitude"), 
                                  show="headings", height=10)
    waypoints_list.heading("ID", text="Waypoint")
    waypoints_list.heading("Latitude", text="Latitude")
    waypoints_list.heading("Longitude", text="Longitude")
    waypoints_list.column("ID", width=80)
    waypoints_list.column("Latitude", width=120)
    waypoints_list.column("Longitude", width=120)
    waypoints_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
    waypoints_scroll = ttk.Scrollbar(waypoints_table_frame, orient="vertical", command=waypoints_list.yview)
    waypoints_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    waypoints_list.configure(yscrollcommand=waypoints_scroll.set)
    
    waypoints = getattr(ship, 'waypoints', [])[:]  # Copy the existing waypoints
    waypoint_markers = []  # <-- FIX: define before use
    
    # Fill waypoints table with existing waypoints
    for i, waypoint in enumerate(waypoints):
        waypoints_list.insert("", "end", values=(f"WP {i+1}", f"{waypoint[0]:.6f}", f"{waypoint[1]:.6f}"))
    
    waypoints_action_frame = ttk.Frame(waypoints_list_frame)
    waypoints_action_frame.pack(fill=tk.X, pady=5)
    
    waypoint_lat_var = tk.StringVar()
    waypoint_lon_var = tk.StringVar()
    
    ttk.Label(waypoints_action_frame, text="Latitude:").pack(side=tk.LEFT, padx=5)
    ttk.Entry(waypoints_action_frame, textvariable=waypoint_lat_var, width=10).pack(side=tk.LEFT, padx=5)
    ttk.Label(waypoints_action_frame, text="Longitude:").pack(side=tk.LEFT, padx=5)
    ttk.Entry(waypoints_action_frame, textvariable=waypoint_lon_var, width=10).pack(side=tk.LEFT, padx=5)
    if MAP_VIEW_AVAILABLE:
        waypoint_map_frame = ttk.LabelFrame(waypoints_frame, text="Pick Waypoint on Map", padding=5)
        waypoint_map_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        waypoint_map = tkintermapview.TkinterMapView(waypoint_map_frame, width=400, height=250, corner_radius=0)
        waypoint_map.pack(fill=tk.BOTH, expand=True)
        try:
            lat0 = float(waypoint_lat_var.get()) if waypoint_lat_var.get() else 39.5
            lon0 = float(waypoint_lon_var.get()) if waypoint_lon_var.get() else -9.25
        except Exception:
            lat0, lon0 = 40.7128, -74.0060
        waypoint_map.set_position(lat0, lon0)
        waypoint_map.set_zoom(10)
        waypoint_marker = [None]
        def on_waypoint_map_click(coords):
            lat, lon = coords
            waypoint_lat_var.set(f"{lat:.6f}")
            waypoint_lon_var.set(f"{lon:.6f}")
            if waypoint_marker[0]:
                waypoint_map.delete(waypoint_marker[0])
            waypoint_marker[0] = waypoint_map.set_marker(lat, lon, text="Waypoint")
            sim_status_var.set("Ready")
        waypoint_map.add_left_click_map_command(on_waypoint_map_click)
        def center_waypoint_map():
            try:
                lat = float(waypoint_lat_var.get())
                lon = float(waypoint_lon_var.get())
                waypoint_map.set_position(lat, lon)
            except Exception:
                pass
        ttk.Button(waypoints_action_frame, text="Center Map", command=center_waypoint_map).pack(side=tk.LEFT, padx=5)
        # Draw existing waypoints as markers
        for i, wp in enumerate(waypoints):
            marker = waypoint_map.set_marker(wp[0], wp[1], text=f"WP {i+1}")
            waypoint_markers.append(marker)
    else:
        ttk.Label(waypoints_frame, text="Map not available. Install tkintermapview for map picking.").pack(pady=10)

    def add_waypoint():
        try:
            lat = float(waypoint_lat_var.get())
            lon = float(waypoint_lon_var.get())
            if lat < -90 or lat > 90:
                raise ValueError("Latitude must be between -90 and 90")
            if lon < -180 or lon > 180:
                raise ValueError("Longitude must be between -180 and 180")
            waypoints.append((lat, lon))
            waypoints_list.insert("", "end", values=(f"WP {len(waypoints)}", f"{lat:.6f}", f"{lon:.6f}"))
            waypoint_lat_var.set("")
            waypoint_lon_var.set("")
            if MAP_VIEW_AVAILABLE:
                marker = waypoint_map.set_marker(lat, lon, text=f"WP {len(waypoints)}")
                waypoint_markers.append(marker)
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))

    def remove_waypoint():
        selected = waypoints_list.selection()
        if not selected:
            messagebox.showerror("Error", "Select a waypoint to remove")
            return
        item = waypoints_list.item(selected[0])
        wp_id = item['values'][0]
        try:
            index = int(wp_id.split(" ")[1]) - 1
            if 0 <= index < len(waypoints):
                waypoints.pop(index)
                waypoints_list.delete(*waypoints_list.get_children())
                if MAP_VIEW_AVAILABLE:
                    for m in waypoint_markers:
                        waypoint_map.delete(m)
                    waypoint_markers.clear()
                    for i, wp in enumerate(waypoints):
                        marker = waypoint_map.set_marker(wp[0], wp[1], text=f"WP {i+1}")
                        waypoint_markers.append(marker)
                for i, wp in enumerate(waypoints):
                    waypoints_list.insert("", "end", values=(f"WP {i+1}", f"{wp[0]:.6f}", f"{wp[1]:.6f}"))
        except (ValueError, IndexError) as e:
            messagebox.showerror("Error", f"Could not remove waypoint: {str(e)}")
    def clear_waypoints():
        if messagebox.askyesno("Confirm", "Remove all waypoints?"):
            waypoints.clear()
            waypoints_list.delete(*waypoints_list.get_children())
            if MAP_VIEW_AVAILABLE:
                for m in waypoint_markers:
                    waypoint_map.delete(m)
                waypoint_markers.clear()

    # --- Ship Type Reference Panel for Dialog ---
    reference_frame = ttk.Frame(basic_frame)
    reference_frame.grid(row=len(fields)+1, column=0, columnspan=4, sticky=tk.W, padx=0, pady=(10, 0))

    ship_type_frame = ttk.LabelFrame(reference_frame, text="Ship Type Codes Reference", padding=10)
    ship_type_frame.pack(side=tk.LEFT, padx=(0, 10), pady=0, anchor="n")

    ttk.Label(ship_type_frame, text="Common AIS Ship Types:", font=("Segoe UI", 11, "bold")).pack(anchor=tk.W, pady=5)

    ship_type_scroll = tk.Scrollbar(ship_type_frame)
    ship_type_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    ship_type_text = tk.Text(
        ship_type_frame, wrap=tk.WORD, yscrollcommand=ship_type_scroll.set,
        height=12, width=18, font=("Segoe UI", 11), relief=tk.FLAT, borderwidth=0
    )
    ship_type_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
    ship_type_scroll.config(command=ship_type_text.yview)
    ship_type_text.config(state=tk.NORMAL)
    ship_type_text.delete(1.0, tk.END)
    ship_type_text.insert(tk.END, """\
20 - Wing in ground (WIG)
30 - Fishing
31 - Towing
32 - Towing (long)
33 - Dredging or underwater ops
34 - Diving ops
35 - Military ops
36 - Sailing
37 - Pleasure craft
40 - High speed craft (HSC)
50 - Pilot vessel
51 - Search and rescue vessel
52 - Tug
53 - Port tender
54 - Anti-pollution
55 - Law enforcement
60 - Passenger
70 - Cargo
80 - Tanker
90 - Other type

(0 = Not available, 99 = Other)
""")
    ship_type_text.config(state=tk.DISABLED)

    # --- Navigation Status Codes Reference (Improved UI) ---
    nav_status_frame = ttk.LabelFrame(reference_frame, text="Navigation Status Codes Reference", padding=(12, 8))
    nav_status_frame.pack(side=tk.LEFT, padx=(0, 0), pady=0, anchor="n")

    ttk.Label(nav_status_frame, text="Common AIS Navigation Status Codes:", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 6))

    nav_status_scroll = tk.Scrollbar(nav_status_frame)
    nav_status_text = tk.Text(
        nav_status_frame, width=25, height=12, wrap=tk.WORD,
        font=("Segoe UI", 11), relief=tk.FLAT, borderwidth=0,
        yscrollcommand=nav_status_scroll.set
    )
    nav_status_scroll.config(command=nav_status_text.yview)
    nav_status_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
    nav_status_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    nav_status_text.insert(tk.END, """\
0 - Under way using engine
1 - At anchor
2 - Not under command
3 - Restricted manoeuverability
4 - Constrained by her draught
5 - Moored
6 - Aground
7 - Engaged in fishing
8 - Under way sailing
9 - Reserved for HSC
10 - Reserved for WIG
11 - Reserved
12 - Reserved
13 - Reserved
14 - AIS-SART/MOB-AIS/EPIRB-AIS
15 - Not defined (default)
""")
    nav_status_text.config(state=tk.DISABLED)


    ttk.Button(waypoints_action_frame, text="Add", command=add_waypoint).pack(side=tk.LEFT, padx=5)
    ttk.Button(waypoints_action_frame, text="Remove", command=remove_waypoint).pack(side=tk.LEFT, padx=5)
    ttk.Button(waypoints_action_frame, text="Clear All", command=clear_waypoints).pack(side=tk.LEFT, padx=5)
    ttk.Label(waypoints_frame, text="Note: Ship will follow waypoints in order. Max 20 waypoints.", wraplength=400).pack(pady=10)
    # Update function
    def update_ship():
        try:
            # Validate
            mmsi = int(vars_dict["mmsi"].get())
            mmsi_str = vars_dict["mmsi"].get()
            
            # Fix the validation check to simply ensure it's 9 digits
            if len(mmsi_str) != 9 and (mmsi < 200000000 or mmsi > 999999999):
                raise ValueError("MMSI must be a 9-digit number")
            
            # Rest of the validation and update code
            lat = float(vars_dict["lat"].get())
            if lat < -90 or lat > 90:
                raise ValueError("Latitude must be -90 to 90")
                
            lon = float(vars_dict["lon"].get())
            if lon < -180 or lon > 180:
                raise ValueError("Longitude must be -180 to 180")
            
            # Update ship
            ship.name = vars_dict["ship_name"].get()
            ship.mmsi = mmsi
            ship.ship_type = int(vars_dict["ship_type"].get())
            ship.length = float(vars_dict["length"].get())
            ship.beam = float(vars_dict["beam"].get())
            ship.lat = lat
            ship.lon = lon
            ship.course = float(vars_dict["course"].get())
            ship.speed = float(vars_dict["speed"].get())
            ship.status = int(vars_dict["status"].get())
            ship.turn = int(vars_dict["turn"].get())
            ship.destination = vars_dict["dest"].get()
            ship.heading = round(ship.course)
            
            # Update waypoints
            ship.waypoints = waypoints.copy()
            
            # Reset current_waypoint if waypoints were changed
            if waypoints:
                ship.current_waypoint = 0
            else:
                ship.current_waypoint = -1  # No waypoints
            
            update_ship_listbox()
            save_ship_configs()
            ship_dialog.destroy()
            
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))
    
    # Bottom button frame
    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(fill=tk.X, pady=10)
    
    ttk.Button(btn_frame, text="Update Ship", command=update_ship, 
              padding=(20, 10)).pack(side=tk.LEFT, padx=10)
    ttk.Button(btn_frame, text="Cancel", command=ship_dialog.destroy, 
              padding=(20, 10)).pack(side=tk.LEFT, padx=10)
    
    # Set layout weights
    basic_frame.columnconfigure(1, weight=1)

# Initialize by loading ship configurations
load_ship_configs()

# Update ship listbox with loaded ships
update_ship_listbox()

# Set tab to ship simulation by default
notebook.select(2)  # Index 2 corresponds to the Ship Simulation tab

# Center the window on screen
window_width = 1000
window_height = 750
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
center_x = int((screen_width - window_width) / 2)
center_y = int((screen_height - window_height) / 2)
root.geometry(f"{window_width}x{window_height}+{center_x}+{center_y}")

# Make sure the UI persists until closed
if __name__ == "__main__":
    try:
        root.mainloop()
    except KeyboardInterrupt:
        # Handle any cleanup needed when closing with Ctrl+C
        if ship_simulation_active:
            ship_simulation_active = False
        
        # Save ship configurations on exit
        save_ship_configs()
        print("Program terminated.")