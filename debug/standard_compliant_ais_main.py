#!/usr/bin/env python3
"""
Standard-Compliant AIS NMEA Generator & Transmitter
- Generates AIS Type 1 messages (168-bit)
- Implements standard HDLC framing (Preamble, Flags, Bit Stuffing, Postamble)
- Uses CRC-16-CCITT
- Standard GMSK modulation (BT=0.4, NRZI)
- Transmits using SoapySDR devices
- Simulates vessel movements
"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import numpy as np
import time
import threading
import json
import os
import logging
import queue
from datetime import datetime, timedelta
from pathlib import Path
import math
import gc
import tempfile
import subprocess

### LOGGING SETUP ###
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(threadName)s - %(module)s - %(funcName)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT,
                    handlers=[logging.FileHandler("standard_compliant_ais_main.log"),
                              logging.StreamHandler()])
logger = logging.getLogger(__name__)

class QueueHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(self.format(record))

### SDR CONFIGURATION ###
try:
    import SoapySDR
    SOAPY_SDR_TX = getattr(SoapySDR, "SOAPY_SDR_TX", "TX")
    SOAPY_SDR_CF32 = getattr(SoapySDR, "SOAPY_SDR_CF32", "CF32")
    SDR_AVAILABLE = True
    logger.info("SoapySDR imported successfully")
except ImportError as e:
    logger.warning(f"SoapySDR import error: {e}. SDR_AVAILABLE set to False.")
    SDR_AVAILABLE = False

### VALIDATION FUNCTIONS (Mostly unchanged from robust_ais_main.py) ###
def validate_mmsi(mmsi_str):
    mmsi_str = str(mmsi_str).strip()
    if not mmsi_str.isdigit() or len(mmsi_str) != 9:
        raise ValueError(f"MMSI must be a 9-digit number. Got: '{mmsi_str}'")
    mmsi = int(mmsi_str)
    # Basic range check, full MID validation is complex
    if not (100000000 <= mmsi <= 999999999):
        raise ValueError(f"MMSI '{mmsi_str}' is not a valid 9-digit number range.")
    return mmsi

def validate_coordinates(lat_str, lon_str):
    lat = float(lat_str)
    lon = float(lon_str)
    if not (-90 <= lat <= 90):
        raise ValueError(f"Latitude {lat} out of range [-90, 90]")
    if not (-180 <= lon <= 180):
        raise ValueError(f"Longitude {lon} out of range [-180, 180]")
    return lat, lon

def validate_course(course_str): # COG
    course = float(course_str)
    # AIS COG is 0-359.9 or 3600 (not available). GUI input likely 0-359.
    if not (0 <= course < 360):
        # Allow 360 as input to mean "not available" for COG, which is encoded as 3600
        if course != 360:
             raise ValueError(f"Course {course} out of range [0, 359.9] or 360 (not available)")
    return course

def validate_speed(speed_str): # SOG
    speed = float(speed_str)
    # AIS SOG is 0-102.2 knots, 102.3 for "not available"
    if not (0 <= speed <= 102.3):
        raise ValueError(f"Speed {speed} out of range [0, 102.3] knots")
    return speed

def validate_nav_status(status_str):
    status = int(status_str)
    if not (0 <= status <= 15):
        raise ValueError(f"Nav Status {status} out of range [0, 15]")
    return status

def validate_rot(rot_str):
    rot = int(rot_str)
    if not (-128 <= rot <= 127): # -128 is 'not available' / no turn information
        raise ValueError(f"Rate of Turn {rot} out of range [-128, 127]")
    return rot

def validate_heading(hdg_str): # HDG
    hdg = int(hdg_str)
    # AIS Heading is 0-359, 511 for "not available"
    if not (0 <= hdg <= 359 or hdg == 511):
        raise ValueError(f"Heading {hdg} out of range [0, 359] or 511 (not available)")
    return hdg

def validate_ship_type(st_str):
    st = int(st_str)
    if not (0 <= st <= 99): # Type 0 is "Not available or no ship"
        raise ValueError(f"Ship Type {st} out of range [0,99]")
    return st

def validate_maneuver(man_str):
    man = int(man_str)
    if not (0 <= man <= 2): # 0=N/A, 1=No special, 2=Special
        raise ValueError(f"Maneuver Indicator {man} out of range [0,2]")
    return man

### AIS MESSAGE ENCODING FUNCTIONS ###
def sixbit_to_char(val):
    if not (0 <= val <= 63):
        raise ValueError(f"6-bit value {val} out of range [0, 63]")
    return chr(val + 48 if val < 40 else val + 56)

def char_to_sixbit(char_val):
    val = ord(char_val)
    if 48 <= val < 88:
        val -= 48
    elif 96 <= val < 128:
        val -= 56
    else:
        raise ValueError(f"Invalid AIS character for 6-bit conversion: '{char_val}'")
    if not (0 <= val <= 63):
        raise ValueError(f"Converted value {val} for char '{char_val}' is out of 6-bit range")
    return [(val >> i) & 1 for i in range(5, -1, -1)]

def compute_nmea_checksum(sentence_body): # Renamed for clarity
    cs = 0
    for c in sentence_body:
        cs ^= ord(c)
    return f"{cs:02X}"

def build_ais_type1_message_bits(fields): # Now returns 168 bits directly
    bits = []
    def add(value, length):
        val_int = int(value)
        for i in range(length - 1, -1, -1):
            bits.append((val_int >> i) & 1)

    add(1, 6)  # Message Type 1
    add(fields['repeat'], 2)
    add(fields['mmsi'], 30)
    add(fields['nav_status'], 4)
    add(fields['rot'] & 0xFF, 8) # ROT is signed, mask gets 8 LSB (2's complement)

    sog_val = int(fields['sog'] * 10) if fields['sog'] <= 102.2 else 1023 # 102.3 knots = 1023 (not available)
    add(sog_val, 10)
    add(fields['accuracy'], 1) # 0=default (>=10m), 1=high (<10m)

    # Longitude: 1/10000 min = 1/600000 degree. Max val 180*600000 = 108,000,000. Fits in 28 bits signed.
    lon_val = int(fields['lon'] * 600000)
    add(lon_val & ((1 << 28) - 1), 28)
    # Latitude: 1/10000 min. Max val 90*600000 = 54,000,000. Fits in 27 bits signed.
    lat_val = int(fields['lat'] * 600000)
    add(lat_val & ((1 << 27) - 1), 27)

    cog_val = int(fields['cog'] * 10) if fields['cog'] < 360 else 3600 # 360 deg = 3600 (not available)
    add(cog_val, 12)
    add(fields['hdg'], 9) # 511 for not available
    add(int(fields['timestamp']) % 60, 6) # Second of UTC minute
    add(fields['maneuver'], 2) # Maneuver Indicator
    add(0, 3)  # Spare bits, set to 0
    add(fields.get('raim', 0), 1) # RAIM flag: 0=not in use, 1=in use

    # SOTDMA Communication state (19 bits)
    # Sync State (2 bits): 00=UTC direct
    # Slot Timeout (3 bits): e.g., 001 (1 slot remaining)
    # Sub Message (14 bits): e.g., Slot Offset. 0 for simplicity.
    comm_state_sync = 0b00
    comm_state_timeout = 0b001
    comm_state_sub_message = 0 # Slot offset 0
    
    comm_state_val = (comm_state_sync << 17) | \
                     (comm_state_timeout << 14) | \
                     comm_state_sub_message
    add(comm_state_val, 19)

    if len(bits) != 168:
        raise RuntimeError(f"AIS Type 1 message construction error: Expected 168 bits, got {len(bits)}")
    return bits

def ais_bits_to_payload_string(message_bits_168):
    # Pad 168 bits to be multiple of 6 for NMEA payload characters
    fill_count = (6 - (len(message_bits_168) % 6)) % 6
    padded_bits = message_bits_168 + [0] * fill_count
    
    payload_chars = []
    for i in range(0, len(padded_bits), 6):
        val = int("".join(map(str, padded_bits[i:i+6])), 2)
        payload_chars.append(sixbit_to_char(val))
    
    return "".join(payload_chars), fill_count


### STANDARD CRC-16-CCITT ###
def calculate_crc_standard(bits: list[int]) -> list[int]:
    poly = 0x1021  # CRC-16-CCITT polynomial G(x) = x^16 + x^12 + x^5 + 1
    crc = 0xFFFF   # Initial value
    for bit_val in bits:
        # Test top bit of CRC. If it's 1, then (crc >> 15) is 1.
        # If current data bit is 1, then (crc >> 15) ^ bit_val is 0 if crc_msb was 1, or 1 if crc_msb was 0.
        # This is equivalent to: if ( (crc >> 15) ^ bit_val ) == 1:
        if ((crc & 0x8000) >> 15) ^ bit_val: # if MSB of crc combined with bit is 1
            crc = (crc << 1) ^ poly
        else:
            crc = (crc << 1)
        crc &= 0xFFFF  # Ensure CRC remains 16-bit
    return [(crc >> i) & 1 for i in range(15, -1, -1)] # MSB first

### SIGNAL GENERATION FUNCTIONS (Standard Compliant) ###
SIGNAL_PRESETS = [
    {"name": "AIS Channel A", "freq": 161.975e6, "gain": 40, "modulation": "GMSK", "sdr_type": "hackrf"},
    {"name": "AIS Channel B", "freq": 162.025e6, "gain": 40, "modulation": "GMSK", "sdr_type": "hackrf"},
]

def create_ais_signal_standard(nmea_sentence, sample_rate=2e6):
    # 1. Parse NMEA sentence to get payload characters and NMEA fill bit count
    parts = nmea_sentence.split(',')
    if len(parts) < 7 or not parts[0].startswith("!AIVDM"): # Example !AIVDM,1,1,,A,13PInstantiationException...L,0*CS
        raise ValueError(f"Invalid NMEA sentence format for signal creation: {nmea_sentence}")
    
    payload_char_string = parts[5]
    try:
        nmea_fill_count = int(parts[6].split('*')[0]) # Get the number before '*'
    except (IndexError, ValueError):
        raise ValueError(f"Could not parse NMEA fill bits from: {parts[6]}")

    logger.debug(f"NMEA Payload Chars: {payload_char_string}, NMEA Fill Bits: {nmea_fill_count}")

    # 2. Convert payload characters to bits
    raw_bits_with_padding = []
    for char_val in payload_char_string:
        raw_bits_with_padding.extend(char_to_sixbit(char_val))
    
    # 3. Remove NMEA padding to get the 168-bit AIS message
    if nmea_fill_count > 0:
        message_bits_168 = raw_bits_with_padding[:-nmea_fill_count]
    else:
        message_bits_168 = raw_bits_with_padding
    
    if len(message_bits_168) != 168:
        # This can happen if build_ais_type1_message_bits has an issue or NMEA generation is off
        raise ValueError(f"Decoded AIS message is {len(message_bits_168)} bits, expected 168. NMEA: {nmea_sentence}")

    # 4. Calculate standard CRC-16-CCITT for the 168-bit message
    crc_bits_16 = calculate_crc_standard(message_bits_168)
    
    # 5. Form Data + CRC (168 + 16 = 184 bits)
    data_plus_crc = message_bits_168 + crc_bits_16

    # 6. Bit Stuffing (on Data + CRC)
    # Insert a 0 after five consecutive 1s
    stuffed_data_plus_crc = []
    consecutive_ones = 0
    for bit in data_plus_crc:
        stuffed_data_plus_crc.append(bit)
        if bit == 1:
            consecutive_ones += 1
            if consecutive_ones == 5:
                stuffed_data_plus_crc.append(0)
                consecutive_ones = 0
        else:
            consecutive_ones = 0
    
    # 7. Construct HDLC Frame
    preamble = [0, 1] * 12  # 24 bits: 010101...
    hdlc_flag = [0, 1, 1, 1, 1, 1, 1, 0]  # 8 bits
    postamble = [0] * 24 # 24 bits of 0s (or 1s, or alternating. Simpler with 0s)

    full_hdlc_frame = preamble + hdlc_flag + stuffed_data_plus_crc + hdlc_flag + postamble
    logger.debug(f"Full HDLC Frame length: {len(full_hdlc_frame)}")

    # 8. NRZI Encoding (Non-Return to Zero Inverted)
    # Level changes for '0', stays same for '1'. Bit value '0' makes a transition.
    nrzi_bits = []
    current_level = 1 # Initial level (can be 0 or 1, standard often starts after preamble with a known state)
                      # Let's assume last bit of preamble sets current_level to 1 (if preamble ends in 1)
                      # Or, more simply, define a starting level.
    for bit in full_hdlc_frame:
        if bit == 0: # A '0' in the HDLC frame causes a transition
            current_level = 1 - current_level
        nrzi_bits.append(current_level) # The level itself is transmitted
        
    # 9. GMSK Modulation
    bit_rate = 9600.0
    samples_per_bit = int(sample_rate / bit_rate)
    if samples_per_bit <=0: samples_per_bit = 1 # Safety

    # Standard GMSK Gaussian Filter (BT=0.4)
    bt_product = 0.4
    # Filter span in bit periods (e.g., 2 bit periods on each side of center)
    span_bit_periods = 2.0 
    # Time vector for filter, in units of T_bit (bit duration)
    t_filter_norm = np.arange(-span_bit_periods, span_bit_periods + 1.0/samples_per_bit, 1.0/samples_per_bit)
    # Sigma of Gaussian pulse in units of T_bit
    sigma_prime_norm_Tbit = math.sqrt(math.log(2.0)) / (2.0 * math.pi * bt_product)
    # Gaussian filter impulse response
    h_gauss = (1.0 / (math.sqrt(2.0 * math.pi) * sigma_prime_norm_Tbit)) * \
              np.exp(-t_filter_norm**2 / (2.0 * sigma_prime_norm_Tbit**2))
    h_gauss = h_gauss / np.sum(h_gauss) # Normalize filter taps

    # Upsample NRZI bits (0 maps to -1, 1 maps to +1 for phase modulation)
    # Note: NRZI bits are already 0 or 1 representing levels.
    mapped_nrzi_bits = (2 * np.array(nrzi_bits) - 1).astype(float)
    
    upsampled_signal = np.zeros(len(mapped_nrzi_bits) * samples_per_bit)
    upsampled_signal[::samples_per_bit] = mapped_nrzi_bits # Place pulses at start of each bit period

    # Convolve with Gaussian filter
    # 'full' creates tails, 'same' would be same length as upsampled_signal
    # For phase integration, it's common to filter then integrate.
    filtered_signal = np.convolve(upsampled_signal, h_gauss, mode='same')

    # Integrate phase (Frequency modulation part of GMSK)
    # Modulation index for GMSK is 0.5. Phase changes by +/- pi/2 over one bit period.
    phase_change_per_sample = (np.pi / 2.0) * (filtered_signal / samples_per_bit)
    instantaneous_phase = np.cumsum(phase_change_per_sample)

    # Generate I/Q samples
    i_samples = np.cos(instantaneous_phase)
    q_samples = np.sin(instantaneous_phase)
    iq_samples = (i_samples + 1j * q_samples).astype(np.complex64)
    
    # Normalize signal amplitude (e.g., to 0.95 for SDR headroom)
    max_abs_val = np.max(np.abs(iq_samples))
    if max_abs_val > 0:
        iq_samples = iq_samples / max_abs_val * 0.95

    return iq_samples # Single burst, no repetitions parameter needed here

### SHIP SIMULATION (AISShip class mostly unchanged) ###
class AISShip:
    def __init__(self, name, mmsi, ship_type, length=30.0, beam=10.0,
                 lat=40.7128, lon=-74.0060, course=90.0, speed=8.0,
                 status=0, turn=0, destination="", accuracy=1, heading=None,
                 maneuver=0, raim=0): # Added maneuver, raim
        self.name = str(name)
        self.mmsi = validate_mmsi(mmsi)
        self.ship_type = validate_ship_type(ship_type)
        self.length = float(length) if length is not None else 30.0
        self.beam = float(beam) if beam is not None else 10.0
        self.lat, self.lon = validate_coordinates(lat, lon)
        self.course = validate_course(course) # COG
        self.speed = validate_speed(speed)   # SOG
        self.status = validate_nav_status(status)
        self.turn = validate_rot(turn)
        self.destination = str(destination)[:20]
        self.accuracy = 1 if int(accuracy) == 1 else 0
        # HDG: if not provided, use course. Ensure validation.
        self.heading = validate_heading(heading if heading is not None else int(round(self.course)))
        self.maneuver = validate_maneuver(maneuver)
        self.raim = 1 if int(raim) == 1 else 0


    def move(self, elapsed_seconds): # Unchanged from robust_ais_main.py
        if self.speed <= 0 or self.speed > 102.2 : # 102.3 is "not available"
            return

        speed_nm_per_sec = self.speed / 3600.0
        distance_nm = speed_nm_per_sec * elapsed_seconds
        
        lat_deg_per_nm = 1.0 / 60.0
        lon_deg_per_nm = 1.0 / (60.0 * math.cos(math.radians(self.lat)))

        delta_lat = distance_nm * math.cos(math.radians(self.course)) * lat_deg_per_nm
        delta_lon = distance_nm * math.sin(math.radians(self.course)) * lon_deg_per_nm
        
        self.lat += delta_lat
        self.lon += delta_lon

        self.lat = max(-90.0, min(90.0, self.lat))
        self.lon = (self.lon + 180.0) % 360.0 - 180.0

        if self.turn != 0 and self.turn != -128:
            # ROT is complicated. Field is -127 to +127. 
            # Actual turn rate (deg/min) = (ROT / 4.733)^2 * sign(ROT)
            # For simulation: if ROT is directly deg/min / factor as in user code, keep it simple
            rot_val_for_calc = self.turn # Signed value from -127 to 127
            # Simplified model: assume rot_val_for_calc is roughly scaled deg/min
            # Let's assume rot_val_for_calc of +/-70 is ~15 deg/min for simplicity
            # This part needs careful thought if high fidelity simulation is required.
            # Using the user's previous simpler model for consistency:
            rot_deg_per_min_scaled = self.turn / 4.0 # User's previous interpretation.
            course_change_deg = rot_deg_per_min_scaled * (elapsed_seconds / 60.0)
            
            self.course = (self.course + course_change_deg) % 360.0
            self.heading = int(round(self.course)) % 360


    def get_ais_fields(self): # For Type 1 message
        return {
            'repeat': 0, # Default repeat
            'mmsi': self.mmsi,
            'nav_status': self.status,
            'rot': self.turn,
            'sog': self.speed,
            'accuracy': self.accuracy,
            'lon': self.lon,
            'lat': self.lat,
            'cog': self.course,
            'hdg': self.heading,
            'timestamp': datetime.now().second % 60,
            'maneuver': self.maneuver,
            'raim': self.raim
        }

    def to_dict(self): # Added maneuver, raim
        return {
            'name': self.name, 'mmsi': self.mmsi, 'ship_type': self.ship_type,
            'length': self.length, 'beam': self.beam, 'lat': self.lat, 'lon': self.lon,
            'course': self.course, 'speed': self.speed, 'status': self.status,
            'turn': self.turn, 'destination': self.destination,
            'accuracy': self.accuracy, 'heading': self.heading,
            'maneuver': self.maneuver, 'raim': self.raim
        }

    @classmethod
    def from_dict(cls, data): # Added maneuver, raim
        try:
            return cls(
                name=data.get('name', 'Unknown Vessel'),
                mmsi=data.get('mmsi', '000000000'),
                ship_type=data.get('ship_type', 0), # 0 = Not available
                length=data.get('length', 0.0), # 0 = Not available
                beam=data.get('beam', 0.0),   # 0 = Not available
                lat=data.get('lat', 91.0), # 91 = Not available
                lon=data.get('lon', 181.0),# 181 = Not available
                course=data.get('course', 360.0), # 360 = Not available
                speed=data.get('speed', 102.3), # 102.3 = Not available
                status=data.get('status', 15), # 15 = Not defined
                turn=data.get('turn', -128), # -128 = No info
                destination=data.get('destination', ''),
                accuracy=data.get('accuracy', 0), # 0 = default GPS
                heading=data.get('heading', 511), # 511 = Not available
                maneuver=data.get('maneuver', 0), # 0 = Not available
                raim=data.get('raim',0) # 0 = RAIM not in use
            )
        except ValueError as e:
            logger.warning(f"Failed to create AISShip from dict data {data}: {e}. Skipping.")
            return None

CONFIG_FILE_PATH = Path(__file__).parent / "robust_ship_configs.json" # Uses same config file

class AISApp: # GUI Class, largely unchanged except where interacting with new AIS functions
    def __init__(self, root_tk):
        self.root = root_tk
        self.root.title("Standard AIS NMEA Generator & Transmitter")
        self.root.minsize(850, 700)
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        self.ship_configs = []
        self.simulation_active = False
        self.simulation_thread = None
        self.log_queue = queue.Queue()

        self._setup_gui_logging()
        self._create_widgets() # Minor changes here for new fields
        self._load_ship_configs()
        self._update_ship_listbox()

        self.root.after(100, self._process_log_queue)

    def _setup_gui_logging(self):
        queue_handler = QueueHandler(self.log_queue)
        queue_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logging.getLogger().addHandler(queue_handler)

    def _process_log_queue(self):
        try:
            while True:
                record = self.log_queue.get(block=False)
                self._display_log(record, self.log_text_widget)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._process_log_queue)

    def _display_log(self, message, text_widget):
        if self.root.winfo_exists():
            text_widget.configure(state='normal')
            text_widget.insert(tk.END, message + '\n')
            text_widget.see(tk.END)
            text_widget.configure(state='disabled')

    def _gui_log_update(self, message, text_widget_ref):
        if self.root.winfo_exists():
            self.root.after(0, self._display_log, message, text_widget_ref)

    def _create_widgets(self):
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self._create_generator_tab(notebook)
        self._create_log_tab(notebook)
        self._create_simulation_tab(notebook)

        self.status_var = tk.StringVar(value="Ready" if SDR_AVAILABLE else "SDR support NOT available")
        ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W).pack(side=tk.BOTTOM, fill=tk.X)

    def _create_generator_tab(self, notebook):
        ais_frame = ttk.Frame(notebook, padding=10)
        notebook.add(ais_frame, text="AIS Generator (Type 1)")

        input_frame = ttk.LabelFrame(ais_frame, text="Message Parameters", padding=10)
        input_frame.grid(row=0, column=0, sticky=(tk.N, tk.W, tk.E, tk.S), padx=5, pady=5)

        self.gen_vars = {}
        # Matched to AISShip defaults for "Not Available" where applicable
        labels_defaults = [
            ("Repeat Indicator", "0"), ("MMSI", "366999001"),
            ("Nav Status (0-15)", "15"), ("ROT (-128..127)", "-128"),
            ("SOG (knots, 102.3=N/A)", "102.3"), ("Accuracy (0=Low, 1=High)", "0"),
            ("Longitude (°)", "181.0"), ("Latitude (°)", "91.0"),
            ("COG (°, 360=N/A)", "360.0"), ("Heading (°, 511=N/A)", "511"),
            ("Timestamp (s, 0-59)", str(datetime.now().second % 60)),
            ("Maneuver (0-2, 0=N/A)", "0"), ("RAIM in use (0/1)", "0")
        ]
        for i, (lbl, default) in enumerate(labels_defaults):
            ttk.Label(input_frame, text=lbl + ":").grid(column=0, row=i, sticky=tk.W, padx=5, pady=2)
            var = tk.StringVar(value=default)
            key = lbl.lower().split(" ")[0].replace("(", "").replace("indicator","").strip() # e.g. "mmsi", "rot", "raim"
            self.gen_vars[key] = var
            ttk.Entry(input_frame, textvariable=var, width=20).grid(column=1, row=i, sticky=(tk.W, tk.E), padx=5, pady=2)
        input_frame.columnconfigure(1, weight=1)

        ttk.Button(input_frame, text="Generate Message", command=self._generate_message_gui).grid(
            column=0, row=len(labels_defaults), columnspan=2, pady=10)

        output_frame = ttk.LabelFrame(ais_frame, text="Message Output", padding=10)
        output_frame.grid(row=0, column=1, sticky=(tk.N, tk.W, tk.E, tk.S), padx=5, pady=5)
        output_frame.columnconfigure(0, weight=1)


        self.payload_var = tk.StringVar()
        self.fill_var = tk.StringVar()
        self.nmea_var = tk.StringVar()

        ttk.Label(output_frame, text="AIS Payload Chars (168-bit data):").grid(column=0, row=0, sticky=tk.W, pady=2)
        ttk.Entry(output_frame, textvariable=self.payload_var, width=45, state='readonly').grid(column=0, row=1, sticky=(tk.W, tk.E))
        ttk.Label(output_frame, text="NMEA Fill Bits:").grid(column=0, row=2, sticky=tk.W, pady=2)
        ttk.Entry(output_frame, textvariable=self.fill_var, width=5, state='readonly').grid(column=0, row=3, sticky=tk.W)
        ttk.Label(output_frame, text="NMEA Sentence (!AIVDM):").grid(column=0, row=4, sticky=tk.W, pady=2)
        ttk.Entry(output_frame, textvariable=self.nmea_var, width=70, state='readonly').grid(column=0, row=5, sticky=(tk.W, tk.E))

        signal_frame = ttk.LabelFrame(output_frame, text="Transmission Signal", padding=10)
        signal_frame.grid(column=0, row=6, sticky=(tk.W, tk.E), pady=10)
        self.signal_listbox = tk.Listbox(signal_frame, height=3, exportselection=False)
        self.signal_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        for i, preset in enumerate(SIGNAL_PRESETS):
            self.signal_listbox.insert(i, f"{preset['name']} ({preset['freq']/1e6:.3f} MHz)")
        if SIGNAL_PRESETS: self.signal_listbox.selection_set(0)
        
        # Edit Signal Settings button (can be re-enabled if implemented)
        # ttk.Button(output_frame, text="Edit Signal Settings", command=self._edit_signal_preset_gui).grid(...)
        
        self.tx_btn = ttk.Button(output_frame, text="Transmit Message", command=self._transmit_message_gui)
        self.tx_btn.grid(column=0, row=8, sticky=(tk.W, tk.E), pady=10)
        if not SDR_AVAILABLE: self.tx_btn.config(state="disabled")
    
    def _create_log_tab(self, notebook): # Unchanged
        log_frame = ttk.Frame(notebook, padding=10)
        notebook.add(log_frame, text="General Log")
        self.log_text_widget = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, width=80, height=20, state='disabled')
        self.log_text_widget.pack(fill=tk.BOTH, expand=True)

    def _create_simulation_tab(self, notebook): # Unchanged
        sim_frame = ttk.Frame(notebook, padding=10)
        notebook.add(sim_frame, text="Ship Simulation")

        ship_list_frame = ttk.LabelFrame(sim_frame, text="Ships", padding=10)
        ship_list_frame.grid(row=0, column=0, sticky=(tk.N, tk.W, tk.E, tk.S), padx=5, pady=5, rowspan=2)
        
        self.ship_listbox = tk.Listbox(ship_list_frame, height=15, selectmode=tk.EXTENDED, exportselection=False)
        self.ship_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ship_scrollbar = ttk.Scrollbar(ship_list_frame, orient="vertical", command=self.ship_listbox.yview)
        ship_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.ship_listbox.configure(yscrollcommand=ship_scrollbar.set)

        ship_control_frame = ttk.Frame(ship_list_frame)
        ship_control_frame.pack(fill=tk.X, pady=5)
        ttk.Button(ship_control_frame, text="Add", command=self._add_new_ship_gui).pack(side=tk.LEFT, padx=2)
        ttk.Button(ship_control_frame, text="Edit", command=self._edit_selected_ship_gui).pack(side=tk.LEFT, padx=2)
        ttk.Button(ship_control_frame, text="Delete", command=self._delete_selected_ships_gui).pack(side=tk.LEFT, padx=2)

        sim_control_frame = ttk.LabelFrame(sim_frame, text="Simulation Controls", padding=10)
        sim_control_frame.grid(row=0, column=1, sticky=(tk.N, tk.W, tk.E, tk.S), padx=5, pady=5)

        ttk.Label(sim_control_frame, text="AIS Channel:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.sim_channel_var = tk.StringVar()
        sim_channel_options = [f"{idx}: {p['name']}" for idx, p in enumerate(SIGNAL_PRESETS)]
        if not sim_channel_options: sim_channel_options = ["0: No Presets"]
        else: self.sim_channel_var.set(sim_channel_options[0]) # Default to first
        ttk.Combobox(sim_control_frame, textvariable=self.sim_channel_var, values=sim_channel_options, state="readonly").grid(
            row=0, column=1, sticky=(tk.W, tk.E), pady=5)

        ttk.Label(sim_control_frame, text="Interval (s):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.sim_interval_var = tk.StringVar(value="20") # Increased default interval
        ttk.Entry(sim_control_frame, textvariable=self.sim_interval_var, width=5).grid(row=1, column=1, sticky=tk.W)

        self.start_sim_btn = ttk.Button(sim_control_frame, text="Start Simulation", command=self._start_ship_simulation_gui)
        self.start_sim_btn.grid(row=2, column=0, columnspan=2, pady=10)
        self.stop_sim_btn = ttk.Button(sim_control_frame, text="Stop Simulation", command=self._stop_ship_simulation_gui, state=tk.DISABLED)
        self.stop_sim_btn.grid(row=3, column=0, columnspan=2, pady=5)
        if not SDR_AVAILABLE: self.start_sim_btn.config(state="disabled")

        sim_log_frame = ttk.LabelFrame(sim_frame, text="Simulation Log", padding=10)
        sim_log_frame.grid(row=1, column=1, sticky=(tk.N, tk.S, tk.W, tk.E), padx=5, pady=5)
        self.sim_log_text_widget = scrolledtext.ScrolledText(sim_log_frame, wrap=tk.WORD, width=40, height=10, state='disabled')
        self.sim_log_text_widget.pack(fill=tk.BOTH, expand=True)
        
        self.sim_status_var = tk.StringVar(value="Simulation Ready")
        ttk.Label(sim_control_frame, textvariable=self.sim_status_var).grid(row=4, column=0, columnspan=2, pady=5)
        sim_frame.rowconfigure(1, weight=1)

    def _generate_message_gui(self):
        try:
            fields = {
                'repeat': int(self.gen_vars['repeat'].get()), # key is 'repeat' from labels_defaults
                'mmsi': validate_mmsi(self.gen_vars['mmsi'].get()),
                'nav_status': validate_nav_status(self.gen_vars['nav'].get()),
                'rot': validate_rot(self.gen_vars['rot'].get()),
                'sog': validate_speed(self.gen_vars['sog'].get()),
                'accuracy': 1 if int(self.gen_vars['accuracy'].get()) == 1 else 0,
                 # Ensure correct keys for lat/lon validation
                'lon': validate_coordinates(self.gen_vars['latitude'].get(), self.gen_vars['longitude'].get())[1],
                'lat': validate_coordinates(self.gen_vars['latitude'].get(), self.gen_vars['longitude'].get())[0],
                'cog': validate_course(self.gen_vars['cog'].get()),
                'hdg': validate_heading(self.gen_vars['heading'].get()),
                'timestamp': int(self.gen_vars['timestamp'].get()) % 60,
                'maneuver': validate_maneuver(self.gen_vars['maneuver'].get()),
                'raim': 1 if int(self.gen_vars['raim'].get()) == 1 else 0
            }
            
            message_bits_168 = build_ais_type1_message_bits(fields)
            payload_char_str, nmea_fill_bits = ais_bits_to_payload_string(message_bits_168)

            self.payload_var.set(payload_char_str)
            self.fill_var.set(str(nmea_fill_bits))

            channel = 'A' # Default for single message generation
            sentence_body = f"AIVDM,1,1,,{channel},{payload_char_str},{nmea_fill_bits}"
            cs = compute_nmea_checksum(sentence_body)
            full_sentence = f"!{sentence_body}*{cs}"
            self.nmea_var.set(full_sentence)
            logger.info(f"Generated Standard NMEA: {full_sentence}")

        except ValueError as e:
            messagebox.showerror("Input Error", str(e))
            logger.error(f"GUI Generation Error: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"An unexpected error occurred: {e}")
            logger.exception("Unexpected GUI Generation Error")

    def _transmit_message_gui(self): # Uses new create_ais_signal_standard
        nmea_sentence = self.nmea_var.get()
        if not nmea_sentence:
            messagebox.showerror("Error", "Generate an AIS message first.")
            return

        selected_idx = self.signal_listbox.curselection()
        if not selected_idx:
            messagebox.showerror("Error", "Select a signal preset for transmission.")
            return
        signal_preset = SIGNAL_PRESETS[selected_idx[0]]

        if messagebox.askyesno("Confirm Transmission",
                               f"Transmit AIS message using {signal_preset['name']}?\n"
                               f"Frequency: {signal_preset['freq']/1e6:.3f} MHz\n\n"
                               "WARNING: Transmitting on AIS frequencies without authorization is illegal and may interfere with maritime safety."):
            threading.Thread(
                target=self._transmit_signal_thread_wrapper,
                args=(signal_preset, nmea_sentence, create_ais_signal_standard), # Pass standard func
                daemon=True, name="TransmitThread"
            ).start()

    def _transmit_signal_thread_wrapper(self, signal_preset, nmea_sentence, signal_creation_func):
        try:
            success = transmit_signal(signal_preset, nmea_sentence, 
                                      lambda msg: self._gui_log_update(msg, self.log_text_widget),
                                      signal_creation_func) # Pass the signal_creation_func
            log_target = self.log_text_widget
            if hasattr(threading.current_thread(), 'sim_log_target'): # Check if called from sim
                log_target = threading.current_thread().sim_log_target

            if success:
                self._gui_log_update(f"Transmission successful: {signal_preset['name']}", log_target)
            else:
                self._gui_log_update(f"Transmission failed: {signal_preset['name']}", log_target)
        except Exception as e:
            logger.exception("Error during _transmit_signal_thread_wrapper")
            self._gui_log_update(f"Critical transmission error: {e}", self.log_text_widget)

    def _add_new_ship_gui(self): self._ship_dialog(None)
    def _edit_selected_ship_gui(self):
        selected_indices = self.ship_listbox.curselection()
        if not selected_indices: messagebox.showerror("Error", "Select a ship to edit."); return
        self._ship_dialog(self.ship_configs[selected_indices[0]])

    def _ship_dialog(self, ship_instance=None): # Add maneuver and raim fields
        dialog = tk.Toplevel(self.root)
        dialog.title("Add New Ship" if ship_instance is None else f"Edit Ship: {ship_instance.name}")
        
        # Matched to AISShip defaults
        fields_data = [
            ("Name:", "name", tk.StringVar(), "New Vessel"),
            ("MMSI:", "mmsi", tk.StringVar(), "366999002"),
            ("Ship Type (0-99):", "ship_type", tk.StringVar(), "0"),
            ("Length (m, 0=N/A):", "length", tk.StringVar(), "0"),
            ("Beam (m, 0=N/A):", "beam", tk.StringVar(), "0"),
            ("Latitude (°, 91=N/A):", "lat", tk.StringVar(), "91.0"),
            ("Longitude (°, 181=N/A):", "lon", tk.StringVar(), "181.0"),
            ("Course (COG°, 360=N/A):", "course", tk.StringVar(), "360.0"),
            ("Speed (SOG knots, 102.3=N/A):", "speed", tk.StringVar(), "102.3"),
            ("Nav Status (0-15, 15=Undef):", "status", tk.StringVar(), "15"),
            ("Rate of Turn (-128..127, -128=N/Info):", "turn", tk.StringVar(), "-128"),
            ("Destination (max 20char):", "destination", tk.StringVar(), ""),
            ("Accuracy (0=Low, 1=High):", "accuracy", tk.StringVar(), "0"),
            ("Heading (HDG°, 511=N/A):", "heading", tk.StringVar(), "511"),
            ("Maneuver (0-2, 0=N/A):", "maneuver", tk.StringVar(), "0"),
            ("RAIM in use (0/1):", "raim", tk.StringVar(), "0")
        ]
        entries = {}
        for i, (label_text, key, var, default_val) in enumerate(fields_data):
            ttk.Label(dialog, text=label_text).grid(row=i, column=0, sticky=tk.W, padx=5, pady=2)
            current_val = str(getattr(ship_instance, key, default_val)) if ship_instance else default_val
            var.set(current_val)
            entry = ttk.Entry(dialog, textvariable=var, width=25)
            entry.grid(row=i, column=1, sticky=tk.EW, padx=5, pady=2)
            entries[key] = var
        dialog.columnconfigure(1, weight=1)

        def on_save():
            try:
                ship_data_from_gui = {key: var.get() for key, var in entries.items()}
                new_ship = AISShip.from_dict(ship_data_from_gui) # Validation in AISShip
                if new_ship is None: return # Error handled by AISShip.from_dict or shown by messagebox
                
                if ship_instance: # Editing
                    idx = self.ship_configs.index(ship_instance)
                    self.ship_configs[idx] = new_ship
                else: # Adding
                    self.ship_configs.append(new_ship)
                
                self._update_ship_listbox()
                self._save_ship_configs()
                dialog.destroy()
            except ValueError as e: messagebox.showerror("Input Error", str(e), parent=dialog)
            except Exception as e:
                messagebox.showerror("Error", f"Unexpected error: {e}", parent=dialog)
                logger.exception("Error in ship dialog save")

        ttk.Button(dialog, text="Save", command=on_save).grid(row=len(fields_data), column=0, pady=10, padx=5, sticky=tk.E)
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).grid(row=len(fields_data), column=1, pady=10, padx=5, sticky=tk.W)
    
    def _delete_selected_ships_gui(self): # Unchanged
        selected_indices = self.ship_listbox.curselection()
        if not selected_indices: messagebox.showerror("Error", "Select ship(s) to delete."); return
        if messagebox.askyesno("Confirm Delete", f"Delete {len(selected_indices)} selected ship(s)?"):
            for i in sorted(selected_indices, reverse=True): del self.ship_configs[i]
            self._update_ship_listbox(); self._save_ship_configs()
            logger.info(f"Deleted {len(selected_indices)} ship(s).")

    def _start_ship_simulation_gui(self): # Uses new create_ais_signal_standard implicitly
        if self.simulation_active: messagebox.showwarning("Simulation", "Already running."); return
        try:
            sim_channel_str = self.sim_channel_var.get()
            if not sim_channel_str or ":" not in sim_channel_str: messagebox.showerror("Error", "Invalid AIS channel."); return
            selected_preset_idx = int(sim_channel_str.split(":")[0])
            if not (0 <= selected_preset_idx < len(SIGNAL_PRESETS)): messagebox.showerror("Error", "Channel index out of bounds."); return
            signal_preset = SIGNAL_PRESETS[selected_preset_idx]
            interval = float(self.sim_interval_var.get())
            if interval < 1: raise ValueError("Interval must be >= 1s.")
        except ValueError as e: messagebox.showerror("Input Error", f"Invalid parameter: {e}"); return

        selected_indices = self.ship_listbox.curselection()
        if not selected_indices: messagebox.showerror("Error", "Select ships for simulation."); return
        sim_ships = [self.ship_configs[i] for i in selected_indices] # Copy for thread

        if messagebox.askyesno("Start Simulation",
                               f"Simulate {len(sim_ships)} ship(s) on {signal_preset['name']} every {interval:.1f}s?\n"
                               "WARNING: Unauthorized transmission is illegal."):
            self.simulation_active = True
            self.start_sim_btn.config(state=tk.DISABLED)
            self.stop_sim_btn.config(state=tk.NORMAL)
            self.sim_status_var.set("Simulation Active")
            
            self.simulation_thread = threading.Thread(
                target=self._run_ship_simulation_thread,
                args=(signal_preset, interval, sim_ships, create_ais_signal_standard), # Pass standard func
                daemon=True, name="ShipSimThread"
            )
            self.simulation_thread.start()
            logger.info("Ship simulation started.")

    def _stop_ship_simulation_gui(self): # Unchanged
        if not self.simulation_active: return
        self.simulation_active = False 
        self.start_sim_btn.config(state=tk.NORMAL if SDR_AVAILABLE else tk.DISABLED)
        self.stop_sim_btn.config(state=tk.DISABLED)
        self.sim_status_var.set("Simulation Stopped")
        logger.info("Ship simulation stop requested.")
            
    def _run_ship_simulation_thread(self, signal_preset, interval, sim_ships_list, signal_creation_func):
        logger.info(f"Sim thread started with {len(sim_ships_list)} ships, interval {interval}s.")
        last_move_time = datetime.now()
        try:
            while self.simulation_active and sim_ships_list:
                current_time = datetime.now()
                elapsed_seconds = (current_time - last_move_time).total_seconds()
                last_move_time = current_time

                for ship in sim_ships_list:
                    if not self.simulation_active: break
                    try: ship.move(elapsed_seconds)
                    except Exception as e: logger.error(f"Error moving ship {ship.name}: {e}")
                if not self.simulation_active: break

                for i, ship in enumerate(sim_ships_list):
                    if not self.simulation_active: break
                    try:
                        fields = ship.get_ais_fields()
                        message_bits_168 = build_ais_type1_message_bits(fields)
                        payload_char_str, nmea_fill_bits = ais_bits_to_payload_string(message_bits_168)
                        
                        channel_char = 'A' if signal_preset["freq"] < 162.0e6 else 'B'
                        sentence_body = f"AIVDM,1,1,,{channel_char},{payload_char_str},{nmea_fill_bits}"
                        cs = compute_nmea_checksum(sentence_body)
                        full_sentence = f"!{sentence_body}*{cs}"
                        
                        log_msg_sim = f"Sim: Tx {ship.name} ({ship.mmsi}) on {signal_preset['name']}"
                        # Set thread-local attribute for transmit_signal_thread_wrapper to log to correct widget
                        threading.current_thread().sim_log_target = self.sim_log_text_widget
                        transmit_signal(signal_preset, full_sentence, 
                                        lambda msg: self._gui_log_update(msg, self.sim_log_text_widget),
                                        signal_creation_func) # Pass standard func
                        delattr(threading.current_thread(), 'sim_log_target') # Clean up

                        if self.simulation_active: time.sleep(0.2) 
                    except Exception as e:
                        err_msg = f"Sim Error (ship {ship.name}): {e}"
                        logger.exception(err_msg)
                        self._gui_log_update(err_msg, self.sim_log_text_widget)
                
                if self.simulation_active:
                    wait_msg = f"Sim: Cycle complete. Waiting {interval:.1f}s..."
                    self._gui_log_update(wait_msg, self.sim_log_text_widget)
                    for _ in range(int(interval)): # Allow interruption
                        if not self.simulation_active: break
                        time.sleep(1)
        except Exception as e:
            sim_err_msg = f"Critical simulation thread error: {e}"
            logger.exception(sim_err_msg)
            self._gui_log_update(sim_err_msg, self.sim_log_text_widget)
        finally:
            self.simulation_active = False
            self.root.after(0, self._simulation_thread_ended_gui_update)
            logger.info("Simulation thread finished.")
            
    def _simulation_thread_ended_gui_update(self): # Unchanged
        if not self.simulation_active : 
            self.start_sim_btn.config(state=tk.NORMAL if SDR_AVAILABLE else tk.DISABLED)
            self.stop_sim_btn.config(state=tk.DISABLED)
            self.sim_status_var.set("Simulation Ended / Error")

    def _update_ship_listbox(self): # Unchanged
        self.ship_listbox.delete(0, tk.END)
        for ship in self.ship_configs: self.ship_listbox.insert(tk.END, f"{ship.name} (MMSI: {ship.mmsi})")
        logger.debug("Ship listbox updated.")

    def _save_ship_configs(self): # Unchanged
        try:
            with open(CONFIG_FILE_PATH, 'w') as f: json.dump([ship.to_dict() for ship in self.ship_configs], f, indent=2)
            logger.info(f"Ship configurations saved to {CONFIG_FILE_PATH}")
        except Exception as e: logger.error(f"Error saving ship configurations: {e}"); messagebox.showerror("File Error", f"Could not save: {e}")

    def _load_ship_configs(self): # Unchanged, but AISShip.from_dict is more robust
        self.ship_configs = []
        if CONFIG_FILE_PATH.exists():
            try:
                with open(CONFIG_FILE_PATH, 'r') as f:
                    data_list = json.load(f)
                    for ship_data in data_list:
                        ship = AISShip.from_dict(ship_data)
                        if ship: self.ship_configs.append(ship)
                logger.info(f"Loaded {len(self.ship_configs)} ship(s) from {CONFIG_FILE_PATH}")
            except Exception as e: logger.error(f"Error loading/parsing {CONFIG_FILE_PATH}: {e}"); messagebox.showerror("Load Error", f"Failed to load: {e}")
        else: logger.info(f"{CONFIG_FILE_PATH} not found.")
        if not self.ship_configs: self._create_sample_ships()
        self._update_ship_listbox()
        
    def _create_sample_ships(self): # Added maneuver, raim to sample
        logger.info("Creating sample ships.")
        sample_data = [
            {"name": "Cargo Alpha", "mmsi": "366123001", "ship_type": 70, "lat": 40.7028, "lon": -74.0160, "course": 45, "speed": 8, "maneuver":1, "raim":0},
            {"name": "Tanker Bravo", "mmsi": "366123002", "ship_type": 80, "lat": 40.7050, "lon": -74.0180, "course": 90, "speed": 5, "maneuver":0, "raim":1},
        ]
        for data in sample_data:
            ship = AISShip.from_dict(data)
            if ship: self.ship_configs.append(ship)
        self._save_ship_configs()

    def _on_closing(self): # Unchanged
        logger.info("Application closing sequence started.")
        if self.simulation_active: self.simulation_active = False
        logger.info("Destroying root window.")
        self.root.destroy()
        logger.info("Application closed.")

# transmit_signal now takes signal_creation_func
def transmit_signal(signal_preset, nmea_sentence, status_callback, signal_creation_func):
    if not SDR_AVAILABLE:
        msg = "SoapySDR not available. Cannot transmit."
        logger.error(msg)
        if status_callback: status_callback(msg)
        return False

    sdr = None; tx_stream = None
    try:
        if status_callback: status_callback(f"Preparing TX: {signal_preset['name']} for NMEA: {nmea_sentence[:30]}...")
        logger.info(f"Attempting TX: {signal_preset['name']}, NMEA: {nmea_sentence}")

        sdr_driver = signal_preset.get("sdr_type", "hackrf")
        devices = SoapySDR.Device.enumerate({'driver': sdr_driver})
        if not devices:
            logger.warning(f"No SDRs for '{sdr_driver}'. Trying generic."); devices = SoapySDR.Device.enumerate()
            if not devices: raise RuntimeError(f"No SDR devices found.")
        
        sdr = SoapySDR.Device(devices[0])
        sdr_info = devices[0].get('label', 'N/A') if isinstance(devices[0], dict) else "Unknown SDR"
        logger.info(f"SDR Initialized: {sdr_info}")
        if status_callback: status_callback(f"SDR Initialized: {sdr_info}")

        sample_rate = 2e6
        center_freq = signal_preset["freq"]
        tx_gain = float(signal_preset["gain"])

        sdr.setSampleRate(SOAPY_SDR_TX, 0, sample_rate)
        sdr.setFrequency(SOAPY_SDR_TX, 0, center_freq)
        # Generic gain setting (same as robust_ais_main.py)
        available_gains = sdr.listGains(SOAPY_SDR_TX, 0)
        if available_gains:
            try: # Try to set overall gain first if it has a range that includes the target
                gain_range = sdr.getGainRange(SOAPY_SDR_TX, 0)
                if gain_range.minimum() <= tx_gain <= gain_range.maximum():
                    sdr.setGain(SOAPY_SDR_TX, 0, tx_gain)
                    logger.info(f"Set overall SDR gain to {tx_gain} dB")
                else: # Fallback to individual gain elements
                    raise SoapySDR.SoapySDR_Exception("Overall gain out of range") # force fallback
            except SoapySDR.SoapySDR_Exception: # If overall gain setting fails or not applicable
                 logger.warning(f"Could not set overall gain to {tx_gain}. Trying element gains.")
                 for gain_name in available_gains: # Try to set all available elements
                    try: 
                        # Distribute gain or set specific known elements (e.g. LNA, VGA)
                        # Simple approach: set first element to target gain or part of it
                        gain_to_set_element = tx_gain / len(available_gains) if len(available_gains) > 1 else tx_gain
                        gain_element_range = sdr.getGainRange(SOAPY_SDR_TX, 0, gain_name)
                        clamped_gain = max(gain_element_range.minimum(), min(gain_element_range.maximum(), gain_to_set_element))
                        sdr.setGain(SOAPY_SDR_TX, 0, gain_name, clamped_gain)
                        logger.info(f"Set gain '{gain_name}' to {clamped_gain} dB")
                    except Exception as e_gain:
                        logger.warning(f"Could not set gain for element {gain_name}: {e_gain}")
        else: # No gain elements listed, try setting overall gain directly
            sdr.setGain(SOAPY_SDR_TX, 0, tx_gain)
            logger.info(f"Set overall gain to {tx_gain} dB (no specific gain elements listed).")

        if status_callback: status_callback(f"SDR Configured: {center_freq/1e6:.3f}MHz, Gain ~{tx_gain}dB")

        signal_data = signal_creation_func(nmea_sentence, sample_rate) # Use passed function
        if status_callback: status_callback(f"AIS signal (len: {len(signal_data)}). Setting up stream...")

        tx_stream = sdr.setupStream(SOAPY_SDR_TX, SOAPY_SDR_CF32, [0])
        sdr.activateStream(tx_stream)
        if status_callback: status_callback("Stream activated. Transmitting...")

        # Transmit in one go as AIS bursts are short
        ret = sdr.writeStream(tx_stream, [signal_data.astype(np.complex64)], len(signal_data))
        
        if ret.ret != len(signal_data) or ret.flags != 0: # Check flags for issues like timeout, underflow
            logger.warning(f"TX issue: sent {ret.ret}/{len(signal_data)} samples. Flags: {ret.flags}, Timestamp: {ret.timeNs}")
            if status_callback: status_callback(f"TX issue: {ret.ret}/{len(signal_data)}. Flags: {ret.flags}")
        else:
            logger.info(f"TX successful: {ret.ret} samples. Flags: {ret.flags}")
            if status_callback: status_callback(f"TX successful: {ret.ret} samples.")
        
        time.sleep(0.1) # Allow SDR buffer to flush
        return True

    except Exception as e: # Catch-all for SoapySDR_Exception, RuntimeError, etc.
        err_msg = f"TX Error ({type(e).__name__}): {e}"
        logger.exception(err_msg)
        if status_callback: status_callback(err_msg)
        return False
    finally:
        if tx_stream and sdr:
            try: sdr.deactivateStream(tx_stream); sdr.closeStream(tx_stream)
            except Exception as e_clean: logger.error(f"Error cleaning TX stream: {e_clean}")
        if sdr: del sdr; gc.collect()
        if status_callback: status_callback("TX attempt finished.")

def transmit_with_hackrf(signal_data, center_freq, sample_rate=2e6):
    """Transmit I/Q samples using HackRF at maximum power"""
    # Convert complex samples to 8-bit I/Q data for hackrf_transfer
    iq_data = np.zeros(len(signal_data)*2, dtype=np.int8)
    
    # Maximize amplitude while avoiding clipping
    # Normalize to 0.99 of maximum to leave small headroom
    max_amp = np.max(np.abs(signal_data))
    if max_amp > 0:
        signal_data = signal_data / max_amp * 0.99
    
    # Convert to 8-bit with maximum amplitude
    iq_data[0::2] = np.clip(np.real(signal_data) * 127, -127, 127).astype(np.int8)
    iq_data[1::2] = np.clip(np.imag(signal_data) * 127, -127, 127).astype(np.int8)
    
    # Save to temporary file
    with tempfile.NamedTemporaryFile(delete=False) as f:
        temp_filename = f.name
        iq_data.tofile(f)
    
    try:
        # Transmit using hackrf_transfer with maximum power settings
        cmd = [
            "hackrf_transfer",
            "-t", temp_filename,
            "-f", str(int(center_freq)),
            "-s", str(int(sample_rate)),
            "-a", "1",      # Enable antenna port
            "-x", "47",     # Maximum VGA gain (0-47)
            "-l", "47",     # Maximum TX LNA gain
            "-i", "47",     # Maximum IF gain
            "-b", "2.75"    # Optimal baseband filter bandwidth
        ]
        
        print(f"Transmitting at MAXIMUM POWER on {center_freq/1e6:.3f} MHz")
        print(f"Command: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error: {result.stderr}")
        else:
            print("High-power transmission completed successfully")
            
    except Exception as e:
        print(f"Transmission error: {e}")
    finally:
        # Clean up
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

if __name__ == "__main__":
    root = tk.Tk()
    app = AISApp(root)
    try:
        root.mainloop()
    except KeyboardInterrupt: logger.info("App interrupted."); app._on_closing()
    except Exception: logger.exception("Unhandled exception in mainloop.");
    finally: logging.shutdown()