#!/usr/bin/env python3
"""
ais_sniff_limesdr.py – receive & show raw AIS payloads from a LimeSDR (using AIS-catcher)

Usage examples
--------------

# 1) Just show everything for 15 s (LimeSDR with auto gain, default PPM)
./ais_sniff_limesdr.py --seconds 15

# 2) Show only my exact payload string
./ais_sniff_limesdr.py --payload "15M:Gw@01pre<=PGCtcP001600"

# 3) Filter by MMSI (and keep the bit dump), specify PPM correction
./ais_sniff_limesdr.py 366123005 --seconds 30 --ppm 5

Note: This script assumes 'AIS-catcher' is installed and in your PATH,
      and SoapySDR is configured for your LimeSDR.
      The LimeSDR gain is set to 'auto' by AIS-catcher in this script.
      The AIS frequencies (161.975 MHz and 162.025 MHz) are scanned by default by AIS-catcher.
"""
import argparse, os, re, shlex, signal, socket, subprocess, sys, time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Set

# ---------- 6-bit helpers ----------
NMEA_RE = re.compile(r"^!AIVDM,1,1,,[AB],([^,]+),(\d)\*([0-9A-F]{2})")

def ascii6_to_bits(payload: str) -> List[List[int]]:
    out = []
    for ch in payload:
        v = ord(ch)
        # AIS 6-bit ASCII encoding:
        # 0-39 (ASCII 48-87) map to 0-39
        # 40-63 (ASCII 96-119) map to 40-63
        # This script's original logic:
        # v = v - 48 if 48 <= v <= 87 else v - 56
        # Let's use a more standard AIS 6-bit char to int conversion
        if 48 <= v <= 87: # ASCII '0' to 'W'
            v -= 48
        elif 96 <= v <= 119: # ASCII '`' to 'w'
            v -= 56 # This seems to be the original script's logic for the second range
        else: # Character out of expected AIS 6-bit range
            # Handle error or use a placeholder. For now, retain original logic.
            # A more robust parser might raise an error or skip the char.
            # The original logic implies ASCII 96-119 maps to 40-63 if v-56.
            # ASCII 96 ('`') - 56 = 40. ASCII 119 ('w') - 56 = 63. This is correct.
            v = v - 48 if 48 <= v <= 87 else v - 56


        bits = [(v >> k) & 1 for k in (5, 4, 3, 2, 1, 0)]
        out.append(bits)
    return out

def nmea_checksum(line: str) -> str:
    cs = 0
    # Check if '*' is present before trying to slice
    if '*' not in line or '!' not in line:
        return "00" # Or raise an error
    try:
        payload_part = line[line.index('!') + 1 : line.index('*')]
        for c in payload_part:
            cs ^= ord(c)
    except ValueError: # Should not happen if '*' is checked
        return "00"
    return f"{cs:02X}"

def parse(line: str) -> Dict[str, any]: # Changed type hint for "fill"
    m = NMEA_RE.match(line.strip())
    if not m: 
        raise ValueError("NMEA regex mismatch")
    payload, fill_str, cs_from_msg = m.groups()
    
    # Verify checksum
    calculated_cs = nmea_checksum(line)
    if calculated_cs != cs_from_msg.upper():
        raise ValueError(f"Checksum mismatch: got {cs_from_msg.upper()}, expected {calculated_cs}")
    
    return {"payload": payload, "fill": int(fill_str)}

# ---------- AIS-catcher (for LimeSDR) launcher ----------
def spawn_sdr_process(cmd):
    print("⧉ Launching SDR command:", " ".join(shlex.quote(c) for c in cmd))
    # Use preexec_fn=os.setsid to create a new process group
    # This allows killing the entire group (AIS-catcher and any children it might spawn)
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.PIPE, # Capture stderr for potential errors
                                 preexec_fn=os.setsid)

def start_ais_catcher_limesdr(ppm_correction: int, device_string: str = "driver=lime", sample_rate: str = "2.4M"):
    """
    Starts AIS-catcher configured for a LimeSDR.
    AIS-catcher will output NMEA to UDP 127.0.0.1:10110 by default.
    It will scan AIS channels 1 and 2 by default.
    """
    # AIS-catcher command:
    # -d <device_string>: SoapySDR device string (e.g., "driver=lime" or "soapy=0,driver=lime")
    # -s <sample_rate>: e.g., "2.4M" or "2000000"
    # -gr <gain_mode_or_string>: e.g., "auto" or "LNA=MAX,TIA=12,PGA=0"
    # -p <ppm_correction>: PPM frequency correction
    # AIS-catcher defaults to UDP output on 127.0.0.1:10110 and scans AIS1/AIS2
    cmd = [
        "AIS-catcher",
        "-d", device_string,
        "-s", sample_rate,
        "-gr", "auto",  # Use automatic gain for simplicity
        "-p", str(ppm_correction)
    ]
    return spawn_sdr_process(cmd)

