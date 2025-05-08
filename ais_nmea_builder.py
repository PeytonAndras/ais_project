import tkinter as tk          
from tkinter import ttk, messagebox, scrolledtext
import numpy as np            
import time
import threading

### SoapySDR and LimeSDR inintialization ###
# Try to import SoapySDR for HackRF functionality
# If not available, disable transmission functionality
try:
    import SoapySDR
    print("SoapySDR imported successfully")
    # Define constants that might be missing from the Python module
    SOAPY_SDR_TX = "TX"
    SOAPY_SDR_CF32 = "CF32"
    # Try to import from SoapySDR if available, otherwise use our definitions
    try:
        from SoapySDR import SOAPY_SDR_TX, SOAPY_SDR_CF32
    except ImportError:
        print("Using manually defined SDR constants")
    print("SDR constants defined")
    SDR_AVAILABLE = True
except ImportError as e:
    print(f"SoapySDR import error: {e}")
    SDR_AVAILABLE = False

### AIS payload generation ###
# AIS 6-bit ASCII conversion
# AIS uses a special 6-bit ASCII encoding to save bandwidth
def sixbit_to_char(val):
    if val < 0 or val > 63:
        raise ValueError("6-bit value out of range")
    if val < 40:
        return chr(val + 48)  # ASCII 0-9, :, ;, <, =, >, ?
    else:
        return chr(val + 56)  # ASCII @, A-Z, [, \, ], ^, _

# Compute NMEA checksum
# XOR all characters between $ and * to generate a 2-digit hex value
def compute_checksum(sentence):
    cs = 0
    for c in sentence:
        cs ^= ord(c)  # XOR operation with ASCII value
    return f"{cs:02X}"  # Return as 2-digit hex

# Build AIS payload for message type 1 (Position Report Class A)
# Constructs binary representation according to AIS protocol specification
def build_ais_payload(fields):
    bits = []
    # Helper function to add bits to the message
    def add(value, length):
        for i in range(length - 1, -1, -1):
            bits.append((value >> i) & 1)  # Add individual bits MSB first

    # Mandatory fields for type 1
    add(fields['msg_type'], 6)   # Message type (1-27)
    add(fields['repeat'], 2)     # Repeat indicator
    add(fields['mmsi'], 30)      # Maritime Mobile Service Identity (ship ID)
    add(fields['nav_status'], 4) # Navigation status (0-15)
    
    # ROT: Rate of Turn (-127 to +127, two's complement 8 bits)
    rot = fields['rot'] & 0xFF   # Mask to 8 bits
    add(rot, 8)
    
    # Speed over ground: 0.1 knot units
    sog = int(fields['sog'] * 10) & 0x3FF  # Convert to 1/10th knots, mask to 10 bits
    add(sog, 10)
    
    # Position accuracy (1=high, 0=low)
    add(fields['accuracy'], 1)
    
    # Longitude: 1/10000 minute, two's complement 28 bits
    lon_minutes = fields['lon'] * 60  # Convert to minutes
    lon_value = int(lon_minutes * 10000)  # Convert to 1/10000 minute
    if lon_value < 0:
        lon_value = (1 << 28) + lon_value  # Proper two's complement for negative values
    lon_value = int(lon_value) & ((1 << 28) - 1)  # Ensure we have an integer
    add(lon_value, 28)
    
    # Latitude: 1/10000 minute, two's complement 27 bits
    lat_val = int(fields['lat'] * 600000)
    lat = int(lat_val) & ((1 << 27) - 1)
    add(lat, 27)
    
    # COG: Course Over Ground in 0.1 degree units
    cog = int(fields['cog'] * 10) & 0xFFF  # 12 bits
    add(cog, 12)
    
    # True heading (0-359, 511=N/A)
    # Add checking for special values
    # For example:
    if fields['hdg'] == -1:  # -1 used to indicate "not available"
        add(511, 9)  # 511 = HDG not available
    else:
        add(int(fields['hdg']) & 0x1FF, 9)
    
    # Timestamp (UTC second, 0-59)
    add(int(fields['timestamp']) & 0x3F, 6)  # 6 bits
    
    # Spare + flags (set to zero)
    add(0, 8)

    # Pad to 6-bit boundary for proper encoding
    fill = (6 - (len(bits) % 6)) % 6
    for _ in range(fill): bits.append(0)

    # Convert binary data to 6-bit ASCII for NMEA encoding
    payload = ''.join(sixbit_to_char(int(''.join(str(b) for b in bits[i:i+6]), 2))
                      for i in range(0, len(bits), 6))
    return payload, fill

# Signal configuration presets
SIGNAL_PRESETS = [
    {"name": "AIS Channel A", "freq": 161.975e6, "gain": 70, "modulation": "GMSK", "sdr_type": "hackrf"},
    {"name": "AIS Channel B", "freq": 162.025e6, "gain": 65, "modulation": "GMSK", "sdr_type": "hackrf"},
]

