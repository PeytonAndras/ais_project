/**
 * AIS Receiver Web Application
 * Receives and plots AIS data from RTL-AIS decoded strings
 */

class AISReceiver {
    constructor() {
        this.map = null;
        this.ships = new Map(); // MMSI -> ship data
        this.shipMarkers = new Map(); // MMSI -> marker
        this.shipTracks = new Map(); // MMSI -> track coordinates
        this.websocket = null;
        this.messageCount = 0;
        this.messageLog = [];
        
        this.init();
    }

    init() {
        this.initializeMap();
        this.setupEventListeners();
        console.log('AIS Receiver initialized');
    }

    initializeMap() {
        // Initialize Leaflet map
        this.map = L.map('map').setView([39.5, -9.2], 8);

        // Add tile layer (using offline tiles if available, otherwise online)
        const offlineLayer = L.tileLayer('tiles/openstreetmap/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap (Offline)',
            maxZoom: 18,
            errorTileUrl: 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjU2IiBoZWlnaHQ9IjI1NiIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMjU2IiBoZWlnaHQ9IjI1NiIgZmlsbD0iI2Y4ZjlmYSIvPjx0ZXh0IHg9IjEyOCIgeT0iMTI4IiBmb250LWZhbWlseT0ic2Fucy1zZXJpZiIgZm9udC1zaXplPSIxNCIgZmlsbD0iIzZjNzU3ZCIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPk5vIE9mZmxpbmUgVGlsZTwvdGV4dD48L3N2Zz4='
        });