def kill_sdr_process(p: subprocess.Popen):
    if p and p.poll() is None: # Check if process is still running
        print(f"⏹ Stopping SDR process (PID: {p.pid})...")
        try:
            # Send SIGINT to the entire process group
            os.killpg(os.getpgid(p.pid), signal.SIGINT)
            p.wait(timeout=5) # Wait for the process to terminate
            print("SDR process terminated.")
        except ProcessLookupError:
            print("SDR process already terminated.")
        except subprocess.TimeoutExpired:
            print("SDR process did not terminate gracefully, attempting SIGKILL...")
            os.killpg(os.getpgid(p.pid), signal.SIGKILL) # Force kill
            p.wait(timeout=2)
            print("SDR process force killed.")
        except Exception as e:
            print(f"Error killing SDR process: {e}")
        
        # Print any stderr from AIS-catcher
        if p.stderr:
            try:
                stderr_output = p.stderr.read().decode(errors="ignore")
                if stderr_output:
                    print("--- AIS-catcher stderr ---")
                    print(stderr_output)
                    print("--------------------------")
            except Exception as e_stderr:
                print(f"Error reading stderr from AIS-catcher: {e_stderr}")


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser(description="Show raw AIS payload & bits from LimeSDR via AIS-catcher")
    ap.add_argument("mmsi", nargs="*", type=int, help="optional MMSI filter(s)")
    ap.add_argument("--payload", help="filter exact 6-bit ASCII payload string")
    # Note: The --gain argument from the original script is removed as AIS-catcher's gain
    # for LimeSDR is set to 'auto' or would require a more complex gain string.
    ap.add_argument("--ppm", type=int, default=0, help="PPM frequency correction for LimeSDR")
    ap.add_argument("--seconds", "-t", type=int, default=60, help="Duration to listen in seconds")
    ap.add_argument("--sdr-device", default="driver=lime", help="SoapySDR device string for LimeSDR (e.g., 'driver=lime', 'soapy=0,driver=lime')")
    ap.add_argument("--sdr-samplerate", default="2.4M", help="Sample rate for LimeSDR (e.g., '2.4M', '2000000')")

    args = ap.parse_args()

    mmsi_set = set(args.mmsi)
    want_payload = args.payload

    sdr_process = None # Initialize sdr_process
    try:
        sdr_process = start_ais_catcher_limesdr(args.ppm, args.sdr_device, args.sdr_samplerate)
        # Give AIS-catcher a moment to start up and print potential errors
        time.sleep(2) 
        if sdr_process.poll() is not None: # Check if AIS-catcher started successfully
            print("❌ AIS-catcher process failed to start or exited prematurely.")
            if sdr_process.stderr:
                 stderr_output = sdr_process.stderr.read().decode(errors="ignore")
                 if stderr_output:
                    print("--- AIS-catcher stderr ---")
                    print(stderr_output)
                    print("--------------------------")
            return 1


        # AIS-catcher outputs NMEA to UDP 127.0.0.1 port 10110 by default
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", 10110))
        sock.settimeout(1.0) # Timeout for sock.recvfrom()

        end_time = time.time() + args.seconds
        print(f"▶ Listening for AIS NMEA on UDP 127.0.0.1:10110 for {args.seconds} seconds...")
        
        received_packets = 0
        while time.time() < end_time:
            try:
                data, _ = sock.recvfrom(2048)
            except socket.timeout:
                if sdr_process.poll() is not None:
                    print("AIS-catcher process seems to have terminated unexpectedly.")
                    break
                continue # Go back to checking time and trying to receive

            line = data.decode(errors="ignore").strip()
            if not line.startswith("!AIVDM"):
                continue

            try:
                info = parse(line)
                received_packets +=1
            except ValueError as e:
                # print(f"Failed to parse NMEA: {line} ({e})") # Optional: for debugging
                continue

            # 6-bit bits
            bits_payload = ascii6_to_bits(info["payload"]) # Renamed for clarity

            # Quick MMSI extract (first 38 bits = type6 + rep2 + mmsi30)
            # This logic assumes a Type 1, 2, or 3 message primarily.
            all_payload_bits = [b for char_bits in bits_payload for b in char_bits]
            
            mmsi = None
            if len(all_payload_bits) >= 38: # Message type is 6 bits, repeater 2 bits, MMSI 30 bits
                # Message Type: bits 0-5
                # Repeater Indicator: bits 6-7
                # MMSI: bits 8-37
                try:
                    mmsi_str = "".join(map(str, all_payload_bits[8:38]))
                    if len(mmsi_str) == 30: # Ensure we have 30 bits for MMSI
                         mmsi = int(mmsi_str, 2)
                except ValueError:
                    mmsi = None # Could not convert to int

            if mmsi_set and (mmsi is None or mmsi not in mmsi_set):
                continue
            if want_payload and info["payload"] != want_payload:
                continue

            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3] # Added milliseconds
            print("─────────────────────────────────────────────────")
            print(f"{ts}  {line} (MMSI: {mmsi if mmsi is not None else 'N/A'})")
            
            bit_dump_parts = []
            for i, char_val in enumerate(info["payload"]):
                if i < len(bits_payload):
                    char_bits_str = "".join(map(str, bits_payload[i]))
                    bit_dump_parts.append(f"{char_val}:[{char_bits_str}]")
                else: # Should not happen if ascii6_to_bits processes full payload
                    bit_dump_parts.append(f"{char_val}:[ERROR]")
            print(" ".join(bit_dump_parts))

        if received_packets == 0:
            print("No AIS packets received/parsed during the listening period.")

    except KeyboardInterrupt:
        print("\n⏹ User interrupted. Exiting...")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if 'sock' in locals() and sock:
            sock.close()
        if sdr_process: # Ensure sdr_process was initialized
            kill_sdr_process(sdr_process)
        print("Cleanup complete. Exiting.")

if __name__ == "__main__":
    sys.exit(main() or 0)