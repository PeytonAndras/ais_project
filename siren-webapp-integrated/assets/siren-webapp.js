/**
 * SIREN Integrated Web Application
 * Spoofed Identification & Real-time Emulation Node
 * 
 * Combines the proven ais-simulator transmission with comprehensive
 * ship simulation, fleet management, and scenario capabilities.
 * 
 * @author Peyton Andras @ Louisiana State University 2025
 */

class SIRENWebApp {
    constructor() {
        this.ships = [];
        this.selectedShips = [];
        this.simulation = {
            active: false,
            interval: 10,
            intervalId: null,
            messageCount: 0,
            startTime: null
        };
        this.websocket = null;
        this.isConnected = false;
        this.currentShipIndex = -1;
        
        // Map-related properties
        this.map = null;
        this.mapState = null;
        this.mapLayers = null;
        this.shipIcon = null;
        this.selectedShipIcon = null;
        
        this.init();
    }

    init() {
        this.loadShipsFromStorage();
        this.setupEventListeners();
        this.updateUI();
        this.connectToGNURadio();
        
        console.log(`SIREN Web Application initialized with ${this.ships.length} ships`);
        
        // If no ships loaded from storage, you might want to load sample data
        if (this.ships.length === 0) {
            console.log('No ships found in storage. You can load sample data using the "Load Sample" button in Fleet Management.');
        }
    }

