#!/bin/bash
#
# SIREN GNU Radio Setup Script
# 
# This script sets up GNU Radio and related dependencies for SIREN AIS transmission.
# Based on the working ais-simulator.py approach.
#
# @ author: Peyton Andras @ Louisiana State University 2025
#

set -e  # Exit on any error

echo "🚢 SIREN GNU Radio Setup Script"
echo "================================"
echo

# Detect OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    if command -v apt-get &> /dev/null; then
        OS="ubuntu"
        echo "📋 Detected: Ubuntu/Debian"
    elif command -v pacman &> /dev/null; then
        OS="arch"
        echo "📋 Detected: Arch Linux"
    elif command -v dnf &> /dev/null; then
        OS="fedora"
        echo "📋 Detected: Fedora"
    else
        echo "❌ Unsupported Linux distribution"
        exit 1
    fi
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
    echo "📋 Detected: macOS"
else
    echo "❌ Unsupported operating system: $OSTYPE"
    exit 1
fi

echo

# Function to check if command exists
command_exists() {
    command -v "$1" &> /dev/null
}

# Function to check Python module
python_module_exists() {
    python3 -c "import $1" &> /dev/null
}

# Check current dependencies
echo "🔍 Checking current dependencies..."

# Check Python
if command_exists python3; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    echo "✅ Python: $PYTHON_VERSION"
else
    echo "❌ Python 3 not found"
    exit 1
fi

# Check GNU Radio
if python_module_exists "gnuradio"; then
    echo "✅ GNU Radio: Available"
    GNURADIO_INSTALLED=true
else
    echo "❌ GNU Radio: Not installed"
    GNURADIO_INSTALLED=false
fi

# Check gr-osmosdr
if python_module_exists "osmosdr"; then
    echo "✅ gr-osmosdr: Available"
    OSMOSDR_INSTALLED=true
else
    echo "❌ gr-osmosdr: Not installed"
    OSMOSDR_INSTALLED=false
fi

# Check gr-ais
if python_module_exists "gnuradio.ais_simulator"; then
    echo "✅ gr-ais: Available"
    AIS_INSTALLED=true
elif python_module_exists "gnuradio.ais"; then
    echo "✅ gr-ais: Available (alternative)"
    AIS_INSTALLED=true
else
    echo "❌ gr-ais: Not installed"
    AIS_INSTALLED=false
fi

# Check websocket-client
if python_module_exists "websocket"; then
    echo "✅ websocket-client: Available"
    WEBSOCKET_INSTALLED=true
else
    echo "❌ websocket-client: Not installed"
    WEBSOCKET_INSTALLED=false
fi

echo

# Install function for Ubuntu/Debian
install_ubuntu() {
    echo "📦 Installing GNU Radio dependencies on Ubuntu/Debian..."
    
    # Update package list
    echo "🔄 Updating package list..."
    sudo apt-get update
    
    # Install GNU Radio
    if [ "$GNURADIO_INSTALLED" = false ]; then
        echo "📻 Installing GNU Radio..."
        sudo apt-get install -y gnuradio gnuradio-dev
    fi
    
    # Install gr-osmosdr
    if [ "$OSMOSDR_INSTALLED" = false ]; then
        echo "📡 Installing gr-osmosdr..."
        sudo apt-get install -y gr-osmosdr
    fi
    
    # Install gr-ais (this might need to be built from source)
    if [ "$AIS_INSTALLED" = false ]; then
        echo "🛰️ Installing gr-ais..."
        # Try package first
        if sudo apt-get install -y gr-ais; then
            echo "✅ gr-ais installed from package"
        else
            echo "⚠️  gr-ais package not available, will need manual installation"
            echo "   See: https://github.com/bistromath/gr-ais"
        fi
    fi
    
    # Install Python dependencies
    if [ "$WEBSOCKET_INSTALLED" = false ]; then
        echo "🐍 Installing Python websocket-client..."
        pip3 install websocket-client
    fi
    
    # Additional useful packages
    echo "🔧 Installing additional packages..."
    sudo apt-get install -y \
        cmake \
        build-essential \
        libboost-all-dev \
        libcppunit-dev \
        liblog4cpp5-dev \
        libfftw3-dev \
        swig \
        pkg-config
}

# Install function for Arch Linux
install_arch() {
    echo "📦 Installing GNU Radio dependencies on Arch Linux..."
    
    # Update package list
    echo "🔄 Updating package list..."
    sudo pacman -Sy
    
    # Install GNU Radio
    if [ "$GNURADIO_INSTALLED" = false ]; then
        echo "📻 Installing GNU Radio..."
        sudo pacman -S --noconfirm gnuradio
    fi
    
    # Install gr-osmosdr
    if [ "$OSMOSDR_INSTALLED" = false ]; then
        echo "📡 Installing gr-osmosdr..."
        sudo pacman -S --noconfirm gnuradio-osmosdr
    fi
    
    # Install gr-ais (from AUR)
    if [ "$AIS_INSTALLED" = false ]; then
        echo "🛰️ Installing gr-ais from AUR..."
        if command_exists yay; then
            yay -S --noconfirm gr-ais
        elif command_exists paru; then
            paru -S --noconfirm gr-ais
        else
            echo "⚠️  AUR helper (yay/paru) not found. Install manually:"
            echo "   git clone https://aur.archlinux.org/gr-ais.git"
            echo "   cd gr-ais && makepkg -si"
        fi
    fi
    
    # Install Python dependencies
    if [ "$WEBSOCKET_INSTALLED" = false ]; then
        echo "🐍 Installing Python websocket-client..."
        pip3 install websocket-client
    fi
}

