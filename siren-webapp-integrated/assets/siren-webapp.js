/**
 * SIREN Integrated Web Application
 * Spoofed Identification & Real-time Emulation Node
 * 
 * This is a comprehensive maritime vessel simulation system that generates and transmits
 * spoofed AIS (Automatic Identification System) messages for testing and demonstration
 * purposes. The system allows users to create virtual ships, define waypoint-based
 * navigation, and broadcast realistic AIS data via GNU Radio.
 * 
 * MAIN FEATURES:
 * - Fleet Management: Create, edit, and organize virtual vessels
 * - Real-time Simulation: Move ships with realistic physics and navigation
 * - Waypoint Navigation: Define complex routes for autonomous ship movement
 * - AIS Message Generation: Create standards-compliant AIS Type 1 position reports
 * - GNU Radio Integration: Transmit AIS signals via software-defined radio
 * - Interactive Mapping: Visualize ship positions, tracks, and routes
 * - Offline Capability: Works without internet for secure/isolated environments
 * 
 * SECURITY NOTE: This tool is intended for authorized testing, research, and
 * demonstration purposes only. Unauthorized transmission of false AIS signals
 * is illegal and dangerous to maritime safety.
 * 
 * @author Peyton Andras @ Louisiana State University 2025
 * @version 1.0
 * @requires Bootstrap 5, Leaflet.js, Noty.js, GNU Radio backend
 */

class SIRENWebApp {
    /**
     * Constructor initializes the SIREN Web Application with all necessary
     * state variables and objects for ship simulation and AIS transmission.
     * 
     * The application manages several key data structures:
     * - ships: Array containing all vessel objects with navigation data
     * - simulation: Object controlling the real-time simulation loop
     * - websocket: Connection to GNU Radio backend for AIS transmission
     * - map: Leaflet map instance for visualization
     */
    constructor() {
        // Core fleet data - array of ship objects with navigation properties
        this.ships = [];
        
        // Currently selected ships for simulation (indices into ships array)
        this.selectedShips = [];
        
        // Simulation control object manages the real-time update loop
        this.simulation = {
            active: false,           // Whether simulation is currently running
            interval: 10,            // Update interval in seconds
            intervalId: null,        // JavaScript interval timer ID
            messageCount: 0,         // Total AIS messages transmitted
            startTime: null,         // Simulation start timestamp
            lockedSelection: [],     // Ships locked for simulation (prevents UI changes)
            selectedShipDetails: []  // Cached ship data for validation
        };
        
        // WebSocket connection to GNU Radio backend for AIS transmission
        this.websocket = null;
        this.isConnected = false;
        
        // UI state tracking
        this.currentShipIndex = -1;  // Currently edited ship (-1 = none)
        
        // Interactive map system using Leaflet.js
        this.map = null;              // Leaflet map instance
        this.mapState = null;         // Map-specific state and settings
        this.mapLayers = null;        // Available tile layers (online/offline)
        this.shipIcon = null;         // Default ship marker icon
        this.selectedShipIcon = null; // Highlighted ship marker icon
        
        // Initialize the application
        this.init();
    }

    /**
     * Initialize the SIREN application by loading saved data, setting up event handlers,
     * updating the UI, and establishing connection to the GNU Radio backend.
     * 
     * This is the main entry point that coordinates all system components.
     */
    init() {
        // Load previously saved ship fleet from browser localStorage
        this.loadShipsFromStorage();
        
        // Set up all DOM event listeners for user interactions
        this.setupEventListeners();
        
        // Refresh the user interface with current data
        this.updateUI();
        
        // Attempt to connect to the GNU Radio backend for AIS transmission
        this.connectToGNURadio();
        
        console.log(`SIREN Web Application initialized with ${this.ships.length} ships`);
        
        // Provide user guidance if no ships are loaded
        if (this.ships.length === 0) {
            console.log('No ships found in storage. You can load sample data using the "Load Sample" button in Fleet Management.');
        }
    }