# Create different signal types
def create_signal(signal_type, sample_rate, duration=2.0):
    num_samples = int(sample_rate * duration)
    
    if signal_type == "GMSK":
        # Simple carrier for AIS (would be GMSK modulated in a real implementation)
        return np.exp(1j * 2 * np.pi * np.arange(num_samples) * 1000 / sample_rate) * 0.5
    
    elif signal_type == "FM":
        # Simple FM modulation for voice channels
        t = np.arange(num_samples) / sample_rate
        # Create a 1kHz tone with FM modulation
        modulation = np.sin(2 * np.pi * 1000 * t) 
        phase = 0.5 * np.cumsum(modulation) / sample_rate
        return 0.5 * np.exp(1j * 2 * np.pi * (1000 * t + phase))
    
    elif signal_type == "FSK":
        # Simple 2-level FSK for DSC
        t = np.arange(num_samples) / sample_rate
        # Alternate between two frequencies
        bits = np.round(np.random.rand(num_samples // 1000)).repeat(1000)
        freq_shift = bits * 100  # 100Hz shift
        return 0.5 * np.exp(1j * 2 * np.pi * (1000 + freq_shift) * t / sample_rate)
    
    elif signal_type == "BFSK":
        # Binary FSK for NAVTEX
        t = np.arange(num_samples) / sample_rate
        # Create a sequence of random bits
        bits = np.round(np.random.rand(num_samples // 2000)).repeat(2000)
        freq_shift = bits * 170  # 170Hz shift for NAVTEX
        return 0.5 * np.exp(1j * 2 * np.pi * (100 + freq_shift) * t / sample_rate)
    
    else:  # Custom/Default
        # Simple carrier wave
        return np.exp(1j * 2 * np.pi * np.arange(num_samples) * 1000 / sample_rate) * 0.5

def create_gmsk_signal(data_bits, sample_rate):
    """Create a GMSK modulated signal with proper AIS parameters"""
    # AIS uses 9600 bits/sec
    bit_rate = 9600.0
    # GMSK BT product for AIS is 0.4
    bt = 0.4
    # Samples per bit
    samples_per_bit = int(sample_rate / bit_rate)
    # Generate GMSK modulation
    # [Implement GMSK modulation here]
    # ...

def create_ais_signal(nmea_sentence, sample_rate=2e6, repetitions=6):
    """Create a properly modulated AIS signal from NMEA sentence"""
    
    # Step 1: Extract payload from NMEA sentence
    parts = nmea_sentence.split(',')
    if len(parts) < 6:
        raise ValueError("Invalid NMEA sentence")
    
    payload = parts[5]  # The actual AIS data in 6-bit ASCII
    
    # Step 2: Convert 6-bit ASCII back to bits
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
    
    # Get all bits from payload
    bits = []
    for char in payload:
        bits.extend(char_to_sixbit(char))
    
    # Step 3: Add start/end flags and bit stuffing
    # AIS start/end flag is 0x7E (01111110)
    start_flag = [0, 1, 1, 1, 1, 1, 1, 0]
    
    # Add CRC (simplified - real AIS needs proper CRC)
    # and perform bit stuffing (add 0 after five consecutive 1s)
    stuffed_bits = []
    consecutive_ones = 0
    
    # Add start flag
    stuffed_bits.extend(start_flag)
    
    # Add preamble (training sequence of alternating 0s and 1s)
    stuffed_bits.extend([0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1])
    
    # Add data bits with bit stuffing
    for bit in bits:
        if bit == 1:
            consecutive_ones += 1
        else:
            consecutive_ones = 0
            
        stuffed_bits.append(bit)
        
        # After 5 consecutive ones, insert a 0
        if consecutive_ones == 5:
            stuffed_bits.append(0)
            consecutive_ones = 0
    
    # Add end flag
    stuffed_bits.extend(start_flag)
    
    # Step 4: NRZI encoding
    nrzi_bits = []
    current_level = 0  # Start with 0
    
    for bit in stuffed_bits:
        if bit == 0:
            # For 0, we invert the level
            current_level = 1 - current_level
        # For 1, level stays the same
        nrzi_bits.append(current_level)
    
    # Step 5: GMSK modulation
    bit_rate = 9600.0  # AIS bit rate
    samples_per_bit = int(sample_rate / bit_rate)
    num_samples = len(nrzi_bits) * samples_per_bit
    
    # BT product for AIS is 0.4 (bandwidth time product)
    bt = 0.4
    
    # Create Gaussian filter
    def gaussian_impulse(t, bt):
        return np.sqrt(2*np.pi/np.log(2)) * bt * np.exp(-2*np.pi**2*bt**2*t**2/np.log(2))
    
    # Create Gaussian filter kernel
    filter_length = 4  # Length in symbols
    t = np.arange(-filter_length/2, filter_length/2, 1/samples_per_bit)
    h = gaussian_impulse(t, bt)
    h = h / np.sum(h)  # Normalize
    
    # Upsample bits to sample rate
    upsampled = np.zeros(num_samples)
    for i, bit in enumerate(nrzi_bits):
        upsampled[i*samples_per_bit] = 2*bit - 1  # Convert 0/1 to -1/+1
    
    # Apply Gaussian filter
    filtered = np.convolve(upsampled, h, 'same')
    
    # Integrate to get phase
    phase = np.cumsum(filtered) * np.pi / samples_per_bit  # π/2 phase shift for each bit
    
    # Generate complex I/Q samples
    i_samples = np.cos(phase)
    q_samples = np.sin(phase)
    iq_samples = i_samples + 1j * q_samples
    
    # Normalize to ensure consistent amplitude
    max_amp = np.max(np.abs(iq_samples))
    if max_amp > 0:
        iq_samples = iq_samples / max_amp * 0.9
    
    # Apply amplitude scaling
    return np.tile(iq_samples * 1.0, repetitions)  # Increased from 0.9 to 1.0

### TRANSMISSION FUNCTIONALITY ###
# Function to transmit an AIS message or custom signal using LimeSDR Mini
def transmit_signal(signal_preset, nmea_sentence=None, status_callback=None):
    if not SDR_AVAILABLE:
        message = "SoapySDR module not available. Install with: pip install soapysdr"
        if status_callback:
            status_callback(message)
        else:
            messagebox.showerror("Error", message)
        return
    
    def update_status(msg):
        print(msg)
        if status_callback:
            status_callback(msg)
    
    try:
        update_status(f"Preparing to transmit {signal_preset['name']}...")
        
        # Find available SDR devices
        try:
            # Try multiple device types
            devices = []
            
            # Try HackRF
            try:
                hackrf_devices = SoapySDR.Device.enumerate({'driver': 'hackrf'})
                if (hackrf_devices):
                    devices = hackrf_devices
                    update_status(f"Found {len(hackrf_devices)} HackRF device(s)")
            except:
                update_status("No HackRF devices found, trying LimeSDR...")
            
            # Try LimeSDR if no HackRF
            if not devices:
                try:
                    lime_devices = SoapySDR.Device.enumerate({'driver': 'lime'})
                    if lime_devices:
                        devices = lime_devices
                        update_status(f"Found {len(lime_devices)} LimeSDR device(s)")
                except:
                    update_status("No LimeSDR devices found...")
            
            # Try generic enumeration as last resort
            if not devices:
                devices = SoapySDR.Device.enumerate()
                update_status(f"Found {len(devices)} SDR device(s) with generic search")
            
            if not devices:
                raise RuntimeError("No SDR devices found. Connect a HackRF or LimeSDR.")
        
        except Exception as e:
            update_status(f"Error finding SDR: {str(e)}")
            raise
        
        # Initialize the HackRF
        try:
            # Try different initialization methods
            try:
                sdr = SoapySDR.Device(devices[0])
            except AttributeError:
                # Fall back to makeDevice for older versions
                sdr = SoapySDR.makeDevice(devices[0])
            update_status("HackRF initialized successfully")
        except Exception as e:
            update_status(f"Failed to initialize HackRF: {str(e)}")
            # Try generic driver approach
            try:
                sdr = SoapySDR.Device({'driver': 'hackrf'})
            except AttributeError:
                sdr = SoapySDR.makeDevice({'driver': 'hackrf'})
            update_status("HackRF initialized with generic driver")
        
        # Configure HackRF parameters for transmission
        center_freq = signal_preset["freq"]
        sample_rate = 2e6  # 2 MHz sample rate (HackRF supports 8-20 MHz, but we'll use 2MHz for compatibility)
        tx_gain = signal_preset["gain"]
        
        update_status(f"Configuring transmission parameters: {center_freq/1e6} MHz, Gain: {tx_gain} dB...")
        
        # HackRF gain settings are different than LimeSDR
        # HackRF has separate RF amplifier, IF gain, and baseband gain settings
        try:
            # Set sample rate
            sdr.setSampleRate(SOAPY_SDR_TX, 0, sample_rate)
            
            # Set frequency
            sdr.setFrequency(SOAPY_SDR_TX, 0, center_freq)
            
            # HackRF gain handling - different approach
            try:
                # First approach: Try to list gain names
                gain_names = sdr.listGains(SOAPY_SDR_TX, 0)
                print(f"Available gain elements: {gain_names}")
                
                # Try to set individual gains if available
                if 'AMP' in gain_names:
                    amp_value = 14 if tx_gain > 30 else 0
                    sdr.setGain(SOAPY_SDR_TX, 0, 'AMP', amp_value)
                    print(f"Set AMP gain to {amp_value}")
                    
                if 'VGA' in gain_names:
                    vga_value = min(47, max(0, tx_gain))
                    sdr.setGain(SOAPY_SDR_TX, 0, 'VGA', vga_value)
                    print(f"Set VGA gain to {vga_value}")
                    
            except Exception as e:
                # Fallback: Just set overall gain
                print(f"Could not set individual gains: {e}")
                print("Using overall gain setting instead")
                sdr.setGain(SOAPY_SDR_TX, 0, tx_gain)
                print(f"Set overall gain to {tx_gain}")
            
            # Set bandwidth if available (HackRF supports this)
            try:
                sdr.setBandwidth(SOAPY_SDR_TX, 0, 1.75e6)  # 1.75 MHz bandwidth
            except Exception as bw_e:
                update_status(f"Note: Cannot set bandwidth ({str(bw_e)}), continuing anyway")
            
            update_status("Parameters set successfully")
        except Exception as param_error:
            raise RuntimeError(f"Failed to configure HackRF parameters: {str(param_error)}")
        
        # Create transmission signal based on modulation type
        update_status(f"Creating {signal_preset['modulation']} signal...")
        if signal_preset["modulation"] == "GMSK" and nmea_sentence:
            # Use the proper AIS signal generation if we have an NMEA sentence
            signal = create_ais_signal(nmea_sentence, sample_rate)
            update_status("Created properly modulated AIS signal")
        else:
            # Use the simple signal generation for other modulations or testing
            signal = create_signal(signal_preset["modulation"], sample_rate)
        
        # Add before transmitting
        print(f"Signal stats: min={np.min(np.abs(signal)):.3f}, max={np.max(np.abs(signal)):.3f}, len={len(signal)}")

        # Setup and activate the transmit stream
        update_status("Setting up transmission stream...")
        tx_stream = sdr.setupStream(SOAPY_SDR_TX, SOAPY_SDR_CF32, [0])
        sdr.activateStream(tx_stream)
        
        # Transmit the signal
        update_status("Transmitting signal...")
        status = sdr.writeStream(tx_stream, [signal], len(signal))
        update_status(f"Transmission status: {status}")
        
        # HackRF devices need explicit cleanup
        update_status("Cleaning up...")
        
        # Important: HackRF may need more time to finish
        time.sleep(1.0)  # Increased from 0.5 to 1.0 second
        
        # Proper cleanup sequence
        sdr.deactivateStream(tx_stream)
        sdr.closeStream(tx_stream)
        
        # Force Python garbage collection to properly release the device
        del sdr
        time.sleep(0.5)  # Give system time to release device
        
        update_status(f"Successfully transmitted {signal_preset['name']} on {center_freq/1e6} MHz")
        return True
    except Exception as e:
        error_msg = f"Transmission Error: {str(e)}"
        update_status(error_msg)
        
        # Suggest recovery steps for HackRF
        recovery_msg = """
Try these recovery steps:
1. Unplug the HackRF and wait 10 seconds
2. Plug it back into a different USB port
3. Run these commands in the terminal:
   hackrf_info
   hackrf_transfer -R   (This resets the device)

If problems persist, try restarting your computer.
"""
        update_status(recovery_msg)
        return False

# Generate AIS message from GUI input fields
def generate():
    try:
        # Collect all field values from GUI inputs
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
        
        # Build the AIS payload
        payload, fill = build_ais_payload(fields)
        payload_var.set(payload)
        fill_var.set(str(fill))
        
        # Assemble complete NMEA sentence
        # Allow channel selection or alternation
        channel = 'A'  # Could be selectable in the UI or alternate
        sentence = f"AIVDM,1,1,,{channel},{payload},{fill}"
        cs = compute_checksum(sentence)
        full_sentence = f"!{sentence}*{cs}"  # Add start character and checksum
        nmea_var.set(full_sentence)
    except Exception as e:
        messagebox.showerror("Error", str(e))

# Function to handle transmission button click
def transmit():
    nmea_sentence = nmea_var.get()
    if not nmea_sentence:
        messagebox.showerror("Error", "Generate an AIS message before transmitting")
        return
    
    # Get the selected signal preset
    selected_index = signal_listbox.curselection()
    if not selected_index:
        messagebox.showerror("Error", "Please select a signal type")
        return
    
    selected_preset = SIGNAL_PRESETS[selected_index[0]]
    
    # Confirm transmission intent (safety check)
    if messagebox.askyesno("Transmit", 
                          f"Are you sure you want to transmit this AIS message using {selected_preset['name']}?\n"
                          f"Frequency: {selected_preset['freq']/1e6} MHz\n"
                          f"Modulation: {selected_preset['modulation']}\n\n"
                          "Ensure you have proper authorization to transmit on these frequencies."):
        
        # Start transmission in a separate thread to keep UI responsive
        def update_log(msg):
            log_text.configure(state='normal')
            log_text.insert(tk.END, f"{msg}\n")
            log_text.see(tk.END)
            log_text.configure(state='disabled')
            status_var.set(f"Last action: {msg}")
        
        threading.Thread(
            target=transmit_signal, 
            args=(selected_preset, nmea_sentence, update_log),
            daemon=True
        ).start()

# Function to edit a signal preset
def edit_signal_preset():
    selected_index = signal_listbox.curselection()
    if not selected_index:
        messagebox.showerror("Error", "Please select a signal to edit")
        return
        
    idx = selected_index[0]
    preset = SIGNAL_PRESETS[idx]
    
    # Create edit dialog
    edit_window = tk.Toplevel(root)
    edit_window.title(f"Edit {preset['name']}")
    edit_window.geometry("300x200")
    edit_window.resizable(False, False)
    
    # Create form
    frame = ttk.Frame(edit_window, padding=10)
    frame.pack(fill=tk.BOTH, expand=True)
    
    ttk.Label(frame, text="Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
    name_var = tk.StringVar(value=preset["name"])
    ttk.Entry(frame, textvariable=name_var).grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5)
    
    ttk.Label(frame, text="Frequency (MHz):").grid(row=1, column=0, sticky=tk.W, pady=5)
    freq_var = tk.StringVar(value=str(preset["freq"]/1e6))
    ttk.Entry(frame, textvariable=freq_var).grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5)
    
    ttk.Label(frame, text="Gain (0-70):").grid(row=2, column=0, sticky=tk.W, pady=5)
    gain_var = tk.StringVar(value=str(preset["gain"]))
    ttk.Entry(frame, textvariable=gain_var).grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5)
    
    ttk.Label(frame, text="Modulation:").grid(row=3, column=0, sticky=tk.W, pady=5)
    mod_var = tk.StringVar(value=preset["modulation"])
    mod_combo = ttk.Combobox(frame, textvariable=mod_var, values=["GMSK", "FM", "FSK", "BFSK", "Custom"])
    mod_combo.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=5)
    
    def save_changes():
        try:
            # Validate and update the preset
            freq_mhz = float(freq_var.get())
            gain = int(gain_var.get())
            
            if gain < 0 or gain > 70:
                raise ValueError("Gain must be between 0 and 70")
                
            if freq_mhz <= 0:
                raise ValueError("Frequency must be positive")
                
            SIGNAL_PRESETS[idx] = {
                "name": name_var.get(),
                "freq": freq_mhz * 1e6,  # Convert to Hz
                "gain": gain,
                "modulation": mod_var.get()
            }
            
            # Update the listbox
            signal_listbox.delete(idx)
            signal_listbox.insert(idx, f"{name_var.get()} ({freq_mhz} MHz)")
            signal_listbox.selection_set(idx)
            
            edit_window.destroy()
            
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))

    btn_frame = ttk.Frame(frame)
    btn_frame.grid(row=4, column=0, columnspan=2, pady=10)
    
    ttk.Button(btn_frame, text="Save", command=save_changes).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Cancel", command=edit_window.destroy).pack(side=tk.LEFT, padx=5)