        const onlineLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 19
        });

        // Try offline first, fallback to online
        offlineLayer.addTo(this.map);
        
        // If offline tiles fail to load, switch to online
        offlineLayer.on('tileerror', () => {
            this.map.removeLayer(offlineLayer);
            onlineLayer.addTo(this.map);
        });

        // Add mouse coordinate tracking
        this.map.on('mousemove', (e) => {
            const coords = document.getElementById('coordinates');
            coords.textContent = `Lat: ${e.latlng.lat.toFixed(6)}, Lon: ${e.latlng.lng.toFixed(6)}`;
        });

        console.log('Map initialized');
    }

    setupEventListeners() {
        // Input method change
        document.getElementById('inputMethod').addEventListener('change', (e) => {
            this.switchInputMethod(e.target.value);
        });

        // Set default input method
        this.switchInputMethod('manual');
    }

    switchInputMethod(method) {
        // Hide all input groups
        document.getElementById('manualInputGroup').style.display = 'none';
        document.getElementById('websocketGroup').style.display = 'none';
        document.getElementById('fileInputGroup').style.display = 'none';

        // Show selected input group
        switch (method) {
            case 'manual':
                document.getElementById('manualInputGroup').style.display = 'block';
                break;
            case 'websocket':
                document.getElementById('websocketGroup').style.display = 'block';
                break;
            case 'file':
                document.getElementById('fileInputGroup').style.display = 'block';
                break;
        }
    }

    parseAISMessage(nmeaString) {
        try {
            // Clean up the input
            nmeaString = nmeaString.trim();
            
            // Handle AIVDM messages (most common)
            if (!nmeaString.startsWith('!AIVDM') && !nmeaString.startsWith('!AIVDO')) {
                // If it doesn't start with !, try to add it
                if (!nmeaString.startsWith('AIVDM') && !nmeaString.startsWith('AIVDO')) {
                    throw new Error('Not a valid NMEA AIS message');
                }
                nmeaString = '!' + nmeaString;
            }

            // Parse NMEA sentence
            const parts = nmeaString.split(',');
            if (parts.length < 6) {
                throw new Error('Invalid NMEA sentence format');
            }

            const payload = parts[5];
            if (!payload) {
                throw new Error('Empty payload');
            }

            // Decode AIS payload
            const aisData = this.decodeAISPayload(payload);
            
            if (aisData) {
                this.addShip(aisData);
                this.messageCount++;
                this.updateStatus();
                this.logMessage(`Parsed: MMSI ${aisData.mmsi} at ${aisData.lat.toFixed(6)}, ${aisData.lon.toFixed(6)}`);
                return true;
            }
            
            return false;
        } catch (error) {
            this.logMessage(`Error parsing message: ${error.message}`, 'error');
            return false;
        }
    }

    decodeAISPayload(payload) {
        try {
            // Convert 6-bit ASCII to binary
            let bits = '';
            for (let i = 0; i < payload.length; i++) {
                const char = payload.charCodeAt(i);
                let val;
                
                if (char >= 48 && char < 88) {
                    val = char - 48;
                } else if (char >= 96 && char < 128) {
                    val = char - 56;
                } else {
                    continue;
                }
                
                // Convert to 6 bits
                bits += val.toString(2).padStart(6, '0');
            }

            if (bits.length < 168) { // Minimum for position report
                throw new Error('Payload too short');
            }

            // Extract fields from binary data
            const msgType = parseInt(bits.substr(0, 6), 2);
            const repeat = parseInt(bits.substr(6, 2), 2);
            const mmsi = parseInt(bits.substr(8, 30), 2);
            const navStatus = parseInt(bits.substr(38, 4), 2);
            const rot = this.parseSignedInt(bits.substr(42, 8), 8);
            const sog = parseInt(bits.substr(50, 10), 2) / 10.0;
            const accuracy = parseInt(bits.substr(60, 1), 2);
            
            // Longitude (28 bits, signed)
            const lonRaw = this.parseSignedInt(bits.substr(61, 28), 28);
            const lon = lonRaw / 600000.0;
            
            // Latitude (27 bits, signed)
            const latRaw = this.parseSignedInt(bits.substr(89, 27), 27);
            const lat = latRaw / 600000.0;
            
            const cog = parseInt(bits.substr(116, 12), 2) / 10.0;
            const hdg = parseInt(bits.substr(128, 9), 2);
            const timestamp = parseInt(bits.substr(137, 6), 2);

            // Validate coordinates
            if (Math.abs(lat) > 90 || Math.abs(lon) > 180) {
                throw new Error('Invalid coordinates');
            }

            if (lat === 0 && lon === 0) {
                throw new Error('Null coordinates');
            }

            return {
                msgType,
                mmsi,
                navStatus,
                rot,
                sog,
                accuracy,
                lon,
                lat,
                cog,
                hdg,
                timestamp,
                receivedAt: new Date()
            };
        } catch (error) {
            throw new Error(`Payload decode error: ${error.message}`);
        }
    }

    parseSignedInt(binaryStr, bits) {
        const value = parseInt(binaryStr, 2);
        const signBit = 1 << (bits - 1);
        
        if (value & signBit) {
            return value - (1 << bits);
        }
        return value;
    }

    addShip(aisData) {
        const mmsi = aisData.mmsi;
        
        // Update ship data
        this.ships.set(mmsi, {
            ...aisData,
            lastSeen: new Date(),
            name: this.getShipName(aisData),
            type: this.getShipType(aisData.navStatus),
            color: this.getShipColor(mmsi)
        });

        // Add to track history
        if (!this.shipTracks.has(mmsi)) {
            this.shipTracks.set(mmsi, []);
        }
        
        const track = this.shipTracks.get(mmsi);
        track.push([aisData.lat, aisData.lon, new Date()]);
        
        // Limit track history to last 50 points
        if (track.length > 50) {
            track.shift();
        }

        // Update map marker
        this.updateShipMarker(mmsi);
        this.updateShipList();
    }

    updateShipMarker(mmsi) {
        const ship = this.ships.get(mmsi);
        if (!ship) return;

        // Remove existing marker
        if (this.shipMarkers.has(mmsi)) {
            this.map.removeLayer(this.shipMarkers.get(mmsi));
        }

        // Create new marker
        const marker = L.circleMarker([ship.lat, ship.lon], {
            color: ship.color,
            fillColor: ship.color,
            fillOpacity: 0.8,
            radius: 8,
            weight: 2
        });

        // Create popup content
        const popupContent = `
            <div style="font-family: monospace; font-size: 12px;">
                <strong>MMSI: ${ship.mmsi}</strong><br>
                <strong>Type:</strong> ${ship.type}<br>
                <strong>Position:</strong> ${ship.lat.toFixed(6)}, ${ship.lon.toFixed(6)}<br>
                <strong>Speed:</strong> ${ship.sog.toFixed(1)} knots<br>
                <strong>Course:</strong> ${ship.cog.toFixed(1)}°<br>
                <strong>Heading:</strong> ${ship.hdg === 511 ? 'N/A' : ship.hdg + '°'}<br>
                <strong>Status:</strong> ${this.getNavStatusText(ship.navStatus)}<br>
                <strong>Last Seen:</strong> ${ship.lastSeen.toLocaleTimeString()}
            </div>
        `;

        marker.bindPopup(popupContent);
        marker.addTo(this.map);
        this.shipMarkers.set(mmsi, marker);

        // Draw track if we have multiple points
        const track = this.shipTracks.get(mmsi);
        if (track && track.length > 1) {
            const trackPoints = track.map(point => [point[0], point[1]]);
            const trackLine = L.polyline(trackPoints, {
                color: ship.color,
                weight: 2,
                opacity: 0.6,
                dashArray: '5, 5'
            });
            trackLine.addTo(this.map);
        }
    }

    updateShipList() {
        const shipList = document.getElementById('shipList');
        
        if (this.ships.size === 0) {
            shipList.innerHTML = `
                <div style="text-align: center; color: #666; padding: 20px;">
                    No ships detected yet. Add AIS messages to see ships appear.
                </div>
            `;
            return;
        }

        const ships = Array.from(this.ships.values())
            .sort((a, b) => b.lastSeen - a.lastSeen);

        shipList.innerHTML = ships.map(ship => `
            <div class="ship-item" onclick="aisReceiver.focusOnShip(${ship.mmsi})">
                <div class="ship-mmsi">MMSI: ${ship.mmsi}</div>
                <div class="ship-details">
                    Type: ${ship.type}<br>
                    Position: ${ship.lat.toFixed(4)}, ${ship.lon.toFixed(4)}<br>
                    Speed: ${ship.sog.toFixed(1)} kts | Course: ${ship.cog.toFixed(0)}°<br>
                    Status: ${this.getNavStatusText(ship.navStatus)}<br>
                    Last: ${ship.lastSeen.toLocaleTimeString()}
                </div>
            </div>
        `).join('');

        document.getElementById('shipCount').textContent = this.ships.size;
    }

    focusOnShip(mmsi) {
        const ship = this.ships.get(mmsi);
        if (ship) {
            this.map.setView([ship.lat, ship.lon], 12);
            const marker = this.shipMarkers.get(mmsi);
            if (marker) {
                marker.openPopup();
            }
        }
    }

    getShipName(aisData) {
        // In a real implementation, you might have a database of ship names
        return `Ship-${aisData.mmsi}`;
    }

    getShipType(navStatus) {
        const types = {
            0: 'Under way using engine',
            1: 'At anchor',
            2: 'Not under command',
            3: 'Restricted manoeuvrability',
            4: 'Constrained by her draught',
            5: 'Moored',
            6: 'Aground',
            7: 'Engaged in fishing',
            8: 'Under way sailing',
            15: 'Undefined'
        };
        return types[navStatus] || 'Unknown';
    }

    getNavStatusText(status) {
        const statuses = {
            0: 'Under way',
            1: 'At anchor',
            2: 'Not under command',
            3: 'Restricted',
            4: 'Constrained',
            5: 'Moored',
            6: 'Aground',
            7: 'Fishing',
            8: 'Sailing',
            15: 'Undefined'
        };
        return statuses[status] || `Status ${status}`;
    }

    getShipColor(mmsi) {
        const colors = ['#007bff', '#28a745', '#ffc107', '#17a2b8', '#6f42c1', '#e83e8c'];
        return colors[mmsi % colors.length];
    }

    updateStatus() {
        document.getElementById('messageCount').textContent = this.messageCount;
        document.getElementById('shipCount').textContent = this.ships.size;
    }

    logMessage(message, type = 'info') {
        const timestamp = new Date().toLocaleTimeString();
        const entry = `[${timestamp}] ${message}`;
        
        this.messageLog.push({ timestamp, message, type });
        
        // Keep only last 100 messages
        if (this.messageLog.length > 100) {
            this.messageLog.shift();
        }
        
        console.log(entry);
    }

    // WebSocket functionality
    connectWebSocket() {
        const url = document.getElementById('wsUrl').value;
        
        try {
            this.websocket = new WebSocket(url);
            
            this.websocket.onopen = () => {
                document.getElementById('status').innerHTML = 
                    '<span class="status-connected">● Connected</span> | Ships: <span id="shipCount">0</span> | Messages: <span id="messageCount">0</span>';
                document.getElementById('connectBtn').style.display = 'none';
                document.getElementById('disconnectBtn').style.display = 'inline-block';
                this.logMessage('WebSocket connected', 'success');
            };
            
            this.websocket.onmessage = (event) => {
                this.parseAISMessage(event.data);
            };
            
            this.websocket.onclose = () => {
                this.disconnectWebSocket();
            };
            
            this.websocket.onerror = (error) => {
                this.logMessage('WebSocket error: ' + error, 'error');
                this.disconnectWebSocket();
            };
            
        } catch (error) {
            this.logMessage('Failed to connect: ' + error.message, 'error');
        }
    }

    disconnectWebSocket() {
        if (this.websocket) {
            this.websocket.close();
            this.websocket = null;
        }
        
        document.getElementById('status').innerHTML = 
            '<span class="status-disconnected">● Disconnected</span> | Ships: <span id="shipCount">' + this.ships.size + '</span> | Messages: <span id="messageCount">' + this.messageCount + '</span>';
        document.getElementById('connectBtn').style.display = 'inline-block';
        document.getElementById('disconnectBtn').style.display = 'none';
        this.logMessage('WebSocket disconnected');
    }
}

