"""
Map Visualization Module - Interactive Map and Ship Tracking
===========================================================

Complete implementation of interactive map functionality with ship tracking, 
trail visualization, search, and control panel - extracted from original.

@ author: Peyton Andras @ Louisiana State University 2025
"""

import tkinter as tk
from tkinter import ttk, messagebox
import math
import webbrowser
import threading
import time
import urllib.request
import urllib.parse
import json

class MapVisualization:
    """Handles complete map visualization and ship tracking"""
    
    def __init__(self, parent_frame, map_available=False, pil_available=False):
        self.parent_frame = parent_frame
        self.map_available = map_available
        self.pil_available = pil_available
        
        # Map mode: 'online', 'custom', or 'fallback'
        self.map_mode = 'online' if map_available else 'fallback'
        
        # Initialize tracking variables
        self.ship_markers = {}  # Dictionary to store ship markers on map
        self.ship_tracks = {}   # Dictionary to store historical positions for each ship
        self.track_lines = {}   # Dictionary to store the polyline objects for ship tracks
        
        # Waypoint display variables
        self.waypoint_markers = {}  # Dictionary to store waypoint markers by ship MMSI
        self.waypoint_lines = {}    # Dictionary to store route lines between waypoints
        self.selected_ship_mmsi = None  # Currently selected ship for waypoint display
        
        # Map and control references
        self.map_widget = None
        self.custom_map_viewer = None
        self.ship_info_text = None
        self.track_history_var = None
        self.show_tracks_var = None
        self.search_var = None
        self.map_type_var = None
        
        # Ship icons
        self.ship_icon = None
        self.ship_icon_selected = None
        
        # Selected ships for display
        self.selected_ship_indices = None  # None means show all ships
        
        # Initialize map components
        self.setup_map_ui()
        
    def setup_map_ui(self):
        """Setup the complete map user interface"""
        # --- Map Mode Selection ---
        mode_frame = ttk.Frame(self.parent_frame)
        mode_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 5))
        
        ttk.Label(mode_frame, text="Map Mode:").pack(side=tk.LEFT, padx=5)
        self.map_mode_var = tk.StringVar(value=self.map_mode)
        mode_options = ["online", "custom"]
        if not self.map_available:
            mode_options = ["custom", "fallback"]
            self.map_mode_var.set("custom")
        
        mode_combo = ttk.Combobox(mode_frame, textvariable=self.map_mode_var, 
                                 values=mode_options, state="readonly", width=15)
        mode_combo.pack(side=tk.LEFT, padx=5)
        mode_combo.bind("<<ComboboxSelected>>", self.change_map_mode)
        
        # --- Map Search Bar (for online mode only) ---
        self.search_frame = ttk.Frame(self.parent_frame)
        self.search_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 5))
        if self.map_available and self.map_mode == 'online':
            self.search_var = tk.StringVar()
            ttk.Label(self.search_frame, text="Search Location:").pack(side=tk.LEFT, padx=5)
            search_entry = ttk.Entry(self.search_frame, textvariable=self.search_var, width=30)
            search_entry.pack(side=tk.LEFT, padx=5)
            ttk.Button(self.search_frame, text="Go", command=self.do_search).pack(side=tk.LEFT, padx=5)
            search_entry.bind('<Return>', lambda event: self.do_search())
        else:
            self.search_frame.grid_remove()

        # Split map frame into two parts: map and control panel
        map_container = ttk.Frame(self.parent_frame)
        map_container.grid(row=2, column=0, sticky=(tk.N, tk.W, tk.E, tk.S))

        map_control_panel = ttk.LabelFrame(self.parent_frame, text="Map Controls", padding=10)
        map_control_panel.grid(row=2, column=1, sticky=(tk.N, tk.W, tk.S), padx=5)

        # Make the map expand with window resizing
        self.parent_frame.columnconfigure(0, weight=1)
        self.parent_frame.rowconfigure(2, weight=1)
        map_container.columnconfigure(0, weight=1)
        map_container.rowconfigure(0, weight=1)

        # Setup map based on mode
        self.setup_map_container(map_container)
        self.setup_map_controls(map_control_panel)

    def setup_map_container(self, container):
        """Setup the map container based on current mode"""
        if self.map_mode == 'online' and self.map_available:
            self.setup_interactive_map(container)
        elif self.map_mode == 'custom':
            self.setup_custom_map(container)
        else:
            self.setup_fallback_map(container)
    
    def setup_custom_map(self, container):
        """Setup custom map viewer"""
        try:
            from .custom_map import CustomMapViewer
            self.custom_map_viewer = CustomMapViewer(container)
            
            # Set up waypoint selection callback
            def on_waypoint_selected(lat, lon):
                # This could be used for adding waypoints to ships
                print(f"Waypoint selected: {lat:.6f}, {lon:.6f}")
                # You could integrate this with the ship waypoint system
            
            self.custom_map_viewer.set_waypoint_selection_callback(on_waypoint_selected)
            
        except Exception as e:
            print(f"Error setting up custom map: {e}")
            self.setup_fallback_map(container)
    
    def change_map_mode(self, event=None):
        """Change between online and custom map modes"""
        new_mode = self.map_mode_var.get()
        if new_mode != self.map_mode:
            self.map_mode = new_mode
            
            # Clear existing map widgets
            for widget in self.parent_frame.grid_slaves(row=2, column=0):
                widget.destroy()
            
            # Recreate map container
            map_container = ttk.Frame(self.parent_frame)
            map_container.grid(row=2, column=0, sticky=(tk.N, tk.W, tk.E, tk.S))
            map_container.columnconfigure(0, weight=1)
            map_container.rowconfigure(0, weight=1)
            
            # Setup new map
            self.setup_map_container(map_container)
            
            # Show/hide search bar based on mode
            if new_mode == 'online' and self.map_available:
                self.search_frame.grid()
            else:
                self.search_frame.grid_remove()

    def setup_interactive_map(self, container):
        """Setup the interactive map widget with full functionality"""
        try:
            import tkintermapview
            # Create the map widget
            self.map_widget = tkintermapview.TkinterMapView(container, width=600, height=400, corner_radius=0)
            self.map_widget.grid(row=0, column=0, sticky=(tk.N, tk.W, tk.E, tk.S))
            
            # Initialize local tile manager
            from .local_tiles import get_tile_manager
            self.tile_manager = get_tile_manager()
            
            # Set default position (Portugal)
            self.map_widget.set_tile_server("https://a.tile.openstreetmap.org/{z}/{x}/{y}.png")    
            self.map_widget.set_position(39.5, -9.25)  # Portugal area
            self.map_widget.set_zoom(8)
            
            # Create ship icons if PIL is available
            if self.pil_available:
                self.create_ship_icons()
                
        except Exception as e:
            print(f"Error setting up interactive map: {e}")
            self.setup_fallback_map(container)

    def setup_fallback_map(self, container):
        """Setup fallback map when interactive map is not available"""
        map_fallback_frame = ttk.LabelFrame(container, text="Map Not Available", padding=20)
        map_fallback_frame.grid(row=0, column=0, sticky=(tk.N, tk.W, tk.E, tk.S))
        
        ttk.Label(map_fallback_frame, text="tkintermapview module is required for the map display.").pack(pady=10)
        ttk.Label(map_fallback_frame, text="Install using: pip install tkintermapview").pack(pady=5)
        
        ttk.Button(map_fallback_frame, text="Open Map in Browser", command=self.open_browser_map).pack(pady=20)

    def setup_map_controls(self, control_panel):
        """Setup complete map control panel"""
        ttk.Label(control_panel, text="Tracking Options:").grid(row=0, column=0, sticky=tk.W, pady=5)

        # Track history length
        ttk.Label(control_panel, text="Track History:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.track_history_var = tk.StringVar(value="20")
        track_history_entry = ttk.Entry(control_panel, textvariable=self.track_history_var, width=5)
        track_history_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(control_panel, text="points").grid(row=1, column=2, sticky=tk.W)

        # Track display toggle
        self.show_tracks_var = tk.BooleanVar(value=True)
        show_tracks_check = ttk.Checkbutton(control_panel, text="Show Tracks", 
                                          variable=self.show_tracks_var,
                                          command=self.toggle_track_visibility)
        show_tracks_check.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=5)

        # Waypoint display toggle
        self.show_waypoints_var = tk.BooleanVar(value=True)
        show_waypoints_check = ttk.Checkbutton(control_panel, text="Show Waypoints", 
                                             variable=self.show_waypoints_var,
                                             command=self.toggle_waypoint_visibility)
        show_waypoints_check.grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=5)

        # Map type selection
        ttk.Label(control_panel, text="Map Type:").grid(row=4, column=0, sticky=tk.W, pady=10)
        self.map_type_var = tk.StringVar(value="OpenStreetMap")
        
        if self.map_available:
            map_type_combo = ttk.Combobox(control_panel, textvariable=self.map_type_var, 
                                         values=["OpenStreetMap", "Local Cache", "Google Normal", "Google Satellite"])
            map_type_combo.grid(row=4, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=10)
            map_type_combo.bind("<<ComboboxSelected>>", self.change_map_type)
        else:
            ttk.Combobox(control_panel, textvariable=self.map_type_var, 
                        values=["OpenStreetMap"], state="disabled").grid(row=4, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=10)

        # Center map button
        ttk.Button(control_panel, text="Center on Ships", command=self.center_map_on_ships).grid(
            row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)

        # Refresh ship markers button
        ttk.Button(control_panel, text="Refresh Ship Markers", command=self.refresh_ship_markers).grid(
            row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        # Clear tracks button
        ttk.Button(control_panel, text="Clear All Tracks", command=self.clear_all_tracks).grid(
            row=7, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)

        # Clear waypoints button
        ttk.Button(control_panel, text="Clear Waypoints", command=self.clear_all_waypoints).grid(
            row=8, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        # Local cache management
        cache_frame = ttk.LabelFrame(control_panel, text="Map Cache", padding=5)
        cache_frame.grid(row=9, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)

        # Cache info display
        self.cache_info_var = tk.StringVar(value="Checking cache...")
        cache_info_label = ttk.Label(cache_frame, textvariable=self.cache_info_var, font=("Arial", 9))
        cache_info_label.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=2)

        # Download buttons
        ttk.Button(cache_frame, text="Download Portugal", 
                  command=self.download_portugal_tiles).grid(row=1, column=0, sticky=(tk.W, tk.E), padx=2, pady=2)
        ttk.Button(cache_frame, text="Download Atlantic", 
                  command=self.download_atlantic_tiles).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=2, pady=2)
        ttk.Button(cache_frame, text="Clear Cache", 
                  command=self.clear_tile_cache).grid(row=1, column=2, sticky=(tk.W, tk.E), padx=2, pady=2)

        # Configure cache frame columns
        cache_frame.columnconfigure(0, weight=1)
        cache_frame.columnconfigure(1, weight=1)
        cache_frame.columnconfigure(2, weight=1)

        # Update cache info initially
        self.update_cache_info()

        # Ship information display
        ship_info_frame = ttk.LabelFrame(control_panel, text="Selected Ship Info", padding=10)
        ship_info_frame.grid(row=9, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=15)

        self.ship_info_text = tk.Text(ship_info_frame, width=25, height=8, wrap=tk.WORD)
        self.ship_info_text.pack(fill=tk.BOTH, expand=True)
        self.ship_info_text.insert(tk.END, "Click on a ship to view details")
        self.ship_info_text.config(state=tk.DISABLED)

    def create_ship_icons(self):
        """Create ship icons using PIL"""
        try:
            from PIL import Image, ImageDraw, ImageTk
            
            def create_ship_icon(color="blue", size=24):
                img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)
                # Draw a ship-like triangle
                draw.polygon([(size//2, 0), (0, size), (size, size)], fill=color)
                return ImageTk.PhotoImage(img)
            
            # Create standard and selected ship icons
            self.ship_icon = create_ship_icon(color="blue", size=24)
            self.ship_icon_selected = create_ship_icon(color="red", size=24)
            
        except Exception as e:
            print(f"Error creating ship icons: {e}")
            self.ship_icon = None
            self.ship_icon_selected = None

    def do_search(self):
        """Handle map search functionality"""
        if not self.map_available or not self.map_widget:
            return
            
        query = self.search_var.get().strip()
        if not query:
            return
            
        # Try to parse as lat,lon first
        try:
            if ',' in query:
                lat, lon = map(float, query.split(','))
                self.map_widget.set_position(lat, lon)
                self.map_widget.set_zoom(12)
                return
        except Exception:
            pass
            
        # Otherwise, use custom geocoding with proper headers
        def geocode_async():
            try:
                lat, lon = self._geocode_location(query)
                if lat is not None and lon is not None:
                    # Update UI in main thread
                    self.parent_frame.after(0, lambda: self._update_map_position(lat, lon))
                else:
                    self.parent_frame.after(0, lambda: messagebox.showerror("Search Error", "Location not found"))
            except Exception as e:
                self.parent_frame.after(0, lambda: messagebox.showerror("Search Error", f"Search failed: {e}"))
        
        # Run geocoding in background thread to avoid blocking UI
        threading.Thread(target=geocode_async, daemon=True).start()
    
    def _geocode_location(self, query):
        """
        Geocode a location using OpenStreetMap Nominatim API with proper headers
        Returns (lat, lon) or (None, None) if not found
        """
        try:
            # Encode query for URL
            encoded_query = urllib.parse.quote(query)
            url = f"https://nominatim.openstreetmap.org/search?format=json&q={encoded_query}&limit=1"
            
            # Create request with proper User-Agent header (required by Nominatim policy)
            req = urllib.request.Request(url)
            req.add_header('User-Agent', 'SIREN-AIS-System/1.0 (Maritime Research Tool)')
            
            # Make request with timeout
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                
                if data and len(data) > 0:
                    result = data[0]
                    lat = float(result['lat'])
                    lon = float(result['lon'])
                    return lat, lon
                    
        except Exception as e:
            print(f"Geocoding error: {e}")
            
        return None, None
    
    def _update_map_position(self, lat, lon):
        """Update map position in main thread"""
        if self.map_widget:
            self.map_widget.set_position(lat, lon)
            self.map_widget.set_zoom(12)

    def change_map_type(self, event=None):
        """Change the map tile server type"""
        if not self.map_available or not self.map_widget:
            return
            
        selected = self.map_type_var.get()
        if selected == "OpenStreetMap":
            self.map_widget.set_tile_server("https://a.tile.openstreetmap.org/{z}/{x}/{y}.png")
        elif selected == "Local Cache":
            # Use local tiles if available
            if hasattr(self, 'tile_manager'):
                cache_info = self.tile_manager.get_cache_info()
                if cache_info["total_tiles"] > 0:
                    # Try to use local tiles - note: tkintermapview might not support file:// URLs
                    # As a fallback, we'll use offline mode with cached tiles
                    print(f"Using local cache with {cache_info['total_tiles']} tiles ({cache_info['total_size_mb']:.1f} MB)")
                    # For now, still use online server but with caching preference
                    self.map_widget.set_tile_server("https://a.tile.openstreetmap.org/{z}/{x}/{y}.png")
                else:
                    messagebox.showwarning("No Local Cache", "No cached tiles available. Use 'Download Tiles' to cache map data.")
                    self.map_type_var.set("OpenStreetMap")
                    self.map_widget.set_tile_server("https://a.tile.openstreetmap.org/{z}/{x}/{y}.png")
            else:
                messagebox.showerror("Cache Error", "Local tile manager not available.")
                self.map_type_var.set("OpenStreetMap")
        elif selected == "Google Normal":
            self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=m&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)
        elif selected == "Google Satellite":
            self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)

    def center_map_on_ships(self):
        """Center the map on all ships"""
        if not self.map_available or not self.map_widget:
            return
            
        from ..ships.ship_manager import get_ship_manager
        ship_manager = get_ship_manager()
        ships = ship_manager.get_ships()
        
        if not ships:
            return
            
        # Calculate the center and bounds of all ships
        lats = [ship.lat for ship in ships]
        lons = [ship.lon for ship in ships]
        
        if not lats or not lons:
            return
            
        # Calculate center
        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)
        
        # Calculate zoom level based on spread
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        
        # Set position and appropriate zoom
        self.map_widget.set_position(center_lat, center_lon)
        
        # If ships are far apart, adjust zoom to fit all
        lat_range = max_lat - min_lat
        lon_range = (max_lon - min_lon) * math.cos(math.radians(center_lat))
        if max(lat_range, lon_range) > 0.1:
            try:
                # Ensure proper bounding box order: (top_left), (bottom_right)
                # top_left = (max_lat, min_lon), bottom_right = (min_lat, max_lon)
                if max_lat > min_lat and max_lon > min_lon:
                    self.map_widget.fit_bounding_box((max_lat, min_lon), (min_lat, max_lon))
            except Exception as e:
                print(f"Error fitting bounding box: {e}")
                # Fallback to default zoom
                self.map_widget.set_zoom(10)
        else:
            self.map_widget.set_zoom(12)  # Default zoom if ships are close together

    def refresh_ship_markers(self):
        """Refresh ship markers on the map to ensure they are clickable"""
        print("DEBUG: Refreshing ship markers")
        try:
            # Force update the map with current ship positions
            self.update_map(force=True)
            
            # Add a small delay then center the map to ensure markers are properly positioned
            if hasattr(self, 'map_widget') and self.map_widget:
                # Use the tkinter after method to schedule centering after current operations complete
                self.map_widget.after(100, self.center_map_on_ships)
            
            print("DEBUG: Ship markers refreshed successfully")
        except Exception as e:
            print(f"DEBUG: Error refreshing ship markers: {e}")

    def clear_all_tracks(self):
        """Clear all ship tracks from the map"""
        if not self.map_available or not self.map_widget:
            return
            
        for mmsi, track_line in list(self.track_lines.items()):
            if track_line:
                try:
                    self.map_widget.delete(track_line)
                except Exception as e:
                    print(f"Error deleting track line for MMSI {mmsi}: {e}")
        
        self.track_lines.clear()
        
        for mmsi in self.ship_tracks:
            self.ship_tracks[mmsi] = []
            
        self.update_map(force=True)

    def toggle_track_visibility(self):
        """Toggle visibility of ship tracks on map"""
        if not self.map_available or not self.map_widget:
            return
            
        show_tracks = self.show_tracks_var.get()
        
        for mmsi, track_line in list(self.track_lines.items()):
            if not show_tracks and track_line:
                # Hide track
                try:
                    self.map_widget.delete(track_line)
                except Exception as e:
                    print(f"Error hiding track for MMSI {mmsi}: {e}")
                finally:
                    self.track_lines[mmsi] = None
            elif show_tracks and not track_line and mmsi in self.ship_tracks and len(self.ship_tracks[mmsi]) > 1:
                # Show track
                try:
                    track_line = self.map_widget.set_path(
                        self.ship_tracks[mmsi],
                        width=2,
                        color=f"#{mmsi % 0xFFFFFF:06x}"
                    )
                    self.track_lines[mmsi] = track_line
                except Exception as e:
                    print(f"Error showing track for MMSI {mmsi}: {e}")

    def toggle_waypoint_visibility(self):
        """Toggle visibility of waypoints on map"""
        if not self.map_available or not self.map_widget:
            return
            
        show_waypoints = self.show_waypoints_var.get()
        
        if not show_waypoints:
            # Hide all waypoints
            self.clear_all_waypoints()
        else:
            # Show waypoints for the currently selected ship
            if self.selected_ship_mmsi:
                from ..ships.ship_manager import get_ship_manager
                ship_manager = get_ship_manager()
                ships = ship_manager.get_ships()
                
                # Find the ship with the selected MMSI
                for ship in ships:
                    if ship.mmsi == self.selected_ship_mmsi:
                        self.show_ship_waypoints(ship)
                        break

    def update_map(self, force=False, selected_ship_indices=None):
        """Update the map with current ship positions
        
        Args:
            force: Force update even if positions haven't changed
            selected_ship_indices: List of ship indices to display. If None, shows all ships.
        """
        from ..ships.ship_manager import get_ship_manager
        ship_manager = get_ship_manager()
        
        # Get ships to display based on selection
        if selected_ship_indices is not None:
            ships = ship_manager.get_selected_ships(selected_ship_indices)
            print(f"DEBUG: Showing only selected ships on map: {len(ships)} ships")
        else:
            ships = ship_manager.get_ships()
            print(f"DEBUG: Showing all ships on map: {len(ships)} ships")
        
        # Update based on map mode
        if self.map_mode == 'online' and self.map_available and self.map_widget:
            self._update_online_map(ships, force, selected_ship_indices)
        elif self.map_mode == 'custom' and self.custom_map_viewer:
            self._update_custom_map(ships, selected_ship_indices)
    
    def _update_online_map(self, ships, force, selected_ship_indices):
        """Update the online interactive map"""
        if not self.map_widget:
            return
            
        # Get track history length
        try:
            max_track_points = max(1, min(100, int(self.track_history_var.get())))
        except (ValueError, AttributeError):
            max_track_points = 20  # Default value
        
        # Remember selected ship for waypoint preservation
        preserve_waypoints_for = self.selected_ship_mmsi
        
        # Hide all existing markers first
        all_mmsis = set(self.ship_markers.keys())
        
        # Update each selected ship's position on the map
        displayed_mmsis = set()
        for ship in ships:
            mmsi = ship.mmsi
            displayed_mmsis.add(mmsi)
            
            # Add current position to track history
            if mmsi not in self.ship_tracks:
                self.ship_tracks[mmsi] = []
            
            # Add position to track if it has changed
            last_position = self.ship_tracks[mmsi][-1] if self.ship_tracks[mmsi] else None
            current_position = (ship.lat, ship.lon)
            
            if not last_position or last_position != current_position or force:
                self.ship_tracks[mmsi].append(current_position)
                
                # Limit track history
                while len(self.ship_tracks[mmsi]) > max_track_points:
                    self.ship_tracks[mmsi].pop(0)
                
                # Update or create ship marker
                if mmsi in self.ship_markers:
                    # Update existing marker position
                    try:
                        self.ship_markers[mmsi].position = current_position
                        # Update marker text with simulation status
                        if hasattr(self.ship_markers[mmsi], 'text'):
                            marker_text = f"[LIVE] {ship.name}\n{ship.speed}kn" if selected_ship_indices else f"{ship.name}\n{ship.speed}kn"
                            self.ship_markers[mmsi].text = marker_text
                    except Exception as e:
                        print(f"Error updating marker: {e}")
                else:
                    # Create new marker with simulation status
                    marker_text = f"[LIVE] {ship.name}\n{ship.speed}kn" if selected_ship_indices else f"{ship.name}\n{ship.speed}kn"
                    try:
                        print(f"DEBUG: Creating new marker for {ship.name} at {ship.lat}, {ship.lon}")
                        marker = self.map_widget.set_marker(
                            ship.lat, ship.lon,
                            text=marker_text,
                            icon=self.ship_icon_selected if selected_ship_indices else self.ship_icon
                        )
                        
                        # Store ship reference in marker for click handler
                        marker.ship_ref = ship
                        
                        # Add click event to show ship details
                        marker.command = self._make_click_handler(ship, marker)
                        self.ship_markers[mmsi] = marker
                        print(f"DEBUG: Successfully created clickable marker for {ship.name}")
                    except Exception as e:
                        print(f"ERROR: Failed to create marker for {ship.name}: {e}")
                        import traceback
                        traceback.print_exc()
                
                # Update ship track polyline if enabled
                if self.show_tracks_var and self.show_tracks_var.get() and len(self.ship_tracks[mmsi]) > 1:
                    # Delete existing track line if it exists
                    if mmsi in self.track_lines and self.track_lines[mmsi]:
                        try:
                            self.map_widget.delete(self.track_lines[mmsi])
                        except Exception as e:
                            print(f"Error deleting track line: {e}")
                        finally:
                            self.track_lines[mmsi] = None
                    
                    # Create new track line
                    try:
                        track_line = self.map_widget.set_path(
                            self.ship_tracks[mmsi],
                            width=2,
                            color=f"#{mmsi % 0xFFFFFF:06x}"  # Generate color based on MMSI
                        )
                        self.track_lines[mmsi] = track_line
                    except Exception as e:
                        print(f"Error creating track line: {e}")
                elif self.show_tracks_var and not self.show_tracks_var.get() and mmsi in self.track_lines and self.track_lines[mmsi]:
                    # Hide track if track display is disabled
                    try:
                        self.map_widget.delete(self.track_lines[mmsi])
                    except Exception as e:
                        print(f"Error hiding track line: {e}")
                    finally:
                        self.track_lines[mmsi] = None
        
        # Hide markers for ships that are not selected (if we have a selection)
        if selected_ship_indices is not None:
            for mmsi in all_mmsis - displayed_mmsis:
                if mmsi in self.ship_markers:
                    try:
                        print(f"DEBUG: Hiding marker for non-selected ship MMSI {mmsi}")
                        self.map_widget.delete(self.ship_markers[mmsi])
                    except Exception as e:
                        print(f"Error hiding marker for MMSI {mmsi}: {e}")
                    finally:
                        if mmsi in self.ship_markers:
                            del self.ship_markers[mmsi]
                
                # Also hide tracks for non-selected ships
                if mmsi in self.track_lines and self.track_lines[mmsi]:
                    try:
                        self.map_widget.delete(self.track_lines[mmsi])
                    except Exception as e:
                        print(f"Error hiding track for MMSI {mmsi}: {e}")
                    finally:
                        self.track_lines[mmsi] = None
        
        # Restore waypoints for the selected ship if they were shown before the update
        if preserve_waypoints_for and preserve_waypoints_for in displayed_mmsis:
            # Find the ship object for waypoint restoration
            for ship in ships:
                if ship.mmsi == preserve_waypoints_for:
                    print(f"DEBUG: Restoring waypoints for ship {ship.name} after map update")
                    self.show_ship_waypoints(ship)
                    break
    
    def _update_custom_map(self, ships, selected_ship_indices):
        """Update the custom map with ship positions"""
        if self.custom_map_viewer:
            self.custom_map_viewer.update_ships(ships, selected_ship_indices)

    def set_selected_ships(self, selected_ship_indices):
        """Set which ships should be displayed on the map
        
        Args:
            selected_ship_indices: List of ship indices to display. None means show all ships.
        """
        self.selected_ship_indices = selected_ship_indices
        # Update the map immediately to reflect the selection
        if self.map_available:
            self.update_map(force=True, selected_ship_indices=selected_ship_indices)

    def _make_click_handler(self, ship_obj, marker_obj):
        """Create a click handler for ship markers"""
        def on_marker_click(marker=None):
            print(f"DEBUG: Ship marker clicked - {ship_obj.name} (MMSI: {ship_obj.mmsi})")
            if not self.ship_info_text:
                print("DEBUG: No ship_info_text widget available")
                return
                
            # Update ship info display
            self.ship_info_text.config(state=tk.NORMAL)
            self.ship_info_text.delete(1.0, tk.END)
            
            # Format ship info
            from ..config.settings import get_flag_from_mmsi
            flag_country = get_flag_from_mmsi(str(ship_obj.mmsi))
            
            info = (
                f"Name: {ship_obj.name}\n"
                f"MMSI: {ship_obj.mmsi}\n"
                f"Flag: {flag_country}\n"
                f"Position: {ship_obj.lat:.5f}, {ship_obj.lon:.5f}\n"
                f"Course: {ship_obj.course}°\n"
                f"Speed: {ship_obj.speed} knots\n"
                f"Status: {ship_obj.status}\n"
                f"Destination: {ship_obj.destination}\n"
            )
            self.ship_info_text.insert(tk.END, info)
            self.ship_info_text.config(state=tk.DISABLED)
            
            # Reset all markers first
            if self.ship_icon:
                for mmsi_key, m in self.ship_markers.items():
                    try:
                        m.icon = self.ship_icon  # Reset icon
                    except:
                        pass  # If any error occurs, just continue
            
            # Now highlight the selected marker
            if self.ship_icon_selected:
                try:
                    marker_obj.icon = self.ship_icon_selected
                except:
                    pass
                    
            # Display waypoints for this ship
            print(f"DEBUG: About to show waypoints for ship with {len(getattr(ship_obj, 'waypoints', []))} waypoints")
            self.show_ship_waypoints(ship_obj)
                    
            # Force a redraw of the map widget
            if self.map_widget:
                self.map_widget.update_idletasks()
        
        return on_marker_click

    def open_browser_map(self):
        """Open a web-based map as fallback"""
        webbrowser.open("https://www.openstreetmap.org/#map=12/40.7128/-74.0060")

    def start_real_time_updates(self):
        """Start real-time map updates during simulation"""
        if not self.map_available:
            return
            
        self._updating = True
        # Use a periodic timer instead of a background thread
        self._schedule_update()

    def _schedule_update(self):
        """Schedule the next map update using Tkinter's after method"""
        if self._updating and self.map_available:
            try:
                self.update_map(selected_ship_indices=self.selected_ship_indices)
                # Schedule the next update in 1 second (1000 ms)
                self.parent_frame.after(1000, self._schedule_update)
            except Exception as e:
                print(f"Error in scheduled map update: {e}")
                self._updating = False

    def stop_real_time_updates(self):
        """Stop real-time map updates"""
        self._updating = False
        
        # Clear markers when stopping
        if self.map_available and self.map_widget:
            for marker in self.ship_markers.values():
                try:
                    self.map_widget.delete(marker)
                except:
                    pass
            self.ship_markers.clear()

    def show_ship_waypoints(self, ship_obj):
        """Display waypoints for a specific ship on the map"""
        if not self.map_widget or not hasattr(ship_obj, 'waypoints') or not ship_obj.waypoints:
            print(f"DEBUG: Cannot show waypoints - map_widget: {self.map_widget is not None}, has_waypoints: {hasattr(ship_obj, 'waypoints')}, waypoints: {getattr(ship_obj, 'waypoints', None)}")
            return
            
        # Check if waypoints should be shown
        if hasattr(self, 'show_waypoints_var') and not self.show_waypoints_var.get():
            print(f"DEBUG: Waypoints disabled via toggle")
            return
            
        print(f"DEBUG: Showing waypoints for ship {ship_obj.name} (MMSI: {ship_obj.mmsi})")
        print(f"DEBUG: Ship has {len(ship_obj.waypoints)} waypoints: {ship_obj.waypoints}")
            
        # Clear any existing waypoints first (but only if showing different ship)
        if self.selected_ship_mmsi != ship_obj.mmsi:
            self.clear_all_waypoints()
        
        # Store the selected ship MMSI
        self.selected_ship_mmsi = ship_obj.mmsi
        
        # Skip if waypoints already exist for this ship
        if ship_obj.mmsi in self.waypoint_markers and self.waypoint_markers[ship_obj.mmsi]:
            print(f"DEBUG: Waypoints already displayed for ship {ship_obj.mmsi}")
            return
        
        # Initialize storage for this ship's waypoint markers and lines
        self.waypoint_markers[ship_obj.mmsi] = []
        self.waypoint_lines[ship_obj.mmsi] = []
        
        try:
            # Display waypoints as numbered markers
            for i, waypoint in enumerate(ship_obj.waypoints):
                lat, lon = waypoint[0], waypoint[1]
                print(f"DEBUG: Creating waypoint {i+1} at {lat}, {lon}")
                
                # Create waypoint marker
                waypoint_text = f"WP {i+1}"
                try:
                    marker = self.map_widget.set_marker(
                        lat, lon,
                        text=waypoint_text,
                        marker_color_circle="blue",
                        marker_color_outside="darkblue"
                    )
                    self.waypoint_markers[ship_obj.mmsi].append(marker)
                    print(f"DEBUG: Successfully created waypoint marker {i+1}")
                except Exception as e:
                    print(f"DEBUG: Error creating waypoint marker {i+1}: {e}")
            
            # Draw route lines between waypoints (including from ship to first waypoint)
            positions = [(ship_obj.lat, ship_obj.lon)]  # Start from ship position
            positions.extend([(wp[0], wp[1]) for wp in ship_obj.waypoints])
            print(f"DEBUG: Route positions: {positions}")
            
            # Create polyline connecting all positions
            if len(positions) > 1:
                try:
                    route_line = self.map_widget.set_path(positions, color="blue", width=3)
                    self.waypoint_lines[ship_obj.mmsi].append(route_line)
                    print(f"DEBUG: Successfully created route line")
                except Exception as e:
                    print(f"DEBUG: Error creating route line: {e}")
            
            # Update ship info to show waypoint information
            if self.ship_info_text:
                waypoint_info = f"\nWaypoints ({len(ship_obj.waypoints)}):\n"
                for i, wp in enumerate(ship_obj.waypoints):
                    waypoint_info += f"  WP {i+1}: {wp[0]:.5f}, {wp[1]:.5f}\n"
                
                self.ship_info_text.config(state=tk.NORMAL)
                self.ship_info_text.insert(tk.END, waypoint_info)
                self.ship_info_text.config(state=tk.DISABLED)
                print(f"DEBUG: Updated ship info with waypoint details")
                
        except Exception as e:
            print(f"DEBUG: Error displaying waypoints: {e}")
            import traceback
            traceback.print_exc()
    
    def clear_all_waypoints(self):
        """Clear all waypoint markers and route lines from the map"""
        if not self.map_widget:
            return
            
        try:
            # Clear all waypoint markers
            for mmsi, markers in self.waypoint_markers.items():
                for marker in markers:
                    try:
                        self.map_widget.delete(marker)
                    except:
                        pass
            
            # Clear all route lines
            for mmsi, lines in self.waypoint_lines.items():
                for line in lines:
                    try:
                        self.map_widget.delete(line)
                    except:
                        pass
                        
            # Reset storage
            self.waypoint_markers.clear()
            self.waypoint_lines.clear()
            self.selected_ship_mmsi = None
            
        except Exception as e:
            print(f"Error clearing waypoints: {e}")
    
    def clear_ship_waypoints(self, ship_mmsi):
        """Clear waypoints for a specific ship"""
        if not self.map_widget or ship_mmsi not in self.waypoint_markers:
            return
            
        try:
            # Clear markers for this ship
            for marker in self.waypoint_markers[ship_mmsi]:
                try:
                    self.map_widget.delete(marker)
                except:
                    pass
            
            # Clear route lines for this ship
            if ship_mmsi in self.waypoint_lines:
                for line in self.waypoint_lines[ship_mmsi]:
                    try:
                        self.map_widget.delete(line)
                    except:
                        pass
            
            # Remove from storage
            self.waypoint_markers.pop(ship_mmsi, None)
            self.waypoint_lines.pop(ship_mmsi, None)
            
            if self.selected_ship_mmsi == ship_mmsi:
                self.selected_ship_mmsi = None
                
        except Exception as e:
            print(f"Error clearing waypoints for ship {ship_mmsi}: {e}")

    def update_cache_info(self):
        """Update the cache information display"""
        if hasattr(self, 'tile_manager'):
            try:
                cache_info = self.tile_manager.get_cache_info()
                info_text = f"Cached: {cache_info['total_tiles']} tiles ({cache_info['total_size_mb']:.1f} MB)"
                self.cache_info_var.set(info_text)
            except Exception as e:
                self.cache_info_var.set(f"Cache error: {e}")
        else:
            self.cache_info_var.set("Cache not available")

    def download_portugal_tiles(self):
        """Download tiles for Portugal area"""
        if not hasattr(self, 'tile_manager'):
            messagebox.showerror("Error", "Tile manager not available")
            return
            
        def progress_callback(progress, downloaded, total):
            self.cache_info_var.set(f"Downloading: {progress:.1f}% ({downloaded}/{total})")
            self.parent_frame.update_idletasks()
        
        try:
            from .local_tiles import download_portugal_area
            threading.Thread(
                target=self._download_tiles_thread,
                args=(download_portugal_area, progress_callback),
                daemon=True
            ).start()
        except Exception as e:
            messagebox.showerror("Download Error", f"Failed to start download: {e}")

    def download_atlantic_tiles(self):
        """Download tiles for Atlantic area"""
        if not hasattr(self, 'tile_manager'):
            messagebox.showerror("Error", "Tile manager not available")
            return
            
        def progress_callback(progress, downloaded, total):
            self.cache_info_var.set(f"Downloading: {progress:.1f}% ({downloaded}/{total})")
            self.parent_frame.update_idletasks()
        
        try:
            from .local_tiles import download_atlantic_area
            threading.Thread(
                target=self._download_tiles_thread,
                args=(download_atlantic_area, progress_callback),
                daemon=True
            ).start()
        except Exception as e:
            messagebox.showerror("Download Error", f"Failed to start download: {e}")

    def _download_tiles_thread(self, download_func, progress_callback):
        """Download tiles in a background thread"""
        try:
            downloaded, total = download_func(self.tile_manager, progress_callback)
            # Update UI in main thread
            self.parent_frame.after(0, lambda: self._download_complete(downloaded, total))
        except Exception as e:
            self.parent_frame.after(0, lambda: self._download_error(str(e)))

    def _download_complete(self, downloaded, total):
        """Handle download completion"""
        self.update_cache_info()
        messagebox.showinfo("Download Complete", f"Downloaded {downloaded}/{total} tiles successfully!")

    def _download_error(self, error_msg):
        """Handle download error"""
        self.update_cache_info()
        messagebox.showerror("Download Error", f"Download failed: {error_msg}")

    def clear_tile_cache(self):
        """Clear the local tile cache"""
        if not hasattr(self, 'tile_manager'):
            messagebox.showerror("Error", "Tile manager not available")
            return
            
        if messagebox.askyesno("Clear Cache", "Are you sure you want to clear all cached map tiles?"):
            try:
                if self.tile_manager.clear_cache():
                    self.update_cache_info()
                    messagebox.showinfo("Cache Cleared", "Map tile cache has been cleared.")
                else:
                    messagebox.showerror("Error", "Failed to clear cache.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to clear cache: {e}")