# Add these imports at the top of your file, after existing imports
import queue
import datetime

# Queue to manage multiple simultaneous transmissions
transmission_queue = queue.Queue()
is_transmitting = False

# Function to manage multiple signal transmissions
def transmission_worker():
    global is_transmitting
    is_transmitting = True
    
    while not transmission_queue.empty():
        job = transmission_queue.get()
        signal_preset, nmea_sentence, update_log = job
        
        try:
            # Call the existing transmission function
            transmit_signal(signal_preset, nmea_sentence, update_log)
            # Small delay between transmissions
            time.sleep(0.5)
        except Exception as e:
            if update_log:
                update_log(f"Error in transmission queue: {str(e)}")
            print(f"Transmission worker error: {str(e)}")
        finally:
            transmission_queue.task_done()
    
    is_transmitting = False

# Function to transmit multiple signals in sequence
def transmit_multiple_signals():
    # Get selected signals from the multi_signal_listbox
    selected_indices = multi_signal_listbox.curselection()
    if not selected_indices:
        messagebox.showerror("Error", "Please select at least one signal to transmit")
        return
    
    # Check for warning if too many signals selected
    if len(selected_indices) > 5:
        if not messagebox.askyesno("Warning", 
                                 f"You have selected {len(selected_indices)} signals to transmit. "
                                 "Transmitting many signals consecutively might cause hardware issues. Continue?"):
            return
    
    # Clear the queue if needed
    while not transmission_queue.empty():
        try:
            transmission_queue.get_nowait()
            transmission_queue.task_done()
        except queue.Empty:
            break
    
    # Function to update the log
    def update_log(msg):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_text.configure(state='normal')
        log_text.insert(tk.END, f"[{timestamp}] {msg}\n")
        log_text.see(tk.END)
        log_text.configure(state='disabled')
        status_var.set(f"Last action: {msg}")
    
    # Add selected signals to queue
    selected_presets = [SIGNAL_PRESETS[i] for i in selected_indices]
    for preset in selected_presets:
        transmission_queue.put((preset, None, update_log))
    
    update_log(f"Queued {len(selected_indices)} signals for transmission")
    
    # Start the worker thread if it's not already running
    if not is_transmitting:
        threading.Thread(target=transmission_worker, daemon=True).start()