    /**
     * Set up all DOM event listeners for user interactions.
     * This method binds click handlers, form submissions, keyboard events,
     * and Bootstrap tab switching events to their respective handler methods.
     * 
     * Event categories:
     * - Fleet Management: Add, edit, remove ships; load/save fleet data
     * - Simulation Control: Start/stop simulation with selected ships
     * - Transmission: Connect to GNU Radio and send test messages
     * - Map Interface: Tab switching, waypoint picking, map controls
     * - Keyboard: ESC to cancel waypoint picking mode
     */
    setupEventListeners() {
        // ===== FLEET MANAGEMENT EVENTS =====
        // Show modal dialog for adding new ships with random MMSI generation
        document.getElementById('addShipBtn').addEventListener('click', () => this.showAddShipModal());
        
        // Process new ship form submission with validation
        document.getElementById('saveShipBtn').addEventListener('click', () => this.addShip());
        
        // File input for loading saved fleet configurations (JSON format)
        document.getElementById('loadFleetBtn').addEventListener('click', () => this.loadFleet());
        
        // Export current fleet to downloadable JSON file
        document.getElementById('saveFleetBtn').addEventListener('click', () => this.saveFleet());
        
        // Load predefined sample ships for testing and demonstration
        document.getElementById('loadSampleBtn').addEventListener('click', () => this.loadSampleData());

        // ===== SIMULATION CONTROL EVENTS =====
        // Begin real-time ship movement and AIS transmission
        document.getElementById('startSimulationBtn').addEventListener('click', () => this.startSimulation());
        
        // Stop simulation and unlock ship selection UI
        document.getElementById('stopSimulationBtn').addEventListener('click', () => this.stopSimulation());

        // ===== GNU RADIO TRANSMISSION EVENTS =====
        // Establish WebSocket connection to GNU Radio backend
        document.getElementById('connectBtn').addEventListener('click', () => this.connectToGNURadio());
        
        // Send a predefined test AIS message to verify transmission
        document.getElementById('testTransmissionBtn').addEventListener('click', () => this.sendTestMessage());

        // ===== BOOTSTRAP TAB SWITCHING =====
        // Handle map tab activation with proper initialization and sizing
        document.addEventListener('shown.bs.tab', (e) => {
            if (e.target.id === 'map-tab') {
                // Initialize map when map tab is shown (with delay for DOM)
                setTimeout(() => {
                    if (!this.map) {
                        this.initializeMap();
                    } else {
                        // Map exists, just refresh to ensure proper sizing
                        this.map.invalidateSize();
                    }
                    // Force update ship positions when map tab is shown
                    this.updateShipPositions();
                }, 100);
            }
        });

        // ===== KEYBOARD EVENTS =====
        // ESC key cancels waypoint picking mode for user convenience
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.waypointPickingMode && this.waypointPickingMode.active) {
                this.disableWaypointPickingMode();
                this.showNotification('Waypoint picking cancelled', 'info');
            }
        });

        // ===== WAYPOINT CONTROL BUTTONS =====
        // Show all ship waypoints and routes on the map
        document.getElementById('showAllWaypointsBtn').addEventListener('click', () => this.showAllWaypoints());
        
        // Hide all waypoint markers and route lines
        document.getElementById('hideAllWaypointsBtn').addEventListener('click', () => this.hideAllWaypoints());
        
        // Center map view on all defined waypoints
        document.getElementById('centerOnWaypointsBtn').addEventListener('click', () => this.centerOnWaypoints());
    }

    // =====================================
    // SHIP FLEET MANAGEMENT FUNCTIONS
    // =====================================
    // This section handles creation, modification, and removal of virtual ships.
    // Each ship object contains navigation data, AIS identification info, and
    // waypoint-based routing capabilities for autonomous movement simulation.

    /**
     * Display the "Add Ship" modal dialog with a randomly generated MMSI.
     * MMSI (Maritime Mobile Service Identity) is a unique 9-digit identifier
     * required for all AIS-transmitting vessels in real maritime operations.
     * 
     * The generated MMSI follows ITU-R M.585 standard format but uses
     * test ranges to avoid conflicts with real vessels.
     */
    showAddShipModal() {
        // Generate random MMSI (9-digit number, can start with 0)
        // Range 100000000-999999999 ensures valid 9-digit format
        const randomMMSI = Math.floor(Math.random() * 900000000) + 100000000;
        document.getElementById('shipMMSI').value = randomMMSI;
        
        // Show Bootstrap modal dialog for ship creation
        const modal = new bootstrap.Modal(document.getElementById('addShipModal'));
        modal.show();
    }

    /**
     * Process the add ship form and create a new ship object.
     * Validates all input fields and adds the ship to the fleet.
     * 
     * Ship object structure:
     * - name: Human-readable vessel name
     * - mmsi: 9-digit unique identifier for AIS transmission
     * - ship_type: AIS vessel type code (30=Fishing, 70=Cargo, etc.)
     * - length/beam: Physical dimensions in meters
     * - lat/lon: Current position in decimal degrees
     * - course/speed: Navigation state (degrees true, knots)
     * - status: AIS navigation status code
     * - waypoints: Array of [lat,lon] coordinates for route planning
     */
    addShip() {
        const form = document.getElementById('addShipForm');
        
        // Use HTML5 form validation first
        if (!form.checkValidity()) {
            form.reportValidity();
            return;
        }

        // Additional MMSI validation beyond HTML5 constraints
        const mmsiValue = document.getElementById('shipMMSI').value;
        if (mmsiValue.length !== 9) {
            this.showNotification('MMSI must be exactly 9 digits', 'error');
            return;
        }

        // Create ship object with form data and sensible defaults
        const ship = {
            name: document.getElementById('shipName').value,
            mmsi: parseInt(mmsiValue),
            ship_type: parseInt(document.getElementById('shipType').value),
            length: parseFloat(document.getElementById('shipLength').value),
            beam: 10, // Default beam width in meters
            lat: parseFloat(document.getElementById('shipLat').value),
            lon: parseFloat(document.getElementById('shipLon').value),
            course: parseFloat(document.getElementById('shipCourse').value),
            speed: parseFloat(document.getElementById('shipSpeed').value),
            status: 0, // Under way using engine (AIS status code)
            turn: 0,   // Rate of turn in degrees/minute
            destination: "", // Free-form destination text
            accuracy: 1,     // GPS accuracy flag (1 = high accuracy <10m)
            heading: parseFloat(document.getElementById('shipCourse').value), // True heading
            waypoints: [],        // Route waypoints for autonomous navigation
            current_waypoint: -1, // Index of current target waypoint (-1 = not navigating)
            waypoint_radius: 0.01 // Arrival radius in degrees (~1km at equator)
        };

        // Add to fleet and persist data
        this.ships.push(ship);
        this.saveShipsToStorage();
        this.updateUI();
        
        // Close modal and reset form
        const modal = bootstrap.Modal.getInstance(document.getElementById('addShipModal'));
        modal.hide();
        form.reset();
        
        this.showNotification('Ship added successfully', 'success');
    }

    /**
     * Remove a ship from the fleet with confirmation dialog.
     * Also cleans up all associated map markers, waypoints, and track data
     * to prevent memory leaks and orphaned visual elements.
     * 
     * @param {number} index - Index of ship in the ships array
     */
    removeShip(index) {
        if (confirm(`Remove ship "${this.ships[index].name}"?`)) {
            const ship = this.ships[index];
            const mmsi = ship.mmsi;
            
            // ===== CLEAN UP MAP VISUALIZATION DATA =====
            // This prevents orphaned markers and lines from remaining on map
            if (this.map) {
                // Remove ship position marker
                if (this.mapState.shipMarkers && this.mapState.shipMarkers.has(mmsi)) {
                    this.map.removeLayer(this.mapState.shipMarkers.get(mmsi));
                    this.mapState.shipMarkers.delete(mmsi);
                }
                
                // Remove waypoint markers (route planning indicators)
                if (this.mapState.waypoints && this.mapState.waypoints.has(mmsi)) {
                    this.mapState.waypoints.get(mmsi).forEach(marker => this.map.removeLayer(marker));
                    this.mapState.waypoints.delete(mmsi);
                }
                
                // Remove route lines (planned path visualization)
                if (this.mapState.routeLines && this.mapState.routeLines.has(mmsi)) {
                    this.mapState.routeLines.get(mmsi).forEach(line => this.map.removeLayer(line));
                    this.mapState.routeLines.delete(mmsi);
                }
                
                // Remove ship movement tracks (historical path)
                if (this.mapState.shipTracks && this.mapState.shipTracks.has(mmsi)) {
                    this.mapState.shipTracks.delete(mmsi);
                }
                
                // Remove track lines (visual representation of movement history)
                if (this.mapState.trackLines && this.mapState.trackLines.has(mmsi)) {
                    this.map.removeLayer(this.mapState.trackLines.get(mmsi));
                    this.mapState.trackLines.delete(mmsi);
                }
            }
            
            // Remove from ships array and update UI
            this.ships.splice(index, 1);
            this.saveShipsToStorage();
            this.updateUI();
            this.showNotification('Ship removed', 'info');
        }
    }

    /**
     * Create an inline ship editor for modifying vessel properties.
     * This method dynamically generates a comprehensive form interface
     * that allows editing of ship navigation data and waypoint management.
     * 
     * The editor includes:
     * - Basic ship properties (name, position, course, speed, status)
     * - Waypoint management interface with visual list display
     * - Route planning controls (add, remove, pick from map)
     * - Navigation control buttons (start/stop waypoint following)
     * 
     * @param {number} index - Index of ship to edit in ships array
     */
    editShip(index) {
        this.currentShipIndex = index;
        const ship = this.ships[index];
        
        // Generate comprehensive HTML form for ship editing
        const editor = document.getElementById('shipEditor');
        editor.innerHTML = `
            <form id="shipEditForm">
                <!-- BASIC SHIP PROPERTIES -->
                <div class="mb-2">
                    <label class="form-label">Name</label>
                    <input type="text" class="form-control form-control-sm" id="editName" value="${ship.name}">
                </div>
                
                <!-- GEOGRAPHIC POSITION (latitude/longitude in decimal degrees) -->
                <div class="mb-2">
                    <label class="form-label">Position</label>
                    <div class="row">
                        <div class="col-6">
                            <input type="number" class="form-control form-control-sm" id="editLat" value="${ship.lat}" step="0.000001">
                        </div>
                        <div class="col-6">
                            <input type="number" class="form-control form-control-sm" id="editLon" value="${ship.lon}" step="0.000001">
                        </div>
                    </div>
                </div>
                
                <!-- NAVIGATION PARAMETERS -->
                <div class="mb-2">
                    <label class="form-label">Course (°)</label>
                    <input type="number" class="form-control form-control-sm" id="editCourse" value="${ship.course}" min="0" max="359">
                </div>
                <div class="mb-2">
                    <label class="form-label">Speed (knots)</label>
                    <input type="number" class="form-control form-control-sm" id="editSpeed" value="${ship.speed}" min="0" max="50">
                </div>
                
                <!-- AIS NAVIGATION STATUS (standardized codes) -->
                <div class="mb-2">
                    <label class="form-label">Status</label>
                    <select class="form-control form-control-sm" id="editStatus">
                        <option value="0" ${ship.status === 0 ? 'selected' : ''}>Under way using engine</option>
                        <option value="1" ${ship.status === 1 ? 'selected' : ''}>At anchor</option>
                        <option value="2" ${ship.status === 2 ? 'selected' : ''}>Not under command</option>
                        <option value="3" ${ship.status === 3 ? 'selected' : ''}>Restricted manoeuvrability</option>
                        <option value="5" ${ship.status === 5 ? 'selected' : ''}>Moored</option>
                        <option value="7" ${ship.status === 7 ? 'selected' : ''}>Engaged in fishing</option>
                    </select>
                </div>
                
                <!-- WAYPOINT NAVIGATION SYSTEM -->
                <!-- This section provides complete route planning and management -->
                <div class="mb-3">
                    <hr>
                    <h6><i class="fas fa-route"></i> Waypoint Navigation</h6>
                    
                    <!-- Scrollable list of defined waypoints with coordinates -->
                    <div class="waypoint-list mb-2" style="max-height: 150px; overflow-y: auto; border: 1px solid #dee2e6; border-radius: 4px; padding: 5px;">
                        <div id="waypointList-${index}">
                            ${this.renderWaypointList(ship.waypoints || [])}
                        </div>
                    </div>
                    
                    <!-- Manual waypoint coordinate entry -->
                    <div class="row mb-2">
                        <div class="col-5">
                            <input type="number" class="form-control form-control-sm" id="waypointLat-${index}" placeholder="Latitude" step="0.000001">
                        </div>
                        <div class="col-5">
                            <input type="number" class="form-control form-control-sm" id="waypointLon-${index}" placeholder="Longitude" step="0.000001">
                        </div>
                        <div class="col-2">
                            <button type="button" class="btn btn-outline-primary btn-sm" onclick="sirenApp.addWaypoint(${index})" title="Add Waypoint">
                                <i class="fas fa-plus"></i>
                            </button>
                        </div>
                    </div>
                    
                    <!-- Waypoint management controls -->
                    <div class="btn-group btn-group-sm w-100 mb-2">
                        <!-- Interactive map waypoint selection -->
                        <button type="button" class="btn btn-outline-info" onclick="sirenApp.pickWaypointFromMap(${index})" title="Pick from Map">
                            <i class="fas fa-map-marker-alt"></i> Pick from Map
                        </button>
                        <!-- Remove all waypoints for this ship -->
                        <button type="button" class="btn btn-outline-warning" onclick="sirenApp.clearWaypoints(${index})" title="Clear All">
                            <i class="fas fa-trash"></i> Clear All
                        </button>
                    </div>
                    
                    <!-- Current navigation status display -->
                    <small class="text-muted">
                        ${ship.waypoints && ship.waypoints.length > 0 
                            ? `Ship will automatically follow ${ship.waypoints.length} waypoints in a continuous loop. Current: ${ship.current_waypoint >= 0 ? ship.current_waypoint + 1 : 'Auto-start on simulation'}`
                            : 'No waypoints set - ship will move in straight line'
                        }
                    </small>
                </div>
                
                <!-- FORM ACTION BUTTONS -->
                <div class="d-grid gap-1">
                    <button type="button" class="btn btn-siren btn-sm" onclick="sirenApp.updateShip()">Update</button>
                    <button type="button" class="btn btn-outline-secondary btn-sm" onclick="sirenApp.clearEditor()">Cancel</button>
                </div>
            </form>
        `;
    }

    /**
     * Update ship properties from the editor form.
     * Applies changes made in the inline editor to the ship object
     * and synchronizes heading with course for realistic navigation.
     */
    updateShip() {
        if (this.currentShipIndex === -1) return;
        
        const ship = this.ships[this.currentShipIndex];
        
        // Update ship properties from form inputs
        ship.name = document.getElementById('editName').value;
        ship.lat = parseFloat(document.getElementById('editLat').value);
        ship.lon = parseFloat(document.getElementById('editLon').value);
        ship.course = parseFloat(document.getElementById('editCourse').value);
        ship.speed = parseFloat(document.getElementById('editSpeed').value);
        ship.status = parseInt(document.getElementById('editStatus').value);
        
        // Keep heading synchronized with course for realistic AIS data
        ship.heading = ship.course;
        
        // Persist changes and update UI
        this.saveShipsToStorage();
        this.updateUI();
        this.clearEditor();
        this.showNotification('Ship updated', 'success');
    }

    /**
     * Clear the ship editor and reset to default state.
     * Returns the editor panel to its initial empty state.
     */
    clearEditor() {
        this.currentShipIndex = -1;
        document.getElementById('shipEditor').innerHTML = '<p class="text-muted">Select a ship to edit its properties</p>';
    }

    // =====================================
    // WAYPOINT MANAGEMENT
    // =====================================

    renderWaypointList(waypoints) {
        if (!waypoints || waypoints.length === 0) {
            return '<small class="text-muted">No waypoints set</small>';
        }
        
        return waypoints.map((wp, i) => `
            <div class="d-flex justify-content-between align-items-center mb-1 p-1 border-bottom">
                <small><strong>WP${i + 1}:</strong> ${wp[0].toFixed(6)}, ${wp[1].toFixed(6)}</small>
                <button type="button" class="btn btn-outline-danger btn-sm" onclick="sirenApp.removeWaypoint(${this.currentShipIndex}, ${i})" title="Remove">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `).join('');
    }

    addWaypoint(shipIndex) {
        const ship = this.ships[shipIndex];
        const latInput = document.getElementById(`waypointLat-${shipIndex}`);
        const lonInput = document.getElementById(`waypointLon-${shipIndex}`);
        
        const lat = parseFloat(latInput.value);
        const lon = parseFloat(lonInput.value);
        
        if (isNaN(lat) || isNaN(lon)) {
            this.showNotification('Please enter valid coordinates', 'warning');
            return;
        }
        
        if (lat < -90 || lat > 90 || lon < -180 || lon > 180) {
            this.showNotification('Coordinates out of range', 'warning');
            return;
        }
        
        if (!ship.waypoints) ship.waypoints = [];
        if (ship.waypoints.length >= 20) {
            this.showNotification('Maximum 20 waypoints allowed', 'warning');
            return;
        }
        
        ship.waypoints.push([lat, lon]);
        latInput.value = '';
        lonInput.value = '';
        
        // Update the waypoint list display
        const waypointList = document.getElementById(`waypointList-${shipIndex}`);
        waypointList.innerHTML = this.renderWaypointList(ship.waypoints);
        
        // Add waypoint to map if visible
        this.updateShipWaypoints(ship);
        
        this.saveShipsToStorage();
        this.showNotification('Waypoint added', 'success');
    }

    removeWaypoint(shipIndex, waypointIndex) {
        const ship = this.ships[shipIndex];
        if (!ship.waypoints || waypointIndex < 0 || waypointIndex >= ship.waypoints.length) return;
        
        ship.waypoints.splice(waypointIndex, 1);
        
        // Adjust current waypoint index if needed
        if (ship.current_waypoint > waypointIndex) {
            ship.current_waypoint--;
        } else if (ship.current_waypoint === waypointIndex) {
            ship.current_waypoint = -1; // Reset if current waypoint was removed
        }
        
        // Update the waypoint list display
        const waypointList = document.getElementById(`waypointList-${shipIndex}`);
        waypointList.innerHTML = this.renderWaypointList(ship.waypoints);
        
        // Update map
        this.updateShipWaypoints(ship);
        
        this.saveShipsToStorage();
        this.showNotification('Waypoint removed', 'info');
    }

    clearWaypoints(shipIndex) {
        if (!confirm('Remove all waypoints for this ship?')) return;
        
        const ship = this.ships[shipIndex];
        ship.waypoints = [];
        ship.current_waypoint = -1;
        
        // Update the waypoint list display
        const waypointList = document.getElementById(`waypointList-${shipIndex}`);
        waypointList.innerHTML = this.renderWaypointList(ship.waypoints);
        
        // Update map
        this.updateShipWaypoints(ship);
        
        this.saveShipsToStorage();
        this.showNotification('All waypoints cleared', 'info');
    }

    pickWaypointFromMap(shipIndex) {
        // Switch to map tab and enable waypoint picking mode
        if (!this.map) {
            this.showNotification('Map not initialized. Go to Live Map tab first.', 'warning');
            return;
        }
        
        // Switch to map tab
        const mapTab = document.getElementById('map-tab');
        const tabInstance = new bootstrap.Tab(mapTab);
        tabInstance.show();
        
        // Enable waypoint picking mode
        this.enableWaypointPickingMode(shipIndex);
        this.showNotification('Click on the map to add a waypoint', 'info');
    }

    enableWaypointPickingMode(shipIndex) {
        this.waypointPickingMode = {
            active: true,
            shipIndex: shipIndex,
            originalClickHandler: null
        };
        
        // Store original click handler and set new one
        if (this.map) {
            this.map.off('click'); // Remove existing handlers
            this.map.on('click', (e) => this.onWaypointPickClick(e));
            
            // Change cursor to crosshair
            document.getElementById('shipMap').style.cursor = 'crosshair';
            
            // Add instruction overlay
            this.showMapInstruction('Click to add waypoint. ESC to cancel.');
        }
    }

    onWaypointPickClick(e) {
        if (!this.waypointPickingMode || !this.waypointPickingMode.active) return;
        
        const lat = e.latlng.lat;
        const lon = e.latlng.lng;
        const shipIndex = this.waypointPickingMode.shipIndex;
        
        // Add waypoint to ship
        const ship = this.ships[shipIndex];
        if (!ship.waypoints) ship.waypoints = [];
        if (ship.waypoints.length >= 20) {
            this.showNotification('Maximum 20 waypoints allowed', 'warning');
            this.disableWaypointPickingMode();
            return;
        }
        
        ship.waypoints.push([lat, lon]);
        
        // Update waypoint display if ship editor is open
        const waypointList = document.getElementById(`waypointList-${shipIndex}`);
        if (waypointList) {
            waypointList.innerHTML = this.renderWaypointList(ship.waypoints);
        }
        
        // Update map
        this.updateShipWaypoints(ship);
        
        this.saveShipsToStorage();
        this.showNotification(`Waypoint ${ship.waypoints.length} added at ${lat.toFixed(6)}, ${lon.toFixed(6)}`, 'success');
        
        // Exit picking mode
        this.disableWaypointPickingMode();
    }

    disableWaypointPickingMode() {
        if (!this.waypointPickingMode) return;
        
        this.waypointPickingMode.active = false;
        
        // Restore normal map behavior
        if (this.map) {
            this.map.off('click');
            this.map.on('click', (e) => this.onMapClick(e)); // Restore original handler
            document.getElementById('shipMap').style.cursor = '';
        }
        
        this.hideMapInstruction();
    }

    startWaypointNavigation(shipIndex) {
        const ship = this.ships[shipIndex];
        if (!ship.waypoints || ship.waypoints.length === 0) {
            this.showNotification('No waypoints to navigate to', 'warning');
            return;
        }
        
        ship.current_waypoint = 0; // Start with first waypoint
        
        // Calculate course to first waypoint
        const firstWaypoint = ship.waypoints[0];
        ship.course = this.calculateBearing(ship.lat, ship.lon, firstWaypoint[0], firstWaypoint[1]);
        ship.heading = ship.course;
        
        this.saveShipsToStorage();
        this.updateUI();
        this.showNotification(`Started navigation to ${ship.waypoints.length} waypoints`, 'success');
    }

    stopWaypointNavigation(shipIndex) {
        const ship = this.ships[shipIndex];
        ship.current_waypoint = -1;
        
        this.saveShipsToStorage();
        this.updateUI();
        this.showNotification('Waypoint navigation stopped', 'info');
    }

    showMapInstruction(text) {
        const mapContainer = document.getElementById('shipMap');
        let instructionDiv = document.getElementById('mapInstruction');
        
        if (!instructionDiv) {
            instructionDiv = document.createElement('div');
            instructionDiv.id = 'mapInstruction';
            instructionDiv.style.cssText = `
                position: absolute;
                top: 10px;
                left: 50%;
                transform: translateX(-50%);
                background: rgba(0,0,0,0.8);
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                z-index: 1001;
                font-size: 14px;
            `;
            mapContainer.appendChild(instructionDiv);
        }
        
        instructionDiv.textContent = text;
        instructionDiv.style.display = 'block';
    }

    hideMapInstruction() {
        const instructionDiv = document.getElementById('mapInstruction');
        if (instructionDiv) {
            instructionDiv.style.display = 'none';
        }
    }

    // =====================================
    // REAL-TIME SIMULATION CONTROL SYSTEM
    // =====================================
    // This section manages the core simulation loop that moves ships in real-time
    // and generates AIS messages for transmission. The simulation uses a time-based
    // approach with configurable intervals and proper ship selection management.

    /**
     * Start the real-time ship simulation with selected vessels.
     * 
     * This method initiates a complex process that:
     * 1. Validates ship data and ensures GNU Radio connection
     * 2. Locks ship selection to prevent UI interference during simulation
     * 3. Begins interval-based ship movement and AIS message generation
     * 4. Manages timing to prevent message collisions on AIS channels
     * 
     * The simulation uses a "locked selection" approach to ensure that the
     * ships being simulated cannot be changed mid-simulation, preventing
     * data corruption and maintaining consistent behavior.
     */
    startSimulation() {
        // ===== PRE-SIMULATION VALIDATION =====
        if (this.ships.length === 0) {
            this.showNotification('No ships available to simulate', 'warning');
            return;
        }

        if (!this.isConnected) {
            this.showNotification('Not connected to GNU Radio backend', 'error');
            return;
        }

        // Validate and clean ship data to prevent runtime errors
        this.validateAndCleanShipData();

        // ===== SIMULATION STATE INITIALIZATION =====
        this.simulation.active = true;
        this.simulation.interval = parseInt(document.getElementById('simulationInterval').value);
        this.simulation.messageCount = 0;
        this.simulation.startTime = new Date();

        // ===== SHIP SELECTION AND LOCKING =====
        // Get explicitly selected ships from the UI multiselect
        const selectedOptions = Array.from(document.getElementById('selectedShips').selectedOptions);
        if (selectedOptions.length === 0) {
            this.showNotification('Please select at least one ship for simulation', 'warning');
            this.simulation.active = false;
            return;
        }
        
        // Lock the selection to prevent UI changes during simulation
        // This is critical for preventing data corruption and ensuring
        // consistent simulation behavior
        this.selectedShips = selectedOptions.map(option => parseInt(option.value));
        this.simulation.lockedSelection = [...this.selectedShips]; // Create immutable copy
        
        // Disable ship selection UI to prevent user interference
        document.getElementById('selectedShips').disabled = true;
        
        // ===== DEBUGGING AND VALIDATION =====
        // Extensive logging for troubleshooting simulation issues
        console.log('=== SIMULATION STARTED ===');
        console.log(`Selected ship indices: [${this.selectedShips.join(', ')}]`);
        console.log(`Locked selection: [${this.simulation.lockedSelection.join(', ')}]`);
        
        const selectedShipDetails = [];
        this.selectedShips.forEach(shipIndex => {
            const ship = this.ships[shipIndex];
            if (ship) {
                selectedShipDetails.push({
                    index: shipIndex,
                    name: ship.name,
                    mmsi: ship.mmsi,
                    lat: ship.lat,
                    lon: ship.lon
                });
                console.log(`  - Ship ${shipIndex}: ${ship.name} (MMSI: ${ship.mmsi})`);
            } else {
                console.error(`  - Ship ${shipIndex}: NOT FOUND!`);
            }
        });
        
        // Store selected ship details for validation during simulation
        this.simulation.selectedShipDetails = selectedShipDetails;
        
        // Log all ships for comparison and debugging
        console.log('All ships in fleet:');
        this.ships.forEach((ship, index) => {
            console.log(`  ${index}: ${ship.name} (MMSI: ${ship.mmsi}) - ${this.selectedShips.includes(index) ? 'SELECTED' : 'not selected'}`);
        });

        // ===== UI STATE UPDATES =====
        document.getElementById('startSimulationBtn').disabled = true;
        document.getElementById('stopSimulationBtn').disabled = false;
        document.getElementById('simulationStatus').textContent = 'Running';
        document.getElementById('simulationStatus').className = 'badge bg-success';
        document.getElementById('activeShipCount').textContent = this.selectedShips.length;

        // ===== START SIMULATION LOOP =====
        // Run first simulation step immediately, then set up interval
        this.runSimulationStep();
        this.simulation.intervalId = setInterval(() => this.runSimulationStep(), this.simulation.interval * 1000);

        // Log and notify successful start
        this.logMessage('simulationLog', `Started simulation with ${this.selectedShips.length} ships: ${selectedShipDetails.map(s => s.name).join(', ')}`);
        this.showNotification('Simulation started', 'success');
    }

    /**
     * Stop the real-time simulation and clean up resources.
     * Restores UI to normal state and unlocks ship selection.
     */
    stopSimulation() {
        this.simulation.active = false;
        
        // Clear the simulation interval timer
        if (this.simulation.intervalId) {
            clearInterval(this.simulation.intervalId);
            this.simulation.intervalId = null;
        }

        // Clear locked selection and re-enable ship selection UI
        this.simulation.lockedSelection = [];
        document.getElementById('selectedShips').disabled = false;

        // Update UI to reflect stopped state
        document.getElementById('startSimulationBtn').disabled = false;
        document.getElementById('stopSimulationBtn').disabled = true;
        document.getElementById('simulationStatus').textContent = 'Stopped';
        document.getElementById('simulationStatus').className = 'badge bg-secondary';

        console.log('=== SIMULATION STOPPED ===');
        this.logMessage('simulationLog', 'Simulation stopped');
        this.showNotification('Simulation stopped', 'info');
    }

    runSimulationStep() {
        if (!this.simulation.active) return;

        const channel = document.getElementById('aisChannel').value;
        const stepStartTime = new Date().toISOString().substr(11, 12);
        
        // CRITICAL: Use the locked selection to prevent changes during simulation
        const activeSelection = this.simulation.lockedSelection || this.selectedShips;
        
        console.log('=== SIMULATION STEP START ===');
        console.log(`Step time: ${stepStartTime}`);
        console.log(`Active selection: [${activeSelection.join(', ')}]`);
        console.log(`Current selectedShips: [${this.selectedShips.join(', ')}]`);
        console.log(`Locked selection: [${(this.simulation.lockedSelection || []).join(', ')}]`);
        
        this.logMessage('simulationLog', `${stepStartTime} === Simulation Step Started ===`);
        this.logMessage('simulationLog', `Processing ${activeSelection.length} selected ships: [${activeSelection.join(', ')}]`);
        
        // Validate that we're only processing selected ships
        if (activeSelection.length === 0) {
            console.error('No ships selected for simulation step!');
            this.logMessage('simulationLog', 'ERROR: No ships selected for simulation step');
            return;
        }
        
        // Process ONLY the selected ships
        activeSelection.forEach((shipIndex, i) => {
            const ship = this.ships[shipIndex];
            if (!ship) {
                console.warn(`Simulation step: Ship at index ${shipIndex} not found`);
                this.logMessage('simulationLog', `WARNING: Ship at index ${shipIndex} not found`);
                return;
            }
            
            console.log(`Processing ship ${i + 1}/${activeSelection.length}: ${ship.name} (MMSI: ${ship.mmsi}, Index: ${shipIndex})`);
            this.logMessage('simulationLog', `Processing: ${ship.name} (MMSI: ${ship.mmsi})`);

            // Validate ship state before processing
            if (typeof ship.lat !== 'number' || isNaN(ship.lat)) {
                console.error(`${ship.name}: Invalid latitude ${ship.lat}, skipping simulation step`);
                return;
            }
            if (typeof ship.lon !== 'number' || isNaN(ship.lon)) {
                console.error(`${ship.name}: Invalid longitude ${ship.lon}, skipping simulation step`);
                return;
            }
            if (typeof ship.speed !== 'number' || isNaN(ship.speed) || ship.speed < 0) {
                console.error(`${ship.name}: Invalid speed ${ship.speed}, skipping simulation step`);
                return;
            }

            // Store previous position for logging
            const prevLat = ship.lat;
            const prevLon = ship.lon;
            const prevCourse = ship.course;
            
            // Log ship state before movement for debugging
            console.log(`${ship.name} before movement: Lat=${ship.lat.toFixed(6)}, Lon=${ship.lon.toFixed(6)}, Course=${ship.course.toFixed(1)}°, Speed=${ship.speed}kt`);

            // Move the ship FIRST
            this.moveShip(ship);
            
            // Log ship state after movement for debugging
            console.log(`${ship.name} after movement: Lat=${ship.lat.toFixed(6)}, Lon=${ship.lon.toFixed(6)}, Course=${ship.course.toFixed(1)}°, Speed=${ship.speed}kt`);

            // Verify ship state after movement
            if (typeof ship.lat !== 'number' || isNaN(ship.lat) || typeof ship.lon !== 'number' || isNaN(ship.lon)) {
                console.error(`${ship.name}: Ship position corrupted after movement! Restoring previous position.`);
                ship.lat = prevLat;
                ship.lon = prevLon;
                ship.course = prevCourse;
                return;
            }

            // Log movement details for debugging
            const moved = (Math.abs(ship.lat - prevLat) > 0.0001 || Math.abs(ship.lon - prevLon) > 0.0001);
            if (moved) {
                this.logMessage('simulationLog', 
                    `${ship.name}: Moved from ${prevLat.toFixed(6)},${prevLon.toFixed(6)} to ${ship.lat.toFixed(6)},${ship.lon.toFixed(6)} ` +
                    `(Course: ${ship.course.toFixed(1)}°, Speed: ${ship.speed}kt)`
                );
            }

            // Save ship positions to localStorage to persist simulation changes
            // This ensures that tab switches don't revert to old positions
            this.saveShipsToStorage();

            // Capture ship state snapshot at the time of scheduling to avoid race conditions
            const shipSnapshot = {
                name: ship.name,
                mmsi: ship.mmsi,
                lat: ship.lat,
                lon: ship.lon,
                course: ship.course,
                speed: ship.speed,
                heading: ship.heading,
                status: ship.status,
                turn: ship.turn,
                accuracy: ship.accuracy
            };

            // Comprehensive validation of the snapshot before transmission
            if (typeof shipSnapshot.lat !== 'number' || isNaN(shipSnapshot.lat) || 
                typeof shipSnapshot.lon !== 'number' || isNaN(shipSnapshot.lon) ||
                typeof shipSnapshot.course !== 'number' || isNaN(shipSnapshot.course) ||
                typeof shipSnapshot.speed !== 'number' || isNaN(shipSnapshot.speed) ||
                typeof shipSnapshot.heading !== 'number' || isNaN(shipSnapshot.heading)) {
                console.error(`${ship.name}: Invalid snapshot data detected, skipping transmission`);
                console.error('Snapshot:', shipSnapshot);
                return;
            }
            
            // Additional range validation
            if (shipSnapshot.lat < -90 || shipSnapshot.lat > 90) {
                console.error(`${ship.name}: Latitude ${shipSnapshot.lat} out of range, skipping transmission`);
                return;
            }
            if (shipSnapshot.lon < -180 || shipSnapshot.lon > 180) {
                console.error(`${ship.name}: Longitude ${shipSnapshot.lon} out of range, skipping transmission`);
                return;
            }
            if (shipSnapshot.speed < 0 || shipSnapshot.speed > 102) {
                console.error(`${ship.name}: Speed ${shipSnapshot.speed} out of range, skipping transmission`);
                return;
            }

            // Schedule transmission with proper delay between ships
            setTimeout(() => {
                // Double-check that simulation is still active
                if (!this.simulation.active) {
                    console.log(`${shipSnapshot.name}: Simulation stopped, skipping transmission`);
                    return;
                }
                
                // Generate AIS message with captured state snapshot
                const aisMessage = this.generateAISMessage(shipSnapshot, channel);
                
                // Log the actual values being transmitted with timestamp
                const timestamp = new Date().toISOString().substr(11, 12); // HH:MM:SS.mmm
                console.log(`${timestamp} TRANSMITTING: ${shipSnapshot.name} (MMSI: ${shipSnapshot.mmsi})`);
                this.logMessage('transmissionLog', 
                    `${timestamp} TX ${shipSnapshot.name}: MMSI=${shipSnapshot.mmsi}, Lat=${shipSnapshot.lat.toFixed(6)}, Lon=${shipSnapshot.lon.toFixed(6)}, ` +
                    `COG=${shipSnapshot.course.toFixed(1)}°, SOG=${shipSnapshot.speed}kt, HDG=${shipSnapshot.heading}°, Status=${shipSnapshot.status}`
                );
                
                // Send to GNU Radio
                this.sendAISMessage(aisMessage, shipSnapshot.name);
            }, i * 500); // Delay between ships to avoid message collisions
        });

        // Save updated ship positions to storage
        this.saveShipsToStorage();
        
        const stepEndTime = new Date().toISOString().substr(11, 12);
        this.logMessage('simulationLog', `${stepEndTime} === Simulation Step Completed ===`);
        console.log('=== SIMULATION STEP END ===');
        
        this.updateUI();
        
        // Update map if initialized
        if (this.map) {
            this.updateShipPositions();
        }
    }

    moveShip(ship) {
        if (ship.speed <= 0) return;

        // Check if ship has waypoints defined - if so, always follow them
        if (ship.waypoints && ship.waypoints.length > 0) {
            // Auto-start waypoint navigation if not already active
            if (ship.current_waypoint < 0) {
                ship.current_waypoint = 0;
                // Calculate initial course to first waypoint
                const firstWaypoint = ship.waypoints[0];
                ship.course = this.calculateBearing(ship.lat, ship.lon, firstWaypoint[0], firstWaypoint[1]);
                ship.heading = ship.course;
                console.log(`${ship.name}: Auto-started waypoint navigation to ${ship.waypoints.length} waypoints`);
            }
            this.moveShipWithWaypoints(ship);
        } else {
            this.moveShipStraight(ship);
        }
    }

    moveShipStraight(ship) {
        // Validate ship state before movement
        if (!ship || typeof ship.speed !== 'number' || ship.speed <= 0) {
            return; // No movement for invalid or stationary ships
        }
        
        // Store original position for recovery if needed
        const originalLat = ship.lat;
        const originalLon = ship.lon;
        const originalCourse = ship.course;
        
        // Validate input values - be more conservative about resetting
        if (typeof ship.lat !== 'number' || isNaN(ship.lat) || ship.lat < -90 || ship.lat > 90) {
            console.error(`${ship.name}: Invalid latitude ${ship.lat} before movement, cannot move safely`);
            return; // Don't move if position is invalid
        }
        if (typeof ship.lon !== 'number' || isNaN(ship.lon) || ship.lon < -180 || ship.lon > 180) {
            console.error(`${ship.name}: Invalid longitude ${ship.lon} before movement, cannot move safely`);
            return; // Don't move if position is invalid
        }
        if (typeof ship.course !== 'number' || isNaN(ship.course)) {
            console.error(`${ship.name}: Invalid course ${ship.course} before movement, cannot move safely`);
            return; // Don't move if course is invalid
        }
        
        // Normalize course to 0-359.9 range
        ship.course = ((ship.course % 360) + 360) % 360;
        
        // Movement calculation with safety checks
        const timeStep = this.simulation.interval / 3600; // Convert seconds to hours
        let distanceNM = ship.speed * timeStep;
        
        // Prevent extreme movement near poles
        if (Math.abs(ship.lat) > 85) {
            console.warn(`${ship.name}: Near pole (lat=${ship.lat}), limiting movement`);
            // Reduce movement near poles to prevent coordinate system issues
            const limitedDistance = Math.min(distanceNM, 0.1); // Limit to 0.1 NM near poles
            distanceNM = limitedDistance;
        }
        
        // Calculate lat/lon changes with safety checks
        const latChange = distanceNM * Math.cos(ship.course * Math.PI / 180) / 60;
        
        // Prevent division by zero near poles for longitude calculation
        const cosLat = Math.cos(ship.lat * Math.PI / 180);
        if (Math.abs(cosLat) < 0.01) {
            console.warn(`${ship.name}: Too close to pole for longitude calculation, skipping movement`);
            return;
        }
        
        const lonChange = distanceNM * Math.sin(ship.course * Math.PI / 180) / (60 * cosLat);
        
        // Validate calculated changes
        if (isNaN(latChange) || isNaN(lonChange) || !isFinite(latChange) || !isFinite(lonChange)) {
            console.error(`${ship.name}: Invalid movement calculation: latChange=${latChange}, lonChange=${lonChange}`);
            return; // Don't move if calculations are invalid
        }
        
        // Check if movement is reasonable (not too large)
        if (Math.abs(latChange) > 1.0 || Math.abs(lonChange) > 1.0) {
            console.error(`${ship.name}: Movement too large: latChange=${latChange}, lonChange=${lonChange}, probably a calculation error`);
            return; // Don't move if movement is unreasonably large
        }
        
        // Debug logging for movement calculation
        if (distanceNM > 0) {
            console.log(`${ship.name}: Moving ${distanceNM.toFixed(4)}NM over ${timeStep.toFixed(4)}h at ${ship.course.toFixed(1)}°, latΔ=${latChange.toFixed(6)}, lonΔ=${lonChange.toFixed(6)}`);
        }
        
        // Apply movement
        const newLat = ship.lat + latChange;
        const newLon = ship.lon + lonChange;
        
        // Validate new position before applying
        if (isNaN(newLat) || isNaN(newLon) || !isFinite(newLat) || !isFinite(newLon)) {
            console.error(`${ship.name}: Invalid new position: lat=${newLat}, lon=${newLon}, keeping original position`);
            return; // Don't move if new position is invalid
        }
        
        // Check if new position is within reasonable bounds
        if (newLat < -90 || newLat > 90 || newLon < -180 || newLon > 180) {
            console.error(`${ship.name}: New position out of bounds: lat=${newLat}, lon=${newLon}, keeping original position`);
            return; // Don't move if new position is out of bounds
        }
        
        // Apply the validated movement
        ship.lat = newLat;
        ship.lon = newLon;

        // Proper longitude wrap-around (keep within -180 to 180)
        while (ship.lon > 180) {
            ship.lon -= 360;
        }
        while (ship.lon < -180) {
            ship.lon += 360;
        }
        
        // Final validation after movement
        if (isNaN(ship.lat) || isNaN(ship.lon) || !isFinite(ship.lat) || !isFinite(ship.lon)) {
            console.error(`${ship.name}: Position corrupted after movement! Restoring original position.`);
            ship.lat = originalLat;
            ship.lon = originalLon;
            ship.course = originalCourse;
            return;
        }
        
        // Update heading to match course
        ship.heading = ship.course;
        
        // Save ship positions to localStorage during simulation to ensure changes persist
        // This is important for preventing tab switches from reverting to old positions
        if (this.simulation && this.simulation.active) {
            this.saveShipsToStorage();
        }
    }

    moveShipWithWaypoints(ship) {
        if (ship.current_waypoint >= ship.waypoints.length) {
            // All waypoints reached, restart from beginning (loop navigation)
            ship.current_waypoint = 0;
            console.log(`${ship.name}: All waypoints reached, restarting navigation loop`);
            
            // Set course to first waypoint again
            const firstWaypoint = ship.waypoints[0];
            ship.course = this.calculateBearing(ship.lat, ship.lon, firstWaypoint[0], firstWaypoint[1]);
            ship.heading = ship.course;
        }

        const currentWaypoint = ship.waypoints[ship.current_waypoint];
        const distanceToWaypoint = this.haversineDistance(ship.lat, ship.lon, currentWaypoint[0], currentWaypoint[1]);
        
        // Check if waypoint is reached (within ~1km)
        if (distanceToWaypoint <= ship.waypoint_radius * 111.0) { // waypoint_radius in degrees * 111 km/degree
            console.log(`${ship.name}: Waypoint ${ship.current_waypoint + 1} reached`);
            
            // Move to next waypoint
            ship.current_waypoint++;
            
            if (ship.current_waypoint < ship.waypoints.length) {
                // Set course to next waypoint
                const nextWaypoint = ship.waypoints[ship.current_waypoint];
                const newCourse = this.calculateBearing(ship.lat, ship.lon, nextWaypoint[0], nextWaypoint[1]);
                ship.course = newCourse;
                ship.heading = newCourse; // Keep heading synchronized with course
                console.log(`${ship.name}: Set course to waypoint ${ship.current_waypoint + 1}: ${ship.course.toFixed(1)}°`);
                
                // Save ship state after waypoint change during simulation
                if (this.simulation && this.simulation.active) {
                    this.saveShipsToStorage();
                }
            } else {
                // This will be handled by the next moveShipWithWaypoints call (restart loop)
                console.log(`${ship.name}: Reached final waypoint, will restart on next step`);
            }
        } else {
            // Update course continuously to point toward current waypoint
            const currentCourse = this.calculateBearing(ship.lat, ship.lon, currentWaypoint[0], currentWaypoint[1]);
            ship.course = currentCourse;
            ship.heading = currentCourse; // Keep heading synchronized
        }

        // Move ship toward current waypoint
        this.moveShipStraight(ship);
    }

    // Haversine distance calculation (in kilometers)
    haversineDistance(lat1, lon1, lat2, lon2) {
        const R = 6371; // Earth's radius in kilometers
        const dLat = this.toRadians(lat2 - lat1);
        const dLon = this.toRadians(lon2 - lon1);
        const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                  Math.cos(this.toRadians(lat1)) * Math.cos(this.toRadians(lat2)) *
                  Math.sin(dLon / 2) * Math.sin(dLon / 2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        return R * c;
    }

    // Calculate bearing between two points
    calculateBearing(lat1, lon1, lat2, lon2) {
        const dLon = this.toRadians(lon2 - lon1);
        const lat1Rad = this.toRadians(lat1);
        const lat2Rad = this.toRadians(lat2);
        
        const x = Math.sin(dLon) * Math.cos(lat2Rad);
        const y = Math.cos(lat1Rad) * Math.sin(lat2Rad) - 
                  Math.sin(lat1Rad) * Math.cos(lat2Rad) * Math.cos(dLon);
        
        let bearing = Math.atan2(x, y);
        bearing = this.toDegrees(bearing);
        
        // Normalize to 0-360
        return (bearing + 360) % 360;
    }

    toRadians(degrees) {
        return degrees * (Math.PI / 180);
    }

    toDegrees(radians) {
        return radians * (180 / Math.PI);
    }

    // =====================================
    // AIS MESSAGE GENERATION SYSTEM
    // =====================================
    // This section implements the AIS (Automatic Identification System) protocol
    // for generating standards-compliant maritime vessel position reports.
    // 
    // AIS is the international standard for vessel tracking and collision avoidance,
    // defined by ITU-R M.1371-5. This implementation creates Type 1 Position Reports
    // which are the most common AIS message type for vessel tracking.
    //
    // MESSAGE STRUCTURE:
    // - AIS messages use a 6-bit ASCII encoding scheme
    // - Data is packed into bit fields with specific lengths and formats
    // - Messages are transmitted as NMEA 0183 sentences (AIVDM format)
    // - Checksums ensure data integrity during transmission

    /**
     * Generate a complete AIS Type 1 Position Report message.
     * 
     * This method creates a standards-compliant AIS message containing:
     * - Vessel identification (MMSI, ship type)
     * - Position data (latitude, longitude, accuracy)
     * - Navigation data (course, speed, heading, rate of turn)
     * - Status information (navigation status, timestamp)
     * 
     * The resulting message follows NMEA 0183 format:
     * !AIVDM,1,1,,A,<payload>,0*<checksum>
     * 
     * @param {Object} ship - Ship object with navigation data
     * @param {string} channel - AIS channel ('A' or 'B' for VHF channels 87B/88B)
     * @returns {string} Complete NMEA 0183 AIS message ready for transmission
     */
    generateAISMessage(ship, channel = 'A') {
        // Extract ship data - validation should be done before this point
        const mmsi = ship.mmsi;
        const lat = ship.lat;
        const lon = ship.lon;
        const speed = ship.speed;
        const course = ship.course;
        const heading = ship.heading;
        const status = ship.status;
        
        // Final safety checks - log warnings but don't modify values
        // (Modifications at this stage could cause simulation inconsistencies)
        if (lat < -90 || lat > 90 || lon < -180 || lon > 180) {
            console.warn(`${ship.name}: Position out of range in AIS generation: ${lat}, ${lon}`);
        }
        if (speed < 0 || speed > 102.2) {
            console.warn(`${ship.name}: Speed out of range in AIS generation: ${speed}`);
        }
        if (course < 0 || course >= 360) {
            console.warn(`${ship.name}: Course out of range in AIS generation: ${course}`);
        }
        
        // Log the exact values being encoded for debugging
        console.log(`Generating AIS for ${ship.name}: MMSI=${mmsi}, lat=${lat.toFixed(6)}, lon=${lon.toFixed(6)}, course=${course.toFixed(1)}, speed=${speed.toFixed(1)}, heading=${heading.toFixed(1)}, status=${status}`);
        
        // ===== AIS TYPE 1 MESSAGE FIELD STRUCTURE =====
        // Create standardized AIS Type 1 Position Report fields
        const fields = {
            msg_type: 1,                    // Message type 1 = Position Report Class A
            repeat: 0,                      // Repeat indicator (0 = default)
            mmsi: mmsi,                     // Maritime Mobile Service Identity
            nav_status: status,             // Navigation status (0-15, see AIS standard)
            rot: ship.turn || 0,            // Rate of turn (-127 to +127 degrees/minute)
            sog: speed,                     // Speed over ground (knots)
            accuracy: ship.accuracy || 1,   // Position accuracy (1 = high <10m, 0 = low >10m)
            lon: lon,                       // Longitude (decimal degrees)
            lat: lat,                       // Latitude (decimal degrees)
            cog: course,                    // Course over ground (degrees true)
            hdg: heading,                   // True heading (degrees)
            timestamp: new Date().getSeconds() % 60  // UTC seconds (0-59)
        };

        // Build the binary payload using AIS bit packing rules
        const payload = this.buildAISPayload(fields);
        
        // Create NMEA 0183 sentence structure
        // Format: AIVDM,<fragment_count>,<fragment_number>,<message_id>,<channel>,<payload>,<padding>
        const sentence = `AIVDM,1,1,,${channel},${payload},0`;
        
        // Calculate NMEA checksum (XOR of all characters between $ and *)
        const checksum = this.computeChecksum(sentence);
        
        // Return complete NMEA sentence with start delimiter and checksum
        return `!${sentence}*${checksum}`;
    }

    /**
     * Build the AIS message payload using bit-level packing.
     * 
     * This method implements the exact AIS Type 1 message structure as defined
     * in ITU-R M.1371-5, packing navigation data into a binary bit string
     * and converting it to 6-bit ASCII encoding for transmission.
     * 
     * AIS TYPE 1 BIT STRUCTURE (total 168 bits):
     * - Message Type: 6 bits (always 1 for Position Report)
     * - Repeat Indicator: 2 bits
     * - MMSI: 30 bits
     * - Navigation Status: 4 bits
     * - Rate of Turn: 8 bits (signed, with special encoding)
     * - Speed Over Ground: 10 bits (0.1 knot resolution)
     * - Position Accuracy: 1 bit
     * - Longitude: 28 bits (signed, 1/600000 minute resolution)
     * - Latitude: 27 bits (signed, 1/600000 minute resolution)  
     * - Course Over Ground: 12 bits (0.1 degree resolution)
     * - True Heading: 9 bits (1 degree resolution)
     * - Timestamp: 6 bits (UTC seconds)
     * - Regional: 4 bits (reserved)
     * - Spare: 3 bits
     * - RAIM: 1 bit (integrity flag)
     * - Communication State: 19 bits
     * 
     * @param {Object} fields - AIS message fields with navigation data
     * @returns {string} 6-bit ASCII encoded payload string
     */
    buildAISPayload(fields) {
        // Initialize binary bit string for message construction
        let bits = '';
        
        // ===== PACK MESSAGE HEADER =====
        bits += this.toBits(fields.msg_type, 6);      // Message type (always 1)
        bits += this.toBits(fields.repeat, 2);        // Repeat indicator
        bits += this.toBits(fields.mmsi, 30);         // MMSI (30-bit unique identifier)
        bits += this.toBits(fields.nav_status, 4);    // Navigation status
        
        // ===== RATE OF TURN (SPECIAL ENCODING) =====
        // Rate of turn uses special encoding with offset and saturation values
        const rotValue = Math.max(-127, Math.min(127, Math.round(fields.rot)));
        bits += this.toBits(rotValue + 128, 8);       // ROT with 128 offset for signed values
        
        // ===== SPEED OVER GROUND =====
        // Speed in 0.1 knot resolution, max 102.2 knots (value 1022)
        const sogValue = Math.max(0, Math.min(1022, Math.round(fields.sog * 10)));
        bits += this.toBits(sogValue, 10);
        
        // ===== POSITION ACCURACY FLAG =====
        bits += this.toBits(fields.accuracy, 1);
        
        // ===== LONGITUDE (SIGNED 28-BIT) =====
        // Longitude in 1/600000 minute resolution (approximately 1.85m at equator)
        let lonValue = Math.round(fields.lon * 600000);
        lonValue = Math.max(-180*600000, Math.min(180*600000, lonValue));  // Clamp to valid range
        bits += this.toSignedBits(lonValue, 28);
        
        // ===== LATITUDE (SIGNED 27-BIT) =====  
        // Latitude in 1/600000 minute resolution
        let latValue = Math.round(fields.lat * 600000);
        latValue = Math.max(-90*600000, Math.min(90*600000, latValue));    // Clamp to valid range
        bits += this.toSignedBits(latValue, 27);
        
        // ===== COURSE OVER GROUND =====
        // Course in 0.1 degree resolution, range 0-359.9° (values 0-3599)
        const cogValue = Math.max(0, Math.min(3599, Math.round(fields.cog * 10)));
        bits += this.toBits(cogValue, 12);
        
        // ===== TRUE HEADING =====
        // Heading in 1 degree resolution, range 0-359°
        const hdgValue = Math.max(0, Math.min(359, Math.round(fields.hdg)));
        bits += this.toBits(hdgValue, 9);
        
        // ===== TIMESTAMP =====
        bits += this.toBits(fields.timestamp, 6);     // UTC seconds (0-59)
        
        // ===== RESERVED/SPARE FIELDS =====
        bits += this.toBits(0, 4);                    // Regional reserved
        bits += this.toBits(0, 3);                    // Spare bits
        bits += this.toBits(0, 1);                    // RAIM flag (integrity indicator)
        bits += this.toBits(0, 19);                   // Communication state

        // Debug logging for bit string validation
        console.log(`AIS bit string length: ${bits.length} bits`);
        
        // ===== PAD TO 6-BIT BOUNDARY =====
        // AIS uses 6-bit ASCII encoding, so bit string must be multiple of 6
        while (bits.length % 6 !== 0) {
            bits += '0';
        }

        // ===== CONVERT TO 6-BIT ASCII =====
        // Convert binary bit string to AIS 6-bit ASCII character encoding
        let payload = '';
        for (let i = 0; i < bits.length; i += 6) {
            const sixBits = parseInt(bits.substr(i, 6), 2);
            payload += this.sixBitToChar(sixBits);
        }

        return payload;
    }

    /**
     * Convert a decimal value to binary bits with specified length.
     * Used for packing unsigned integer values into AIS bit fields.
     * 
     * @param {number} value - Unsigned integer value to convert
     * @param {number} length - Number of bits in the output
     * @returns {string} Binary string padded to specified length
     */
    toBits(value, length) {
        // Handle unsigned values only - negative values indicate error
        if (value < 0) {
            console.warn(`toBits called with negative value ${value}, using 0`);
            value = 0;
        }
        
        // Clamp value to maximum representable in specified bit length
        const maxValue = (1 << length) - 1;
        if (value > maxValue) {
            console.warn(`toBits: value ${value} exceeds max ${maxValue} for ${length} bits`);
            value = maxValue;
        }
        
        // Convert to binary string and pad with leading zeros
        return value.toString(2).padStart(length, '0');
    }

    /**
     * Convert a signed decimal value to two's complement binary representation.
     * Used for latitude, longitude, and other signed AIS fields.
     * 
     * @param {number} value - Signed integer value to convert
     * @param {number} length - Number of bits in the output
     * @returns {string} Binary string in two's complement format
     */
    toSignedBits(value, length) {
        // Calculate valid range for signed values
        const maxValue = (1 << (length - 1)) - 1;     // 2^(n-1) - 1
        const minValue = -(1 << (length - 1));        // -2^(n-1)
        
        // Clamp to valid signed range
        if (value > maxValue) {
            console.warn(`toSignedBits: value ${value} exceeds max ${maxValue} for ${length} bits`);
            value = maxValue;
        }
        if (value < minValue) {
            console.warn(`toSignedBits: value ${value} below min ${minValue} for ${length} bits`);
            value = minValue;
        }
        
        // Convert negative numbers to unsigned two's complement representation
        if (value < 0) {
            value = (1 << length) + value;  // Add 2^length to negative value
        }
        
        // Return binary string padded to specified length
        return value.toString(2).padStart(length, '0');
    }

    /**
     * Convert 6-bit value to AIS character encoding.
     * AIS uses a modified ASCII encoding where values 0-63 map to specific characters.
     * 
     * ENCODING RULES:
     * - Values 0-39: ASCII 48-87 (characters '0'-'W')
     * - Values 40-63: ASCII 96-119 (characters '`'-'w')
     * 
     * @param {number} val - 6-bit value (0-63)
     * @returns {string} Single AIS-encoded character
     */
    sixBitToChar(val) {
        // AIS 6-bit ASCII encoding - ITU-R M.1371-5 standard
        if (val < 40) {
            return String.fromCharCode(val + 48);  // 0-39 -> '0'-'W'
        } else {
            return String.fromCharCode(val + 56);  // 40-63 -> '`'-'w'
        }
    }

    /**
     * Compute NMEA 0183 checksum for message validation.
     * The checksum is calculated as the XOR of all characters in the sentence
     * (excluding the leading '!' and the checksum itself).
     * 
     * @param {string} sentence - NMEA sentence without leading '!' or trailing checksum
     * @returns {string} Two-digit hexadecimal checksum
     */
    computeChecksum(sentence) {
        let checksum = 0;
        
        // XOR all characters in the sentence
        for (let i = 0; i < sentence.length; i++) {
            checksum ^= sentence.charCodeAt(i);
        }
        
        // Return as uppercase hexadecimal with leading zero if needed
        return checksum.toString(16).toUpperCase().padStart(2, '0');
    }

    // =====================================
    // GNU RADIO COMMUNICATION SYSTEM
    // =====================================
    // This section handles WebSocket communication with the GNU Radio backend
    // for transmitting AIS messages via software-defined radio (SDR).
    // 
    // The communication flow:
    // 1. SIREN Web App generates AIS messages in NMEA format
    // 2. Messages are converted to raw bitstrings
    // 3. Bitstrings are sent via WebSocket to GNU Radio
    // 4. GNU Radio modulates and transmits the signals via SDR hardware
    //
    // SECURITY NOTE: This system can transmit on actual maritime frequencies.
    // Ensure proper authorization and compliance with local regulations.

    /**
     * Establish WebSocket connection to GNU Radio backend.
     * The backend server handles AIS signal modulation and SDR transmission.
     * Connection status is monitored and displayed to the user.
     */
    connectToGNURadio() {
        // Get WebSocket port from UI configuration
        const port = document.getElementById('websocketPort').textContent;
        const wsUrl = `ws://localhost:${port}/ws`;

        try {
            // Create new WebSocket connection
            this.websocket = new WebSocket(wsUrl);

            // ===== CONNECTION ESTABLISHED =====
            this.websocket.onopen = () => {
                this.isConnected = true;
                
                // Update UI to show successful connection
                document.getElementById('connectionStatus').textContent = 'Connected';
                document.getElementById('connectionStatus').className = 'badge bg-success';
                document.getElementById('testTransmissionBtn').disabled = false;
                
                // Log connection success
                this.logMessage('transmissionLog', 'Connected to GNU Radio backend');
                this.showNotification('Connected to GNU Radio!', 'success');
            };

            // ===== CONNECTION ERROR =====
            this.websocket.onerror = (error) => {
                this.isConnected = false;
                
                // Update UI to show error state
                document.getElementById('connectionStatus').textContent = 'Error';
                document.getElementById('connectionStatus').className = 'badge bg-danger';
                
                // Log error details
                this.logMessage('transmissionLog', `Connection error: ${error}`);
                this.showNotification('Failed to connect to GNU Radio', 'error');
            };

            // ===== CONNECTION CLOSED =====
            this.websocket.onclose = () => {
                this.isConnected = false;
                
                // Update UI to show disconnected state
                document.getElementById('connectionStatus').textContent = 'Disconnected';
                document.getElementById('connectionStatus').className = 'badge bg-warning';
                document.getElementById('testTransmissionBtn').disabled = true;
                
                // Log disconnection
                this.logMessage('transmissionLog', 'Disconnected from GNU Radio');
            };

            // ===== MESSAGE RECEIVED =====
            // Handle responses and status messages from GNU Radio backend
            this.websocket.onmessage = (event) => {
                this.logMessage('transmissionLog', `Received: ${event.data}`);
            };

        } catch (error) {
            // Handle WebSocket creation errors
            this.showNotification('Failed to create websocket connection', 'error');
            console.error('Websocket error:', error);
        }
    }

    /**
     * Send an AIS message to GNU Radio for transmission.
     * 
     * This method processes NMEA-formatted AIS messages and converts them
     * to raw bitstrings for GNU Radio transmission. The conversion process:
     * 1. Extract the AIS payload from the NMEA sentence
     * 2. Convert 6-bit ASCII payload to binary bitstring  
     * 3. Send raw bitstring via WebSocket to GNU Radio
     * 4. Update transmission counters and logs
     * 
     * @param {string} nmea - Complete NMEA AIS sentence (e.g., !AIVDM,1,1,,A,payload,0*checksum)
     * @param {string} shipName - Name of transmitting ship for logging
     * @returns {boolean} Success status of transmission attempt
     */
    sendAISMessage(nmea, shipName = 'Unknown') {
        // Verify connection status before attempting transmission
        if (!this.isConnected || !this.websocket) {
            console.warn('Not connected to GNU Radio');
            return false;
        }

        try {
            // ===== EXTRACT AIS PAYLOAD FROM NMEA SENTENCE =====
            // NMEA format: !AIVDM,1,1,,A,<payload>,0*checksum
            const parts = nmea.split(',');
            if (parts.length < 6) {
                console.error('Invalid NMEA sentence:', nmea);
                return false;
            }

            const payload = parts[5];  // Extract the AIS payload portion
            
            // ===== CONVERT PAYLOAD TO RAW BITSTRING =====
            // GNU Radio expects raw binary data, not ASCII-encoded payload
            const bitstring = this.payloadToBitstring(payload);
            
            // ===== TRANSMIT VIA WEBSOCKET =====
            // Send raw bitstring to GNU Radio for modulation and transmission
            this.websocket.send(bitstring);
            
            // ===== UPDATE TRANSMISSION STATISTICS =====
            this.simulation.messageCount++;
            document.getElementById('messageCount').textContent = this.simulation.messageCount;
            document.getElementById('totalPackets').textContent = this.simulation.messageCount;
            
            // ===== LOG TRANSMISSION =====
            // Log the complete NMEA sentence for debugging and audit trail
            this.logMessage('transmissionLog', `${shipName}: ${nmea}`);
            return true;

        } catch (error) {
            // Handle transmission errors gracefully
            console.error('Failed to send AIS message:', error);
            this.logMessage('transmissionLog', `Error sending ${shipName}: ${error.message}`);
            return false;
        }
    }

    /**
     * Convert AIS 6-bit ASCII payload to raw binary bitstring.
     * 
     * This method reverses the AIS encoding process, converting the
     * 6-bit ASCII characters back to their original binary representation
     * for transmission by GNU Radio.
     * 
     * CONVERSION PROCESS:
     * 1. Each ASCII character represents a 6-bit value
     * 2. Characters are decoded using AIS character mapping
     * 3. Each 6-bit value is converted to binary string
     * 4. All binary strings are concatenated into final bitstring
     * 
     * @param {string} payload - AIS payload in 6-bit ASCII encoding
     * @returns {string} Raw binary bitstring for GNU Radio transmission
     */
    payloadToBitstring(payload) {
        let bitstring = '';
        
        // Process each character in the payload
        for (let i = 0; i < payload.length; i++) {
            const char = payload.charCodeAt(i);  // Get ASCII code
            let val;
            
            // Decode AIS 6-bit ASCII character mapping
            if (char >= 48 && char < 88) {
                val = char - 48;    // Characters '0'-'W' (values 0-39)
            } else if (char >= 96 && char < 128) {
                val = char - 56;    // Characters '`'-'w' (values 40-63)
            } else {
                continue; // Skip invalid characters
            }
            
            // Convert 6-bit value to binary string
            for (let j = 5; j >= 0; j--) {
                bitstring += ((val >> j) & 1).toString();
            }
        }
        
        return bitstring;
    }

    /**
     * Send a predefined test message to verify GNU Radio connectivity.
     * Uses a known-good AIS message to test the transmission pipeline.
     */
    sendTestMessage() {
        // Predefined AIS test message (valid Type 1 position report)
        const testNMEA = '!AIVDM,1,1,,A,14eG;o@034o8sd<L9i:a;WF>062D,0*7D';
        
        if (this.sendAISMessage(testNMEA, 'Test Vessel')) {
            this.showNotification('Test message sent', 'success');
        } else {
            this.showNotification('Failed to send test message', 'error');
        }
    }

    // =====================================
    // USER INTERFACE UPDATES
    // =====================================

    updateUI() {
        this.updateShipList();
        this.updateShipSelection();
        
        // Update map if initialized
        if (this.map) {
            this.updateShipPositions();
        }
    }

    updateShipList() {
        const shipList = document.getElementById('shipList');
        
        if (this.ships.length === 0) {
            shipList.innerHTML = '<p class="text-muted">No ships in fleet. Click "Add Ship" to get started.</p>';
            return;
        }

        shipList.innerHTML = this.ships.map((ship, index) => `
            <div class="ship-card ${this.selectedShips.includes(index) ? 'ship-active' : ''}" data-index="${index}">
                <div class="card-body p-3">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <h6 class="mb-1">${ship.name}</h6>
                            <small class="text-muted">MMSI: ${ship.mmsi} | Type: ${this.getShipTypeName(ship.ship_type)}</small>
                            <div class="ship-position">
                                ${ship.lat.toFixed(6)}, ${ship.lon.toFixed(6)} | ${ship.course}° | ${ship.speed} kts
                            </div>
                        </div>
                        <div class="btn-group btn-group-sm">
                            <button class="btn btn-outline-primary" onclick="sirenApp.editShip(${index})" title="Edit">
                                <i class="fas fa-edit"></i>
                            </button>
                            <button class="btn btn-outline-danger" onclick="sirenApp.removeShip(${index})" title="Remove">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `).join('');
    }

    updateShipSelection() {
        // Don't update ship selection UI during simulation to prevent interference
        if (this.simulation.active) {
            console.log('Skipping ship selection update during simulation');
            return;
        }
        
        const select = document.getElementById('selectedShips');
        select.innerHTML = this.ships.map((ship, index) => 
            `<option value="${index}">${ship.name} (${ship.mmsi})</option>`
        ).join('');
    }

    getShipTypeName(type) {
        const types = {
            30: 'Fishing',
            52: 'Tug',
            60: 'Passenger',
            70: 'Cargo',
            80: 'Tanker'
        };
        return types[type] || 'Unknown';
    }

    getShipColor(mmsi) {
        // Generate a consistent color for each ship based on its MMSI
        const colors = [
            '#007bff', '#28a745', '#dc3545', '#ffc107', '#6f42c1', 
            '#fd7e14', '#20c997', '#e83e8c', '#6c757d', '#17a2b8'
        ];
        const hash = mmsi.toString().split('').reduce((a, b) => {
            a = ((a << 5) - a) + b.charCodeAt(0);
            return a & a;
        }, 0);
        return colors[Math.abs(hash) % colors.length];
    }

    // =====================================
    // STORAGE AND PERSISTENCE
    // =====================================

    saveShipsToStorage() {
        localStorage.setItem('siren-ships', JSON.stringify(this.ships));
    }

    loadShipsFromStorage() {
        // Don't load from storage during simulation to prevent interference
        if (this.simulation.active) {
            console.log('Skipping ship loading from storage during simulation');
            return;
        }
        
        const saved = localStorage.getItem('siren-ships');
        if (saved) {
            try {
                this.ships = JSON.parse(saved);
            } catch (error) {
                console.error('Failed to load ships from storage:', error);
                this.ships = [];
            }
        }
    }

    /**
     * Clear all ship data from browser localStorage.
     * This completely removes the stored ship fleet data.
     */
    clearStorage() {
        localStorage.removeItem('siren-ships');
        console.log('Browser storage cleared');
        this.showNotification('Storage cleared', 'info');
    }

    /**
     * Reinitialize browser storage with current ship data.
     * This overwrites any existing stored data with the current fleet.
     */
    reinitializeStorage() {
        this.clearStorage();
        this.saveShipsToStorage();
        console.log('Browser storage reinitialized with current fleet');
        this.showNotification('Storage reinitialized', 'success');
    }

    /**
     * Reset the entire application to a clean state.
     * This clears all ships, resets the UI, and clears storage.
     */
    resetToCleanState() {
        if (confirm('This will remove all ships and reset the application. Are you sure?')) {
            // Stop simulation if running
            if (this.simulation.active) {
                this.stopSimulation();
            }
            
            // Clear all ships
            this.ships = [];
            
            // Clear storage
            this.clearStorage();
            
            // Reset UI
            this.updateUI();
            
            // Clear map markers if map exists
            if (this.map && this.mapState) {
                this.mapState.shipMarkers.forEach(marker => this.map.removeLayer(marker));
                this.mapState.shipMarkers.clear();
                
                if (this.mapState.waypoints) {
                    this.mapState.waypoints.forEach(markers => {
                        markers.forEach(marker => this.map.removeLayer(marker));
                    });
                    this.mapState.waypoints.clear();
                }
                
                if (this.mapState.routeLines) {
                    this.mapState.routeLines.forEach(lines => {
                        lines.forEach(line => this.map.removeLayer(line));
                    });
                    this.mapState.routeLines.clear();
                }
                
                if (this.mapState.trackLines) {
                    this.mapState.trackLines.forEach(line => this.map.removeLayer(line));
                    this.mapState.trackLines.clear();
                }
                
                this.mapState.shipTracks.clear();
            }
            
            console.log('Application reset to clean state');
            this.showNotification('Application reset successfully', 'success');
        }
    }

    /**
     * Backup current storage to a downloadable JSON file.
     * This creates a backup of the current localStorage data.
     */
    backupStorage() {
        const storageData = {
            ships: this.ships,
            timestamp: new Date().toISOString(),
            version: '1.0'
        };
        
        const data = JSON.stringify(storageData, null, 2);
        const blob = new Blob([data], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `siren-storage-backup-${new Date().toISOString().split('T')[0]}.json`;
        a.click();
        
        URL.revokeObjectURL(url);
        this.showNotification('Storage backup created', 'success');
    }

    /**
     * Restore storage from a backup file.
     * This loads ship data from a previously created backup.
     */
    restoreStorage() {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.json';
        input.onchange = (e) => {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    try {
                        const backupData = JSON.parse(e.target.result);
                        
                        // Validate backup structure
                        if (backupData.ships && Array.isArray(backupData.ships)) {
                            this.ships = backupData.ships;
                            this.reinitializeStorage();
                            this.updateUI();
                            this.showNotification('Storage restored successfully', 'success');
                        } else {
                            throw new Error('Invalid backup file structure');
                        }
                    } catch (error) {
                        console.error('Failed to restore storage:', error);
                        this.showNotification('Invalid backup file', 'error');
                    }
                };
                reader.readAsText(file);
            }
        };
        input.click();
    }

    /**
     * Get storage usage information.
     * Returns details about localStorage usage and available space.
     */
    getStorageInfo() {
        const storageKey = 'siren-ships';
        const stored = localStorage.getItem(storageKey);
        
        const info = {
            hasData: !!stored,
            shipCount: this.ships.length,
            storageSize: stored ? new Blob([stored]).size : 0,
            storageDate: stored ? new Date(JSON.parse(stored).timestamp || Date.now()) : null
        };
        
        // Estimate localStorage usage (rough approximation)
        let totalSize = 0;
        for (let key in localStorage) {
            if (localStorage.hasOwnProperty(key)) {
                totalSize += localStorage[key].length;
            }
        }
        info.totalLocalStorageSize = totalSize;
        
        return info;
    }

    /**
     * Display storage information in the console.
     * Useful for debugging storage-related issues.
     */
    showStorageInfo() {
        const info = this.getStorageInfo();
        console.log('=== STORAGE INFORMATION ===');
        console.log(`Ships in memory: ${info.shipCount}`);
        console.log(`Storage data exists: ${info.hasData}`);
        console.log(`Storage size: ${(info.storageSize / 1024).toFixed(2)} KB`);
        console.log(`Total localStorage usage: ${(info.totalLocalStorageSize / 1024).toFixed(2)} KB`);
        if (info.storageDate) {
            console.log(`Last saved: ${info.storageDate.toLocaleString()}`);
        }
        console.log('Ships data:', this.ships);
        
        this.showNotification(`Storage: ${info.shipCount} ships, ${(info.storageSize / 1024).toFixed(2)} KB`, 'info');
    }
    // =====================================
    // =====================================
    // INTERACTIVE MAP FUNCTIONALITY
    // =====================================

    initializeMap() {
        // Initialize map if not already done
        if (!this.map) {
            this.setupMap();
        }
        
        this.setupMapEventListeners();
        this.startMapUpdates();
        this.showNotification('Map initialized successfully', 'success');
    }

    setupMap() {
        console.log('Setting up offline-capable map...');
        
        // Check if Leaflet is available
        if (typeof L === 'undefined') {
            console.error('Leaflet library not loaded!');
            this.showNotification('Leaflet library not found', 'error');
            return;
        }
        
        // Check if map container exists
        const mapContainer = document.getElementById('shipMap');
        if (!mapContainer) {
            console.error('Map container not found!');
            this.showNotification('Map container not found', 'error');
            return;
        }
        
        console.log('Map container found, initializing offline-capable Leaflet map...');
        
        // Define offline tile layers (prefer these)
        const offlineLayers = {
            'OpenStreetMap (Offline)': L.tileLayer('tiles/openstreetmap/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap (Offline Cache)',
                maxZoom: 18,
                minZoom: 1,
                errorTileUrl: 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjU2IiBoZWlnaHQ9IjI1NiIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMjU2IiBoZWlnaHQ9IjI1NiIgZmlsbD0iI2Y4ZjlmYSIvPjx0ZXh0IHg9IjEyOCIgeT0iMTI4IiBmb250LWZhbWlseT0ic2Fucy1zZXJpZiIgZm9udC1zaXplPSIxNCIgZmlsbD0iIzZjNzU3ZCIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPk5vIE9mZmxpbmUgVGlsZTwvdGV4dD48L3N2Zz4='
            }),
            'Satellite (Offline)': L.tileLayer('tiles/satellite/{z}/{x}/{y}.png', {
                attribution: '© Satellite Imagery (Offline Cache)',
                maxZoom: 18,
                minZoom: 1,
                errorTileUrl: 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjU2IiBoZWlnaHQ9IjI1NiIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMjU2IiBoZWlnaHQ9IjI1NiIgZmlsbD0iIzM0NDAyZCIvPjx0ZXh0IHg9IjEyOCIgeT0iMTI4IiBmb250LWZhbWlseT0ic2Fucy1zZXJpZiIgZm9udC1zaXplPSIxNCIgZmlsbD0iIzZjNzU3ZCIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPk5vIE9mZmxpbmUgVGlsZTwvdGV4dD48L3N2Zz4='
            })
        };
        
        // Define online fallback layers
        const onlineLayers = {
            'OpenStreetMap (Online)': L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors',
                maxZoom: 19,
                subdomains: ['a', 'b', 'c']
            }),
            'Satellite (Online)': L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
                attribution: '© Esri, DigitalGlobe, GeoEye, Earthstar Geographics',
                maxZoom: 19
            })
        };
        
        // Detect connection status
        const isOnline = navigator.onLine;
        
        // Combine layers based on connection status
        this.mapLayers = isOnline ? {...offlineLayers, ...onlineLayers} : offlineLayers;
        
        // Initialize Leaflet map with offline-first approach
        const defaultLayer = offlineLayers['OpenStreetMap (Offline)'];
        this.map = L.map('shipMap', {
            center: [39.5, -9.2], // Portugal coast
            zoom: 10,
            layers: [defaultLayer],
            zoomControl: false // We'll add custom controls
        });
        
        // Add custom zoom control
        L.control.zoom({
            position: 'bottomright'
        }).addTo(this.map);
        
        // Add layer control
        const layerControl = L.control.layers(this.mapLayers, {}, {
            position: 'topright',
            collapsed: true
        }).addTo(this.map);
        
        // Add scale control
        L.control.scale({
            position: 'bottomleft',
            imperial: false
        }).addTo(this.map);
        
        // Add connection status indicator
        this.addConnectionStatus();
        
        // Add mouse coordinates display
        this.addMouseCoordinates();
        
        // Map state
        this.mapState = {
            shipMarkers: new Map(),
            shipTracks: new Map(),
            trackLines: new Map(),
            waypoints: new Map(),
            routeLines: new Map(),
            updateInterval: null,
            showTracks: true,
            showWaypoints: true,
            autoFollow: false,
            maxTrackPoints: 20,
            selectedShip: null,
            isOnline: isOnline
        };

        // Add map event listeners
        this.map.on('click', (e) => this.onMapClick(e));
        this.map.on('mousemove', (e) => this.updateMouseCoordinates(e));
        this.map.on('zoomend', () => this.updateZoomDisplay());

        // Create ship icons
        this.shipIcon = L.divIcon({
            className: 'ship-marker',
            html: '<i class="fas fa-ship"></i>',
            iconSize: [24, 24],
            iconAnchor: [12, 12]
        });

        this.selectedShipIcon = L.divIcon({
            className: 'ship-marker selected',
            html: '<i class="fas fa-ship"></i>',
            iconSize: [28, 28],
            iconAnchor: [14, 14]
        });
        
        // Listen for connection changes
        window.addEventListener('online', () => this.handleConnectionChange(true));
        window.addEventListener('offline', () => this.handleConnectionChange(false));

        console.log(`Offline-capable map initialized (${isOnline ? 'Online' : 'Offline'} mode)`);
    }

    setupMapEventListeners() {
        // Map type selection
        document.getElementById('mapTypeSelect').addEventListener('change', (e) => {
            this.changeMapType(e.target.value);
        });

        // Location search
        document.getElementById('searchLocationBtn').addEventListener('click', () => {
            this.searchLocation();
        });
        document.getElementById('locationSearch').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.searchLocation();
        });

        // Map controls
        document.getElementById('centerMapBtn').addEventListener('click', () => this.centerMapOnShips());
        document.getElementById('refreshMapBtn').addEventListener('click', () => this.refreshMap());
        document.getElementById('toggleTracksBtn').addEventListener('click', () => this.toggleTracks());
        document.getElementById('fullscreenMapBtn').addEventListener('click', () => this.toggleFullscreen());

        // Control panel events
        document.getElementById('mapCenterInput').addEventListener('change', (e) => this.setMapCenter(e.target.value));
        document.getElementById('mapZoomSlider').addEventListener('input', (e) => this.setMapZoom(e.target.value));
        document.getElementById('showShipTracks').addEventListener('change', (e) => this.toggleTrackVisibility(e.target.checked));
        document.getElementById('showWaypoints').addEventListener('change', (e) => this.toggleWaypointVisibility(e.target.checked));
        document.getElementById('autoFollowShips').addEventListener('change', (e) => this.toggleAutoFollow(e.target.checked));
        document.getElementById('trackHistorySlider').addEventListener('input', (e) => this.setTrackHistory(e.target.value));
        document.getElementById('mapUpdateInterval').addEventListener('change', (e) => this.setUpdateInterval(e.target.value));
        document.getElementById('realTimeMapUpdates').addEventListener('change', (e) => this.toggleRealTimeUpdates(e.target.checked));

        // Action buttons
        document.getElementById('initializeMapBtn').addEventListener('click', () => this.initializeMap());
        document.getElementById('resetMapViewBtn').addEventListener('click', () => this.resetMapView());
        document.getElementById('exportMapBtn').addEventListener('click', () => this.exportMapView());

        // Waypoint control buttons
        document.getElementById('showAllWaypointsBtn').addEventListener('click', () => this.showAllWaypoints());
        document.getElementById('hideAllWaypointsBtn').addEventListener('click', () => this.hideAllWaypoints());
        document.getElementById('centerOnWaypointsBtn').addEventListener('click', () => this.centerOnWaypoints());
    }

    changeMapType(type) {
        // Remove current layer
        this.map.eachLayer((layer) => {
            if (layer instanceof L.TileLayer) {
                this.map.removeLayer(layer);
            }
        });

        // Add new layer - handle both old and new naming conventions
        let selectedLayer = null;
        
        // Try exact match first
        if (this.mapLayers[type]) {
            selectedLayer = this.mapLayers[type];
        } else {
            // Try to find layer by partial name match
            for (const [layerName, layer] of Object.entries(this.mapLayers)) {
                if (layerName.toLowerCase().includes(type.toLowerCase())) {
                    selectedLayer = layer;
                    break;
                }
            }
        }
        
        // Fallback to first available offline layer
        if (!selectedLayer) {
            const offlineLayers = Object.entries(this.mapLayers).filter(([name]) => 
                name.includes('Offline')
            );
            if (offlineLayers.length > 0) {
                selectedLayer = offlineLayers[0][1];
                console.log(`Fallback to offline layer: ${offlineLayers[0][0]}`);
            }
        }
        
        if (selectedLayer) {
            selectedLayer.addTo(this.map);
        } else {
            console.error('No suitable map layer found');
            this.showNotification('Map layer not available', 'error');
        }
    }

    searchLocation() {
        const query = document.getElementById('locationSearch').value.trim();
        if (!query) return;

        // Check if it's coordinates (lat, lon)
        const coordMatch = query.match(/^(-?\d+\.?\d*),\s*(-?\d+\.?\d*)$/);
        if (coordMatch) {
            const lat = parseFloat(coordMatch[1]);
            const lon = parseFloat(coordMatch[2]);
            this.map.setView([lat, lon], 10);
                       this.addSearchMarker(lat, lon, 'Searched Location');
            return;
        }

        // For location names, you could integrate with a geocoding service
        this.showNotification('Use coordinates format: lat, lon (e.g., 39.5, -9.2)', 'info');
    }

    addSearchMarker(lat, lon, title) {
        L.marker([lat, lon])
            .addTo(this.map)
            .bindPopup(title)
            .openPopup();
    }

    centerMapOnShips() {
        if (this.ships.length === 0) {
            this.showNotification('No ships to center on', 'warning');
            return;
        }

        const bounds = L.latLngBounds();
        this.ships.forEach(ship => {
            bounds.extend([ship.lat, ship.lon]);
        });

        this.map.fitBounds(bounds, { padding: [20, 20] });
    }

    refreshMap() {
        this.updateShipPositions();
        this.showNotification('Map refreshed', 'info');
    }

    toggleTracks() {
        this.mapState.showTracks = !this.mapState.showTracks;
        this.updateTrackVisibility();
        
        const button = document.getElementById('toggleTracksBtn');
        button.innerHTML = this.mapState.showTracks ? 
            '<i class="fas fa-route"></i> Hide Tracks' : 
            '<i class="fas fa-route"></i> Show Tracks';
    }

    toggleFullscreen() {
        const mapElement = document.getElementById('shipMap');
        if (!document.fullscreenElement) {
            mapElement.requestFullscreen().then(() => {
                setTimeout(() => this.map.invalidateSize(), 100);
            });
        } else {
            document.exitFullscreen();
        }
    }

    setMapCenter(value) {
        const match = value.match(/^(-?\d+\.?\d*),\s*(-?\d+\.?\d*)$/);
        if (match) {
            const lat = parseFloat(match[1]);
            const lon = parseFloat(match[2]);
            this.map.setView([lat, lon]);
        }
    }

    setMapZoom(zoom) {
        this.map.setZoom(parseInt(zoom));
        document.getElementById('zoomLevel').textContent = zoom;
    }

    toggleTrackVisibility(show) {
        this.mapState.showTracks = show;
        this.updateTrackVisibility();
    }

    toggleWaypointVisibility(show) {
        this.mapState.showWaypoints = show;
        // Implementation for waypoint visibility
    }

    toggleAutoFollow(enabled) {
        this.mapState.autoFollow = enabled;
    }

    setTrackHistory(points) {
        this.mapState.maxTrackPoints = parseInt(points);
        document.getElementById('trackHistoryValue').textContent = points;
        
        // Trim existing tracks
        this.mapState.shipTracks.forEach((track, mmsi) => {
            if (track.length > this.mapState.maxTrackPoints) {
                this.mapState.shipTracks.set(mmsi, track.slice(-this.mapState.maxTrackPoints));
            }
        });
        this.updateTrackLines();
    }

    setUpdateInterval(interval) {
        this.stopMapUpdates();
        if (document.getElementById('realTimeMapUpdates').checked) {
            this.startMapUpdates(parseInt(interval));
        }
    }

    toggleRealTimeUpdates(enabled) {
        if (enabled) {
            const interval = parseInt(document.getElementById('mapUpdateInterval').value);
            this.startMapUpdates(interval);
        } else {
            this.stopMapUpdates();
        }
    }

    resetMapView() {
        this.map.setView([39.5, -9.2], 8);
        document.getElementById('mapCenterInput').value = '39.5, -9.2';
        document.getElementById('mapZoomSlider').value = '8';
        document.getElementById('zoomLevel').textContent = '8';
    }

    exportMapView() {
        // Simple export functionality - could be enhanced with actual map export
        const center = this.map.getCenter();
        const zoom = this.map.getZoom();
        const mapType = document.getElementById('mapTypeSelect').value;
        
        const data = {
            center: { lat: center.lat, lon: center.lng },
            zoom: zoom,
            mapType: mapType,
            ships: this.ships,
            timestamp: new Date().toISOString()
        };

        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `siren-map-export-${new Date().toISOString().split('T')[0]}.json`;
        a.click();
        URL.revokeObjectURL(url);
        
        this.showNotification('Map view exported', 'success');
    }

    onMapClick(e) {
        // Display click coordinates
        const lat = e.latlng.lat.toFixed(6);
        const lon = e.latlng.lng.toFixed(6);
        console.log(`Map clicked at: ${lat}, ${lon}`);
    }

    updateMouseCoordinates(e) {
        const lat = e.latlng.lat.toFixed(6);
        const lon = e.latlng.lng.toFixed(6);
        document.getElementById('mouseCoords').textContent = `Lat: ${lat}, Lon: ${lon}`;
    }

    updateZoomDisplay() {
        const zoom = this.map.getZoom();
        document.getElementById('mapZoomSlider').value = zoom;
        document.getElementById('zoomLevel').textContent = zoom;
    }

    startMapUpdates(interval = 2000) {
        // Stop any existing update interval
        this.stopMapUpdates();
        
        // Start new update interval
        this.mapState.updateInterval = setInterval(() => {
            if (this.map && this.ships.length > 0) {
                this.updateShipPositions();
            }
        }, interval);
        
        console.log(`Started map updates with ${interval}ms interval`);
    }

    stopMapUpdates() {
        if (this.mapState.updateInterval) {
            clearInterval(this.mapState.updateInterval);
            this.mapState.updateInterval = null;
            console.log('Stopped map updates');
        }
    }

    updateMapCounters() {
        // Update ship count display
        const shipCount = this.ships.length;
        const activeShips = this.ships.filter(ship => ship.speed > 0).length;
        const navigatingShips = this.ships.filter(ship => ship.current_waypoint >= 0).length;
        
        // Update map info panel if it exists
        const mapInfo = document.getElementById('mapInfo');
        if (mapInfo) {
            mapInfo.innerHTML = `
                <small class="text-muted">
                    Ships: ${shipCount} | Active: ${activeShips} | Navigating: ${navigatingShips}
                </small>
            `;
        }
        
        // Update markers count
        const markerCount = this.mapState.shipMarkers ? this.mapState.shipMarkers.size : 0;
        console.log(`Map updated: ${markerCount} ship markers displayed`);
    }

    updateTrackVisibility() {
        if (!this.mapState.trackLines) return;
        
        this.mapState.trackLines.forEach((trackLine, mmsi) => {
            if (this.mapState.showTracks) {
                if (!this.map.hasLayer(trackLine)) {
                    this.map.addLayer(trackLine);
                }
            } else {
                if (this.map.hasLayer(trackLine)) {
                    this.map.removeLayer(trackLine);
                }
            }
        });
    }

    updateTrackLines() {
        if (!this.mapState.showTracks) return;
        
        this.mapState.shipTracks.forEach((track, mmsi) => {
            if (track.length > 1) {
                // Remove existing track line
                if (this.mapState.trackLines.has(mmsi)) {
                    this.map.removeLayer(this.mapState.trackLines.get(mmsi));
                }
                
                // Create new track line
                const trackLine = L.polyline(track, {
                    color: this.getShipColor(mmsi),
                    weight: 2,
                    opacity: 0.5,
                    smoothFactor: 1
                }).addTo(this.map);
                
                // Add tooltip
                const ship = this.ships.find(s => s.mmsi === mmsi);
                if (ship) {
                    trackLine.bindTooltip(`${ship.name} - Movement Track`, {
                        permanent: false,
                        direction: 'center'
                    });
                }
                
                this.mapState.trackLines.set(mmsi, trackLine);
            }
        });
    }

    updateShipPositions() {
        if (!this.map) {
            console.log('Map not initialized, skipping ship position update');
            return;
        }

        if (this.ships.length === 0) {
            console.log('No ships to display on map');
            return;
        }

        console.log(`Updating map positions for ${this.ships.length} ships`);

        this.ships.forEach((ship, index) => {
            this.updateShipMarker(ship, index);
            this.updateShipTrack(ship);
            this.updateShipWaypoints(ship);
        });

        this.updateTrackLines();
        this.updateMapCounters();

        // Auto-follow if enabled and simulation is active
        if (this.mapState.autoFollow && this.simulation.active && this.ships.length > 0) {
            this.centerMapOnShips();
        }
    }

    updateShipMarker(ship, index) {
        const mmsi = ship.mmsi;
        
        if (this.mapState.shipMarkers.has(mmsi)) {
            // Update existing marker
            const marker = this.mapState.shipMarkers.get(mmsi);
            marker.setLatLng([ship.lat, ship.lon]);
        } else {
            // Create new marker
            const marker = L.marker([ship.lat, ship.lon], {
                icon: this.shipIcon,
                rotationAngle: ship.course || 0
            }).addTo(this.map);

            marker.bindPopup(this.createShipPopup(ship));
            marker.on('click', () => this.selectShip(ship, index));
            
            this.mapState.shipMarkers.set(mmsi, marker);
            console.log(`Added ship marker: ${ship.name} (${this.mapState.shipMarkers.size} total)`);
        }
    }

    updateShipTrack(ship) {
        const mmsi = ship.mmsi;
        
        if (!this.mapState.shipTracks.has(mmsi)) {
            this.mapState.shipTracks.set(mmsi, []);
        }
        
        const track = this.mapState.shipTracks.get(mmsi);
        const currentPos = [ship.lat, ship.lon];
        
        // Add position if it's different from the last one
        if (track.length === 0 || 
            track[track.length - 1][0] !== currentPos[0] || 
            track[track.length - 1][1] !== currentPos[1]) {
            
            track.push(currentPos);
            
            // Limit track length
            if (track.length > this.mapState.maxTrackPoints) {
                track.shift();
            }
        }
    }

    createShipPopup(ship) {
        return `
            <div class="ship-popup">
                <h6><strong>${ship.name}</strong></h6>
                <p><strong>MMSI:</strong> ${ship.mmsi}<br>
                <strong>Type:</strong> ${this.getShipTypeName(ship.ship_type)}<br>
                <strong>Position:</strong> ${ship.lat.toFixed(6)}, ${ship.lon.toFixed(6)}<br>
                <strong>Course:</strong> ${ship.course}°<br>
                <strong>Speed:</strong> ${ship.speed} knots<br>
                <strong>Length:</strong> ${ship.length}m</p>
            </div>
        `;
    }

    selectShip(ship, index) {
        this.mapState.selectedShip = ship;
        
        // Update ship marker icons
        this.mapState.shipMarkers.forEach((marker, mmsi) => {
            marker.setIcon(mmsi === ship.mmsi ? this.selectedShipIcon : this.shipIcon);
        });

        // Update ship info panel
        this.updateSelectedShipInfo(ship, index);
    }

    updateSelectedShipInfo(ship, index) {
        const infoPanel = document.getElementById('selectedShipInfo');
        if (infoPanel) {
            infoPanel.innerHTML = `
                <h6><strong>${ship.name}</strong></h6>
                <table class="table table-sm">
                    <tr><td><strong>MMSI:</strong></td><td>${ship.mmsi}</td></tr>
                    <tr><td><strong>Type:</strong></td><td>${this.getShipTypeName(ship.ship_type)}</td></tr>
                    <tr><td><strong>Position:</strong></td><td>${ship.lat.toFixed(6)}, ${ship.lon.toFixed(6)}</td></tr>
                    <tr><td><strong>Course:</strong></td><td>${ship.course}°</td></tr>
                    <tr><td><strong>Speed:</strong></td><td>${ship.speed} knots</td></tr>
                    <tr><td><strong>Length:</strong></td><td>${ship.length}m</td></tr>
                    <tr><td><strong>Waypoints:</strong></td><td>${ship.waypoints ? ship.waypoints.length : 0}</td></tr>
                </table>
                <button class="btn btn-sm btn-primary" onclick="sirenApp.editShip(${index})">
                    <i class="fas fa-edit"></i> Edit Ship
                </button>
            `;
        }
    }

    updateTrackLines() {
        if (!this.mapState.showTracks) return;
        
        this.mapState.shipTracks.forEach((track, mmsi) => {
            if (track.length > 1) {
                // Remove existing track line
                if (this.mapState.trackLines.has(mmsi)) {
                    this.map.removeLayer(this.mapState.trackLines.get(mmsi));
                }
                
                // Create new track line
                const trackLine = L.polyline(track, {
                    color: this.getShipColor(mmsi),
                    weight: 2,
                    opacity: 0.5,
                    smoothFactor: 1
                }).addTo(this.map);
                
                // Add tooltip
                const ship = this.ships.find(s => s.mmsi === mmsi);
                if (ship) {
                    trackLine.bindTooltip(`${ship.name} - Movement Track`, {
                        permanent: false,
                        direction: 'center'
                    });
                }
                
                this.mapState.trackLines.set(mmsi, trackLine);
            }
        });
    }

    updateShipWaypoints(ship) {
        if (!this.map) return;
        
        const mmsi = ship.mmsi;
        
        // Remove existing waypoint markers and route lines for this ship
        if (this.mapState.waypoints.has(mmsi)) {
            const waypoints = this.mapState.waypoints.get(mmsi);
            waypoints.forEach(marker => this.map.removeLayer(marker));
        }
        
        // Clear any existing route lines for this ship
        if (this.mapState.routeLines && this.mapState.routeLines.has) {
            if (this.mapState.routeLines.has(mmsi)) {
                this.mapState.routeLines.get(mmsi).forEach(line => this.map.removeLayer(line));
                this.mapState.routeLines.delete(mmsi);
            }
        } else {
            // Initialize routeLines if it doesn't exist
            this.mapState.routeLines = new Map();
        }
        
        // Don't show waypoints if visibility is turned off
        if (!this.mapState.showWaypoints) {
            this.mapState.waypoints.set(mmsi, []);
            return;
        }
        
        // Add new waypoint markers and route lines
        const waypointMarkers = [];
        const routeLines = [];
        
        if (ship.waypoints && ship.waypoints.length > 0) {
            const shipColor = this.getShipColor(mmsi);
            
            // Create waypoint markers
            ship.waypoints.forEach((waypoint, index) => {
                const isCurrent = index === ship.current_waypoint;
                const isPassed = ship.current_waypoint > index;
                
                let color = '#28a745'; // Default green for future waypoints
                let borderColor = '#fff';
                let radius = 6;
                
                if (isCurrent) {
                    color = '#ffc107'; // Yellow for current target
                    borderColor = '#000';
                    radius = 8;
                } else if (isPassed) {
                    color = '#6c757d'; // Gray for passed waypoints
                    radius = 5;
                }
                
                const marker = L.circleMarker([waypoint[0], waypoint[1]], {
                    radius: radius,
                    fillColor: color,
                    color: borderColor,
                    weight: 2,
                    opacity: 1,
                    fillOpacity: 0.8
                }).addTo(this.map);
                
                // Add waypoint number label
                const label = L.divIcon({
                    className: 'waypoint-label',
                    html: `<div style="background: white; border-radius: 50%; width: 16px; height: 16px; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: bold; border: 1px solid ${color};">${index + 1}</div>`,
                    iconSize: [16, 16],
                    iconAnchor: [8, 8]
                });
                
                const labelMarker = L.marker([waypoint[0], waypoint[1]], { 
                    icon: label,
                    zIndexOffset: 1000 
                }).addTo(this.map);
                
                marker.bindPopup(`
                    <div class="waypoint-popup">
                        <strong>${ship.name}</strong><br>
                        Waypoint ${index + 1}<br>
                        ${waypoint[0].toFixed(6)}, ${waypoint[1].toFixed(6)}<br>
                        Status: ${isCurrent ? 'Current Target' : isPassed ? 'Completed' : 'Pending'}
                    </div>
                `);
                
                waypointMarkers.push(marker, labelMarker);
            });
            
            // Create route lines
            // 1. Line from ship's current position to first waypoint (if navigating)
            if (ship.current_waypoint >= 0 && ship.current_waypoint < ship.waypoints.length) {
                const currentTarget = ship.waypoints[ship.current_waypoint];
                const shipToWaypointLine = L.polyline([
                    [ship.lat, ship.lon],
                    [currentTarget[0], currentTarget[1]]
                ], {
                    color: shipColor,
                    weight: 3,
                    opacity: 0.8,
                    dashArray: '10, 5'
                }).addTo(this.map);
                
                shipToWaypointLine.bindTooltip(`${ship.name} - Active Route`, {
                    permanent: false,
                    direction: 'center'
                });
                
                routeLines.push(shipToWaypointLine);
            }
            
            // 2. Lines connecting all waypoints in sequence
            if (ship.waypoints.length > 1) {
                for (let i = 0; i < ship.waypoints.length - 1; i++) {
                    const isCompleted = ship.current_waypoint > i + 1;
                    const isActive = ship.current_waypoint === i;
                    
                    let lineStyle = {
                        color: shipColor,
                        weight: 2,
                        opacity: 0.6,
                        dashArray: '5, 10'
                    };
                    
                    if (isCompleted) {
                        lineStyle.color = '#6c757d';
                        lineStyle.opacity = 0.4;
                        lineStyle.dashArray = '2, 8';
                    } else if (isActive) {
                        lineStyle.weight = 3;
                        lineStyle.opacity = 0.8;
                        lineStyle.dashArray = '8, 4';
                    }
                    
                    const routeLine = L.polyline([
                        ship.waypoints[i],
                        ship.waypoints[i + 1]
                    ], lineStyle).addTo(this.map);
                    
                    routeLine.bindTooltip(`${ship.name} - WP${i + 1} to WP${i + 2}`, {
                        permanent: false,
                        direction: 'center'
                    });
                    
                    routeLines.push(routeLine);
                }
            }
            
            // 3. Add planned route line (full route overview)
            const fullRouteLine = L.polyline(ship.waypoints, {
                color: shipColor,
                weight: 1,
                opacity: 0.3,
                dashArray: '1, 5'
            }).addTo(this.map);
            
            fullRouteLine.bindTooltip(`${ship.name} - Complete Route (${ship.waypoints.length} waypoints)`, {
                permanent: false,
                direction: 'center'
            });
            
            routeLines.push(fullRouteLine);
        }
        
        this.mapState.waypoints.set(mmsi, waypointMarkers);
        this.mapState.routeLines.set(mmsi, routeLines);
    }

    showAllWaypoints() {
        this.mapState.showWaypoints = true;
        document.getElementById('showWaypoints').checked = true;
        this.ships.forEach(ship => this.updateShipWaypoints(ship));
        this.showNotification('All waypoints shown', 'info');
    }

    hideAllWaypoints() {
        this.mapState.showWaypoints = false;
        document.getElementById('showWaypoints').checked = false;
        
        // Hide all waypoint markers
        this.mapState.waypoints.forEach((waypoints, mmsi) => {
            waypoints.forEach(marker => this.map.removeLayer(marker));
        });
        this.mapState.waypoints.clear();
        
        // Hide all route lines
        if (this.mapState.routeLines) {
            this.mapState.routeLines.forEach((routeLines, mmsi) => {
                routeLines.forEach(line => this.map.removeLayer(line));
            });
            this.mapState.routeLines.clear();
        }
        
        this.showNotification('All waypoints and routes hidden', 'info');
    }

    centerOnWaypoints() {
        const bounds = L.latLngBounds();
        let hasWaypoints = false;
        
        this.ships.forEach(ship => {
            if (ship.waypoints && ship.waypoints.length > 0) {
                ship.waypoints.forEach(waypoint => {
                    bounds.extend([waypoint[0], waypoint[1]]);
                    hasWaypoints = true;
                });
            }
        });
        
        if (hasWaypoints) {
            this.map.fitBounds(bounds, { padding: [20, 20] });
            this.showNotification('Centered on all routes', 'info');
        } else {
            this.showNotification('No waypoints to center on', 'warning');
        }
    }

    // =====================================
    // SHIP DATA VALIDATION
    // =====================================

    validateAndCleanShipData() {
        console.log('Validating and cleaning ship data...');
        
        this.ships.forEach((ship, index) => {
            let isModified = false;
            
            // Validate and fix MMSI
            if (typeof ship.mmsi !== 'number' || ship.mmsi < 100000000 || ship.mmsi > 999999999) {
                console.warn(`Ship ${index} (${ship.name}): Invalid MMSI ${ship.mmsi}, generating new one`);
                ship.mmsi = Math.floor(Math.random() * 900000000) + 100000000;
                isModified = true;
            }
            
            // Validate and fix position - be more conservative with resets
            if (typeof ship.lat !== 'number' || isNaN(ship.lat) || ship.lat < -90 || ship.lat > 90) {
                console.warn(`Ship ${index} (${ship.name}): Invalid latitude ${ship.lat}, resetting to 39.5`);
                ship.lat = 39.5;
                isModified = true;
            }
            if (typeof ship.lon !== 'number' || isNaN(ship.lon) || ship.lon < -180 || ship.lon > 180) {
                console.warn(`Ship ${index} (${ship.name}): Invalid longitude ${ship.lon}, resetting to -9.2`);
                ship.lon = -9.2;
                isModified = true;
            }
            
            // Validate and fix speed - cap at realistic values
            if (typeof ship.speed !== 'number' || isNaN(ship.speed) || ship.speed < 0) {
                console.warn(`Ship ${index} (${ship.name}): Invalid speed ${ship.speed}, setting to 10`);
                ship.speed = 10;
                isModified = true;
            } else if (ship.speed > 40) {
                console.warn(`Ship ${index} (${ship.name}): Unrealistic speed ${ship.speed}, capping at 25`);
                ship.speed = 25;
                isModified = true;
            }
            
            // Validate and fix course - ensure logical consistency
            if (typeof ship.course !== 'number' || isNaN(ship.course)) {
                if (ship.speed > 0) {
                    // Moving ship needs a proper course
                    ship.course = Math.floor(Math.random() * 360);
                    console.warn(`Ship ${index} (${ship.name}): Invalid course for moving ship, setting random course ${ship.course}`);
                } else {
                    ship.course = 0;
                    console.warn(`Ship ${index} (${ship.name}): Invalid course for stationary ship, setting to 0`);
                }
                isModified = true;
            } else {
                // Normalize course to 0-359.9
                const normalizedCourse = ((ship.course % 360) + 360) % 360;
                if (Math.abs(normalizedCourse - ship.course) > 0.1) {
                    console.warn(`Ship ${index} (${ship.name}): Course ${ship.course} normalized to ${normalizedCourse}`);
                    ship.course = normalizedCourse;
                    isModified = true;
                }
            }
            
            // Fix course/speed inconsistency - if ship is moving but course is 0, randomize course
            if (ship.speed > 0 && ship.course === 0) {
                ship.course = Math.floor(Math.random() * 360);
                console.warn(`Ship ${index} (${ship.name}): Moving ship had course 0°, randomized to ${ship.course}°`);
                isModified = true;
            }
            
            // Validate and fix heading - keep synchronized with course
            if (typeof ship.heading !== 'number' || isNaN(ship.heading)) {
                ship.heading = ship.course;
                console.warn(`Ship ${index} (${ship.name}): Invalid heading, setting to course ${ship.course}`);
                isModified = true;
            } else {
                // Normalize heading to 0-359
                const normalizedHeading = ((ship.heading % 360) + 360) % 360;
                if (Math.abs(normalizedHeading - ship.heading) > 0.1) {
                    console.warn(`Ship ${index} (${ship.name}): Heading ${ship.heading} normalized to ${normalizedHeading}`);
                    ship.heading = normalizedHeading;
                    isModified = true;
                }
            }
            
            // Validate and fix status - ensure consistency with speed
            if (typeof ship.status !== 'number' || isNaN(ship.status) || ship.status < 0 || ship.status > 15) {
                ship.status = ship.speed > 0 ? 0 : 1; // 0 = under way, 1 = at anchor
                console.warn(`Ship ${index} (${ship.name}): Invalid status, setting to ${ship.status}`);
                isModified = true;
            } else if (ship.status === 1 && ship.speed > 0) {
                // Ship is "at anchor" but moving - fix the inconsistency
                ship.status = 0; // Under way using engine
                console.warn(`Ship ${index} (${ship.name}): Status was 'at anchor' but ship is moving, changed to 'under way'`);
                isModified = true;
            }
            
            // Validate and fix other fields
            if (typeof ship.turn !== 'number' || isNaN(ship.turn)) {
                ship.turn = 0;
                isModified = true;
            } else {
                ship.turn = Math.max(-127, Math.min(127, ship.turn));
            }
            
            if (typeof ship.accuracy !== 'number' || isNaN(ship.accuracy)) {
                ship.accuracy = 1;
                isModified = true;
            }
            
            // Ensure other required fields exist
            if (typeof ship.turn !== 'number') {
                ship.turn = 0;
                isModified = true;
            }
            if (typeof ship.accuracy !== 'number') {
                ship.accuracy = 1;
                isModified = true;
            }
            
            if (isModified) {
                console.log(`Ship ${index} (${ship.name}): Data cleaned and validated`);
            }
        });
        
        if (this.ships.some(ship => isNaN(ship.lat) || isNaN(ship.lon))) {
            console.error('Ship data validation failed - some ships still have invalid data!');
        } else {
            console.log('All ship data validated successfully');
        }
        
        // Save cleaned data
        this.saveShipsToStorage();
    }

    // =====================================
    // UTILITY FUNCTIONS AND SYSTEM HELPERS
    // =====================================
    // This section contains general-purpose utilities used throughout the application
    // for logging, notifications, data validation, and user interface management.

    /**
     * Add a timestamped message to a log display element.
     * Used for debugging, audit trails, and user feedback during simulation.
     * 
     * @param {string} elementId - ID of DOM element to append log message
     * @param {string} message - Log message content
     */
    logMessage(elementId, message) {
        const logElement = document.getElementById(elementId);
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = document.createElement('div');
        
        // Format log entry with timestamp and message
        logEntry.innerHTML = `<span class="text-muted">${timestamp}</span> ${message}`;
        
        // Add to log and auto-scroll to bottom
        logElement.appendChild(logEntry);
        logElement.scrollTop = logElement.scrollHeight;
    }

    /**
     * Display a user notification using the Noty library.
     * Provides consistent, non-intrusive feedback for user actions.
     * 
     * @param {string} message - Notification text to display
     * @param {string} type - Notification type ('info', 'success', 'warning', 'error')
     */
    showNotification(message, type = 'info') {
        new Noty({
            layout: 'topRight',      // Position notifications in top-right corner
            text: message,           // Message content
            type: type,              // Visual style based on message type
            timeout: 3000,           // Auto-hide after 3 seconds
            progressBar: true,       // Show countdown progress bar
            closeWith: ['click']     // Allow click-to-dismiss
        }).show();
    }

    // ===== MAP UTILITY FUNCTIONS =====
    // These functions support the interactive mapping system for visualization

    /**
     * Add connection status indicator to the map interface.
     * Shows whether the application is online or offline for tile access.
     */
    addConnectionStatus() {
        const connectionControl = L.control({position: 'topleft'});
        
        connectionControl.onAdd = function(map) {
            const div = L.DomUtil.create('div', 'connection-status');
            
            // Style the connection status indicator
            div.style.cssText = `
                background: rgba(255,255,255,0.95);
                padding: 8px 12px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
                box-shadow: 0 2px 4px rgba(0,0,0,0.2);
                border: 1px solid #ddd;
                margin: 10px;
            `;
            
            // Function to update status display based on connection
            const updateStatus = () => {
                const isOnline = navigator.onLine;
                const iconClass = isOnline ? 'fa-wifi' : 'fa-wifi-slash';
                const iconColor = isOnline ? '#28a745' : '#dc3545';
                const statusText = isOnline ? 'Online' : 'Offline';
                const bgColor = isOnline ? '#d4edda' : '#f8d7da';
                
                div.innerHTML = `
                    <i class="fas ${iconClass}" style="color: ${iconColor}; margin-right: 6px;"></i>
                    <span style="color: #212529;">${statusText}</span>
                `;
                div.style.backgroundColor = bgColor;
            };
            
            // Initialize status display
            updateStatus();
            
            // Update when connection status changes
            window.addEventListener('online', updateStatus);
            window.addEventListener('offline', updateStatus);
            
            return div;
        };
        
        connectionControl.addTo(this.map);
    }

    /**
     * Add mouse coordinates display to the map interface.
     * Shows real-time latitude/longitude coordinates as user moves mouse.
     */
    addMouseCoordinates() {
        const coordsControl = L.control({position: 'bottomright'});
        
        coordsControl.onAdd = function(map) {
            const div = L.DomUtil.create('div', 'mouse-coordinates');
            
            // Style coordinates display
            div.style.cssText = `
                background: rgba(0,0,0,0.8);
                color: white;
                padding: 4px 8px;
                border-radius: 3px;
                font-family: 'Courier New', monospace;
                font-size: 11px;
                margin-bottom: 45px;
                margin-right: 10px;
                min-width: 180px;
                text-align: center;
            `;
            div.innerHTML = 'Lat: ---.------, Lon: ---.------';
            
            return div;
        };
        
        coordsControl.addTo(this.map);
        
        // Update coordinates on mouse movement
        this.map.on('mousemove', (e) => {
            const coords = document.querySelector('.mouse-coordinates');
            if (coords) {
                const lat = e.latlng.lat.toFixed(6);
                const lon = e.latlng.lng.toFixed(6);
                coords.innerHTML = `Lat: ${lat}, Lon: ${lon}`;
            }
        });
        
        // Clear coordinates when mouse leaves map
        this.map.on('mouseout', () => {
            const coords = document.querySelector('.mouse-coordinates');
            if (coords) {
                coords.innerHTML = 'Lat: ---.------, Lon: ---.------';
            }
        });
    }

    /**
     * Handle changes in internet connectivity status.
     * Updates map layers and notifies user of connectivity changes.
     * 
     * @param {boolean} isOnline - Current connection status
     */
    handleConnectionChange(isOnline) {
        const message = isOnline ? 
            'Internet connection restored - Online maps available' : 
            'Internet connection lost - Using offline maps only';
        const type = isOnline ? 'success' : 'warning';
        
        this.showNotification(message, type);
        
        if (this.mapState) {
            this.mapState.isOnline = isOnline;
        }
        
        // Update available map layers based on connection
        this.updateAvailableLayers(isOnline);
        
        console.log(`Connection status changed: ${isOnline ? 'Online' : 'Offline'}`);
    }

    /**
     * Update available map layers based on connection status.
     * Manages fallback between online and offline tile sources.
     * 
     * @param {boolean} isOnline - Current internet connectivity status
     */
    updateAvailableLayers(isOnline) {
        // This could refresh the layer control to show/hide online layers
        // Currently logs the change for debugging
        console.log(`Map layers updated for ${isOnline ? 'online' : 'offline'} mode`);
    }
}

// =====================================
// APPLICATION INITIALIZATION
// =====================================
// Global application instance and startup code

/**
 * Global SIREN application instance.
 * This variable provides access to the application from onclick handlers
 * and other contexts where the class instance is needed.
 */
let sirenApp;

/**
 * Initialize the SIREN application when the DOM is fully loaded.
 * This ensures all HTML elements are available before the application starts.
 */
document.addEventListener('DOMContentLoaded', () => {
    // Create and initialize the main application instance
    sirenApp = new SIRENWebApp();
    
    console.log('SIREN Web Application fully loaded and ready');
});

/**
 * Make the SIREN application globally accessible.
 * Required for onclick handlers in dynamically generated HTML content.
 * 
 * SECURITY NOTE: Global variables can be accessed by any script on the page.
 * In production environments, consider using more secure event handling patterns.
 */
window.sirenApp = sirenApp;