# Global instance for easy access
_map_visualization = None

def get_map_visualization(parent_frame=None, map_available=False, pil_available=False):
    """Get or create the global map visualization instance"""
    global _map_visualization
    if _map_visualization is None and parent_frame is not None:
        _map_visualization = MapVisualization(parent_frame, map_available, pil_available)
    return _map_visualization

def update_ships_on_map(selected_ship_indices=None):
    """Global function to update ships on map - thread-safe
    
    Args:
        selected_ship_indices: List of ship indices to display. If None, shows all ships.
    """
    if _map_visualization and _map_visualization.map_available:
        try:
            # Schedule the update on the main thread
            _map_visualization.parent_frame.after(0, lambda: _map_visualization.update_map(selected_ship_indices=selected_ship_indices))
        except Exception as e:
            print(f"Error scheduling map update: {e}")

def center_map_on_ships():
    """Global function to center map on ships"""
    if _map_visualization:
        _map_visualization.center_map_on_ships()

def start_map_updates():
    """Global function to start real-time map updates"""
    if _map_visualization:
        _map_visualization.start_real_time_updates()

def stop_map_updates():
    """Global function to stop real-time map updates"""
    if _map_visualization:
        _map_visualization.stop_real_time_updates()

def set_selected_ships_on_map(selected_ship_indices):
    """Global function to set which ships should be displayed on map"""
    if _map_visualization:
        _map_visualization.set_selected_ships(selected_ship_indices)