# Add this after your transmit() function to handle individual signal testing
def test_signal():
    selected_index = multi_signal_listbox.curselection()
    if not selected_index:
        messagebox.showerror("Error", "Please select a signal to test")
        return
    
    selected_preset = SIGNAL_PRESETS[selected_index[0]]
    
    # Confirm test transmission
    if messagebox.askyesno("Test Signal", 
                          f"Test transmit {selected_preset['name']}?\n"
                          f"Frequency: {selected_preset['freq']/1e6} MHz\n"
                          f"Modulation: {selected_preset['modulation']}\n\n"
                          "Ensure you have proper authorization to transmit on these frequencies."):
        
        # Update function for the log
        def update_log(msg):
            log_text.configure(state='normal')
            log_text.insert(tk.END, f"[TEST] {msg}\n")
            log_text.see(tk.END)
            log_text.configure(state='disabled')
            status_var.set(f"Test: {msg}")
        
        # Start test transmission in a thread
        threading.Thread(
            target=transmit_signal, 
            args=(selected_preset, None, update_log),
            daemon=True
        ).start()

# Add these imports near the top of your file
import random
import math
import json
import os
from datetime import datetime, timedelta

# Add this global to store ship configurations
SHIP_CONFIGS = []
ship_simulation_active = False
simulation_thread = None

