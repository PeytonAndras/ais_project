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

        # Instructions label
        instructions_text = ("Select ships to simulate, then click Start Simulation.\n"
                           "During simulation: Double-click ships to add/remove, or Edit to modify parameters live.")
        self.instructions_label = ttk.Label(ship_list_frame, text=instructions_text, 
                                          font=('Arial', 10), foreground='gray')
        self.instructions_label.pack(pady=(0, 10))

        # Status legend frame
        legend_frame = ttk.Frame(ship_list_frame)
        legend_frame.pack(fill=tk.X, pady=(0, 10))
        
        legend_title = ttk.Label(legend_frame, text="Status Legend:", font=('Arial', 9, 'bold'))
        legend_title.pack(anchor=tk.W)
        
        # Create visual examples using colored labels
        legend_live_frame = ttk.Frame(legend_frame)
        legend_live_frame.pack(anchor=tk.W, fill=tk.X, pady=2)
        
        live_indicator = tk.Label(legend_live_frame, text="[LIVE]", 
                                 bg='#1B5E20', fg='white', font=('Arial', 9, 'bold'),
                                 relief=tk.RAISED, padx=3)
        live_indicator.pack(side=tk.LEFT, padx=(10, 5))
        
        live_desc = ttk.Label(legend_live_frame, text="Ships currently being simulated (parameters editable live)", 
                             font=('Arial', 9))
        live_desc.pack(side=tk.LEFT)
        
        legend_inactive_frame = ttk.Frame(legend_frame)
        legend_inactive_frame.pack(anchor=tk.W, fill=tk.X, pady=2)
        
        inactive_indicator = tk.Label(legend_inactive_frame, text="[----]", 
                                     bg='#FAFAFA', fg='#424242', font=('Arial', 9),
                                     relief=tk.SUNKEN, padx=3)
        inactive_indicator.pack(side=tk.LEFT, padx=(10, 5))
        
        inactive_desc = ttk.Label(legend_inactive_frame, text="Ships not in simulation (can be added to simulation)", 
                                 font=('Arial', 9))
        inactive_desc.pack(side=tk.LEFT)

        # Ship selection listbox with better sizing
        self.ship_listbox = tk.Listbox(ship_list_frame, height=25, selectmode=tk.MULTIPLE, font=('Arial', 12))
        self.ship_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Add scroll bar
        ship_scrollbar = ttk.Scrollbar(ship_list_frame, orient="vertical", command=self.ship_listbox.yview)
        ship_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.ship_listbox.configure(yscrollcommand=ship_scrollbar.set)
        
        # Bind double-click to add/remove from simulation if running
        self.ship_listbox.bind('<Double-Button-1>', self.on_ship_listbox_double_click)

        # Ship control buttons with better styling
        ship_control_frame = ttk.Frame(ship_list_frame)
        ship_control_frame.pack(fill=tk.X, pady=15)

        # Add/Edit/Delete buttons with larger size
        self.add_ship_btn = ttk.Button(ship_control_frame, text="Add Ship", command=self.add_new_ship)
        self.add_ship_btn.pack(side=tk.LEFT, padx=8, pady=5, ipadx=10, ipady=5)

        self.edit_ship_btn = ttk.Button(ship_control_frame, text="Edit Ship", command=self.edit_selected_ship)
        self.edit_ship_btn.pack(side=tk.LEFT, padx=8, pady=5, ipadx=10, ipady=5)

        self.delete_ship_btn = ttk.Button(ship_control_frame, text="Delete Ship", command=self.delete_selected_ships)
        self.delete_ship_btn.pack(side=tk.LEFT, padx=8, pady=5, ipadx=10, ipady=5)

        # Add ship during simulation button (initially hidden)
        self.add_ship_sim_btn = ttk.Button(ship_control_frame, text="Add Ship to Simulation", 
                                          command=self.add_ship_to_simulation)
        # Don't pack this initially - it will be shown/hidden based on simulation state
        
        # Update simulation selection button (initially hidden)
        self.update_sim_selection_btn = ttk.Button(ship_control_frame, text="Update Simulation Selection", 
                                                  command=self.update_simulation_selection)
        # This will also be shown during simulation

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
        self.sim_status_var = tk.StringVar(value="READY - Select ships and click Start Simulation")
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
        """Update the ship listbox with current configurations and visual indicators"""
        if hasattr(self, 'ship_listbox'):
            # Store current selection
            current_selection = list(self.ship_listbox.curselection())
            
            self.ship_listbox.delete(0, tk.END)
            
            ship_configs = get_ship_configs()
            from ..simulation.simulation_controller import is_simulation_active
            is_sim_active = is_simulation_active()
            
            for i, ship in enumerate(ship_configs):
                # Check if this ship is in the current simulation
                is_in_simulation = (is_sim_active and hasattr(self, 'current_selected_indices') 
                                   and i in self.current_selected_indices)
                
                # Create display text with clear visual indicators
                if is_in_simulation:
                    # Ships currently being simulated - clear status indicator
                    display_text = f"[LIVE] {ship.name} (MMSI: {ship.mmsi}) - {ship.speed} kts, {ship.course}°"
                else:
                    # Ships not in simulation - standard formatting
                    display_text = f"[----] {ship.name} (MMSI: {ship.mmsi}) - {ship.speed} kts, {ship.course}°"
                
                self.ship_listbox.insert(i, display_text)
                
                # Set different colors for simulated vs non-simulated ships
                if is_in_simulation:
                    # Ships in simulation: dark green background, white text
                    self.ship_listbox.itemconfig(i, 
                                                bg='#1B5E20',  # Dark green
                                                fg='white',
                                                selectbackground='#4CAF50',  # Lighter green when selected
                                                selectforeground='white')
                else:
                    # Ships not in simulation: light background, dark text
                    self.ship_listbox.itemconfig(i, 
                                                bg='#FAFAFA',  # Very light gray
                                                fg='#424242',  # Dark gray
                                                selectbackground='#2196F3',  # Blue when selected
                                                selectforeground='white')
            
            # Restore selection if ships are being simulated
            if (hasattr(self, 'current_selected_indices') and is_sim_active):
                for index in self.current_selected_indices:
                    if index < self.ship_listbox.size():
                        self.ship_listbox.selection_set(index)
            else:
                # Restore previous selection if not simulating
                for index in current_selection:
                    if index < self.ship_listbox.size():
                        self.ship_listbox.selection_set(index)

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
        from ..simulation.simulation_controller import is_simulation_active
        
        ship_manager = get_ship_manager()
        ships = ship_manager.get_ships()
        if selected[0] < len(ships):
            ship = ships[selected[0]]
            ship_index = selected[0]
            
            # Check if simulation is running and if this ship is being simulated
            is_simulating = is_simulation_active()
            is_ship_in_simulation = (is_simulating and hasattr(self, 'current_selected_indices') 
                                   and ship_index in self.current_selected_indices)
            
            # Pass simulation context to the dialog
            simulation_context = {
                'is_simulating': is_simulating,
                'is_ship_in_simulation': is_ship_in_simulation,
                'ship_index': ship_index,
                'update_callback': self._handle_ship_update_during_simulation if is_ship_in_simulation else None
            }
            
            print(f"DEBUG: Passing simulation context to edit dialog: {simulation_context}")
            
            edit_ship_dialog(self.root, ship, simulation_context)

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
        """Update the ship display in the UI with visual indicators"""
        # Use the main update method which includes all visual formatting
        self.update_ship_listbox()
        
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
        
        # Show the "Add Ship to Simulation" and "Update Selection" buttons, hide the regular add button
        self.add_ship_btn.pack_forget()
        self.add_ship_sim_btn.pack(side=tk.LEFT, padx=8, pady=5, ipadx=10, ipady=5)
        self.update_sim_selection_btn.pack(side=tk.LEFT, padx=8, pady=5, ipadx=10, ipady=5)
        
        # Update instructions
        self.instructions_label.config(
            text="Simulation running! Double-click ships to add/remove from simulation.\n"
                 "Edit ships to modify parameters live. Use buttons below to add new ships."
        )
        
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
        
        # Store the current simulation parameters for adding ships later
        self.current_signal_preset = signal_preset
        self.current_interval = interval
        self.current_update_callback = update_sim_log
        self.current_selected_indices = selected_indices.copy()
        
        if start_simulation(signal_preset, interval, update_sim_log, selected_indices):
            update_sim_log("Simulation started successfully")
            
            # Update status with detailed information
            from ..ships.ship_manager import get_ship_manager
            ship_manager = get_ship_manager()
            ships = ship_manager.get_ships()
            simulated_ship_names = [ships[i].name for i in selected_indices if i < len(ships)]
            
            if len(simulated_ship_names) <= 2:
                # Show names if we have 2 or fewer ships
                ship_list = ", ".join(simulated_ship_names)
                self.sim_status_var.set(f"SIMULATION ACTIVE - Live: {ship_list}")
            else:
                # Show count if we have many ships
                self.sim_status_var.set(f"SIMULATION ACTIVE - {len(simulated_ship_names)} ships live")
            
            # IMPORTANT: Update the ship listbox to show new visual states
            self.update_ship_listbox()
            
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
        
        # Hide the "Add Ship to Simulation" and "Update Selection" buttons, show the regular add button
        self.add_ship_sim_btn.pack_forget()
        self.update_sim_selection_btn.pack_forget()
        self.add_ship_btn.pack(side=tk.LEFT, padx=8, pady=5, ipadx=10, ipady=5)
        
        # Restore instructions
        self.instructions_label.config(
            text="Select ships to simulate, then click Start Simulation.\n"
                 "During simulation: Double-click ships to add/remove, or Edit to modify parameters live."
        )
        
        self.sim_status_var.set("SIMULATION STOPPED - Ready to start new simulation")
        self.start_sim_btn.config(state=tk.NORMAL)
        self.stop_sim_btn.config(state=tk.DISABLED)
        
        # IMPORTANT: Update the ship listbox to clear visual states
        self.update_ship_listbox()
        
        # Clear simulation state
        if hasattr(self, 'current_signal_preset'):
            delattr(self, 'current_signal_preset')
        if hasattr(self, 'current_interval'):
            delattr(self, 'current_interval')
        if hasattr(self, 'current_update_callback'):
            delattr(self, 'current_update_callback')
        if hasattr(self, 'current_selected_indices'):
            delattr(self, 'current_selected_indices')

    def add_ship_to_simulation(self):
        """Add a new ship to the running simulation"""
        from .ship_dialogs import add_ship_dialog
        from ..simulation.simulation_controller import is_simulation_active, stop_simulation, start_simulation
        
        if not is_simulation_active():
            messagebox.showerror("Error", "No simulation is currently running")
            return
        
        # Get the current ship count before adding new ship
        from ..ships.ship_manager import get_ship_manager
        ship_manager = get_ship_manager()
        initial_ship_count = len(ship_manager.get_ships())
        
        # Store the old refresh callback to temporarily replace it
        old_refresh = self.refresh_ship_display
        simulation_updated = [False]  # Use list to allow modification in nested function
        
        def temp_refresh():
            """Temporary refresh function that handles adding ship to simulation"""
            # Call the original refresh to update UI
            old_refresh()
            
            # Check if a new ship was actually added
            current_ship_count = len(ship_manager.get_ships())
            if current_ship_count > initial_ship_count and not simulation_updated[0]:
                simulation_updated[0] = True
                # Get the new ship index (last ship)
                new_ship_index = current_ship_count - 1
                new_ship = ship_manager.get_ship(new_ship_index)
                
                # Ask user if they want to add the ship to the simulation
                result = messagebox.askyesnocancel(
                    "Add to Simulation",
                    f"Ship '{new_ship.name}' has been created.\n\n"
                    f"Do you want to add it to the running simulation?\n\n"
                    f"• Yes: Add to simulation immediately\n"
                    f"• No: Keep simulation as-is\n"
                    f"• Cancel: Remove the ship",
                    icon='question'
                )
                
                if result is None:  # Cancel - remove the ship
                    ship_manager.remove_ship(new_ship_index)
                    old_refresh()  # Refresh to remove from display
                    return
                elif result:  # Yes - add to simulation
                    # Add the new ship to the current selection
                    self.current_selected_indices.append(new_ship_index)
                    
                    # Update the listbox selection to include the new ship
                    for index in self.current_selected_indices:
                        if index < self.ship_listbox.size():
                            self.ship_listbox.selection_set(index)
                    
                    # Restart simulation with updated ship list
                    if hasattr(self, 'current_signal_preset'):
                        # Stop current simulation
                        stop_simulation()
                        
                        # Log the addition
                        if hasattr(self, 'current_update_callback'):
                            self.current_update_callback(f"Added '{new_ship.name}' to simulation. Now simulating {len(self.current_selected_indices)} ships.")
                        
                        # Restart with updated selection
                        start_simulation(
                            self.current_signal_preset, 
                            self.current_interval, 
                            self.current_update_callback, 
                            self.current_selected_indices
                        )
                        
                        # Update map visualization
                        if hasattr(self, 'map_visualization') and self.map_visualization:
                            self.map_visualization.set_selected_ships(self.current_selected_indices)
                            
                        # Update simulation status
                        # Update status with ship count and names
                        from ..ships.ship_manager import get_ship_manager
                        ship_manager = get_ship_manager()
                        ships = ship_manager.get_ships()
                        simulated_ship_names = [ships[i].name for i in self.current_selected_indices if i < len(ships)]
                        
                        if len(simulated_ship_names) <= 2:
                            ship_list = ", ".join(simulated_ship_names)
                            self.sim_status_var.set(f"SIMULATION ACTIVE - Live: {ship_list}")
                        else:
                            self.sim_status_var.set(f"SIMULATION ACTIVE - {len(simulated_ship_names)} ships live")
                        
                        # IMPORTANT: Update the ship listbox to show new visual states
                        self.update_ship_listbox()
                # If No was selected, ship is added but not included in simulation
        
        # Temporarily replace refresh method
        self.refresh_ship_display = temp_refresh
        
        try:
            # Open the add ship dialog
            add_ship_dialog(self.root)
        finally:
            # Restore the original refresh method
            self.refresh_ship_display = old_refresh

    def on_ship_listbox_double_click(self, event):
        """Handle double-click on ship listbox during simulation"""
        from ..simulation.simulation_controller import is_simulation_active
        
        if is_simulation_active():
            clicked_index = self.ship_listbox.nearest(event.y)
            if clicked_index < self.ship_listbox.size():
                # Get ship info
                from ..ships.ship_manager import get_ship_manager
                ship_manager = get_ship_manager()
                ship = ship_manager.get_ship(clicked_index)
                
                if ship and hasattr(self, 'current_selected_indices'):
                    if clicked_index in self.current_selected_indices:
                        # Remove from simulation
                        result = messagebox.askyesno(
                            "Remove from Simulation",
                            f"Remove '{ship.name}' from the running simulation?"
                        )
                        if result:
                            self.current_selected_indices.remove(clicked_index)
                            self._restart_simulation_with_selection()
                            # Update visual display immediately
                            self.update_ship_listbox()
                    else:
                        # Add to simulation
                        result = messagebox.askyesno(
                            "Add to Simulation",
                            f"Add '{ship.name}' to the running simulation?"
                        )
                        if result:
                            self.current_selected_indices.append(clicked_index)
                            self._restart_simulation_with_selection()
                            # Update visual display immediately
                            self.update_ship_listbox()

    def update_simulation_selection(self):
        """Update the simulation to use currently selected ships in listbox"""
        from ..simulation.simulation_controller import is_simulation_active
        
        if not is_simulation_active():
            messagebox.showerror("Error", "No simulation is currently running")
            return
        
        # Get currently selected ships in the listbox
        new_selection = list(self.ship_listbox.curselection())
        
        if not new_selection:
            messagebox.showwarning("No Selection", "Please select at least one ship to simulate.")
            return
        
        # Update the simulation selection
        old_count = len(self.current_selected_indices) if hasattr(self, 'current_selected_indices') else 0
        self.current_selected_indices = new_selection.copy()
        
        # Restart simulation with new selection
        self._restart_simulation_with_selection()
        
        # Update visual display immediately
        self.update_ship_listbox()
        
        # Show confirmation
        messagebox.showinfo(
            "Simulation Updated",
            f"Simulation updated from {old_count} to {len(new_selection)} ships"
        )

    def _restart_simulation_with_selection(self):
        """Helper method to restart simulation with current selection"""
        from ..simulation.simulation_controller import stop_simulation, start_simulation
        
        if not hasattr(self, 'current_signal_preset') or not self.current_selected_indices:
            return
        
        # Stop current simulation
        stop_simulation()
        
        # Update listbox selection to reflect simulation ships
        self.ship_listbox.selection_clear(0, tk.END)
        for index in self.current_selected_indices:
            if index < self.ship_listbox.size():
                self.ship_listbox.selection_set(index)
        
        # Log the change
        if hasattr(self, 'current_update_callback'):
            self.current_update_callback(f"Simulation updated - now simulating {len(self.current_selected_indices)} ships.")
        
        # Restart with updated selection
        start_simulation(
            self.current_signal_preset, 
            self.current_interval, 
            self.current_update_callback, 
            self.current_selected_indices
        )
        
        # Update map visualization
        if hasattr(self, 'map_visualization') and self.map_visualization:
            self.map_visualization.set_selected_ships(self.current_selected_indices)
            
        # Update simulation status
        # Update simulation status display
        from ..ships.ship_manager import get_ship_manager
        ship_manager = get_ship_manager()
        ships = ship_manager.get_ships()
        simulated_ship_names = [ships[i].name for i in self.current_selected_indices if i < len(ships)]
        
        if len(simulated_ship_names) <= 2:
            ship_list = ", ".join(simulated_ship_names)
            self.sim_status_var.set(f"SIMULATION ACTIVE - Live: {ship_list}")
        else:
            self.sim_status_var.set(f"SIMULATION ACTIVE - {len(simulated_ship_names)} ships live")
        
        # Update the ship listbox to reflect new simulation state
        self.update_ship_listbox()

    def _handle_ship_update_during_simulation(self, ship_index, ship):
        """Handle ship parameter updates during simulation"""
        from ..simulation.simulation_controller import is_simulation_active
        from datetime import datetime
        
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        print(f"DEBUG [{timestamp}]: Live update callback called for ship {ship_index}: {ship.name}")
        print(f"DEBUG [{timestamp}]: Ship parameters - speed: {ship.speed}, course: {ship.course}")
        
        if not is_simulation_active() or not hasattr(self, 'current_update_callback'):
            return
        
        # Log the parameter update
        self.current_update_callback(f"Live update: '{ship.name}' parameters changed - speed: {ship.speed} kts, course: {ship.course}°")
        
        # Update the ship listbox display to reflect new parameters
        self.update_ship_listbox()
        
        # Update map visualization immediately if available
        if hasattr(self, 'map_visualization') and self.map_visualization:
            self.map_visualization.update_map(force=True)
        
        # Show a brief status update
        old_status = self.sim_status_var.get()
        self.sim_status_var.set(f"LIVE UPDATE: {ship.name} - {ship.speed} kts, {ship.course}°")
        
        # Restore the normal status after 3 seconds
        self.root.after(3000, lambda: self.sim_status_var.set(old_status) if hasattr(self, 'sim_status_var') else None)
