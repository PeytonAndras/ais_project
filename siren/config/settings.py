"""
Configuration Module - Settings and Dependency Management
========================================================

This module handles application settings, dependency checking, and configuration management.
"""

import os

def check_dependencies():
    """Check for optional dependencies and return availability flags"""
    sdr_available = False
    map_available = False
    pil_available = False
    
    # Check SoapySDR
    try:
        import SoapySDR
        sdr_available = True
        print("SoapySDR imported successfully")
    except ImportError as e:
        print(f"SoapySDR import error: {e}")
        sdr_available = False

    # Check tkintermapview
    try:
        import tkintermapview
        tkintermapview.TkinterMapView.USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        map_available = True
        print("tkintermapview imported successfully")
    except ImportError as e:
        map_available = False
        print(f"tkintermapview import error: {e}. Map functionality will be limited.")
        print("Install with: pip install tkintermapview")

    # Check PIL
    try:
        from PIL import Image, ImageTk
        pil_available = True
        print("PIL imported successfully")
    except ImportError:
        pil_available = False
        print("PIL import error. Ship icons will be basic. Install with: pip install pillow")
    
    return sdr_available, map_available, pil_available

def get_config_path():
    """Get the path to the configuration directory"""
    return os.path.dirname(os.path.abspath(__file__))

def get_ship_config_path():
    """Get the path to the ship configuration file"""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ship_configs.json")

# MID to Country Mapping for MMSI flag identification
MID_TO_COUNTRY = {
    201: "Albania", 202: "Andorra", 203: "Austria", 204: "Azores", 205: "Belgium",
    206: "Belarus", 207: "Bulgaria", 209: "Cyprus", 210: "Cyprus", 211: "Germany",
    212: "Cyprus", 213: "Georgia", 214: "Moldova", 215: "Malta", 218: "Germany",
    219: "Denmark", 220: "Denmark", 224: "Spain", 225: "Spain", 226: "France",
    227: "France", 228: "France", 229: "Malta", 230: "Finland", 231: "Faeroe Islands",
    232: "United Kingdom", 233: "United Kingdom", 234: "United Kingdom", 235: "United Kingdom",
    236: "Gibraltar", 237: "Greece", 238: "Croatia", 239: "Greece", 240: "Greece",
    241: "Greece", 242: "Morocco", 243: "Hungary", 244: "Netherlands", 245: "Netherlands",
    246: "Netherlands", 247: "Italy", 248: "Malta", 249: "Malta", 250: "Ireland",
    251: "Iceland", 252: "Liechtenstein", 253: "Luxembourg", 254: "Monaco", 255: "Portugal",
    256: "Malta", 257: "Norway", 258: "Norway", 259: "Norway", 261: "Poland",
    262: "Montenegro", 263: "Portugal", 264: "Romania", 265: "Sweden", 266: "Sweden",
    267: "Slovakia", 268: "San Marino", 269: "Switzerland", 270: "Czech Republic",
    271: "Turkey", 272: "Ukraine", 273: "Russia", 274: "Macedonia", 275: "Latvia",
    276: "Estonia", 277: "Lithuania", 278: "Slovenia", 279: "Serbia", 301: "Anguilla",
    303: "Alaska (USA)", 304: "Antigua and Barbuda", 305: "Antigua and Barbuda", 306: "Aruba",
    307: "Netherlands Antilles", 308: "Bahamas", 309: "Bahamas", 310: "Bermuda",
    311: "Bahamas", 312: "Belize", 314: "Barbados", 316: "Canada", 319: "Cayman Islands",
    321: "Costa Rica", 325: "Dominica", 327: "Dominican Republic", 329: "Guadeloupe",
    330: "Grenada", 331: "Greenland", 332: "Guatemala", 334: "Honduras", 336: "Haiti",
    338: "United States", 339: "Jamaica", 341: "Saint Kitts and Nevis", 343: "Saint Lucia",
    345: "Mexico", 348: "Montserrat", 350: "Nicaragua", 351: "Panama", 352: "Panama",
    353: "Panama", 354: "Panama", 355: "Panama", 356: "Panama", 357: "Panama",
    358: "Puerto Rico", 359: "Saint Vincent and the Grenadines", 361: "Trinidad and Tobago",
    362: "Trinidad and Tobago", 364: "Turks and Caicos Islands", 366: "United States",
    367: "United States", 368: "United States", 369: "United States", 370: "Panama",
    371: "Panama", 372: "Panama", 373: "Panama", 374: "Panama", 375: "Saint Pierre and Miquelon",
    376: "Saint Vincent and the Grenadines", 377: "Saint Vincent and the Grenadines",
    378: "British Virgin Islands", 379: "United States Virgin Islands", 401: "Afghanistan",
    # ... (add more as needed)
}

def get_flag_from_mmsi(mmsi):
    """Get country flag from MMSI"""
    try:
        mid = int(str(mmsi)[:3])
        return MID_TO_COUNTRY.get(mid, "Unknown")
    except Exception:
        return "Unknown"