# Define ship simulation classes
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
        self.course = course  # degrees, 0-359
        self.speed = speed    # knots
        self.status = status  # navigation status
        self.turn = turn      # rate of turn
        self.destination = destination
        self.accuracy = 1     # position accuracy (1=high)
        self.heading = course # assume heading matches course initially
        
    def move(self, elapsed_seconds):
        """Move the ship based on speed, course and elapsed time"""
        if self.speed <= 0:
            return
            
        # Convert speed from knots to degrees per second
        # 1 knot = 1 nautical mile per hour = 1/60 degree per hour at equator
        # Adjust for latitude (narrower longitude degrees as we move away from equator)
        lat_factor = math.cos(math.radians(self.lat))
        
        # Calculate distance moved in degrees
        hours = elapsed_seconds / 3600
        distance_nm = self.speed * hours
        
        # Convert distance to changes in lat/lon
        dy = distance_nm * math.cos(math.radians(self.course)) / 60
        dx = distance_nm * math.sin(math.radians(self.course)) / (60 * lat_factor)
        
        # Update position
        self.lat += dy
        self.lon += dx
        
        # Apply rate of turn if any
        if self.turn != 0:
            # Convert ROT value to degrees per second
            # ROT in AIS is encoded as 1/4 degrees per minute squared
            # Simplified version: use ROT directly as degrees per minute
            rot_deg_min = self.turn / 4.0
            
            # Apply to course
            course_change = rot_deg_min * (elapsed_seconds / 60.0)
            self.course = (self.course + course_change) % 360
            self.heading = round(self.course)  # Update heading to match course
        
    def get_ais_fields(self):
        """Return a dict with AIS fields for this ship"""
        timestamp = datetime.now().second % 60  # Current second 0-59
        
        return {
            'msg_type': 1,  # Position report
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
        """Convert ship to dictionary for serialization"""
        return self.__dict__
        
    @classmethod
    def from_dict(cls, data):
        """Create a ship from dictionary"""
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

# Ship simulation functions
def save_ship_configs():
    """Save ship configurations to a JSON file"""
    try:
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ship_configs.json")
        with open(config_path, 'w') as f:
            # Convert ships to dictionaries
            ship_data = [ship.to_dict() for ship in SHIP_CONFIGS]
            json.dump(ship_data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving ship configurations: {e}")
        return False

def load_ship_configs():
    """Load ship configurations from a JSON file"""
    global SHIP_CONFIGS
    try:
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ship_configs.json")
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                ship_data = json.load(f)
                # Convert dictionaries to ships
                SHIP_CONFIGS = [AISShip.from_dict(data) for data in ship_data]
                return True
    except Exception as e:
        print(f"Error loading ship configurations: {e}")
    
    # If no file exists or error occurred, create sample ships
    if not SHIP_CONFIGS:
        create_sample_ships()
    return False

def create_sample_ships():
    """Create some sample ship configurations"""
    global SHIP_CONFIGS
    
    # New York Harbor area ships
    SHIP_CONFIGS = [
        AISShip("Cargo Vessel 1", 366123001, 70, 100, 20, 40.7028, -74.0160, 45, 8, 0),
        AISShip("Tanker 2", 366123002, 80, 120, 25, 40.7050, -74.0180, 90, 5, 0),
        AISShip("Passenger 3", 366123003, 60, 80, 15, 40.6980, -74.0100, 270, 10, 0),
        AISShip("Tug 4", 366123004, 50, 30, 10, 40.7000, -74.0120, 180, 4, 0),
        AISShip("Ferry 5", 366123005, 60, 40, 12, 40.7060, -74.0140, 0, 12, 0)
    ]

def run_ship_simulation(signal_preset, interval=10, update_status_callback=None):
    """Run the ship simulation, transmitting AIS messages at regular intervals"""
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
            current_time = datetime.now()
            elapsed = (current_time - last_move_time).total_seconds()
            
            # Move all ships based on elapsed time
            for ship in SHIP_CONFIGS:
                ship.move(elapsed)
            
            # Send AIS message for each active ship
            for i, ship in enumerate(SHIP_CONFIGS):
                if not ship_simulation_active:
                    break
                    
                # Get AIS fields and build NMEA message
                fields = ship.get_ais_fields()
                payload, fill = build_ais_payload(fields)
                
                # Alternate between channel A and B
                channel = 'A' if i % 2 == 0 else 'B'
                sentence = f"AIVDM,1,1,,{channel},{payload},{fill}"
                cs = compute_checksum(sentence)
                full_sentence = f"!{sentence}*{cs}"
                
                update_status(f"Transmitting ship {i+1}/{len(SHIP_CONFIGS)}: {ship.name} (MMSI: {ship.mmsi})")
                
                # Transmit the AIS message
                transmit_signal(signal_preset, full_sentence, update_status)
                
                # Short delay between ships to avoid conflicts
                time.sleep(0.5)
            
            # Save the last move time
            last_move_time = current_time
            
            # Wait until next interval
            if ship_simulation_active:
                update_status(f"Waiting {interval} seconds until next transmission cycle...")
                time.sleep(interval)
    
    except Exception as e:
        update_status(f"Error in ship simulation: {e}")
    finally:
        ship_simulation_active = False
        update_status("Ship simulation stopped")

def start_ship_simulation():
    """Start the ship simulation in a background thread"""
    global simulation_thread, ship_simulation_active
    
    # Get selected AIS channel
    selected_index = sim_channel_var.get()
    signal_preset = SIGNAL_PRESETS[int(selected_index)]
    
    # Get simulation interval
    try:
        interval = float(sim_interval_var.get())
        if interval < 5:
            interval = 5  # Minimum 5 seconds to avoid hardware issues
    except:
        interval = 10  # Default 10 seconds
    
    # Get selected ships
    selected_indices = ship_listbox.curselection()
    if not selected_indices:
        messagebox.showerror("Error", "Please select at least one ship to simulate")
        return
    
    # Create a subset of ships to simulate
    global SHIP_CONFIGS
    active_ships = [SHIP_CONFIGS[i] for i in selected_indices]
    
    # Confirm with user
    if not messagebox.askyesno("Start Simulation", 
                             f"Start simulation of {len(active_ships)} ships?\n"
                             f"Transmitting on {signal_preset['name']} every {interval} seconds.\n\n"
                             "Ensure you have proper authorization to transmit on these frequencies."):
        return
    
    # Keep only selected ships for simulation
    SHIP_CONFIGS = active_ships
    
    # Update status
    sim_status_var.set("Simulation Active")
    start_sim_btn.config(state=tk.DISABLED)
    stop_sim_btn.config(state=tk.NORMAL)
    
    # Define update function for log
    def update_sim_log(msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        sim_log_text.configure(state='normal')
        sim_log_text.insert(tk.END, f"[{timestamp}] {msg}\n")
        sim_log_text.see(tk.END)
        sim_log_text.configure(state='disabled')
        sim_status_var.set(f"Simulation: {msg}")
    
    # Start simulation in a thread
    ship_simulation_active = True
    simulation_thread = threading.Thread(
        target=run_ship_simulation, 
        args=(signal_preset, interval, update_sim_log),
        daemon=True
    )
    simulation_thread.start()

def stop_ship_simulation():
    """Stop the ship simulation"""
    global ship_simulation_active
    ship_simulation_active = False
    
    sim_status_var.set("Simulation Stopped")
    start_sim_btn.config(state=tk.NORMAL)
    stop_sim_btn.config(state=tk.DISABLED)
    
    # Re-load all ship configurations
    load_ship_configs()
    update_ship_listbox()

def add_new_ship():
    """Add a new ship to the simulation"""
    # Create dialog window
    ship_dialog = tk.Toplevel(root)
    ship_dialog.title("Add New Ship")
    ship_dialog.geometry("400x500")  # Increased height to ensure buttons are visible
    ship_dialog.resizable(False, False)
    
    # Create form
    frame = ttk.Frame(ship_dialog, padding=10)
    frame.pack(fill=tk.BOTH, expand=True)
    
    # Ship details fields
    fields = [
        ("Name:", "ship_name", "Vessel 1"),
        ("MMSI:", "mmsi", "366000001"),
        ("Ship Type (0-99):", "ship_type", "70"),  # 70 = Cargo
        ("Length (m):", "length", "100"),
        ("Beam (m):", "beam", "20"),
        ("Latitude (°):", "lat", "40.7128"),
        ("Longitude (°):", "lon", "-74.0060"),
        ("Course (°):", "course", "90"),
        ("Speed (knots):", "speed", "8"),
        ("Nav Status (0-15):", "status", "0"),  # 0 = Under way using engine
        ("Rate of Turn:", "turn", "0"),
        ("Destination:", "dest", "NEW YORK")
    ]
    
    # Create variables and entry fields
    vars_dict = {}
    for i, (label_text, var_name, default) in enumerate(fields):
        ttk.Label(frame, text=label_text).grid(row=i, column=0, sticky=tk.W, pady=5)
        var = tk.StringVar(value=default)
        vars_dict[var_name] = var
        ttk.Entry(frame, textvariable=var).grid(row=i, column=1, sticky=(tk.W, tk.E), pady=5)
    
    def save_ship():
        try:
            # Validate inputs
            mmsi = int(vars_dict["mmsi"].get())
            if mmsi < 200000000 or mmsi > 999999999:
                raise ValueError("MMSI must be a 9-digit number")
                
            lat = float(vars_dict["lat"].get())
            if lat < -90 or lat > 90:
                raise ValueError("Latitude must be between -90 and 90")
                
            lon = float(vars_dict["lon"].get())
            if lon < -180 or lon > 180:
                raise ValueError("Longitude must be between -180 and 180")
            
            # Create new ship
            new_ship = AISShip(
                name=vars_dict["ship_name"].get(),
                mmsi=mmsi,
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
            
            # Add to configuration
            SHIP_CONFIGS.append(new_ship)
            
            # Update the ship list
            update_ship_listbox()
            
            # Save configurations
            save_ship_configs()
            
            ship_dialog.destroy()
            
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))
    
    # Buttons frame - put at the bottom of the dialog
    btn_frame = ttk.Frame(frame)
    btn_frame.grid(row=len(fields), column=0, columnspan=2, pady=10)
    
    # Make buttons larger and more visible
    save_button = ttk.Button(btn_frame, text="Save Ship", command=save_ship)
    save_button.pack(side=tk.LEFT, padx=10, pady=10)
    
    cancel_button = ttk.Button(btn_frame, text="Cancel", command=ship_dialog.destroy)
    cancel_button.pack(side=tk.LEFT, padx=10, pady=10)
    
    # Set column weights to make the form expandable
    frame.columnconfigure(1, weight=1)
    
    # Set focus to the first entry
    frame.grid_slaves(row=0, column=1)[0].focus_set()

def edit_selected_ship():
    """Edit the selected ship configuration"""
    selected = ship_listbox.curselection()
    if not selected:
        messagebox.showerror("Error", "Please select a ship to edit")
        return
    
    ship_index = selected[0]
    ship = SHIP_CONFIGS[ship_index]
    
    # Create dialog window
    ship_dialog = tk.Toplevel(root)
    ship_dialog.title(f"Edit Ship: {ship.name}")
    ship_dialog.geometry("400x450")
    ship_dialog.resizable(False, False)
    
    # Create form
    frame = ttk.Frame(ship_dialog, padding=10)
    frame.pack(fill=tk.BOTH, expand=True)
    
    # Ship details fields with current values
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
    
    # Create variables and entry fields
    vars_dict = {}
    for i, (label_text, var_name, default) in enumerate(fields):
        ttk.Label(frame, text=label_text).grid(row=i, column=0, sticky=tk.W, pady=5)
        var = tk.StringVar(value=default)
        vars_dict[var_name] = var
        ttk.Entry(frame, textvariable=var).grid(row=i, column=1, sticky=(tk.W, tk.E), pady=5)
    
    def update_ship():
        try:
            # Validate inputs
            mmsi = int(vars_dict["mmsi"].get())
            if mmsi < 200000000 or mmsi > 999999999:
                raise ValueError("MMSI must be a 9-digit number")
                
            lat = float(vars_dict["lat"].get())
            if lat < -90 or lat > 90:
                raise ValueError("Latitude must be between -90 and 90")
                
            lon = float(vars_dict["lon"].get())
            if lon < -180 or lon > 180:
                raise ValueError("Longitude must be between -180 and 180")
            
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
            
            # Update heading to match course
            ship.heading = round(ship.course)
            
            # Update the ship list
            update_ship_listbox()
            
            # Save configurations
            save_ship_configs()
            
            ship_dialog.destroy()
            
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))
    
    # Buttons
    btn_frame = ttk.Frame(frame)
    btn_frame.grid(row=len(fields), column=0, columnspan=2, pady=10)
    
    ttk.Button(btn_frame, text="Update Ship", command=update_ship).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Cancel", command=ship_dialog.destroy).pack(side=tk.LEFT, padx=5)