# Install function for macOS
install_macos() {
    echo "📦 Installing GNU Radio dependencies on macOS..."
    
    # Check for Homebrew
    if ! command_exists brew; then
        echo "❌ Homebrew not found. Please install Homebrew first:"
        echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        exit 1
    fi
    
    # Update Homebrew
    echo "🔄 Updating Homebrew..."
    brew update
    
    # Install GNU Radio
    if [ "$GNURADIO_INSTALLED" = false ]; then
        echo "📻 Installing GNU Radio..."
        brew install gnuradio
    fi
    
    # Install gr-osmosdr
    if [ "$OSMOSDR_INSTALLED" = false ]; then
        echo "📡 Installing gr-osmosdr..."
        brew install gr-osmosdr
    fi
    
    # Install gr-ais (might need manual build)
    if [ "$AIS_INSTALLED" = false ]; then
        echo "🛰️ gr-ais might need manual installation on macOS"
        echo "   See: https://github.com/bistromath/gr-ais"
    fi
    
    # Install Python dependencies
    if [ "$WEBSOCKET_INSTALLED" = false ]; then
        echo "🐍 Installing Python websocket-client..."
        pip3 install websocket-client
    fi
}

# Perform installation based on OS
case $OS in
    "ubuntu")
        install_ubuntu
        ;;
    "arch")
        install_arch
        ;;
    "macos")
        install_macos
        ;;
    "fedora")
        echo "❌ Fedora support not yet implemented"
        echo "   Please install: gnuradio, gr-osmosdr, gr-ais manually"
        exit 1
        ;;
esac

echo
echo "🔧 Post-installation setup..."

# Set up environment variables
echo "📝 Setting up environment variables..."

# Add GNU Radio environment to bashrc if not present
if ! grep -q "GR_LOG_LEVEL" ~/.bashrc; then
    echo "" >> ~/.bashrc
    echo "# GNU Radio environment for SIREN" >> ~/.bashrc
    echo "export GR_LOG_LEVEL=INFO" >> ~/.bashrc
    echo "export GR_SCHEDULER=TPB" >> ~/.bashrc
    echo "Added GNU Radio environment variables to ~/.bashrc"
fi

# Create SIREN GNU Radio config
echo "⚙️ Creating SIREN configuration..."
cat > siren_gnuradio_config.json << EOF
{
    "gnuradio": {
        "channel": "A",
        "sample_rate": 8000000,
        "bit_rate": 9600,
        "tx_gain": 42,
        "bb_gain": 30,
        "ppm": 0,
        "websocket_port": 52002
    },
    "ais": {
        "default_mmsi": 123456789,
        "default_lat": 39.5,
        "default_lon": -9.2,
        "default_speed": 10.0,
        "default_course": 90.0
    }
}
EOF

echo "✅ Configuration saved to siren_gnuradio_config.json"

echo
echo "🧪 Testing installation..."

# Test GNU Radio import
if python3 -c "from gnuradio import gr, blocks, digital; print('✅ GNU Radio core: OK')" 2>/dev/null; then
    echo "✅ GNU Radio core: Working"
else
    echo "❌ GNU Radio core: Failed"
fi

# Test gr-osmosdr
if python3 -c "import osmosdr; print('✅ gr-osmosdr: OK')" 2>/dev/null; then
    echo "✅ gr-osmosdr: Working"
else
    echo "❌ gr-osmosdr: Failed"
fi

# Test gr-ais
if python3 -c "from gnuradio import ais_simulator; print('✅ gr-ais: OK')" 2>/dev/null; then
    echo "✅ gr-ais: Working"
elif python3 -c "from gnuradio import ais; print('✅ gr-ais: OK (alternative)')" 2>/dev/null; then
    echo "✅ gr-ais: Working (alternative)"
else
    echo "❌ gr-ais: Failed"
fi

# Test websocket-client
if python3 -c "import websocket; print('✅ websocket-client: OK')" 2>/dev/null; then
    echo "✅ websocket-client: Working"
else
    echo "❌ websocket-client: Failed"
fi

echo
echo "🎯 Testing SIREN GNU Radio transmitter..."

# Test the actual transmitter (dry run)
if python3 siren_gnuradio_transmitter.py --help &>/dev/null; then
    echo "✅ SIREN GNU Radio transmitter: Ready"
else
    echo "❌ SIREN GNU Radio transmitter: Issues detected"
fi

echo
echo "🚀 Setup complete!"
echo
echo "Usage examples:"
echo "  # Test transmission (one message)"
echo "  python3 siren_gnuradio_transmitter.py --mmsi 123456789 --lat 39.5 --lon -9.2 --once"
echo
echo "  # Continuous transmission"
echo "  python3 siren_gnuradio_transmitter.py --mmsi 123456789 --lat 39.5 --lon -9.2 --continuous --interval 10"
echo
echo "  # Channel B transmission"
echo "  python3 siren_gnuradio_transmitter.py --mmsi 123456789 --lat 39.5 --lon -9.2 --channel B"
echo
echo "⚠️  Remember to:"
echo "  - Connect your LimeSDR"
echo "  - Use appropriate test MMSI numbers (999999xxx)"
echo "  - Ensure you have proper radio licensing"
echo "  - Test in RF-shielded environment initially"
echo
echo "📚 For more information, see the SIREN documentation."
