import os

# Path to the hackrf module
hackrf_init = "./new_venv/lib/python3.13/site-packages/hackrf/__init__.py"

# Check if the file exists
if os.path.exists(hackrf_init):
    # Read the file content
    with open(hackrf_init, 'r') as f:
        content = f.read()
    
    # Fix the library loading for macOS
    modified = content.replace(
        "libhackrf = CDLL('libhackrf.so.0')",
        """import sys
if sys.platform == 'darwin':
    # Try different paths for macOS
    lib_paths = [
        'libhackrf.dylib',
        '/opt/homebrew/lib/libhackrf.dylib',
        '/usr/local/lib/libhackrf.dylib',
        '/opt/homebrew/Cellar/hackrf/*/lib/libhackrf.dylib'
    ]
    
    for path in lib_paths:
        # Handle wildcards in path
        if '*' in path:
            import glob
            candidates = glob.glob(path)
            if candidates:
                path = candidates[0]
        
        try:
            libhackrf = CDLL(path)
            break
        except OSError:
            continue
    else:
        raise OSError("Could not find libhackrf on this system")
else:
    libhackrf = CDLL('libhackrf.so.0')"""
    )
    
    # Write the modified content back
    with open(hackrf_init, 'w') as f:
        f.write(modified)
    
    print("Modified hackrf module to work on macOS")
else:
    print(f"Could not find hackrf module at {hackrf_init}")
    print("Make sure you have the hackrf module installed")