def delete_selected_ships():
    """Delete the selected ships from the configuration"""
    selected = ship_listbox.curselection()
    if not selected:
        messagebox.showerror("Error", "Please select ships to delete")
        return
    
    if messagebox.askyesno("Confirm Delete", 
                         f"Delete {len(selected)} selected ships?"):
        # Convert to list and sort in reverse to avoid index issues
        indices = sorted(list(selected), reverse=True)
        
        # Remove ships
        for idx in indices:
            del SHIP_CONFIGS[idx]
        
        # Update the list
        update_ship_listbox()
        
        # Save configurations
        save_ship_configs()

def update_ship_listbox():
    """Update the ship listbox with current configurations"""
    ship_listbox.delete(0, tk.END)
    
    for i, ship in enumerate(SHIP_CONFIGS):
        ship_listbox.insert(i, f"{ship.name} (MMSI: {ship.mmsi}) - {ship.speed} kts, {ship.course}°")

### GUI ###
# Initialize main Tkinter application window
root = tk.Tk()
root.title("AIS NMEA Generator & Multi-Signal Transmitter")
root.minsize(800, 600)

# Create main frame using grid layout manager
main_frame = ttk.Frame(root, padding=10)
main_frame.pack(fill=tk.BOTH, expand=True)

# Create a notebook for tabbed interface
notebook = ttk.Notebook(main_frame)
notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

