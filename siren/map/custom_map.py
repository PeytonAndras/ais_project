"""
Custom Map Module - Upload and Display Custom Nautical Charts
==============================================================

Handles uploading, calibrating, and displaying custom maps/nautical charts
with coordinate system support for waypoint selection.

@ author: Peyton Andras @ Louisiana State University 2025
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import json
import os
from PIL import Image, ImageTk
import math

class CustomMapViewer:
    """Handles custom map/nautical chart display and interaction"""
    
    def __init__(self, parent_frame):
        self.parent_frame = parent_frame
        self.map_image = None
        self.map_photo = None
        self.canvas = None
        self.scroll_frame = None
        
        # Map calibration data
        self.calibration_points = []  # List of {pixel: (x,y), coord: (lat,lon)}
        self.bounds = None  # {north, south, east, west}
        self.map_file_path = None
        
        # Ship tracking
        self.ship_markers = {}
        self.ship_tracks = {}
        self.track_lines = []
        
        # Interaction state
        self.calibration_mode = False
        self.waypoint_selection_callback = None
        
        self.setup_custom_map_ui()
        
    def setup_custom_map_ui(self):
        """Setup the custom map interface"""
        # Control panel
        control_frame = ttk.Frame(self.parent_frame, padding=10)
        control_frame.pack(side=tk.TOP, fill=tk.X)
        
        # Upload button
        ttk.Button(control_frame, text="Upload Map/Chart", 
                  command=self.upload_map).pack(side=tk.LEFT, padx=5)
        
        # Calibrate button
        self.calibrate_btn = ttk.Button(control_frame, text="Calibrate Map", 
                                       command=self.start_calibration, state=tk.DISABLED)
        self.calibrate_btn.pack(side=tk.LEFT, padx=5)
        
        # Save/Load calibration
        ttk.Button(control_frame, text="Save Calibration", 
                  command=self.save_calibration).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Load Calibration", 
                  command=self.load_calibration).pack(side=tk.LEFT, padx=5)
        
        # Status label
        self.status_label = ttk.Label(control_frame, text="No map loaded")
        self.status_label.pack(side=tk.RIGHT, padx=5)
        
        # Map display area with scrollbars
        map_frame = ttk.Frame(self.parent_frame)
        map_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create canvas with scrollbars
        self.canvas = tk.Canvas(map_frame, bg='lightblue')
        h_scrollbar = ttk.Scrollbar(map_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        v_scrollbar = ttk.Scrollbar(map_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        
        self.canvas.configure(xscrollcommand=h_scrollbar.set, yscrollcommand=v_scrollbar.set)
        
        # Grid layout
        self.canvas.grid(row=0, column=0, sticky=(tk.N, tk.W, tk.E, tk.S))
        h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        map_frame.columnconfigure(0, weight=1)
        map_frame.rowconfigure(0, weight=1)
        
        # Bind mouse events
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        
        # Default message
        self.canvas.create_text(400, 300, text="Upload a map or nautical chart to begin", 
                               font=("Arial", 16), fill="gray")
    
    def upload_map(self):
        """Upload a map or nautical chart image"""
        file_path = filedialog.askopenfilename(
            title="Select Map or Nautical Chart",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp *.tiff"),
                ("All files", "*.*")
            ]
        )
        
        if not file_path:
            return
            
        try:
            # Load and display the image
            self.map_image = Image.open(file_path)
            self.map_file_path = file_path
            
            # Resize if too large (keep aspect ratio)
            max_size = (2000, 2000)
            if self.map_image.size[0] > max_size[0] or self.map_image.size[1] > max_size[1]:
                self.map_image.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            self.map_photo = ImageTk.PhotoImage(self.map_image)
            
            # Clear canvas and display image
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.map_photo, tags="map_image")
            
            # Update canvas scroll region
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            
            # Enable calibration
            self.calibrate_btn.config(state=tk.NORMAL)
            self.status_label.config(text=f"Map loaded: {os.path.basename(file_path)}")
            
            # Reset calibration
            self.calibration_points = []
            self.bounds = None
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load map: {e}")
    
    def start_calibration(self):
        """Start map calibration process"""
        if not self.map_image:
            return
            
        if self.calibration_mode:
            self.finish_calibration()
            return
            
        self.calibration_mode = True
        self.calibrate_btn.config(text="Finish Calibration")
        self.status_label.config(text="Click on map to set calibration points")
        
        # Clear existing calibration points
        self.canvas.delete("calibration_point")
        self.calibration_points = []
        
        # Show instructions
        messagebox.showinfo("Map Calibration", 
                           "Click on known locations on the map.\n"
                           "You'll be asked to enter the latitude/longitude for each point.\n"
                           "Minimum 2 points required, 3+ recommended for accuracy.")
    
    def finish_calibration(self):
        """Finish calibration and calculate transformation"""
        if len(self.calibration_points) < 2:
            messagebox.showwarning("Insufficient Points", 
                                 "Need at least 2 calibration points to calibrate the map.")
            return
            
        self.calibration_mode = False
        self.calibrate_btn.config(text="Calibrate Map")
        
        # Calculate map bounds
        lats = [point['coord'][0] for point in self.calibration_points]
        lons = [point['coord'][1] for point in self.calibration_points]
        
        self.bounds = {
            'north': max(lats),
            'south': min(lats),
            'east': max(lons),
            'west': min(lons)
        }
        
        self.status_label.config(text=f"Map calibrated with {len(self.calibration_points)} points")
        messagebox.showinfo("Calibration Complete", 
                           f"Map calibrated successfully with {len(self.calibration_points)} points.")
    
    def on_canvas_click(self, event):
        """Handle canvas click events"""
        if self.calibration_mode:
            self.add_calibration_point(event.x, event.y)
        elif self.waypoint_selection_callback and self.bounds:
            # Convert pixel to coordinates and call waypoint callback
            lat, lon = self.pixel_to_coord(event.x, event.y)
            if lat is not None and lon is not None:
                self.waypoint_selection_callback(lat, lon)
    
    def add_calibration_point(self, x, y):
        """Add a calibration point"""
        # Get scroll offset
        canvas_x = self.canvas.canvasx(x)
        canvas_y = self.canvas.canvasy(y)
        
        # Ask user for coordinates
        coord_dialog = CoordinateDialog(self.parent_frame)
        if coord_dialog.result:
            lat, lon = coord_dialog.result
            
            # Add calibration point
            point = {
                'pixel': (canvas_x, canvas_y),
                'coord': (lat, lon)
            }
            self.calibration_points.append(point)
            
            # Draw point on map
            self.canvas.create_oval(canvas_x-5, canvas_y-5, canvas_x+5, canvas_y+5, 
                                  fill="red", outline="white", width=2, 
                                  tags="calibration_point")
            self.canvas.create_text(canvas_x+10, canvas_y-10, 
                                  text=f"{lat:.4f}, {lon:.4f}", 
                                  fill="red", font=("Arial", 8), 
                                  tags="calibration_point")
    
    def pixel_to_coord(self, pixel_x, pixel_y):
        """Convert pixel coordinates to lat/lon using calibration"""
        if len(self.calibration_points) < 2:
            return None, None
            
        # Simple linear interpolation for 2 points
        if len(self.calibration_points) == 2:
            p1, p2 = self.calibration_points[0], self.calibration_points[1]
            
            # Calculate ratios
            dx = p2['pixel'][0] - p1['pixel'][0]
            dy = p2['pixel'][1] - p1['pixel'][1]
            
            if dx == 0 or dy == 0:
                return None, None
                
            # Interpolate
            x_ratio = (pixel_x - p1['pixel'][0]) / dx
            y_ratio = (pixel_y - p1['pixel'][1]) / dy
            
            lat = p1['coord'][0] + y_ratio * (p2['coord'][0] - p1['coord'][0])
            lon = p1['coord'][1] + x_ratio * (p2['coord'][1] - p1['coord'][1])
            
            return lat, lon
        
        # For more complex transformations with 3+ points, use a simple averaging approach
        # In a production system, you'd want proper geodetic transformations
        return self._multi_point_interpolation(pixel_x, pixel_y)
    
    def _multi_point_interpolation(self, pixel_x, pixel_y):
        """Simple interpolation for multiple calibration points"""
        if not self.calibration_points:
            return None, None
            
        # Find weighted average based on inverse distance
        total_weight = 0
        weighted_lat = 0
        weighted_lon = 0
        
        for point in self.calibration_points:
            px, py = point['pixel']
            distance = math.sqrt((pixel_x - px)**2 + (pixel_y - py)**2)
            
            # Avoid division by zero
            if distance < 1:
                return point['coord']
                
            weight = 1.0 / distance
            total_weight += weight
            weighted_lat += point['coord'][0] * weight
            weighted_lon += point['coord'][1] * weight
        
        if total_weight > 0:
            return weighted_lat / total_weight, weighted_lon / total_weight
        
        return None, None
    
    def coord_to_pixel(self, lat, lon):
        """Convert lat/lon to pixel coordinates"""
        if len(self.calibration_points) < 2:
            return None, None
            
        # Reverse of pixel_to_coord
        if len(self.calibration_points) == 2:
            p1, p2 = self.calibration_points[0], self.calibration_points[1]
            
            # Calculate ratios
            dlat = p2['coord'][0] - p1['coord'][0]
            dlon = p2['coord'][1] - p1['coord'][1]
            
            if dlat == 0 or dlon == 0:
                return None, None
                
            # Calculate pixel position
            lat_ratio = (lat - p1['coord'][0]) / dlat
            lon_ratio = (lon - p1['coord'][1]) / dlon
            
            pixel_x = p1['pixel'][0] + lon_ratio * (p2['pixel'][0] - p1['pixel'][0])
            pixel_y = p1['pixel'][1] + lat_ratio * (p2['pixel'][1] - p1['pixel'][1])
            
            return pixel_x, pixel_y
        
        return self._multi_point_reverse_interpolation(lat, lon)
    
    def _multi_point_reverse_interpolation(self, lat, lon):
        """Reverse interpolation for multiple points"""
        # Simple approach: find closest calibration point and use its transformation
        min_distance = float('inf')
        closest_point = None
        
        for point in self.calibration_points:
            clat, clon = point['coord']
            distance = math.sqrt((lat - clat)**2 + (lon - clon)**2)
            if distance < min_distance:
                min_distance = distance
                closest_point = point
        
        if closest_point:
            # Use the closest point as a reference
            return closest_point['pixel']
        
        return None, None
    
    def update_ships(self, ships, selected_indices=None):
        """Update ship positions on the custom map"""
        if not self.map_image or not self.bounds:
            return
            
        # Clear existing ship markers
        self.canvas.delete("ship_marker")
        
        # Display ships
        ships_to_show = ships
        if selected_indices is not None:
            ships_to_show = [ships[i] for i in selected_indices if i < len(ships)]
        
        for ship in ships_to_show:
            pixel_x, pixel_y = self.coord_to_pixel(ship.lat, ship.lon)
            if pixel_x is not None and pixel_y is not None:
                # Draw ship marker
                self.canvas.create_oval(pixel_x-3, pixel_y-3, pixel_x+3, pixel_y+3,
                                      fill="blue", outline="white", width=1,
                                      tags="ship_marker")
                self.canvas.create_text(pixel_x+8, pixel_y-8, 
                                      text=ship.name, fill="blue", 
                                      font=("Arial", 8), tags="ship_marker")
    
    def set_waypoint_selection_callback(self, callback):
        """Set callback for waypoint selection"""
        self.waypoint_selection_callback = callback
    
    def save_calibration(self):
        """Save calibration data to file"""
        if not self.calibration_points or not self.map_file_path:
            messagebox.showwarning("No Calibration", "No calibration data to save.")
            return
            
        file_path = filedialog.asksaveasfilename(
            title="Save Calibration",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                calibration_data = {
                    'map_file': self.map_file_path,
                    'calibration_points': self.calibration_points,
                    'bounds': self.bounds
                }
                
                with open(file_path, 'w') as f:
                    json.dump(calibration_data, f, indent=2)
                    
                messagebox.showinfo("Success", "Calibration saved successfully.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save calibration: {e}")
    
    def load_calibration(self):
        """Load calibration data from file"""
        file_path = filedialog.askopenfilename(
            title="Load Calibration",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    calibration_data = json.load(f)
                
                # Load the associated map
                map_file = calibration_data['map_file']
                if os.path.exists(map_file):
                    self.map_file_path = map_file
                    self.map_image = Image.open(map_file)
                    
                    # Resize if needed
                    max_size = (2000, 2000)
                    if self.map_image.size[0] > max_size[0] or self.map_image.size[1] > max_size[1]:
                        self.map_image.thumbnail(max_size, Image.Resampling.LANCZOS)
                    
                    self.map_photo = ImageTk.PhotoImage(self.map_image)
                    
                    # Display image
                    self.canvas.delete("all")
                    self.canvas.create_image(0, 0, anchor=tk.NW, image=self.map_photo, tags="map_image")
                    self.canvas.configure(scrollregion=self.canvas.bbox("all"))
                    
                    # Load calibration data
                    self.calibration_points = calibration_data['calibration_points']
                    self.bounds = calibration_data['bounds']
                    
                    # Draw calibration points
                    for point in self.calibration_points:
                        x, y = point['pixel']
                        lat, lon = point['coord']
                        self.canvas.create_oval(x-5, y-5, x+5, y+5, 
                                              fill="red", outline="white", width=2, 
                                              tags="calibration_point")
                        self.canvas.create_text(x+10, y-10, 
                                              text=f"{lat:.4f}, {lon:.4f}", 
                                              fill="red", font=("Arial", 8), 
                                              tags="calibration_point")
                    
                    self.calibrate_btn.config(state=tk.NORMAL)
                    self.status_label.config(text=f"Loaded: {os.path.basename(map_file)}")
                    messagebox.showinfo("Success", "Calibration loaded successfully.")
                else:
                    messagebox.showerror("Error", f"Map file not found: {map_file}")
                    
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load calibration: {e}")
    
    def on_canvas_drag(self, event):
        """Handle canvas dragging for panning"""
        pass  # Could implement panning here
    
    def on_canvas_release(self, event):
        """Handle canvas mouse release"""
        pass
    
    def on_mouse_wheel(self, event):
        """Handle mouse wheel for zooming"""
        # Could implement zooming here
        pass


class CoordinateDialog:
    """Dialog for entering latitude/longitude coordinates"""
    
    def __init__(self, parent):
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Enter Coordinates")
        self.dialog.geometry("300x150")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - self.dialog.winfo_width()) // 2
        y = (self.dialog.winfo_screenheight() - self.dialog.winfo_height()) // 2
        self.dialog.geometry(f"+{x}+{y}")
        
        # Create widgets
        ttk.Label(self.dialog, text="Enter the coordinates for this point:").pack(pady=10)
        
        coord_frame = ttk.Frame(self.dialog)
        coord_frame.pack(pady=5)
        
        ttk.Label(coord_frame, text="Latitude:").grid(row=0, column=0, padx=5, pady=5)
        self.lat_var = tk.StringVar()
        ttk.Entry(coord_frame, textvariable=self.lat_var, width=15).grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(coord_frame, text="Longitude:").grid(row=1, column=0, padx=5, pady=5)
        self.lon_var = tk.StringVar()
        ttk.Entry(coord_frame, textvariable=self.lon_var, width=15).grid(row=1, column=1, padx=5, pady=5)
        
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="OK", command=self.ok_clicked).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel_clicked).pack(side=tk.LEFT, padx=5)
        
        # Wait for dialog
        self.dialog.wait_window()
    
    def ok_clicked(self):
        """Handle OK button"""
        try:
            lat = float(self.lat_var.get())
            lon = float(self.lon_var.get())
            
            # Basic validation
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                self.result = (lat, lon)
                self.dialog.destroy()
            else:
                messagebox.showerror("Invalid Coordinates", 
                                   "Latitude must be between -90 and 90.\n"
                                   "Longitude must be between -180 and 180.")
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid numeric coordinates.")
    
    def cancel_clicked(self):
        """Handle Cancel button"""
        self.dialog.destroy()
