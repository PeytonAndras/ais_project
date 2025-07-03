/**
 * SIREN Initialization and Sample Data
 */

// Sample ship configurations for demonstration
const SAMPLE_SHIPS = [
    {
        "name": "Atlantic Trader",
        "mmsi": 234567890,
        "ship_type": 70,
        "length": 180.0,
        "beam": 28.0,
        "lat": 39.52,
        "lon": -9.18,
        "course": 45,
        "speed": 12.0,
        "status": 0,
        "turn": 0,
        "destination": "LISBON",
        "accuracy": 1,
        "heading": 45,
        "waypoints": [[39.55, -9.15], [39.58, -9.12]],
        "current_waypoint": -1,
        "waypoint_radius": 0.01
    },
    {
        "name": "Fishing Vessel Maria",
        "mmsi": 345678901,
        "ship_type": 30,
        "length": 25.0,
        "beam": 8.0,
        "lat": 39.45,
        "lon": -9.32,
        "course": 180,
        "speed": 4.0,
        "status": 7,
        "turn": 0,
        "destination": "FISHING GROUNDS",
        "accuracy": 1,
        "heading": 180,
        "waypoints": [],
        "current_waypoint": -1,
        "waypoint_radius": 0.01
    },
    {
        "name": "Container Ship Zeus",
        "mmsi": 456789012,
        "ship_type": 70,
        "length": 300.0,
        "beam": 45.0,
        "lat": 39.60,
        "lon": -9.05,
        "course": 270,
        "speed": 18.0,
        "status": 0,
        "turn": 0,
        "destination": "PORTO",
        "accuracy": 1,
        "heading": 270,
        "waypoints": [[39.62, -9.10], [39.65, -9.15]],
        "current_waypoint": -1,
        "waypoint_radius": 0.01
    }
];

// Scenarios for quick setup
const MARITIME_SCENARIOS = {
    port: {
        name: "Port Operations",
        description: "Ships entering and leaving port with tugboat assistance",
        ships: [
            {
                name: "Container Ship Arriving",
                mmsi: 111111111,
                ship_type: 70,
                lat: 39.45,
                lon: -9.40,
                course: 90,
                speed: 8,
                status: 0
            },
            {
                name: "Tugboat Assist",
                mmsi: 222222222,
                ship_type: 52,
                lat: 39.46,
                lon: -9.35,
                course: 270,
                speed: 3,
                status: 0
            }
        ]
    },
    convoy: {
        name: "Convoy Formation",
        description: "Multiple vessels traveling in formation",
        ships: [
            {
                name: "Lead Vessel",
                mmsi: 333333333,
                ship_type: 70,
                lat: 39.50,
                lon: -9.20,
                course: 45,
                speed: 12,
                status: 0
            },
            {
                name: "Escort 1",
                mmsi: 444444444,
                ship_type: 35,
                lat: 39.48,
                lon: -9.22,
                course: 45,
                speed: 12,
                status: 0
            },
            {
                name: "Escort 2",
                mmsi: 555555555,
                ship_type: 35,
                lat: 39.52,
                lon: -9.18,
                course: 45,
                speed: 12,
                status: 0
            }
        ]
    },
    fishing: {
        name: "Fishing Fleet",
        description: "Fishing vessels operating in fishing grounds",
        ships: [
            {
                name: "Fishing Vessel 1",
                mmsi: 666666666,
                ship_type: 30,
                lat: 39.40,
                lon: -9.30,
                course: 0,
                speed: 2,
                status: 7
            },
            {
                name: "Fishing Vessel 2",
                mmsi: 777777777,
                ship_type: 30,
                lat: 39.42,
                lon: -9.32,
                course: 180,
                speed: 3,
                status: 7
            }
        ]
    }
};

// Initialize SIREN with sample data if no ships exist
function initializeSIREN() {
    // Check if this is first run
    const existingShips = localStorage.getItem('siren-ships');
    if (!existingShips || JSON.parse(existingShips).length === 0) {
        localStorage.setItem('siren-ships', JSON.stringify(SAMPLE_SHIPS));
        console.log('SIREN initialized with sample ships');
    }
}

// Load scenario
function loadScenario(scenarioKey) {
    const scenario = MARITIME_SCENARIOS[scenarioKey];
    if (!scenario) return false;

    // Clear existing ships and load scenario ships
    const ships = scenario.ships.map(ship => ({
        ...ship,
        length: ship.length || 30,
        beam: ship.beam || 10,
        turn: 0,
        destination: ship.destination || "",
        accuracy: 1,
        heading: ship.course,
        waypoints: ship.waypoints || [],
        current_waypoint: -1,
        waypoint_radius: 0.01
    }));

    localStorage.setItem('siren-ships', JSON.stringify(ships));
    
    // Reload the app if it exists
    if (window.sirenApp) {
        window.sirenApp.loadShipsFromStorage();
        window.sirenApp.updateUI();
        window.sirenApp.showNotification(`Loaded scenario: ${scenario.name}`, 'success');
    }

    return true;
}

// Export for global use
window.SIREN_SCENARIOS = MARITIME_SCENARIOS;
window.loadScenario = loadScenario;

// Auto-initialize on load
document.addEventListener('DOMContentLoaded', initializeSIREN);