# Tab 1: AIS Message Generator
ais_frame = ttk.Frame(notebook, padding=10)
notebook.add(ais_frame, text="AIS Message Generator")

# Left side - Input parameters
input_frame = ttk.LabelFrame(ais_frame, text="Message Parameters", padding=10)
input_frame.grid(row=0, column=0, sticky=(tk.N, tk.W, tk.E, tk.S), padx=5, pady=5)

# Create input fields with labels
labels = ["Message Type", "Repeat", "MMSI", "Nav Status",
          "ROT (-127..127)", "SOG (knots)", "Accuracy (0/1)",
          "Longitude (°)", "Latitude (°)", "COG (°)",
          "Heading (°)", "Timestamp (s)"]
vars_ = []  # Store all input variables
for i, lbl in enumerate(labels):
    ttk.Label(input_frame, text=lbl).grid(column=0, row=i, sticky=tk.W, padx=5, pady=2)
    var = tk.StringVar(value="0")  # Default value
    entry = ttk.Entry(input_frame, textvariable=var, width=15)
    entry.grid(column=1, row=i, sticky=tk.W, padx=5, pady=2)
    vars_.append(var)

# Assign variables to meaningful names for easier reference
(msg_type_var, repeat_var, mmsi_var, nav_status_var,
 rot_var, sog_var, acc_var, lon_var,
 lat_var, cog_var, hdg_var, ts_var) = vars_

# Set default values for common fields
msg_type_var.set("1")         # Position Report
repeat_var.set("0")
mmsi_var.set("366123456")     # Example US vessel MMSI
nav_status_var.set("0")       # Under way using engine
lon_var.set("-74.0060")       # Example coordinates (New York)
lat_var.set("40.7128")        # New York
sog_var.set("10.0")           # 10 knots
cog_var.set("90.0")           # Due East

# Generate button
gen_btn = ttk.Button(input_frame, text="Generate Message", command=generate)
gen_btn.grid(column=0, row=len(labels)+1, columnspan=2, pady=10)

# Right side - Output and controls
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

# Initially select the first item
signal_listbox.selection_set(0)

# Button to edit signal preset
edit_btn = ttk.Button(output_frame, text="Edit Signal Settings", command=edit_signal_preset)
edit_btn.grid(column=0, row=7, sticky=tk.W, pady=5)

# Transmit button (disabled if LimeSDR not available)
tx_btn = ttk.Button(output_frame, text="Transmit Message", command=transmit)
tx_btn.grid(column=0, row=8, sticky=(tk.W, tk.E), pady=10)
if not SDR_AVAILABLE:
    tx_btn.config(state="disabled")  # Disable if SDR library not available

# Tab 2: Transmission Log
log_frame = ttk.Frame(notebook, padding=10)
notebook.add(log_frame, text="Transmission Log")

# Text area for logs
log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, width=80, height=20)
log_text.pack(fill=tk.BOTH, expand=True)
log_text.configure(state='disabled')  # Make it read-only

# Status bar at the bottom
status_var = tk.StringVar()
status_var.set("Ready" if SDR_AVAILABLE else "LimeSDR support not available")
status_bar = ttk.Label(main_frame, textvariable=status_var, relief=tk.SUNKEN, anchor=tk.W)
status_bar.pack(side=tk.BOTTOM, fill=tk.X)

# Tab 3: Multi-Signal Transmission
multi_frame = ttk.Frame(notebook, padding=10)
notebook.add(multi_frame, text="Multi-Signal Transmission")

# Split into two columns
left_frame = ttk.Frame(multi_frame)
left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

right_frame = ttk.Frame(multi_frame)
right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)

# Signal selection list with checkboxes on the left
signal_list_frame = ttk.LabelFrame(left_frame, text="Available Signals", padding=10)
signal_list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

# Scrollable listbox for multiple signal selection
multi_signal_listbox = tk.Listbox(signal_list_frame, height=15, selectmode=tk.MULTIPLE)
multi_signal_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# Add scroll bar
multi_scrollbar = ttk.Scrollbar(signal_list_frame, orient="vertical", command=multi_signal_listbox.yview)
multi_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
multi_signal_listbox.configure(yscrollcommand=multi_scrollbar.set)

# Populate the multi-signal listbox
for i, preset in enumerate(SIGNAL_PRESETS):
    multi_signal_listbox.insert(i, f"{preset['name']} ({preset['freq']/1e6} MHz)")

# Control buttons underneath the listbox
control_frame = ttk.Frame(left_frame)
control_frame.pack(fill=tk.X, pady=10)

