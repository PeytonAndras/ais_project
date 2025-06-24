#!/usr/bin/env python3
"""
Ship Management Dialogs
======================

Complete implementation of ship add/edit dialogs with all features from the original:
- Full ship parameter editing
- Interactive waypoint management
- Ship type and navigation status reference panels
- Map integration for waypoint picking
- Flag country display based on MMSI

@ author: Peyton Andras @ Louisiana State University 2025
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os

from ..ships.ais_ship import AISShip
from ..ships.ship_manager import get_ship_manager
from ..config.settings import get_flag_from_mmsi
from ..utils.navigation import calculate_initial_compass_bearing

# Try to import map functionality
try:
    import tkintermapview
    MAP_VIEW_AVAILABLE = True
except ImportError:
    MAP_VIEW_AVAILABLE = False


class ShipDialog:
    """Base class for ship add/edit dialogs"""
    
    def __init__(self, parent, title, ship=None):
        self.parent = parent
        self.ship = ship  # None for add, ship object for edit
        self.dialog = None
        self.vars_dict = {}
        self.flag_var = None
        self.waypoints = []
        self.waypoint_markers = []
        self.waypoint_map = None
        self.waypoint_marker = [None]
        
        # Initialize waypoints from ship if editing
        if self.ship:
            self.waypoints = getattr(self.ship, 'waypoints', [])[:]
        
        self.create_dialog(title)
    
    def create_dialog(self, title):
        """Create the main dialog window"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title(title)
        self.dialog.attributes("-fullscreen", True)
        
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ship_notebook = ttk.Notebook(main_frame)
        ship_notebook.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Create tabs
        self.create_basic_info_tab(ship_notebook)
        self.create_waypoints_tab(ship_notebook)
        
        # Bottom button frame
        self.create_button_frame(main_frame)
    
    def create_basic_info_tab(self, notebook):
        """Create the basic ship information tab"""
        basic_frame = ttk.Frame(notebook, padding=10)
        notebook.add(basic_frame, text="Basic Info")
        
        # Define fields with default values
        if self.ship:
            # Editing existing ship
            fields = [
                ("Name:", "ship_name", self.ship.name),
                ("MMSI:", "mmsi", str(self.ship.mmsi)),
                ("Ship Type (0-99):", "ship_type", str(self.ship.ship_type)),
                ("Length (m):", "length", str(self.ship.length)),
                ("Beam (m):", "beam", str(self.ship.beam)),
                ("Latitude (°):", "lat", str(self.ship.lat)),
                ("Longitude (°):", "lon", str(self.ship.lon)),
                ("Course (°):", "course", str(self.ship.course)),
                ("Speed (knots):", "speed", str(self.ship.speed)),
                ("Nav Status (0-15):", "status", str(self.ship.status)),
                ("Rate of Turn:", "turn", str(self.ship.turn)),
                ("Destination:", "dest", self.ship.destination)
            ]
        else:
            # Adding new ship
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
        
        # Create input fields
        for i, (label_text, var_name, default) in enumerate(fields):
            ttk.Label(basic_frame, text=label_text).grid(row=i, column=0, sticky=tk.W, pady=5)
            var = tk.StringVar(value=default)
            self.vars_dict[var_name] = var
            ttk.Entry(basic_frame, textvariable=var).grid(row=i, column=1, sticky=(tk.W, tk.E), pady=5)
            
            # Flag display next to MMSI
            if var_name == "mmsi":
                self.flag_var = tk.StringVar(value=get_flag_from_mmsi(default))
                def update_flag_var(*args):
                    self.flag_var.set(get_flag_from_mmsi(self.vars_dict["mmsi"].get()))
                self.vars_dict["mmsi"].trace_add("write", lambda *a: update_flag_var())
                ttk.Label(basic_frame, text="Flag:").grid(row=i, column=2, sticky=tk.W, pady=5)
                ttk.Label(basic_frame, textvariable=self.flag_var).grid(row=i, column=3, sticky=tk.W, pady=5)
        
        # Add reference panels
        self.create_reference_panels(basic_frame, len(fields))
        
        # Set layout weights
        basic_frame.columnconfigure(1, weight=1)
    
    def create_reference_panels(self, parent, row_offset):
        """Create ship type and navigation status reference panels"""
        reference_frame = ttk.Frame(parent)
        reference_frame.grid(row=row_offset+1, column=0, columnspan=4, sticky=tk.W, padx=0, pady=(10, 0))
        
        # Ship Type Reference Panel
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
        
        # Navigation Status Reference Panel
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
    
    def create_waypoints_tab(self, notebook):
        """Create the waypoints management tab"""
        waypoints_frame = ttk.Frame(notebook, padding=10)
        notebook.add(waypoints_frame, text="Waypoints")
        
        # Waypoints list
        waypoints_list_frame = ttk.LabelFrame(waypoints_frame, text="Waypoint List")
        waypoints_list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        waypoints_table_frame = ttk.Frame(waypoints_list_frame)
        waypoints_table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.waypoints_list = ttk.Treeview(waypoints_table_frame, columns=("ID", "Latitude", "Longitude"), 
                                          show="headings", height=10)
        self.waypoints_list.heading("ID", text="Waypoint")
        self.waypoints_list.heading("Latitude", text="Latitude")
        self.waypoints_list.heading("Longitude", text="Longitude")
        self.waypoints_list.column("ID", width=80)
        self.waypoints_list.column("Latitude", width=120)
        self.waypoints_list.column("Longitude", width=120)
        self.waypoints_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        waypoints_scroll = ttk.Scrollbar(waypoints_table_frame, orient="vertical", command=self.waypoints_list.yview)
        waypoints_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.waypoints_list.configure(yscrollcommand=waypoints_scroll.set)
        
        # Fill waypoints table with existing waypoints (for edit mode)
        for i, waypoint in enumerate(self.waypoints):
            self.waypoints_list.insert("", "end", values=(f"WP {i+1}", f"{waypoint[0]:.6f}", f"{waypoint[1]:.6f}"))
        
        # Waypoint action controls
        waypoints_action_frame = ttk.Frame(waypoints_list_frame)
        waypoints_action_frame.pack(fill=tk.X, pady=5)
        
        self.waypoint_lat_var = tk.StringVar()
        self.waypoint_lon_var = tk.StringVar()
        
        ttk.Label(waypoints_action_frame, text="Latitude:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(waypoints_action_frame, textvariable=self.waypoint_lat_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(waypoints_action_frame, text="Longitude:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(waypoints_action_frame, textvariable=self.waypoint_lon_var, width=10).pack(side=tk.LEFT, padx=5)
        
        # Map integration if available
        if MAP_VIEW_AVAILABLE:
            self.create_waypoint_map(waypoints_frame, waypoints_action_frame)
        else:
            ttk.Label(waypoints_frame, text="Map not available. Install tkintermapview for map picking.").pack(pady=10)
        
        # Waypoint control buttons
        ttk.Button(waypoints_action_frame, text="Add", command=self.add_waypoint).pack(side=tk.LEFT, padx=5)
        ttk.Button(waypoints_action_frame, text="Remove", command=self.remove_waypoint).pack(side=tk.LEFT, padx=5)
        ttk.Button(waypoints_action_frame, text="Clear All", command=self.clear_waypoints).pack(side=tk.LEFT, padx=5)
        
        # Custom map button
        ttk.Button(waypoints_action_frame, text="Custom Map", command=self.open_custom_map_waypoint_picker).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(waypoints_frame, text="Note: Ship will follow waypoints in order. Max 20 waypoints.", wraplength=400).pack(pady=10)
    
    def create_waypoint_map(self, waypoints_frame, waypoints_action_frame):
        """Create the interactive waypoint map"""
        waypoint_map_frame = ttk.LabelFrame(waypoints_frame, text="Pick Waypoint on Map", padding=5)
        waypoint_map_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.waypoint_map = tkintermapview.TkinterMapView(waypoint_map_frame, width=400, height=250, corner_radius=0)
        self.waypoint_map.pack(fill=tk.BOTH, expand=True)
        
        # Set initial position
        try:
            lat0 = float(self.waypoint_lat_var.get()) if self.waypoint_lat_var.get() else 39.5
            lon0 = float(self.waypoint_lon_var.get()) if self.waypoint_lon_var.get() else -9.25
        except Exception:
            lat0, lon0 = 39.5, -9.25 # default to portugal center
        
        self.waypoint_map.set_position(lat0, lon0)
        self.waypoint_map.set_zoom(10)
        
        # Map click handler
        def on_waypoint_map_click(coords):
            lat, lon = coords
            self.waypoint_lat_var.set(f"{lat:.6f}")
            self.waypoint_lon_var.set(f"{lon:.6f}")
            if self.waypoint_marker[0]:
                self.waypoint_map.delete(self.waypoint_marker[0])
            self.waypoint_marker[0] = self.waypoint_map.set_marker(lat, lon, text="Waypoint")
        
        self.waypoint_map.add_left_click_map_command(on_waypoint_map_click)
        
        # Center map button
        def center_waypoint_map():
            try:
                lat = float(self.waypoint_lat_var.get())
                lon = float(self.waypoint_lon_var.get())
                self.waypoint_map.set_position(lat, lon)
            except Exception:
                pass
        
        ttk.Button(waypoints_action_frame, text="Center Map", command=center_waypoint_map).pack(side=tk.LEFT, padx=5)
        
        # Draw existing waypoints as markers
        for i, wp in enumerate(self.waypoints):
            marker = self.waypoint_map.set_marker(wp[0], wp[1], text=f"WP {i+1}")
            self.waypoint_markers.append(marker)
    
    def add_waypoint(self):
        """Add a waypoint to the list"""
        try:
            lat = float(self.waypoint_lat_var.get())
            lon = float(self.waypoint_lon_var.get())
            if lat < -90 or lat > 90:
                raise ValueError("Latitude must be between -90 and 90")
            if lon < -180 or lon > 180:
                raise ValueError("Longitude must be between -180 and 180")
            
            self.waypoints.append((lat, lon))
            self.waypoints_list.insert("", "end", values=(f"WP {len(self.waypoints)}", f"{lat:.6f}", f"{lon:.6f}"))
            self.waypoint_lat_var.set("")
            self.waypoint_lon_var.set("")
            
            if MAP_VIEW_AVAILABLE and self.waypoint_map:
                marker = self.waypoint_map.set_marker(lat, lon, text=f"WP {len(self.waypoints)}")
                self.waypoint_markers.append(marker)
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))
    
    def remove_waypoint(self):
        """Remove selected waypoint"""
        selected = self.waypoints_list.selection()
        if not selected:
            messagebox.showerror("Error", "Select a waypoint to remove")
            return
        
        item = self.waypoints_list.item(selected[0])
        wp_id = item['values'][0]
        try:
            index = int(wp_id.split(" ")[1]) - 1
            if 0 <= index < len(self.waypoints):
                self.waypoints.pop(index)
                self.waypoints_list.delete(*self.waypoints_list.get_children())
                
                if MAP_VIEW_AVAILABLE and self.waypoint_map:
                    for m in self.waypoint_markers:
                        self.waypoint_map.delete(m)
                    self.waypoint_markers.clear()
                    for i, wp in enumerate(self.waypoints):
                        marker = self.waypoint_map.set_marker(wp[0], wp[1], text=f"WP {i+1}")
                        self.waypoint_markers.append(marker)
                
                for i, wp in enumerate(self.waypoints):
                    self.waypoints_list.insert("", "end", values=(f"WP {i+1}", f"{wp[0]:.6f}", f"{wp[1]:.6f}"))
        except (ValueError, IndexError) as e:
            messagebox.showerror("Error", f"Could not remove waypoint: {str(e)}")
    
    def clear_waypoints(self):
        """Clear all waypoints"""
        if messagebox.askyesno("Confirm", "Remove all waypoints?"):
            self.waypoints.clear()
            self.waypoints_list.delete(*self.waypoints_list.get_children())
            if MAP_VIEW_AVAILABLE and self.waypoint_map:
                for m in self.waypoint_markers:
                    self.waypoint_map.delete(m)
                self.waypoint_markers.clear()
    
    def create_button_frame(self, parent):
        """Create the bottom button frame"""
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, pady=10)
        
        if self.ship:
            ttk.Button(btn_frame, text="Update Ship", command=self.save_ship, 
                      padding=(20, 10)).pack(side=tk.LEFT, padx=10)
        else:
            ttk.Button(btn_frame, text="Save Ship", command=self.save_ship, 
                      padding=(20, 10)).pack(side=tk.LEFT, padx=10)
        
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy, 
                  padding=(20, 10)).pack(side=tk.LEFT, padx=10)
    
    def save_ship(self):
        """Save or update the ship"""
        try:
            # Validate inputs
            mmsi = int(self.vars_dict["mmsi"].get())
            if len(str(mmsi)) != 9 or mmsi < 0:
                raise ValueError("MMSI must be a 9-digit positive integer")
                
            lat = float(self.vars_dict["lat"].get())
            if lat < -90 or lat > 90:
                raise ValueError("Latitude must be -90 to 90")
                
            lon = float(self.vars_dict["lon"].get())
            if lon < -180 or lon > 180:
                raise ValueError("Longitude must be -180 to 180")
            
            ship_manager = get_ship_manager()
            
            # Debug: Print waypoints before saving
            print(f"DEBUG: Dialog waypoints: {self.waypoints}")
            
            if self.ship:
                # Update existing ship
                self.ship.name = self.vars_dict["ship_name"].get()
                self.ship.mmsi = mmsi
                self.ship.ship_type = int(self.vars_dict["ship_type"].get())
                self.ship.length = float(self.vars_dict["length"].get())
                self.ship.beam = float(self.vars_dict["beam"].get())
                self.ship.lat = lat
                self.ship.lon = lon
                self.ship.course = float(self.vars_dict["course"].get())
                self.ship.speed = float(self.vars_dict["speed"].get())
                self.ship.status = int(self.vars_dict["status"].get())
                self.ship.turn = int(self.vars_dict["turn"].get())
                self.ship.destination = self.vars_dict["dest"].get()
                self.ship.heading = round(self.ship.course)
                
                # Update waypoints
                self.ship.waypoints = self.waypoints.copy()
                print(f"DEBUG: Ship waypoints after update: {self.ship.waypoints}")
                
                # Reset current_waypoint if waypoints were changed
                if self.waypoints:
                    self.ship.current_waypoint = 0
                else:
                    self.ship.current_waypoint = -1  # No waypoints
                
                # Force save since we modified the ship directly
                ship_manager.save_ships()
            else:
                # Create new ship
                new_ship = AISShip(
                    name=self.vars_dict["ship_name"].get(),
                    mmsi=mmsi,
                    ship_type=int(self.vars_dict["ship_type"].get()),
                    length=float(self.vars_dict["length"].get()),
                    beam=float(self.vars_dict["beam"].get()),
                    lat=lat,
                    lon=lon,
                    course=float(self.vars_dict["course"].get()),
                    speed=float(self.vars_dict["speed"].get()),
                    status=int(self.vars_dict["status"].get()),
                    turn=int(self.vars_dict["turn"].get()),
                    destination=self.vars_dict["dest"].get()
                )
                
                # Add waypoints to the ship
                if self.waypoints:
                    new_ship.waypoints = self.waypoints.copy()
                    print(f"DEBUG: New ship waypoints: {new_ship.waypoints}")
                    # Set current waypoint to first waypoint
                    new_ship.current_waypoint = 0
                    # Optionally set initial course toward first waypoint
                    if len(self.waypoints) > 0:
                        first_wp = self.waypoints[0]
                        bearing = calculate_initial_compass_bearing((lat, lon), first_wp)
                        new_ship.course = bearing
                        new_ship.heading = round(bearing)
                
                # Add to ship manager
                ship_manager.add_ship(new_ship)
            
            self.dialog.destroy()
            
            # Notify parent to update displays
            if hasattr(self.parent, 'update_ship_display'):
                self.parent.update_ship_display()
            
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))
    
    def open_custom_map_waypoint_picker(self):
        """Open custom map for waypoint selection"""
        try:
            from ..map.visualization import get_map_visualization
            map_viz = get_map_visualization()
            
            if map_viz and map_viz.map_mode == 'custom' and map_viz.custom_map_viewer:
                # Create a modal dialog with instructions
                waypoint_dialog = tk.Toplevel(self.dialog)
                waypoint_dialog.title("Select Waypoint on Map")
                waypoint_dialog.geometry("400x150")
                waypoint_dialog.transient(self.dialog)
                waypoint_dialog.grab_set()
                
                # Center the dialog
                waypoint_dialog.update_idletasks()
                x = (waypoint_dialog.winfo_screenwidth() - waypoint_dialog.winfo_width()) // 2
                y = (waypoint_dialog.winfo_screenheight() - waypoint_dialog.winfo_height()) // 2
                waypoint_dialog.geometry(f"+{x}+{y}")
                
                ttk.Label(waypoint_dialog, 
                         text="Click on the map to select a waypoint location.\n"
                              "The waypoint will be added to your ship's route.",
                         justify=tk.CENTER).pack(pady=20)
                
                self.waypoint_selected = False
                
                def on_waypoint_selected(lat, lon):
                    """Handle waypoint selection from map"""
                    self.waypoints.append([lat, lon])
                    self.waypoint_selected = True
                    waypoint_dialog.destroy()
                    self.refresh_waypoint_list()
                    messagebox.showinfo("Waypoint Added", 
                                       f"Waypoint added at {lat:.6f}, {lon:.6f}")
                
                # Temporarily set the waypoint callback
                original_callback = map_viz.custom_map_viewer.waypoint_selection_callback
                map_viz.custom_map_viewer.set_waypoint_selection_callback(on_waypoint_selected)
                
                def on_dialog_close():
                    # Restore original callback
                    map_viz.custom_map_viewer.set_waypoint_selection_callback(original_callback)
                    waypoint_dialog.destroy()
                
                ttk.Button(waypoint_dialog, text="Cancel", 
                          command=on_dialog_close).pack(pady=10)
                
                waypoint_dialog.protocol("WM_DELETE_WINDOW", on_dialog_close)
                waypoint_dialog.wait_window()
                
            else:
                messagebox.showinfo("Custom Map Required", 
                                   "Please switch to custom map mode and load a map to use this feature.")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open map waypoint picker: {e}")

    def setup_waypoint_management(self, parent_notebook):
        """Setup waypoint management controls and map integration"""
        pass  # Already handled in create_waypoints_tab


def add_ship_dialog(parent):
    """Create add ship dialog"""
    return ShipDialog(parent, "Add New Ship", ship=None)


def edit_ship_dialog(parent, ship):
    """Create edit ship dialog"""
    return ShipDialog(parent, f"Edit: {ship.name}", ship=ship)