// Global functions for HTML event handlers
function parseManualInput() {
    const input = document.getElementById('nmeaInput').value;
    const lines = input.split('\n').filter(line => line.trim());
    
    let processed = 0;
    lines.forEach(line => {
        if (aisReceiver.parseAISMessage(line)) {
            processed++;
        }
    });
    
    if (processed > 0) {
        document.getElementById('nmeaInput').value = '';
        aisReceiver.logMessage(`Processed ${processed} of ${lines.length} messages`, 'success');
    }
}

function connectWebSocket() {
    aisReceiver.connectWebSocket();
}

function disconnectWebSocket() {
    aisReceiver.disconnectWebSocket();
}

function loadFile() {
    const fileInput = document.getElementById('fileInput');
    const file = fileInput.files[0];
    
    if (file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            const content = e.target.result;
            const lines = content.split('\n').filter(line => line.trim());
            
            let processed = 0;
            lines.forEach(line => {
                if (aisReceiver.parseAISMessage(line)) {
                    processed++;
                }
            });
            
            aisReceiver.logMessage(`Loaded ${processed} messages from file`, 'success');
        };
        reader.readAsText(file);
    }
}

function centerOnShips() {
    if (aisReceiver.ships.size === 0) {
        alert('No ships to center on');
        return;
    }
    
    const positions = Array.from(aisReceiver.ships.values()).map(ship => [ship.lat, ship.lon]);
    const bounds = L.latLngBounds(positions);
    aisReceiver.map.fitBounds(bounds, { padding: [20, 20] });
}

function clearAllShips() {
    if (confirm('Clear all ships and tracks?')) {
        // Clear markers
        aisReceiver.shipMarkers.forEach(marker => {
            aisReceiver.map.removeLayer(marker);
        });
        
        // Clear data
        aisReceiver.ships.clear();
        aisReceiver.shipMarkers.clear();
        aisReceiver.shipTracks.clear();
        
        // Update UI
        aisReceiver.updateShipList();
        aisReceiver.updateStatus();
        aisReceiver.logMessage('All ships cleared');
    }
}

function closeLogModal() {
    document.getElementById('logModal').style.display = 'none';
}

// Initialize the application
let aisReceiver;
document.addEventListener('DOMContentLoaded', () => {
    aisReceiver = new AISReceiver();
});
