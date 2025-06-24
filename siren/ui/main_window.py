"""
Main Window - Primary UI Implementation
======================================

This module contains the main GUI window and all its components.
Extracted from the original monolithic implementation.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
from datetime import datetime

# Import modules from our package
from ..protocol.ais_encoding import build_ais_payload, compute_checksum
from ..ships.ship_manager import get_ship_configs, update_ship_listbox_callback
from ..transmission.sdr_controller import transmit_signal, get_signal_presets
from ..simulation.simulation_controller import start_simulation, stop_simulation
from ..config.settings import check_dependencies

class AISMainWindow:
    """Main application window"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SIREN: Spoofed Identification & Real-time Emulation Node")
        self.root.minsize(800, 600)
        
        # Check dependencies
        self.sdr_available, self.map_available, self.pil_available = check_dependencies()
        
        # Initialize UI components
        self.setup_ui()
        self.setup_callbacks()
        
        # Center window
        self.center_window()
        
    def setup_ui(self):
        """Setup the main UI structure"""
        # Main frame with better padding for fullscreen
        self.main_frame = ttk.Frame(self.root, padding=20)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Create tabbed interface with larger font
        style = ttk.Style()
        style.configure('TNotebook.Tab', padding=[20, 10])
        style.configure('TNotebook', tabposition='n')
        
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create tabs
        self.setup_ais_generator_tab()
        self.setup_transmission_log_tab()
        self.setup_ship_simulation_tab()
        self.setup_map_visualization_tab()
        
        # Status bar with better styling
        self.status_var = tk.StringVar()
        self.status_var.set("Ready" if self.sdr_available else "SDR support not available")
        status_frame = ttk.Frame(self.main_frame)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        
        ttk.Label(status_frame, textvariable=self.status_var, 
                 relief=tk.SUNKEN, anchor=tk.W, font=('Arial', 11),
                 padding=(10, 5)).pack(side=tk.LEFT, fill=tk.X, expand=True)

    def setup_ais_generator_tab(self):
        """Setup the AIS message generator tab"""
        # ----- Tab 1: AIS Message Generator -----
        ais_frame = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(ais_frame, text="AIS Generator")

        # Configure grid weights for better scaling
        ais_frame.columnconfigure(0, weight=1)
        ais_frame.columnconfigure(1, weight=1) 
        ais_frame.columnconfigure(2, weight=1)
        ais_frame.rowconfigure(0, weight=1)

        # Left side - Input parameters
        input_frame = ttk.LabelFrame(ais_frame, text="Message Parameters", padding=15)
        input_frame.grid(row=0, column=0, sticky=(tk.N, tk.W, tk.E, tk.S), padx=10, pady=10)

        # Create input fields with better fonts
        labels = ["Message Type", "Repeat", "MMSI", "Nav Status",
                  "ROT (-127..127)", "SOG (knots)", "Accuracy (0/1)",
                  "Longitude (°)", "Latitude (°)", "COG (°)",
                  "Heading (°)", "Timestamp (s)"]
        self.vars_ = []
        for i, lbl in enumerate(labels):
            ttk.Label(input_frame, text=lbl, font=('Arial', 11)).grid(column=0, row=i, sticky=tk.W, padx=8, pady=4)
            var = tk.StringVar(value="0")
            entry = ttk.Entry(input_frame, textvariable=var, width=18, font=('Arial', 11))
            entry.grid(column=1, row=i, sticky=tk.W, padx=8, pady=4)
            self.vars_.append(var)

        # Assign variables
        (self.msg_type_var, self.repeat_var, self.mmsi_var, self.nav_status_var,
         self.rot_var, self.sog_var, self.acc_var, self.lon_var,
         self.lat_var, self.cog_var, self.hdg_var, self.ts_var) = self.vars_

        # Default values
        self.msg_type_var.set("1")
        self.repeat_var.set("0")
        self.mmsi_var.set("366123456")
        self.nav_status_var.set("0")
        self.lon_var.set("-74.0060")
        self.lat_var.set("40.7128")
        self.sog_var.set("10.0")
        self.cog_var.set("90.0")

        # Generate button with better styling
        gen_btn = ttk.Button(input_frame, text="Generate Message", command=self.generate)
        gen_btn.grid(column=0, row=len(labels)+1, columnspan=2, pady=15, ipadx=15, ipady=8)

        # Right side - Output
        output_frame = ttk.LabelFrame(ais_frame, text="Message Output", padding=15)
        output_frame.grid(row=0, column=1, sticky=(tk.N, tk.W, tk.E, tk.S), padx=10, pady=10)

        # Configure column weights
        output_frame.columnconfigure(0, weight=1)

        # Output fields with better styling
        ttk.Label(output_frame, text="AIS Payload:", font=('Arial', 11, 'bold')).grid(column=0, row=0, sticky=tk.W, pady=8)
        self.payload_var = tk.StringVar()
        ttk.Entry(output_frame, textvariable=self.payload_var, width=50, font=('Consolas', 10)).grid(column=0, row=1, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(output_frame, text="Fill Bits:", font=('Arial', 11, 'bold')).grid(column=0, row=2, sticky=tk.W, pady=8)
        self.fill_var = tk.StringVar()
        ttk.Entry(output_frame, textvariable=self.fill_var, width=8, font=('Arial', 11)).grid(column=0, row=3, sticky=tk.W, pady=(0, 10))

        ttk.Label(output_frame, text="NMEA Sentence:", font=('Arial', 11, 'bold')).grid(column=0, row=4, sticky=tk.W, pady=8)
        self.nmea_var = tk.StringVar()
        ttk.Entry(output_frame, textvariable=self.nmea_var, width=70, font=('Consolas', 10)).grid(column=0, row=5, sticky=(tk.W, tk.E), pady=(0, 15))

        # Signal selection with better styling
        signal_frame = ttk.LabelFrame(output_frame, text="Transmission Signal", padding=12)
        signal_frame.grid(column=0, row=6, sticky=(tk.W, tk.E), pady=15)

        # Listbox for signal selection with better font
        self.signal_listbox = tk.Listbox(signal_frame, height=6, font=('Arial', 11))
        self.signal_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Add scroll bar
        scrollbar = ttk.Scrollbar(signal_frame, orient="vertical", command=self.signal_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.signal_listbox.configure(yscrollcommand=scrollbar.set)

        # Populate the signal listbox with enhanced presets
        signal_presets = get_signal_presets()
        for i, preset in enumerate(signal_presets):
            mode_info = f" ({preset.get('mode', 'legacy')})" if 'mode' in preset else ""
            self.signal_listbox.insert(i, f"{preset['name']} ({preset['freq']/1e6} MHz){mode_info}")
        self.signal_listbox.selection_set(0)

        # Edit signal button with better styling
        edit_btn = ttk.Button(output_frame, text="Edit Signal Settings", command=self.edit_signal_preset)
        edit_btn.grid(column=0, row=7, sticky=tk.W, pady=12, ipadx=10, ipady=5)

        # Transmit button with better styling
        tx_btn = ttk.Button(output_frame, text="Transmit Message", command=self.transmit)
        tx_btn.grid(column=0, row=8, sticky=(tk.W, tk.E), pady=15, ipadx=15, ipady=8)
        if not self.sdr_available:
            tx_btn.config(state="disabled")

        # --- AIS Message Type Reference Panel with better sizing ---
        ais_type_frame = ttk.LabelFrame(ais_frame, text="AIS Message Types Reference", padding=15)
        ais_type_frame.grid(row=0, column=2, sticky=(tk.N, tk.W, tk.E, tk.S), padx=10, pady=10)

        ais_type_text = tk.Text(ais_type_frame, width=45, height=30, wrap=tk.WORD, font=('Arial', 10))
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

    def setup_transmission_log_tab(self):
        """Setup the transmission log tab"""
        # ----- Tab 2: Transmission Log -----
        log_frame = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(log_frame, text="Transmission Log")

        # Text area for logs with better font and sizing
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, width=120, height=35, font=('Consolas', 11))
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.log_text.configure(state='disabled')

    def setup_ship_simulation_tab(self):
        """Setup the ship simulation tab"""
        # ----- Tab 3: Ship Simulation -----
        sim_frame = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(sim_frame, text="Ship Simulation")

        # Configure grid weights for better scaling
        sim_frame.columnconfigure(0, weight=2)  # Ship list gets more space
        sim_frame.columnconfigure(1, weight=3)  # Simulation controls get even more space
        sim_frame.rowconfigure(0, weight=1)

        # Left side - Ship list (wider and taller)
        ship_list_frame = ttk.LabelFrame(sim_frame, text="Ships", padding=15)
        ship_list_frame.grid(row=0, column=0, sticky=(tk.N, tk.W, tk.E, tk.S), padx=10, pady=10)

        # Ship selection listbox with better sizing
        self.ship_listbox = tk.Listbox(ship_list_frame, height=25, selectmode=tk.MULTIPLE, font=('Arial', 12))
        self.ship_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Add scroll bar
        ship_scrollbar = ttk.Scrollbar(ship_list_frame, orient="vertical", command=self.ship_listbox.yview)
        ship_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.ship_listbox.configure(yscrollcommand=ship_scrollbar.set)

        # Ship control buttons with better styling
        ship_control_frame = ttk.Frame(ship_list_frame)
        ship_control_frame.pack(fill=tk.X, pady=15)

        # Add/Edit/Delete buttons with larger size
        add_ship_btn = ttk.Button(ship_control_frame, text="Add Ship", command=self.add_new_ship)
        add_ship_btn.pack(side=tk.LEFT, padx=8, pady=5, ipadx=10, ipady=5)

        edit_ship_btn = ttk.Button(ship_control_frame, text="Edit Ship", command=self.edit_selected_ship)
        edit_ship_btn.pack(side=tk.LEFT, padx=8, pady=5, ipadx=10, ipady=5)

        delete_ship_btn = ttk.Button(ship_control_frame, text="Delete Ship", command=self.delete_selected_ships)
        delete_ship_btn.pack(side=tk.LEFT, padx=8, pady=5, ipadx=10, ipady=5)

        # Right side - Simulation controls (larger and better organized)
        sim_control_frame = ttk.LabelFrame(sim_frame, text="Simulation Controls", padding=20)
        sim_control_frame.grid(row=0, column=1, sticky=(tk.N, tk.W, tk.E, tk.S), padx=10, pady=10)

        # Configure internal grid
        sim_control_frame.columnconfigure(1, weight=1)

        # Channel selection with larger fonts
        ttk.Label(sim_control_frame, text="AIS Channel:", font=('Arial', 12)).grid(row=0, column=0, sticky=tk.W, pady=8)
        self.sim_channel_var = tk.StringVar(value="0")
        channel_combo = ttk.Combobox(sim_control_frame, textvariable=self.sim_channel_var, 
                     values=["0", "1"], font=('Arial', 12))
        channel_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=8, padx=(10, 0))

        # Interval setting
        ttk.Label(sim_control_frame, text="Interval (seconds):", font=('Arial', 12)).grid(row=1, column=0, sticky=tk.W, pady=8)
        self.sim_interval_var = tk.StringVar(value="10")
        interval_entry = ttk.Entry(sim_control_frame, textvariable=self.sim_interval_var, font=('Arial', 12))
        interval_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=8, padx=(10, 0))

        # Production mode toggle
        ttk.Label(sim_control_frame, text="Transmission Mode:", font=('Arial', 12)).grid(row=2, column=0, sticky=tk.W, pady=8)
        self.production_mode_var = tk.BooleanVar(value=True)  # Default to production mode
        production_check = ttk.Checkbutton(sim_control_frame, text="Production Mode (ITU-R M.1371-5)", 
                                         variable=self.production_mode_var, command=self.toggle_production_mode)
        production_check.grid(row=2, column=1, sticky=tk.W, pady=8, padx=(10, 0))

        # Continuous transmission toggle
        ttk.Label(sim_control_frame, text="Transmission Type:", font=('Arial', 12)).grid(row=3, column=0, sticky=tk.W, pady=8)
        self.continuous_mode_var = tk.BooleanVar(value=False)
        continuous_check = ttk.Checkbutton(sim_control_frame, text="Continuous Transmission (SOTDMA)", 
                                         variable=self.continuous_mode_var)
        continuous_check.grid(row=3, column=1, sticky=tk.W, pady=8, padx=(10, 0))

        # Start/Stop buttons with better styling
        self.start_sim_btn = ttk.Button(sim_control_frame, text="Start Simulation", command=self.start_ship_simulation)
        self.start_sim_btn.grid(row=4, column=0, columnspan=2, pady=15, ipadx=20, ipady=8, sticky=(tk.W, tk.E))

        self.stop_sim_btn = ttk.Button(sim_control_frame, text="Stop Simulation", command=self.stop_ship_simulation)
        self.stop_sim_btn.grid(row=5, column=0, columnspan=2, pady=10, ipadx=20, ipady=8, sticky=(tk.W, tk.E))
        self.stop_sim_btn.config(state=tk.DISABLED)

        # Transmission status display
        status_info_frame = ttk.LabelFrame(sim_control_frame, text="Transmission Status", padding=10)
        status_info_frame.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        self.tx_status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(status_info_frame, textvariable=self.tx_status_var, font=('Arial', 11))
        status_label.pack()

        # Simulation log with better sizing
        sim_log_frame = ttk.LabelFrame(sim_control_frame, text="Simulation Log", padding=15)
        sim_log_frame.grid(row=7, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=15)

        self.sim_log_text = scrolledtext.ScrolledText(sim_log_frame, wrap=tk.WORD, width=50, height=12, font=('Consolas', 11))
        self.sim_log_text.pack(fill=tk.BOTH, expand=True)
        self.sim_log_text.configure(state='disabled')

        # Status indicator with larger font
        self.sim_status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(sim_control_frame, textvariable=self.sim_status_var, font=('Arial', 12, 'bold'))
        status_label.grid(row=8, column=0, columnspan=2, pady=10)

        # Update ship listbox initially
        self.update_ship_listbox()

    def setup_map_visualization_tab(self):
        """Setup the map visualization tab"""
        map_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(map_frame, text="Map View")
        
        # Create the complete map visualization
        from ..map.visualization import get_map_visualization
        self.map_visualization = get_map_visualization(
            map_frame, 
            map_available=self.map_available, 
            pil_available=self.pil_available
        )

    def setup_callbacks(self):
        """Setup callback functions"""
        # Set up the ship listbox update callback
        update_ship_listbox_callback(self.update_ship_display)

    def update_ship_display(self, ships):
        """Update ship display - callback from ship manager"""
        # This will be called when ships are updated
        pass

    def center_window(self):
        """Launch the window in fullscreen mode"""
        # Set the window to fullscreen
        self.root.attributes('-fullscreen', True)
        
        # Add a title bar with exit button since we're in fullscreen
        title_frame = ttk.Frame(self.root, style='Title.TFrame')
        title_frame.pack(side=tk.TOP, fill=tk.X)
        
        # Application title
        ttk.Label(title_frame, text="SIREN: Spoofed Identification & Real-time Emulation Node", 
                 font=('Arial', 14, 'bold'), foreground='white', background='#2C3E50').pack(side=tk.LEFT, padx=20, pady=8)
        
        # Exit fullscreen button
        ttk.Button(title_frame, text="Exit Fullscreen (or press ESC)", 
                  command=lambda: self.root.attributes('-fullscreen', False)).pack(side=tk.RIGHT, padx=20, pady=8)
        
        # Configure title frame style
        style = ttk.Style()
        style.configure('Title.TFrame', background='#2C3E50')
        
        # Allow Escape key to exit fullscreen
        self.root.bind('<Escape>', lambda e: self.root.attributes('-fullscreen', False))
        
        # Also allow F11 to toggle fullscreen
        self.root.bind('<F11>', lambda e: self.root.attributes('-fullscreen', not self.root.attributes('-fullscreen')))

    def generate(self):
        """Generate AIS message from GUI input fields"""
        try:
            # Collect field values
            fields = {
                'msg_type': int(self.msg_type_var.get()),
                'repeat': int(self.repeat_var.get()),
                'mmsi': int(self.mmsi_var.get()),
                'nav_status': int(self.nav_status_var.get()),
                'rot': int(self.rot_var.get()),
                'sog': float(self.sog_var.get()),
                'accuracy': int(self.acc_var.get()),
                'lon': float(self.lon_var.get()),
                'lat': float(self.lat_var.get()),
                'cog': float(self.cog_var.get()),
                'hdg': int(self.hdg_var.get()),
                'timestamp': int(self.ts_var.get())
            }
            
            # Build payload
            payload, fill = build_ais_payload(fields)
            self.payload_var.set(payload)
            self.fill_var.set(str(fill))
            
            # Create NMEA sentence
            channel = 'A'
            sentence = f"AIVDM,1,1,,{channel},{payload},{fill}"
            cs = compute_checksum(sentence)
            full_sentence = f"!{sentence}*{cs}"
            self.nmea_var.set(full_sentence)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def transmit(self):
        """Transmit generated AIS message"""
        nmea_sentence = self.nmea_var.get()
        if not nmea_sentence:
            messagebox.showerror("Error", "Generate an AIS message first")
            return
        
        # Get selected signal preset
        selected_index = self.signal_listbox.curselection()
        if not selected_index:
            messagebox.showerror("Error", "Select a signal type")
            return
        
        signal_presets = get_signal_presets()
        selected_preset = signal_presets[selected_index[0]]
        
        # Confirm transmission
        if messagebox.askyesno("Transmit", 
                              f"Transmit AIS message using {selected_preset['name']}?\n"
                              f"Frequency: {selected_preset['freq']/1e6} MHz\n\n"
                              "Ensure you have proper authorization to transmit."):
            
            # Update function for log
            def update_log(msg):
                self.log_text.configure(state='normal')
                self.log_text.insert(tk.END, f"{msg}\n")
                self.log_text.see(tk.END)
                self.log_text.configure(state='disabled')
                self.status_var.set(f"Last action: {msg}")
            
            # Start transmission thread
            threading.Thread(
                target=transmit_signal, 
                args=(selected_preset, nmea_sentence, update_log),
                daemon=True
            ).start()

    def edit_signal_preset(self):
        """Edit a signal preset"""
        # Placeholder - will be implemented in the transmission module
        messagebox.showinfo("Info", "Signal preset editing will be implemented in the transmission module")

    def run(self):
        """Start the main application loop"""
        try:
            # Set default tab
            self.notebook.select(2)  # Ship Simulation tab
            
            # Start the main loop
            self.root.mainloop()
        except KeyboardInterrupt:
            print("Program terminated.")
        finally:
            # Cleanup if needed
            stop_simulation()

    def update_ship_listbox(self):
        """Update the ship listbox with current configurations"""
        if hasattr(self, 'ship_listbox'):
            self.ship_listbox.delete(0, tk.END)
            
            ship_configs = get_ship_configs()
            for i, ship in enumerate(ship_configs):
                self.ship_listbox.insert(i, f"{ship.name} (MMSI: {ship.mmsi}) - {ship.speed} kts, {ship.course}°")

    def add_new_ship(self):
        """Add a new ship to the simulation"""
        from .ship_dialogs import add_ship_dialog
        add_ship_dialog(self.root)

    def edit_selected_ship(self):
        """Edit an existing ship"""
        selected = self.ship_listbox.curselection()
        if not selected:
            messagebox.showerror("Error", "Select a ship to edit")
            return
        
        from ..ships.ship_manager import get_ship_manager
        from .ship_dialogs import edit_ship_dialog
        
        ship_manager = get_ship_manager()
        ships = ship_manager.get_ships()
        if selected[0] < len(ships):
            ship = ships[selected[0]]
            edit_ship_dialog(self.root, ship)

    def delete_selected_ships(self):
        """Delete selected ships from the configuration"""
        selected = self.ship_listbox.curselection()
        if not selected:
            messagebox.showerror("Error", "Select ship(s) to delete")
            return
        
        # Confirm deletion
        if messagebox.askyesno("Confirm Delete", 
                              f"Delete {len(selected)} selected ship(s)?"):
            from ..ships.ship_manager import get_ship_manager
            ship_manager = get_ship_manager()
            
            # Delete in reverse order to avoid index shifts
            for index in sorted(selected, reverse=True):
                ship_manager.remove_ship_by_index(index)
            
            ship_manager.save_configs()
            self.update_ship_display()
    
    def update_ship_display(self):
        """Update the ship display in the UI"""
        # Clear current listbox
        self.ship_listbox.delete(0, tk.END)
        
        # Reload and display ships
        from ..ships.ship_manager import get_ship_manager
        ship_manager = get_ship_manager()
        ships = ship_manager.get_ships()
        
        for i, ship in enumerate(ships):
            self.ship_listbox.insert(i, f"{ship.name} (MMSI: {ship.mmsi}) - {ship.speed} kts, {ship.course}°")
        
        # Update map if available
        if hasattr(self, 'map_visualization') and self.map_visualization:
            self.map_visualization.update_map(force=True)

    def start_ship_simulation(self):
        """Start the ship simulation with production or legacy transmission"""
        # Get simulation parameters
        channel_idx = int(self.sim_channel_var.get())
        signal_presets = get_signal_presets()
        if channel_idx < 0 or channel_idx >= len(signal_presets):
            messagebox.showerror("Error", "Invalid channel selection")
            return

        try:
            interval = int(self.sim_interval_var.get())
            if interval < 1:
                raise ValueError("Interval must be at least 1 second")
        except ValueError as e:
            messagebox.showerror("Invalid Interval", str(e))
            return

        # Get selected signal preset
        signal_preset = signal_presets[channel_idx]
        
        # Check production mode availability
        from ..transmission.production_transmitter import is_production_mode_available
        if self.production_mode_var.get() and not is_production_mode_available():
            if messagebox.askyesno("Production Mode Unavailable", 
                                   "Production mode requires SoapySDR but it's not available.\n"
                                   "Would you like to continue with legacy mode?"):
                self.production_mode_var.set(False)
                self.toggle_production_mode()
            else:
                return
        
        # Update UI
        mode_text = "Production" if self.production_mode_var.get() else "Legacy"
        continuous_text = " (Continuous)" if self.continuous_mode_var.get() else ""
        self.sim_status_var.set(f"Running {mode_text} Mode{continuous_text}")
        self.start_sim_btn.config(state=tk.DISABLED)
        self.stop_sim_btn.config(state=tk.DISABLED)
        
        # Clear log
        self.sim_log_text.configure(state='normal')
        self.sim_log_text.delete(1.0, tk.END)
        self.sim_log_text.configure(state='disabled')
        
        # Update log function
        def update_sim_log(msg):
            self.sim_log_text.configure(state='normal')
            self.sim_log_text.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')}: {msg}\n")
            self.sim_log_text.see(tk.END)
            self.sim_log_text.configure(state='disabled')
            # Also update transmission status
            self.root.after(100, self.update_transmission_status)
        
        # Start simulation
        from ..simulation.simulation_controller import start_simulation
        
        # Get selected ship indices
        selected_indices = list(self.ship_listbox.curselection())
        if not selected_indices:
            messagebox.showwarning("No Ships Selected", "Please select at least one ship to simulate.")
            self.stop_ship_simulation()
            return
        
        # Use continuous mode if selected and in production mode
        continuous = self.continuous_mode_var.get() and self.production_mode_var.get()
        
        if start_simulation(signal_preset, interval, update_sim_log, selected_indices, continuous):
            update_sim_log(f"Simulation started in {mode_text} mode{continuous_text}")
            self.stop_sim_btn.config(state=tk.NORMAL)
            
            # Start map updates if map is available and set selected ships
            if hasattr(self, 'map_visualization') and self.map_visualization:
                self.map_visualization.set_selected_ships(selected_indices)
                self.map_visualization.start_real_time_updates()
                
            # Start periodic status updates
            self.start_status_updates()
        else:
            messagebox.showerror("Error", "Failed to start simulation")
            self.stop_ship_simulation()
    
    def start_status_updates(self):
        """Start periodic transmission status updates"""
        self.update_transmission_status()
        # Schedule next update in 5 seconds if simulation is still running
        if self.stop_sim_btn['state'] == tk.NORMAL:
            self.root.after(5000, self.start_status_updates)

    def stop_ship_simulation(self):
        """Stop the ship simulation"""
        from ..simulation.simulation_controller import stop_simulation
        stop_simulation()
        
        # Stop map updates and reset to show all ships
        if hasattr(self, 'map_visualization') and self.map_visualization:
            self.map_visualization.stop_real_time_updates()
            self.map_visualization.set_selected_ships(None)  # Show all ships
        
        self.sim_status_var.set("Simulation Stopped")
        self.start_sim_btn.config(state=tk.NORMAL)
        self.stop_sim_btn.config(state=tk.DISABLED)

    def toggle_production_mode(self):
        """Toggle between production and legacy transmission modes"""
        from ..simulation.simulation_controller import set_production_transmission
        enabled = self.production_mode_var.get()
        set_production_transmission(enabled)
        
        mode_text = "Production Mode (ITU-R M.1371-5)" if enabled else "Legacy Mode"
        self.tx_status_var.set(f"Mode: {mode_text}")
        
        # Update continuous mode availability
        if not enabled:
            self.continuous_mode_var.set(False)  # Disable continuous mode for legacy

    def update_transmission_status(self):
        """Update transmission status display"""
        try:
            from ..simulation.simulation_controller import get_simulation_transmission_status
            status = get_simulation_transmission_status()
            
            if status.get('running', False):
                packets = status.get('packets_sent', 0)
                mode = status.get('mode', 'unknown')
                self.tx_status_var.set(f"Active: {packets} packets sent ({mode} mode)")
            else:
                mode_text = "Production" if self.production_mode_var.get() else "Legacy"
                self.tx_status_var.set(f"Ready ({mode_text} mode)")
                
        except Exception as e:
            self.tx_status_var.set(f"Status error: {str(e)}")
