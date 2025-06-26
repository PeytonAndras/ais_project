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
    
    def __init__(self, parent, title, ship=None, simulation_context=None):
        self.parent = parent
        self.ship = ship  # None for add, ship object for edit
        self.simulation_context = simulation_context or {}
        self.dialog = None
        self.vars_dict = {}
        self.flag_var = None
        self.waypoints = []
        self.waypoint_markers = []
        self.waypoint_map = None
        self.waypoint_marker = [None]
        
        # Position map variables for Basic Info tab
        self.position_map = None
        self.position_marker = None
        
        # Initialize waypoints from ship if editing
        if self.ship:
            self.waypoints = getattr(self.ship, 'waypoints', [])[:]
        
        self.create_dialog(title)
    
    def create_dialog(self, title):
        """Create the main dialog window"""
        self.dialog = tk.Toplevel(self.parent)
        
        # Modify title to show simulation status
        if self.simulation_context.get('is_ship_in_simulation'):
            title += " [SIMULATION RUNNING]"
        elif self.simulation_context.get('is_simulating'):
            title += " [SIMULATION ACTIVE - NOT SIMULATED]"
            
        self.dialog.title(title)
        # Don't make it fullscreen for now - use regular maximized window
        self.dialog.state('zoomed')  # Maximize on Windows/Linux, or use geometry on Mac
        
        # Try to maximize properly on different platforms
        try:
            self.dialog.state('zoomed')
        except:
            # Fallback to manual sizing
            self.dialog.geometry("1200x800")
        
        # Create main container with explicit layout
        main_container = ttk.Frame(self.dialog)
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Add simulation status banner if applicable
        if self.simulation_context.get('is_simulating'):
            self.create_simulation_banner(main_container)
        
        # Content area (notebook) - use grid for better control
        main_container.rowconfigure(0, weight=1)  # Content area expands
        main_container.rowconfigure(1, weight=0)  # Button area fixed
        main_container.columnconfigure(0, weight=1)
        
        content_frame = ttk.Frame(main_container)
        content_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 20))
        
        ship_notebook = ttk.Notebook(content_frame)
        ship_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Create tabs
        self.create_basic_info_tab(ship_notebook)
        self.create_waypoints_tab(ship_notebook)
        
        # Bottom button frame - use grid so it's always at bottom
        button_frame = ttk.Frame(main_container)
        button_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        
        self.create_button_frame_in_container(button_frame)
    
    def create_basic_info_tab(self, notebook):
        """Create the basic ship information tab"""
        basic_frame = ttk.Frame(notebook, padding=10)
        notebook.add(basic_frame, text="Basic Info")
        
        # Create main left and right frames
        left_frame = ttk.Frame(basic_frame)
        left_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        
        right_frame = ttk.Frame(basic_frame)
        right_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        basic_frame.columnconfigure(0, weight=2)  # Left frame gets more space
        basic_frame.columnconfigure(1, weight=1)  # Right frame gets less space
        basic_frame.rowconfigure(0, weight=1)
        
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
                ("Latitude (°):", "lat", "39.5"),
                ("Longitude (°):", "lon", "-9.25"),
                ("Course (°):", "course", "90"),
                ("Speed (knots):", "speed", "8"),
                ("Nav Status (0-15):", "status", "0"),
                ("Rate of Turn:", "turn", "0"),
                ("Destination:", "dest", "LISBON")
            ]
        
        # Create parameter frame for input fields
        param_frame = ttk.LabelFrame(left_frame, text="Vessel Parameters", padding=10)
        param_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), pady=(0, 10))
        
        # Create input fields in a more compact layout
        for i, (label_text, var_name, default) in enumerate(fields):
            ttk.Label(param_frame, text=label_text).grid(row=i, column=0, sticky=tk.W, pady=2)
            var = tk.StringVar(value=default)
            self.vars_dict[var_name] = var
            ttk.Entry(param_frame, textvariable=var, width=15).grid(row=i, column=1, sticky=(tk.W, tk.E), pady=2, padx=(5, 0))
            
            # Add precision hints for coordinate fields
            if var_name == "lat":
                ttk.Label(param_frame, text="(±90°, max 6 decimal places)", font=("Arial", 8), foreground="gray").grid(row=i, column=2, sticky=tk.W, pady=2, padx=(5, 0))
            elif var_name == "lon":
                ttk.Label(param_frame, text="(±180°, max 6 decimal places)", font=("Arial", 8), foreground="gray").grid(row=i, column=2, sticky=tk.W, pady=2, padx=(5, 0))
            
            # Flag display next to MMSI
            if var_name == "mmsi":
                self.flag_var = tk.StringVar(value=get_flag_from_mmsi(default))
                def update_flag_var(*args):
                    self.flag_var.set(get_flag_from_mmsi(self.vars_dict["mmsi"].get()))
                self.vars_dict["mmsi"].trace_add("write", lambda *a: update_flag_var())
                ttk.Label(param_frame, text="Flag:").grid(row=i, column=3, sticky=tk.W, pady=2, padx=(10, 0))
                ttk.Label(param_frame, textvariable=self.flag_var).grid(row=i, column=4, sticky=tk.W, pady=2, padx=(5, 0))
        
        # Configure parameter frame weights
        param_frame.columnconfigure(1, weight=1)
        param_frame.columnconfigure(2, weight=0)  # Hint text column
        param_frame.columnconfigure(3, weight=0)  # Flag label column
        param_frame.columnconfigure(4, weight=0)  # Flag value column
        
        # Create interactive map frame
        map_frame = ttk.LabelFrame(left_frame, text="Position Map", padding=10)
        map_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        left_frame.rowconfigure(1, weight=1)  # Map gets remaining space
        
        # Create map widget if available
        if MAP_VIEW_AVAILABLE:
            self.position_map = tkintermapview.TkinterMapView(map_frame, width=500, height=350, corner_radius=0)
            self.position_map.grid(row=0, column=0, columnspan=4, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
            
            # Set initial position
            try:
                initial_lat = float(self.vars_dict["lat"].get())
                initial_lon = float(self.vars_dict["lon"].get())
            except (ValueError, KeyError):
                initial_lat, initial_lon = 39.5, -9.25  # Default to Portugal area (same as main map)
            
            self.position_map.set_position(initial_lat, initial_lon)
            self.position_map.set_zoom(10)
            
            # Position marker
            self.position_marker = self.position_map.set_marker(initial_lat, initial_lon, text="Position")
            
            # Map click handler
            def on_position_map_click(coords):
                lat, lon = coords
                self.vars_dict["lat"].set(f"{lat:.6f}")
                self.vars_dict["lon"].set(f"{lon:.6f}")
                if self.position_marker:
                    self.position_map.delete(self.position_marker)
                self.position_marker = self.position_map.set_marker(lat, lon, text="Position")
            
            self.position_map.add_left_click_map_command(on_position_map_click)
            
            # Bind coordinate changes to map updates
            self.vars_dict["lat"].trace_add("write", self.on_coordinate_change_map)
            self.vars_dict["lon"].trace_add("write", self.on_coordinate_change_map)
            
        else:
            # Fallback to simple canvas if tkintermapview is not available
            self.map_canvas = tk.Canvas(map_frame, bg="lightblue", height=300, width=500)
            self.map_canvas.grid(row=0, column=0, columnspan=4, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
            
            ttk.Label(map_frame, text="Map view requires tkintermapview package", 
                     font=("Segoe UI", 10)).grid(row=0, column=0, columnspan=4)
        
        # Preset location buttons
        preset_frame = ttk.Frame(map_frame)
        preset_frame.grid(row=1, column=0, columnspan=4, sticky=(tk.W, tk.E))
        
        ttk.Label(preset_frame, text="Quick Locations:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        
        presets = [
            ("Lisbon Port", 38.7078, -9.1365),
            ("Atlantic Coast", 39.5, -9.25),
            ("English Channel", 50.2500, 1.0000),
            ("Mediterranean", 36.0000, 14.0000)
        ]
        
        for i, (name, lat, lon) in enumerate(presets):
            btn = ttk.Button(preset_frame, text=name, 
                           command=lambda l=lat, o=lon: self.set_coordinates(l, o))
            btn.grid(row=0, column=i+1, sticky=tk.W, padx=5)
        
        # Center map button
        def center_position_map():
            if MAP_VIEW_AVAILABLE and hasattr(self, 'position_map'):
                try:
                    lat = float(self.vars_dict["lat"].get())
                    lon = float(self.vars_dict["lon"].get())
                    self.position_map.set_position(lat, lon)
                except Exception:
                    pass
        
        ttk.Button(preset_frame, text="Center Map", command=center_position_map).grid(row=0, column=len(presets)+1, sticky=tk.W, padx=5)
        
        # Configure map frame weights
        map_frame.columnconfigure(0, weight=1)
        map_frame.rowconfigure(0, weight=1)
        
        # Add reference documentation to right frame
        self.create_reference_documentation(right_frame)
    
    def create_reference_documentation(self, parent):
        """Create reference documentation in a notebook widget"""
        ref_notebook = ttk.Notebook(parent)
        ref_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Ship Type Reference Tab
        ship_type_frame = ttk.Frame(ref_notebook, padding=10)
        ref_notebook.add(ship_type_frame, text="Ship Types")
        
        ttk.Label(ship_type_frame, text="AIS Ship Type Codes", font=("Segoe UI", 12, "bold")).pack(anchor=tk.W, pady=(0, 10))
        
        ship_type_text = tk.Text(ship_type_frame, wrap=tk.WORD, height=20, width=30, 
                                font=("Segoe UI", 10), relief=tk.FLAT, borderwidth=1)
        ship_type_scroll = ttk.Scrollbar(ship_type_frame, orient="vertical", command=ship_type_text.yview)
        ship_type_text.configure(yscrollcommand=ship_type_scroll.set)
        
        ship_type_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ship_type_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
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

Special Values:
0 - Not available
99 - Other type not defined above
""")
        ship_type_text.config(state=tk.DISABLED)
        
        # Navigation Status Reference Tab
        nav_status_frame = ttk.Frame(ref_notebook, padding=10)
        ref_notebook.add(nav_status_frame, text="Nav Status")
        
        ttk.Label(nav_status_frame, text="AIS Navigation Status Codes", font=("Segoe UI", 12, "bold")).pack(anchor=tk.W, pady=(0, 10))
        
        nav_status_text = tk.Text(nav_status_frame, wrap=tk.WORD, height=20, width=30,
                                 font=("Segoe UI", 10), relief=tk.FLAT, borderwidth=1)
        nav_status_scroll = ttk.Scrollbar(nav_status_frame, orient="vertical", command=nav_status_text.yview)
        nav_status_text.configure(yscrollcommand=nav_status_scroll.set)
        
        nav_status_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
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

Common Status Values:
- Use 0 for most active vessels
- Use 1 for anchored vessels
- Use 5 for docked vessels
- Use 15 when status is unknown
""")
        nav_status_text.config(state=tk.DISABLED)
    
    def set_coordinates(self, lat, lon):
        """Set coordinates from preset buttons"""
        self.vars_dict["lat"].set(str(lat))
        self.vars_dict["lon"].set(str(lon))
        
        # Update map marker if using tkintermapview
        if MAP_VIEW_AVAILABLE and hasattr(self, 'position_map'):
            if hasattr(self, 'position_marker') and self.position_marker:
                self.position_map.delete(self.position_marker)
            self.position_marker = self.position_map.set_marker(lat, lon, text="Position")
            self.position_map.set_position(lat, lon)
        elif hasattr(self, 'map_canvas'):
            # Fallback for canvas-based map
            self.update_map_marker(lat, lon)
    
    def on_coordinate_change_map(self, *args):
        """Handle coordinate field changes to update the tkintermapview map"""
        if not MAP_VIEW_AVAILABLE or not hasattr(self, 'position_map'):
            return
            
        try:
            lat = float(self.vars_dict["lat"].get())
            lon = float(self.vars_dict["lon"].get())
            
            # Update marker position
            if hasattr(self, 'position_marker') and self.position_marker:
                self.position_map.delete(self.position_marker)
            self.position_marker = self.position_map.set_marker(lat, lon, text="Position")
            
        except ValueError:
            pass  # Ignore invalid values during typing
    
    def on_map_click(self, event):
        """Handle map click events for canvas-based fallback map (deprecated)"""
        # This method is kept for backward compatibility with canvas fallback
        if not hasattr(self, 'map_canvas'):
            return
            
        # Convert canvas coordinates to lat/lon (simplified mapping)
        canvas_width = self.map_canvas.winfo_width()
        canvas_height = self.map_canvas.winfo_height()
        
        # Simple world map projection (not accurate but functional for demo)
        lon = ((event.x / canvas_width) * 360) - 180
        lat = 90 - ((event.y / canvas_height) * 180)
        
        # Clamp values to valid ranges
        lat = max(-90, min(90, lat))
        lon = max(-180, min(180, lon))
        
        self.vars_dict["lat"].set(f"{lat:.6f}")
        self.vars_dict["lon"].set(f"{lon:.6f}")
        self.update_map_marker(lat, lon)
    
    def on_coordinate_change(self, *args):
        """Handle coordinate field changes for canvas-based fallback map (deprecated)"""
        # This method is kept for backward compatibility with canvas fallback
        if not hasattr(self, 'map_canvas'):
            return
            
        try:
            lat = float(self.vars_dict["lat"].get())
            lon = float(self.vars_dict["lon"].get())
            self.update_map_marker(lat, lon)
        except ValueError:
            pass  # Ignore invalid values during typing
    
    def update_map_marker(self, lat, lon):
        """Update the marker position on canvas-based fallback map (deprecated)"""
        if not hasattr(self, 'map_canvas'):
            return
            
        # Clear existing marker and crosshairs
        if hasattr(self, 'map_marker') and self.map_marker:
            self.map_canvas.delete(self.map_marker)
        self.map_canvas.delete("crosshair")
        
        # Convert lat/lon to canvas coordinates (simplified projection)
        canvas_width = self.map_canvas.winfo_width()
        canvas_height = self.map_canvas.winfo_height()
        
        # Ensure canvas has been drawn
        if canvas_width <= 1 or canvas_height <= 1:
            self.map_canvas.after(100, lambda: self.update_map_marker(lat, lon))
            return
        
        x = ((lon + 180) / 360) * canvas_width
        y = ((90 - lat) / 180) * canvas_height
        
        # Draw marker
        marker_size = 8
        self.map_marker = self.map_canvas.create_oval(
            x - marker_size, y - marker_size,
            x + marker_size, y + marker_size,
            fill="red", outline="darkred", width=2
        )
        
        # Draw crosshairs
        self.map_canvas.create_line(x - 15, y, x + 15, y, fill="red", width=2, tags="crosshair")
        self.map_canvas.create_line(x, y - 15, x, y + 15, fill="red", width=2, tags="crosshair")
    
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
    
    def create_button_frame_in_container(self, container):
        """Create the button frame in the provided container"""
        print(f"DEBUG: Creating button frame in container with simulation context: {self.simulation_context}")
        
        # Add simulation note if applicable
        if self.simulation_context.get('is_ship_in_simulation'):
            note_label = ttk.Label(container, text="💡 Changes will be applied to the running simulation immediately", 
                                  font=('Arial', 12, 'bold'), foreground='green')
            note_label.pack(pady=(0, 10))
            print("DEBUG: Added simulation note")
        
        # Button container centered
        button_container = ttk.Frame(container)
        button_container.pack(anchor=tk.CENTER)
        
        if self.ship:
            update_text = "Update Ship Live" if self.simulation_context.get('is_ship_in_simulation') else "Update Ship"
            print(f"DEBUG: Creating update button with text: '{update_text}'")
            
            # Large, visible button
            self.update_btn = tk.Button(button_container, text=update_text, command=self.save_ship,
                                       font=('Arial', 14, 'bold'), bg='#4CAF50', fg='grey',
                                       padx=30, pady=15)
            self.update_btn.pack(side=tk.LEFT, padx=20)
            print("DEBUG: Update button created and packed")
        else:
            print("DEBUG: Creating save button for new ship")
            self.save_btn = tk.Button(button_container, text="Save Ship", command=self.save_ship,
                                     font=('Arial', 14, 'bold'), bg='#4CAF50', fg='grey',
                                     padx=30, pady=15)
            self.save_btn.pack(side=tk.LEFT, padx=20)
            print("DEBUG: Save button created and packed")
        
        self.cancel_btn = tk.Button(button_container, text="Cancel", command=self.dialog.destroy,
                                   font=('Arial', 14, 'bold'), bg='#f44336', fg='grey',
                                   padx=30, pady=15)
        self.cancel_btn.pack(side=tk.LEFT, padx=20)
        print("DEBUG: Cancel button created and packed")
        
        print("DEBUG: All buttons should now be visible!")
    
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
            # Check coordinate precision (AIS standard supports up to 6 decimal places)
            lat_str = self.vars_dict["lat"].get()
            if '.' in lat_str and len(lat_str.split('.')[1]) > 6:
                raise ValueError("Latitude precision: maximum 6 decimal places allowed")
                
            lon = float(self.vars_dict["lon"].get())
            if lon < -180 or lon > 180:
                raise ValueError("Longitude must be -180 to 180")
            # Check coordinate precision (AIS standard supports up to 6 decimal places)
            lon_str = self.vars_dict["lon"].get()
            if '.' in lon_str and len(lon_str.split('.')[1]) > 6:
                raise ValueError("Longitude precision: maximum 6 decimal places allowed")
            
            ship_manager = get_ship_manager()
            
            # Debug: Print waypoints before saving
            print(f"DEBUG: Dialog waypoints: {self.waypoints}")
            print(f"DEBUG: Simulation context: {self.simulation_context}")
            
            if self.ship:
                # Update existing ship by creating a new ship object and using ship manager's update method
                # This ensures proper reference updates
                ship_index = self.simulation_context.get('ship_index')
                if ship_index is None:
                    # Find the ship index if not provided
                    ships = ship_manager.get_ships()
                    ship_index = ships.index(self.ship) if self.ship in ships else -1
                
                if ship_index >= 0:
                    # Update the ship properties
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
                        # Set initial course toward first waypoint
                        first_wp = self.waypoints[0]
                        bearing = calculate_initial_compass_bearing((self.ship.lat, self.ship.lon), first_wp)
                        self.ship.course = bearing
                        self.ship.heading = round(bearing)
                        print(f"DEBUG: Course set to first waypoint: {bearing:.1f}°")
                    else:
                        self.ship.current_waypoint = -1  # No waypoints
                    
                    # Use ship manager's update method to ensure proper notification
                    ship_manager.update_ship(ship_index, self.ship)
                    print(f"DEBUG: Updated ship {ship_index} via ship manager")
                
                # Handle simulation update if ship is being simulated
                if self.simulation_context.get('is_ship_in_simulation') and self.simulation_context.get('update_callback'):
                    ship_index = self.simulation_context.get('ship_index')
                    update_callback = self.simulation_context.get('update_callback')
                    update_callback(ship_index, self.ship)
                    
                    # Show success message for live update
                    messagebox.showinfo("Live Update Successful", 
                                       f"Parameters for '{self.ship.name}' have been updated live!\n\n"
                                       f"New settings:\n"
                                       f"• Speed: {self.ship.speed} knots\n"
                                       f"• Course: {self.ship.course}°\n"
                                       f"• Position: {self.ship.lat:.4f}, {self.ship.lon:.4f}\n"
                                       f"• Status: {self.ship.status}\n\n"
                                       f"Changes are now active in the simulation.")
                else:
                    # Regular update message for non-simulated ships
                    messagebox.showinfo("Ship Updated", f"Ship '{self.ship.name}' has been updated successfully.")
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
            if hasattr(self.parent, 'refresh_ship_display'):
                self.parent.refresh_ship_display()
            
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
    
    def create_simulation_banner(self, parent):
        """Create a banner showing simulation status"""
        banner_frame = ttk.Frame(parent, style='SimulationBanner.TFrame')
        banner_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Configure banner style
        style = ttk.Style()
        if self.simulation_context.get('is_ship_in_simulation'):
            style.configure('SimulationBanner.TFrame', background='#4CAF50')  # Green for simulated
            banner_text = "🔴 LIVE SIMULATION - All changes take effect immediately"
            text_color = 'white'
            sub_text = "Parameters will update in real-time without stopping the simulation"
        else:
            style.configure('SimulationBanner.TFrame', background='#FF9800')  # Orange for not simulated
            banner_text = "⚠️ SIMULATION RUNNING - This ship is not currently being simulated"
            text_color = 'white'
            sub_text = "Changes will be saved but won't affect the running simulation"
        
        # Main banner text
        main_label = ttk.Label(banner_frame, text=banner_text, 
                              font=('Arial', 14, 'bold'), 
                              foreground=text_color,
                              background=style.lookup('SimulationBanner.TFrame', 'background'))
        main_label.pack(pady=(8, 2))
        
        # Sub text
        sub_label = ttk.Label(banner_frame, text=sub_text, 
                             font=('Arial', 10), 
                             foreground=text_color,
                             background=style.lookup('SimulationBanner.TFrame', 'background'))
        sub_label.pack(pady=(0, 8))


def add_ship_dialog(parent):
    """Create add ship dialog"""
    return ShipDialog(parent, "Add New Ship", ship=None)


def edit_ship_dialog(parent, ship, simulation_context=None):
    """Create edit ship dialog
    
    Args:
        parent: Parent window
        ship: Ship object to edit
        simulation_context: Dict with simulation info:
            - is_simulating: bool
            - is_ship_in_simulation: bool  
            - ship_index: int
            - update_callback: function to call when ship is updated
    """
    return ShipDialog(parent, f"Edit: {ship.name}", ship=ship, simulation_context=simulation_context)
