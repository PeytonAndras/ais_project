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
from ..ships.ship_manager import get_ship_configs, update_ship_listbox_callback
from ..transmission.sdr_controller import get_signal_presets
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

        # Start/Stop buttons with better styling
        self.start_sim_btn = ttk.Button(sim_control_frame, text="Start Simulation", command=self.start_ship_simulation)
        self.start_sim_btn.grid(row=2, column=0, columnspan=2, pady=15, ipadx=20, ipady=8, sticky=(tk.W, tk.E))

        self.stop_sim_btn = ttk.Button(sim_control_frame, text="Stop Simulation", command=self.stop_ship_simulation)
        self.stop_sim_btn.grid(row=3, column=0, columnspan=2, pady=10, ipadx=20, ipady=8, sticky=(tk.W, tk.E))
        self.stop_sim_btn.config(state=tk.DISABLED)

        # Simulation log with better sizing
        sim_log_frame = ttk.LabelFrame(sim_control_frame, text="Simulation Log", padding=15)
        sim_log_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=15)

        self.sim_log_text = scrolledtext.ScrolledText(sim_log_frame, wrap=tk.WORD, width=50, height=15, font=('Consolas', 11))
        self.sim_log_text.pack(fill=tk.BOTH, expand=True)
        self.sim_log_text.configure(state='disabled')

        # Status indicator with larger font
        self.sim_status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(sim_control_frame, textvariable=self.sim_status_var, font=('Arial', 12, 'bold'))
        status_label.grid(row=5, column=0, columnspan=2, pady=10)

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
        self.update_ship_listbox()

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

    def run(self):
        """Start the main application loop"""
        try:
            # Set default tab to Ship Simulation (now tab 0)
            self.notebook.select(0)  # Ship Simulation tab
            
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
            self.refresh_ship_display()
    
    def refresh_ship_display(self):
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
        """Start the ship simulation"""
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
        
        # Update UI
        self.sim_status_var.set("Simulation Running...")
        self.start_sim_btn.config(state=tk.DISABLED)
        self.stop_sim_btn.config(state=tk.NORMAL)
        
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
        
        # Start simulation
        from ..simulation.simulation_controller import start_simulation
        
        # Get selected ship indices
        selected_indices = list(self.ship_listbox.curselection())
        if not selected_indices:
            messagebox.showwarning("No Ships Selected", "Please select at least one ship to simulate.")
            self.stop_ship_simulation()
            return
        
        if start_simulation(signal_preset, interval, update_sim_log, selected_indices):
            update_sim_log("Simulation started successfully")
            # Start map updates if map is available and set selected ships
            if hasattr(self, 'map_visualization') and self.map_visualization:
                self.map_visualization.set_selected_ships(selected_indices)
                self.map_visualization.start_real_time_updates()
        else:
            messagebox.showerror("Error", "Failed to start simulation")
            self.stop_ship_simulation()

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