# Test single signal button
test_btn = ttk.Button(control_frame, text="Test Selected Signal", command=test_signal)
test_btn.pack(side=tk.LEFT, padx=5)

# Transmit all selected signals button
multi_tx_btn = ttk.Button(control_frame, text="Transmit Selected Signals", command=transmit_multiple_signals)
multi_tx_btn.pack(side=tk.LEFT, padx=5)
if not SDR_AVAILABLE:
    test_btn.config(state="disabled")
    multi_tx_btn.config(state="disabled")

# Transmission settings on the right
settings_frame = ttk.LabelFrame(right_frame, text="Transmission Settings", padding=10)
settings_frame.pack(fill=tk.BOTH, expand=True, pady=5)

# Sequential vs Simultaneous option
tx_mode_var = tk.StringVar(value="sequential")
ttk.Radiobutton(settings_frame, text="Sequential Transmission", 
                variable=tx_mode_var, value="sequential").pack(anchor=tk.W, pady=5)
ttk.Radiobutton(settings_frame, text="Simultaneous Transmission (Experimental)", 
                variable=tx_mode_var, value="simultaneous").pack(anchor=tk.W, pady=5)

# Delay between transmissions
ttk.Label(settings_frame, text="Delay between signals (seconds):").pack(anchor=tk.W, pady=(10,5))
delay_var = tk.StringVar(value="0.5")
ttk.Entry(settings_frame, textvariable=delay_var, width=5).pack(anchor=tk.W)

# Warning label
ttk.Label(settings_frame, text="WARNING:", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(20,5))
warning_text = """
Transmitting multiple signals, especially simultaneously, may:
1. Cause hardware issues with some SDR devices
2. Create interference on multiple frequencies
3. Potentially violate radio regulations

Always ensure you have proper authorization before transmitting.
"""
warning_label = ttk.Label(settings_frame, text=warning_text, wraplength=300)
warning_label.pack(anchor=tk.W)

# Status indicator for multi-transmission
multi_status_frame = ttk.LabelFrame(right_frame, text="Transmission Status", padding=10)
multi_status_frame.pack(fill=tk.X, pady=5)

multi_status_var = tk.StringVar(value="Ready")
multi_status_label = ttk.Label(multi_status_frame, textvariable=multi_status_var)
multi_status_label.pack(fill=tk.X)

# Progress indicator
progress_var = tk.DoubleVar(value=0.0)
progress = ttk.Progressbar(multi_status_frame, variable=progress_var, maximum=100)
progress.pack(fill=tk.X, pady=5)

# Stop button
stop_btn = ttk.Button(multi_status_frame, text="Stop All Transmissions", 
                     command=lambda: transmission_queue.queue.clear())
stop_btn.pack(pady=5)

# Tab 4: Ship Simulation
sim_frame = ttk.Frame(notebook, padding=10)
notebook.add(sim_frame, text="Ship Simulation")

# Left side - Ship list and controls
ship_list_frame = ttk.LabelFrame(sim_frame, text="Ships", padding=10)
ship_list_frame.grid(row=0, column=0, sticky=(tk.N, tk.W, tk.E, tk.S), padx=5, pady=5)

# Listbox for ship selection
ship_listbox = tk.Listbox(ship_list_frame, height=15, selectmode=tk.MULTIPLE)
ship_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# Add scroll bar
ship_scrollbar = ttk.Scrollbar(ship_list_frame, orient="vertical", command=ship_listbox.yview)
ship_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
ship_listbox.configure(yscrollcommand=ship_scrollbar.set)

# Populate the ship listbox
load_ship_configs()
update_ship_listbox()

# Control buttons underneath the listbox
ship_control_frame = ttk.Frame(ship_list_frame)
ship_control_frame.pack(fill=tk.X, pady=10)

# Add new ship button
add_ship_btn = ttk.Button(ship_control_frame, text="Add New Ship", command=add_new_ship)
add_ship_btn.pack(side=tk.LEFT, padx=5)

# Edit selected ship button
edit_ship_btn = ttk.Button(ship_control_frame, text="Edit Selected Ship", command=edit_selected_ship)
edit_ship_btn.pack(side=tk.LEFT, padx=5)

# Delete selected ships button
delete_ship_btn = ttk.Button(ship_control_frame, text="Delete Selected Ships", command=delete_selected_ships)
delete_ship_btn.pack(side=tk.LEFT, padx=5)

# Right side - Simulation controls and log
sim_control_frame = ttk.LabelFrame(sim_frame, text="Simulation Controls", padding=10)
sim_control_frame.grid(row=0, column=1, sticky=(tk.N, tk.W, tk.E, tk.S), padx=5, pady=5)

# AIS channel selection
ttk.Label(sim_control_frame, text="AIS Channel:").grid(row=0, column=0, sticky=tk.W, pady=5)
sim_channel_var = tk.StringVar(value="0")
ttk.Combobox(sim_control_frame, textvariable=sim_channel_var, values=["0", "1"]).grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5)

# Simulation interval
ttk.Label(sim_control_frame, text="Interval (seconds):").grid(row=1, column=0, sticky=tk.W, pady=5)
sim_interval_var = tk.StringVar(value="10")
ttk.Entry(sim_control_frame, textvariable=sim_interval_var, width=5).grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5)

# Start simulation button
start_sim_btn = ttk.Button(sim_control_frame, text="Start Simulation", command=start_ship_simulation)
start_sim_btn.grid(row=2, column=0, columnspan=2, pady=10)

# Stop simulation button
stop_sim_btn = ttk.Button(sim_control_frame, text="Stop Simulation", command=stop_ship_simulation)
stop_sim_btn.grid(row=3, column=0, columnspan=2, pady=10)
stop_sim_btn.config(state=tk.DISABLED)

# Simulation log
sim_log_frame = ttk.LabelFrame(sim_control_frame, text="Simulation Log", padding=10)
sim_log_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)

# Text area for simulation logs
sim_log_text = scrolledtext.ScrolledText(sim_log_frame, wrap=tk.WORD, width=40, height=10)
sim_log_text.pack(fill=tk.BOTH, expand=True)
sim_log_text.configure(state='disabled')  # Make it read-only

# Status indicator for simulation
sim_status_var = tk.StringVar(value="Ready")
sim_status_label = ttk.Label(sim_control_frame, textvariable=sim_status_var)
sim_status_label.grid(row=5, column=0, columnspan=2, pady=5)

# Start the GUI event loop
root.mainloop()