    setupEventListeners() {
        // Fleet Management
        document.getElementById('addShipBtn').addEventListener('click', () => this.showAddShipModal());
        document.getElementById('saveShipBtn').addEventListener('click', () => this.addShip());
        document.getElementById('loadFleetBtn').addEventListener('click', () => this.loadFleet());
        document.getElementById('saveFleetBtn').addEventListener('click', () => this.saveFleet());
        document.getElementById('loadSampleBtn').addEventListener('click', () => this.loadSampleData());

        // Simulation Control
        document.getElementById('startSimulationBtn').addEventListener('click', () => this.startSimulation());
        document.getElementById('stopSimulationBtn').addEventListener('click', () => this.stopSimulation());

        // Transmission
        document.getElementById('connectBtn').addEventListener('click', () => this.connectToGNURadio());
        document.getElementById('testTransmissionBtn').addEventListener('click', () => this.sendTestMessage());

        // Tab switching
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

        // Keyboard events for waypoint picking
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.waypointPickingMode && this.waypointPickingMode.active) {
                this.disableWaypointPickingMode();
                this.showNotification('Waypoint picking cancelled', 'info');
            }
        });

        // Waypoint control buttons
        document.getElementById('showAllWaypointsBtn').addEventListener('click', () => this.showAllWaypoints());
        document.getElementById('hideAllWaypointsBtn').addEventListener('click', () => this.hideAllWaypoints());
        document.getElementById('centerOnWaypointsBtn').addEventListener('click', () => this.centerOnWaypoints());
    }

    // =====================================
    // SHIP FLEET MANAGEMENT
    // =====================================

    showAddShipModal() {
        // Generate random MMSI
        const randomMMSI = Math.floor(Math.random() * (999999999 - 200000000) + 200000000);
        document.getElementById('shipMMSI').value = randomMMSI;
        
        const modal = new bootstrap.Modal(document.getElementById('addShipModal'));
        modal.show();
    }

    addShip() {
        const form = document.getElementById('addShipForm');
        if (!form.checkValidity()) {
            form.reportValidity();
            return;
        }

        const ship = {
            name: document.getElementById('shipName').value,
            mmsi: parseInt(document.getElementById('shipMMSI').value),
            ship_type: parseInt(document.getElementById('shipType').value),
            length: parseFloat(document.getElementById('shipLength').value),
            beam: 10, // Default beam
            lat: parseFloat(document.getElementById('shipLat').value),
            lon: parseFloat(document.getElementById('shipLon').value),
            course: parseFloat(document.getElementById('shipCourse').value),
            speed: parseFloat(document.getElementById('shipSpeed').value),
            status: 0, // Under way using engine
            turn: 0,
            destination: "",
            accuracy: 1,
            heading: parseFloat(document.getElementById('shipCourse').value),
            waypoints: [],
            current_waypoint: -1,
            waypoint_radius: 0.01
        };

        this.ships.push(ship);
        this.saveShipsToStorage();
        this.updateUI();
        
        const modal = bootstrap.Modal.getInstance(document.getElementById('addShipModal'));
        modal.hide();
        
        form.reset();
        
        this.showNotification('Ship added successfully', 'success');
    }

    removeShip(index) {
        if (confirm(`Remove ship "${this.ships[index].name}"?`)) {
            const ship = this.ships[index];
            const mmsi = ship.mmsi;
            
            // Clean up map markers and routes for this ship
            if (this.map) {
                // Remove ship marker
                if (this.mapState.shipMarkers && this.mapState.shipMarkers.has(mmsi)) {
                    this.map.removeLayer(this.mapState.shipMarkers.get(mmsi));
                    this.mapState.shipMarkers.delete(mmsi);
                }
                
                // Remove waypoint markers
                if (this.mapState.waypoints && this.mapState.waypoints.has(mmsi)) {
                    this.mapState.waypoints.get(mmsi).forEach(marker => this.map.removeLayer(marker));
                    this.mapState.waypoints.delete(mmsi);
                }
                
                // Remove route lines
                if (this.mapState.routeLines && this.mapState.routeLines.has(mmsi)) {
                    this.mapState.routeLines.get(mmsi).forEach(line => this.map.removeLayer(line));
                    this.mapState.routeLines.delete(mmsi);
                }
                
                // Remove ship tracks
                if (this.mapState.shipTracks && this.mapState.shipTracks.has(mmsi)) {
                    this.mapState.shipTracks.delete(mmsi);
                }
                
                // Remove track lines
                if (this.mapState.trackLines && this.mapState.trackLines.has(mmsi)) {
                    this.map.removeLayer(this.mapState.trackLines.get(mmsi));
                    this.mapState.trackLines.delete(mmsi);
                }
            }
            
            this.ships.splice(index, 1);
            this.saveShipsToStorage();
            this.updateUI();
            this.showNotification('Ship removed', 'info');
        }
    }

    editShip(index) {
        this.currentShipIndex = index;
        const ship = this.ships[index];
        
        const editor = document.getElementById('shipEditor');
        editor.innerHTML = `
            <form id="shipEditForm">
                <div class="mb-2">
                    <label class="form-label">Name</label>
                    <input type="text" class="form-control form-control-sm" id="editName" value="${ship.name}">
                </div>
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
                <div class="mb-2">
                    <label class="form-label">Course (°)</label>
                    <input type="number" class="form-control form-control-sm" id="editCourse" value="${ship.course}" min="0" max="359">
                </div>
                <div class="mb-2">
                    <label class="form-label">Speed (knots)</label>
                    <input type="number" class="form-control form-control-sm" id="editSpeed" value="${ship.speed}" min="0" max="50">
                </div>
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
                
                <!-- Waypoint Management Section -->
                <div class="mb-3">
                    <hr>
                    <h6><i class="fas fa-route"></i> Waypoint Navigation</h6>
                    
                    <!-- Waypoint List -->
                    <div class="waypoint-list mb-2" style="max-height: 150px; overflow-y: auto; border: 1px solid #dee2e6; border-radius: 4px; padding: 5px;">
                        <div id="waypointList-${index}">
                            ${this.renderWaypointList(ship.waypoints || [])}
                        </div>
                    </div>
                    
                    <!-- Add Waypoint Controls -->
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
                    
                    <!-- Waypoint Controls -->
                    <div class="btn-group btn-group-sm w-100 mb-2">
                        <button type="button" class="btn btn-outline-info" onclick="sirenApp.pickWaypointFromMap(${index})" title="Pick from Map">
                            <i class="fas fa-map-marker-alt"></i> Pick from Map
                        </button>
                        <button type="button" class="btn btn-outline-warning" onclick="sirenApp.clearWaypoints(${index})" title="Clear All">
                            <i class="fas fa-trash"></i> Clear All
                        </button>
                        <button type="button" class="btn btn-outline-success" onclick="sirenApp.startWaypointNavigation(${index})" title="Start Navigation">
                            <i class="fas fa-play"></i> Start Nav
                        </button>
                    </div>
                    
                    <small class="text-muted">Ship will navigate to waypoints in order. Current: ${ship.current_waypoint >= 0 ? ship.current_waypoint + 1 : 'None'}</small>
                </div>
                
                <div class="d-grid gap-1">
                    <button type="button" class="btn btn-siren btn-sm" onclick="sirenApp.updateShip()">Update</button>
                    <button type="button" class="btn btn-outline-secondary btn-sm" onclick="sirenApp.clearEditor()">Cancel</button>
                </div>
            </form>
        `;
    }

    updateShip() {
        if (this.currentShipIndex === -1) return;
        
        const ship = this.ships[this.currentShipIndex];
        ship.name = document.getElementById('editName').value;
        ship.lat = parseFloat(document.getElementById('editLat').value);
        ship.lon = parseFloat(document.getElementById('editLon').value);
        ship.course = parseFloat(document.getElementById('editCourse').value);
        ship.speed = parseFloat(document.getElementById('editSpeed').value);
        ship.status = parseInt(document.getElementById('editStatus').value);
        ship.heading = ship.course;
        
        this.saveShipsToStorage();
        this.updateUI();
        this.clearEditor();
        this.showNotification('Ship updated', 'success');
    }

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
    // SIMULATION CONTROL
    // =====================================

    startSimulation() {
        if (this.ships.length === 0) {
            this.showNotification('No ships available to simulate', 'warning');
            return;
        }

        if (!this.isConnected) {
            this.showNotification('Not connected to GNU Radio backend', 'error');
            return;
        }

        this.simulation.active = true;
        this.simulation.interval = parseInt(document.getElementById('simulationInterval').value);
        this.simulation.messageCount = 0;
        this.simulation.startTime = new Date();

        // Get selected ships or use all ships
        const selectedOptions = Array.from(document.getElementById('selectedShips').selectedOptions);
        this.selectedShips = selectedOptions.length > 0 
            ? selectedOptions.map(option => parseInt(option.value))
            : this.ships.map((_, index) => index);

        // Update UI
        document.getElementById('startSimulationBtn').disabled = true;
        document.getElementById('stopSimulationBtn').disabled = false;
        document.getElementById('simulationStatus').textContent = 'Running';
        document.getElementById('simulationStatus').className = 'badge bg-success';
        document.getElementById('activeShipCount').textContent = this.selectedShips.length;

        // Start simulation loop
        this.runSimulationStep();
        this.simulation.intervalId = setInterval(() => this.runSimulationStep(), this.simulation.interval * 1000);

        this.logMessage('simulationLog', `Started simulation with ${this.selectedShips.length} ships`);
        this.showNotification('Simulation started', 'success');
    }

    stopSimulation() {
        this.simulation.active = false;
        
        if (this.simulation.intervalId) {
            clearInterval(this.simulation.intervalId);
            this.simulation.intervalId = null;
        }

        // Update UI
        document.getElementById('startSimulationBtn').disabled = false;
        document.getElementById('stopSimulationBtn').disabled = true;
        document.getElementById('simulationStatus').textContent = 'Stopped';
        document.getElementById('simulationStatus').className = 'badge bg-secondary';

        this.logMessage('simulationLog', 'Simulation stopped');
        this.showNotification('Simulation stopped', 'info');
    }

    runSimulationStep() {
        if (!this.simulation.active) return;

        const channel = document.getElementById('aisChannel').value;
        
        this.selectedShips.forEach((shipIndex, i) => {
            const ship = this.ships[shipIndex];
            if (!ship) return;

            // Move the ship
            this.moveShip(ship);

            // Generate AIS message
            const aisMessage = this.generateAISMessage(ship, channel);
            
            // Send to GNU Radio
            this.sendAISMessage(aisMessage, ship.name);

            setTimeout(() => {
                // Delay between ships
            }, i * 500);
        });

        this.updateUI();
        
        // Update map if initialized
        if (this.map) {
            this.updateShipPositions();
        }
    }

    moveShip(ship) {
        if (ship.speed <= 0) return;

        // Check if ship is following waypoints
        if (ship.waypoints && ship.waypoints.length > 0 && ship.current_waypoint >= 0) {
            this.moveShipWithWaypoints(ship);
        } else {
            this.moveShipStraight(ship);
        }
    }

    moveShipStraight(ship) {
        // Simple movement calculation (original behavior)
        const timeStep = this.simulation.interval / 3600; // Convert seconds to hours
        const distanceNM = ship.speed * timeStep;
        
        // Convert to lat/lon change
        const latChange = distanceNM * Math.cos(ship.course * Math.PI / 180) / 60;
        const lonChange = distanceNM * Math.sin(ship.course * Math.PI / 180) / (60 * Math.cos(ship.lat * Math.PI / 180));
        
        ship.lat += latChange;
        ship.lon += lonChange;

        // Simple boundary check (keep in reasonable area)
        if (ship.lat > 90) ship.lat = 90;
        if (ship.lat < -90) ship.lat = -90;
        if (ship.lon > 180) ship.lon = -180;
        if (ship.lon < -180) ship.lon = 180;
    }

    moveShipWithWaypoints(ship) {
        if (ship.current_waypoint >= ship.waypoints.length) {
            // All waypoints reached, stop navigation
            ship.current_waypoint = -1;
            console.log(`${ship.name}: All waypoints reached, stopping navigation`);
            return;
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
                ship.course = this.calculateBearing(ship.lat, ship.lon, nextWaypoint[0], nextWaypoint[1]);
                ship.heading = ship.course;
                console.log(`${ship.name}: Set course to waypoint ${ship.current_waypoint + 1}: ${ship.course.toFixed(1)}°`);
            } else {
                console.log(`${ship.name}: All waypoints reached`);
                ship.current_waypoint = -1; // Stop navigation
                return;
            }
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
    // AIS MESSAGE GENERATION
    // =====================================

    generateAISMessage(ship, channel = 'A') {
        // Create AIS Type 1 Position Report
        const fields = {
            msg_type: 1,
            repeat: 0,
            mmsi: ship.mmsi,
            nav_status: ship.status,
            rot: ship.turn,
            sog: ship.speed,
            accuracy: ship.accuracy,
            lon: ship.lon,
            lat: ship.lat,
            cog: ship.course,
            hdg: ship.heading,
            timestamp: new Date().getSeconds() % 60
        };

        // Build AIS payload (simplified version)
        const payload = this.buildAISPayload(fields);
        const sentence = `AIVDM,1,1,,${channel},${payload},0`;
        const checksum = this.computeChecksum(sentence);
        
        return `!${sentence}*${checksum}`;
    }

    buildAISPayload(fields) {
        // Simplified AIS payload generation
        // In a real implementation, this would follow the complete AIS specification
        let bits = '';
        
        // Message type (6 bits)
        bits += this.toBits(fields.msg_type, 6);
        // Repeat indicator (2 bits)
        bits += this.toBits(fields.repeat, 2);
        // MMSI (30 bits)
        bits += this.toBits(fields.mmsi, 30);
        // Navigation status (4 bits)
        bits += this.toBits(fields.nav_status, 4);
        // Rate of turn (8 bits)
        bits += this.toBits(fields.rot + 128, 8);
        // Speed over ground (10 bits)
        bits += this.toBits(Math.round(fields.sog * 10), 10);
        // Position accuracy (1 bit)
        bits += this.toBits(fields.accuracy, 1);
        // Longitude (28 bits)
        bits += this.toBits(Math.round(fields.lon * 600000), 28);
        // Latitude (27 bits)
        bits += this.toBits(Math.round(fields.lat * 600000), 27);
        // Course over ground (12 bits)
        bits += this.toBits(Math.round(fields.cog * 10), 12);
        // True heading (9 bits)
        bits += this.toBits(fields.hdg, 9);
        // Time stamp (6 bits)
        bits += this.toBits(fields.timestamp, 6);
        // Regional (4 bits)
        bits += this.toBits(0, 4);
        // Spare (3 bits)
        bits += this.toBits(0, 3);
        // RAIM flag (1 bit)
        bits += this.toBits(0, 1);
        // Communication state (19 bits)
        bits += this.toBits(0, 19);

        // Pad to multiple of 6 bits
        while (bits.length % 6 !== 0) {
            bits += '0';
        }

        // Convert to 6-bit ASCII
        let payload = '';
        for (let i = 0; i < bits.length; i += 6) {
            const sixBits = parseInt(bits.substr(i, 6), 2);
            payload += this.sixBitToChar(sixBits);
        }

        return payload;
    }

    toBits(value, length) {
        // Handle negative numbers (two's complement)
        if (value < 0) {
            value = (1 << length) + value;
        }
        return value.toString(2).padStart(length, '0');
    }

    sixBitToChar(val) {
        if (val < 32) return String.fromCharCode(val + 48);
        else return String.fromCharCode(val + 56);
    }

    computeChecksum(sentence) {
        let checksum = 0;
        for (let i = 0; i < sentence.length; i++) {
            checksum ^= sentence.charCodeAt(i);
        }
        return checksum.toString(16).toUpperCase().padStart(2, '0');
    }

    // =====================================
    // GNU RADIO COMMUNICATION
    // =====================================

    connectToGNURadio() {
        const port = document.getElementById('websocketPort').textContent;
        const wsUrl = `ws://localhost:${port}/ws`;

        try {
            this.websocket = new WebSocket(wsUrl);

            this.websocket.onopen = () => {
                this.isConnected = true;
                document.getElementById('connectionStatus').textContent = 'Connected';
                document.getElementById('connectionStatus').className = 'badge bg-success';
                document.getElementById('testTransmissionBtn').disabled = false;
                this.logMessage('transmissionLog', 'Connected to GNU Radio backend');
                this.showNotification('Connected to GNU Radio!', 'success');
            };

            this.websocket.onerror = (error) => {
                this.isConnected = false;
                document.getElementById('connectionStatus').textContent = 'Error';
                document.getElementById('connectionStatus').className = 'badge bg-danger';
                this.logMessage('transmissionLog', `Connection error: ${error}`);
                this.showNotification('Failed to connect to GNU Radio', 'error');
            };

            this.websocket.onclose = () => {
                this.isConnected = false;
                document.getElementById('connectionStatus').textContent = 'Disconnected';
                document.getElementById('connectionStatus').className = 'badge bg-warning';
                document.getElementById('testTransmissionBtn').disabled = true;
                this.logMessage('transmissionLog', 'Disconnected from GNU Radio');
            };

            this.websocket.onmessage = (event) => {
                this.logMessage('transmissionLog', `Received: ${event.data}`);
            };

        } catch (error) {
            this.showNotification('Failed to create websocket connection', 'error');
            console.error('Websocket error:', error);
        }
    }

    sendAISMessage(nmea, shipName = 'Unknown') {
        if (!this.isConnected || !this.websocket) {
            console.warn('Not connected to GNU Radio');
            return false;
        }

        try {
            // Extract payload from NMEA sentence
            const parts = nmea.split(',');
            if (parts.length < 6) {
                console.error('Invalid NMEA sentence:', nmea);
                return false;
            }

            const payload = parts[5];
            
            // Convert AIS payload to bitstring
            const bitstring = this.payloadToBitstring(payload);
            
            // Send raw bitstring to GNU Radio (this is the key!)
            this.websocket.send(bitstring);
            
            this.simulation.messageCount++;
            document.getElementById('messageCount').textContent = this.simulation.messageCount;
            document.getElementById('totalPackets').textContent = this.simulation.messageCount;
            
            this.logMessage('transmissionLog', `Transmitted: ${shipName} (${nmea})`);
            return true;

        } catch (error) {
            console.error('Failed to send AIS message:', error);
            this.logMessage('transmissionLog', `Error: ${error.message}`);
            return false;
        }
    }

    payloadToBitstring(payload) {
        let bitstring = '';
        for (let i = 0; i < payload.length; i++) {
            const char = payload.charCodeAt(i);
            let val;
            
            if (char >= 48 && char < 88) {
                val = char - 48;
            } else if (char >= 96 && char < 128) {
                val = char - 56;
            } else {
                continue; // Skip invalid characters
            }
            
            // Convert to 6 bits
            for (let j = 5; j >= 0; j--) {
                bitstring += ((val >> j) & 1).toString();
            }
        }
        return bitstring;
    }

    sendTestMessage() {
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

    loadFleet() {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.json';
        input.onchange = (e) => {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    try {
                        this.ships = JSON.parse(e.target.result);
                        this.saveShipsToStorage();
                        this.updateUI();
                        this.showNotification('Fleet loaded successfully', 'success');
                    } catch (error) {
                        this.showNotification('Invalid fleet file', 'error');
                    }
                };
                reader.readAsText(file);
            }
        };
        input.click();
    }

    saveFleet() {
        const data = JSON.stringify(this.ships, null, 2);
        const blob = new Blob([data], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = 'siren-fleet.json';
        a.click();
        
        URL.revokeObjectURL(url);
        this.showNotification('Fleet saved', 'success');
    }

    loadSampleData() {
        // Load sample ships for testing
        const sampleShips = [
            {
                name: "Atlantic Trader",
                mmsi: 234567890,
                ship_type: 70,
                length: 180.0,
                beam: 28.0,
                lat: 39.52,
                lon: -9.18,
                course: 45,
                speed: 12.0,
                status: 0,
                turn: 0,
                destination: "LISBON",
                accuracy: 1,
                heading: 45,
                waypoints: [[39.55, -9.15], [39.58, -9.12]],
                current_waypoint: -1,
                waypoint_radius: 0.01
            },
            {
                name: "Fishing Vessel Maria",
                mmsi: 345678901,
                ship_type: 30,
                length: 25.0,
                beam: 8.0,
                lat: 39.48,
                lon: -9.22,
                course: 180,
                speed: 6.0,
                status: 7,
                turn: 0,
                destination: "",
                accuracy: 1,
                heading: 180,
                waypoints: [],
                current_waypoint: -1,
                waypoint_radius: 0.01
            },
            {
                name: "Cargo Express",
                mmsi: 456789012,
                ship_type: 70,
                length: 150.0,
                beam: 22.0,
                lat: 39.60,
                lon: -9.10,
                course: 270,
                speed: 15.0,
                status: 0,
                turn: 0,
                destination: "PORTO",
                accuracy: 1,
                heading: 270,
                waypoints: [[39.62, -9.10], [39.65, -9.15]],
                current_waypoint: -1,
                waypoint_radius: 0.01
            }
        ];

        this.ships = sampleShips;
        this.saveShipsToStorage();
        this.updateUI();
        this.showNotification('Sample fleet loaded successfully', 'success');
        console.log(`Loaded ${this.ships.length} sample ships`);
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
            }),
            'Terrain (Offline)': L.tileLayer('tiles/terrain/{z}/{x}/{y}.png', {
                attribution: '© Terrain (Offline Cache)',
                maxZoom: 18,
                minZoom: 1,
                errorTileUrl: 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjU2IiBoZWlnaHQ9IjI1NiIgeG1zbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMjU2IiBoZWlnaHQ9IjI1NiIgZmlsbD0iIzg3ODQ2MSIvPjx0ZXh0IHg9IjEyOCIgeT0iMTI4IiBmb250LWZhbWlseT0ic2Fucy1zZXJpZiIgZm9udC1zaXplPSIxNCIgZmlsbD0iIzZjNzU3ZCIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPk5vIE9mZmxpbmUgVGlsZTwvdGV4dD48L3N2Zz4='
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
            }),
            'Terrain (Online)': L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Terrain_Base/MapServer/tile/{z}/{y}/{x}', {
                attribution: '© Esri, USGS, NOAA',
                maxZoom: 16
            }),
            'Nautical (Online)': L.tileLayer('https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png', {
                attribution: '© OpenSeaMap contributors',
                maxZoom: 18
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
    // UTILITY FUNCTIONS
    // =====================================

    logMessage(elementId, message) {
        const logElement = document.getElementById(elementId);
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = document.createElement('div');
        logEntry.innerHTML = `<span class="text-muted">${timestamp}</span> ${message}`;
        logElement.appendChild(logEntry);
        logElement.scrollTop = logElement.scrollHeight;
    }

    showNotification(message, type = 'info') {
        new Noty({
            layout: 'topRight',
            text: message,
            type: type,
            timeout: 3000,
            progressBar: true,
            closeWith: ['click']

        }).show();
    }

    // Add connection status indicator
    addConnectionStatus() {
        const connectionControl = L.control({position: 'topleft'});
        
        connectionControl.onAdd = function(map) {
            const div = L.DomUtil.create('div', 'connection-status');
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
            
            updateStatus();
            
            // Update status when connection changes
            window.addEventListener('online', updateStatus);
            window.addEventListener('offline', updateStatus);
            
            return div;
        };
        
        connectionControl.addTo(this.map);
    }

    // Add mouse coordinates display
    addMouseCoordinates() {
        const coordsControl = L.control({position: 'bottomright'});
        
        coordsControl.onAdd = function(map) {
            const div = L.DomUtil.create('div', 'mouse-coordinates');
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
        
        // Update coordinates on mouse move
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

    // Handle connection changes
    handleConnectionChange(isOnline) {
        const message = isOnline ? 
            'Internet connection restored - Online maps available' : 
            'Internet connection lost - Using offline maps only';
        const type = isOnline ? 'success' : 'warning';
        
        this.showNotification(message, type);
        
        if (this.mapState) {
            this.mapState.isOnline = isOnline;
        }
        
        // Update available layers
        this.updateAvailableLayers(isOnline);
        
        console.log(`Connection status changed: ${isOnline ? 'Online' : 'Offline'}`);
    }

    // Update available map layers based on connection status
    updateAvailableLayers(isOnline) {
        // This could refresh the layer control to show/hide online layers
        // For now, we'll just log the change
        console.log(`Map layers updated for ${isOnline ? 'online' : 'offline'} mode`);
    }
}

// Initialize SIREN when page loads
let sirenApp;
document.addEventListener('DOMContentLoaded', () => {
    sirenApp = new SIRENWebApp();
});

// Make sirenApp globally available for onclick handlers
window.sirenApp = sirenApp;
