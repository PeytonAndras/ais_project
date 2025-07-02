"""
GNU Radio Configuration for SIREN

Configuration settings for GNU Radio AIS transmission integration.
This enables the working transmission method based on ais-simulator.py.

@ author: Peyton Andras @ Louisiana State University 2025
"""

import os
import logging
from typing import Dict, Any, Optional

# GNU Radio AIS Configuration
GNURADIO_CONFIG = {
    # Transmission settings
    'channel': 'A',  # 'A' for 161.975MHz, 'B' for 162.025MHz
    'sample_rate': 8000000,  # 8 MHz (matches ais-simulator.py)
    'bit_rate': 9600,  # AIS standard bit rate
    'tx_gain': 42,  # RF gain (dB)
    'bb_gain': 30,  # Baseband gain (dB)
    'ppm': 0,  # Frequency correction in ppm
    
    # Websocket settings for GNU Radio communication
    'websocket_port': 52002,
    'websocket_host': 'localhost',
    'websocket_timeout': 5,
    
    # LimeSDR specific settings (matches ais-simulator.py)
    'sdr_driver': 'lime',
    'antenna': 'BAND1',
    'power_scaling': 0.9,  # Signal power scaling factor
    
    # GNU Radio flowgraph settings
    'gmsk_bt': 0.4,  # GMSK Gaussian filter BT parameter
    'verbose': False,
    'log_flowgraph': False,
    
    # SIREN integration settings
    'prefer_gnuradio': True,  # Prefer GNU Radio over SoapySDR
    'fallback_to_soapy': True,  # Fall back to SoapySDR if GNU Radio fails
    'auto_start_gnuradio': True,  # Auto-start GNU Radio flowgraph
}

# Installation requirements
GNURADIO_REQUIREMENTS = {
    'packages': [
        'gnuradio',
        'gr-osmosdr', 
        'gr-ais',  # or gr-ais_simulator
        'python3-websocket-client'
    ],
    'ubuntu_install': [
        'sudo apt-get update',
        'sudo apt-get install gnuradio',
        'sudo apt-get install gr-osmosdr',
        'sudo apt-get install gr-ais',
        'pip3 install websocket-client'
    ],
    'arch_install': [
        'sudo pacman -S gnuradio',
        'sudo pacman -S gnuradio-osmosdr', 
        'yay -S gr-ais',
        'pip install websocket-client'
    ]
}

def get_gnuradio_config() -> Dict[str, Any]:
    """Get GNU Radio configuration settings"""
    return GNURADIO_CONFIG.copy()

def check_gnuradio_dependencies() -> Dict[str, bool]:
    """Check if GNU Radio dependencies are available"""
    dependencies = {
        'gnuradio': False,
        'gr_ais': False,
        'osmosdr': False,
        'websocket_client': False
    }
    
    # Check GNU Radio
    try:
        from gnuradio import gr, blocks, digital, pdu
        dependencies['gnuradio'] = True
    except ImportError:
        pass
    
    # Check gr-ais
    try:
        from gnuradio import ais_simulator
        dependencies['gr_ais'] = True
    except ImportError:
        # Try alternative import
        try:
            from gnuradio import ais
            dependencies['gr_ais'] = True
        except ImportError:
            pass
    
    # Check osmosdr
    try:
        import osmosdr
        dependencies['osmosdr'] = True
    except ImportError:
        pass
    
    # Check websocket client
    try:
        import websocket
        dependencies['websocket_client'] = True
    except ImportError:
        # Try alternative import name
        try:
            import websocket_client
            dependencies['websocket_client'] = True
        except ImportError:
            pass
    
    return dependencies

def get_installation_instructions() -> str:
    """Get installation instructions for GNU Radio"""
    deps = check_gnuradio_dependencies()
    missing = [name for name, available in deps.items() if not available]
    
    if not missing:
        return "✅ All GNU Radio dependencies are available!"
    
    instructions = f"❌ Missing dependencies: {', '.join(missing)}\n\n"
    instructions += "Installation instructions:\n\n"
    
    instructions += "Ubuntu/Debian:\n"
    for cmd in GNURADIO_REQUIREMENTS['ubuntu_install']:
        instructions += f"  {cmd}\n"
    
    instructions += "\nArch Linux:\n"
    for cmd in GNURADIO_REQUIREMENTS['arch_install']:
        instructions += f"  {cmd}\n"
    
    instructions += "\nNote: After installation, you may need to restart your terminal/IDE.\n"
    
    return instructions

def validate_gnuradio_config(config: Optional[Dict[str, Any]] = None) -> bool:
    """Validate GNU Radio configuration"""
    if config is None:
        config = get_gnuradio_config()
    
    required_keys = ['channel', 'sample_rate', 'bit_rate', 'websocket_port']
    
    for key in required_keys:
        if key not in config:
            logging.error(f"Missing required GNU Radio config key: {key}")
            return False
    
    # Validate channel
    if config['channel'] not in ['A', 'B']:
        logging.error(f"Invalid channel: {config['channel']}. Must be 'A' or 'B'")
        return False
    
    # Validate sample rate
    if not isinstance(config['sample_rate'], int) or config['sample_rate'] <= 0:
        logging.error(f"Invalid sample rate: {config['sample_rate']}")
        return False
    
    # Validate bit rate
    if config['bit_rate'] != 9600:
        logging.warning(f"Unusual bit rate: {config['bit_rate']}. AIS standard is 9600 bps")
    
    # Validate websocket port
    if not (1 <= config['websocket_port'] <= 65535):
        logging.error(f"Invalid websocket port: {config['websocket_port']}")
        return False
    
    return True

def get_frequency_from_channel(channel: str) -> int:
    """Get frequency in Hz for AIS channel"""
    if channel == 'A':
        return 161975000  # AIS Channel A
    elif channel == 'B':
        return 162025000  # AIS Channel B
    else:
        raise ValueError(f"Invalid channel: {channel}. Must be 'A' or 'B'")

def create_gnuradio_args() -> Dict[str, Any]:
    """Create arguments for GNU Radio transmitter initialization"""
    config = get_gnuradio_config()
    
    return {
        'channel': config['channel'],
        'sample_rate': config['sample_rate'],
        'bit_rate': config['bit_rate'],
        'tx_gain': config['tx_gain'],
        'bb_gain': config['bb_gain'],
        'ppm': config['ppm'],
        'websocket_port': config['websocket_port']
    }

# Environment variables for GNU Radio
def setup_gnuradio_environment():
    """Setup environment variables for GNU Radio"""
    # Set GNU Radio log level
    if 'GR_LOG_LEVEL' not in os.environ:
        os.environ['GR_LOG_LEVEL'] = 'INFO'
    
    # Set GNU Radio threading
    if 'GR_SCHEDULER' not in os.environ:
        os.environ['GR_SCHEDULER'] = 'TPB'  # Thread Per Block scheduler

if __name__ == "__main__":
    # Test configuration
    print("GNU Radio Configuration Test")
    print("=" * 40)
    
    config = get_gnuradio_config()
    print(f"Configuration: {config}")
    print()
    
    deps = check_gnuradio_dependencies()
    print("Dependencies:")
    for name, available in deps.items():
        status = "✅" if available else "❌"
        print(f"  {status} {name}")
    print()
    
    if not all(deps.values()):
        print(get_installation_instructions())
    else:
        print("✅ GNU Radio ready for SIREN integration!")
        
        # Test config validation
        if validate_gnuradio_config():
            print("✅ Configuration is valid")
        else:
            print("❌ Configuration validation failed")
