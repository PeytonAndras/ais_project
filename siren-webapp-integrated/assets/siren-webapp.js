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
        
        this.init();
    }

    init() {
        this.loadShipsFromStorage();
        this.setupEventListeners();
        this.updateUI();
        this.connectToGNURadio();
        
        console.log('SIREN Web Application initialized');
    }

    setupEventListeners() {
        // Fleet Management
        document.getElementById('addShipBtn').addEventListener('click', () => this.showAddShipModal());
        document.getElementById('saveShipBtn').addEventListener('click', () => this.addShip());
        document.getElementById('loadFleetBtn').addEventListener('click', () => this.loadFleet());
        document.getElementById('saveFleetBtn').addEventListener('click', () => this.saveFleet());

        // Simulation Control
        document.getElementById('startSimulationBtn').addEventListener('click', () => this.startSimulation());
        document.getElementById('stopSimulationBtn').addEventListener('click', () => this.stopSimulation());

        // Transmission
        document.getElementById('connectBtn').addEventListener('click', () => this.connectToGNURadio());
        document.getElementById('testTransmissionBtn').addEventListener('click', () => this.sendTestMessage());

        // Tab switching
        document.addEventListener('shown.bs.tab', (e) => {
            if (e.target.id === 'messages-tab') {
                this.loadOriginalAISForm();
            }
        });
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
    }

    moveShip(ship) {
        if (ship.speed <= 0) return;

        // Simple movement calculation (can be enhanced with waypoint navigation)
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

    // =====================================
    // ORIGINAL AIS SIMULATOR INTEGRATION
    // =====================================

    loadOriginalAISForm() {
        // Load the original AIS simulator form into the Messages tab
        fetch('./ais-simulator.html')
            .then(response => response.text())
            .then(html => {
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');
                const form = doc.querySelector('.aisParameterForm');
                
                if (form) {
                    document.getElementById('originalAISForm').innerHTML = form.outerHTML;
                    // Re-initialize the original AIS simulator functionality
                    if (typeof aisSimulator !== 'undefined') {
                        // Initialize original AIS simulator code
                    }
                }
            })
            .catch(error => {
                console.error('Failed to load original AIS form:', error);
                document.getElementById('originalAISForm').innerHTML = 
                    '<p class="text-muted">Failed to load original AIS simulator form</p>';
            });
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
}

// Initialize SIREN when page loads
let sirenApp;
document.addEventListener('DOMContentLoaded', () => {
    sirenApp = new SIRENWebApp();
});

// Make sirenApp globally available for onclick handlers
window.sirenApp = sirenApp;
