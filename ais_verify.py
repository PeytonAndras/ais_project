#!/usr/bin/env python3
"""
ais_sniff.py – receive & show raw AIS payloads from an RTL-SDR

Usage examples
--------------

# 1) Just show everything for 15 s
./ais_sniff.py --seconds 15

# 2) Show only my exact payload string
./ais_sniff.py --payload 15M:Gw@01pre<=PGCtcP001600

# 3) Filter by MMSI (and keep the bit dump)
./ais_sniff.py 366123005 --seconds 30
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
        v = v - 48 if 48 <= v <= 87 else v - 56
        bits = [(v >> k) & 1 for k in (5, 4, 3, 2, 1, 0)]
        out.append(bits)
    return out

def nmea_checksum(line: str) -> str:
    cs = 0
    for c in line[line.index('!') + 1 : line.index('*')]:
        cs ^= ord(c)
    return f"{cs:02X}"

def parse(line: str) -> Dict[str, str]:
    m = NMEA_RE.match(line.strip())
    if not m: 
        raise ValueError
    payload, fill, cs = m.groups()
    if nmea_checksum(line) != cs.upper():
        raise ValueError("checksum")
    return {"payload": payload, "fill": int(fill)}

# ---------- rtl_ais launcher ----------
def spawn(cmd):
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.STDOUT,
                                 preexec_fn=os.setsid)

def start_rtl_ais(gain, ppm):
    cmd = ["rtl_ais", "-g", str(gain), "-p", str(ppm), "-n"]
    print("⧉", " ".join(cmd))
    return spawn(cmd)

def kill(p):
    if p and p.poll() is None:
        os.killpg(os.getpgid(p.pid), signal.SIGINT)
        p.wait(5)

# ---------- main ----------
def main():
    ap = argparse.ArgumentParser(description="Show raw AIS payload & bits")
    ap.add_argument("mmsi", nargs="*", type=int, help="optional MMSI filter(s)")
    ap.add_argument("--payload", help="filter exact 6-bit ASCII payload string")
    ap.add_argument("--gain", "-g", type=int, default=38)
    ap.add_argument("--ppm", type=int, default=0)
    ap.add_argument("--seconds", "-t", type=int, default=20)
    args = ap.parse_args()

    mmsi_set = set(args.mmsi)
    want_payload = args.payload

    rtl = start_rtl_ais(args.gain, args.ppm)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 10110))
    sock.settimeout(1.0)

    end = time.time() + args.seconds
    print("▶ listening …")
    try:
        while time.time() < end:
            try:
                data, _ = sock.recvfrom(2048)
            except socket.timeout:
                continue

            line = data.decode(errors="ignore").strip()
            try:
                info = parse(line)
            except ValueError:
                continue

            # 6-bit bits
            bits = ascii6_to_bits(info["payload"])

            # quick MMSI extract (first 38 bits = type6 + rep2 + mmsi30)
            first_bits = [b for char in bits for b in char][:38]
            mmsi = int("".join(map(str, first_bits[8:])), 2) if len(first_bits)==38 else None

            if mmsi_set and mmsi not in mmsi_set:
                continue
            if want_payload and info["payload"] != want_payload:
                continue

            ts = datetime.now().strftime("%H:%M:%S")
            print("─────────────────────────────────────────────────")
            print(f"{ts}  {line}")
            bit_dump = " ".join(
                f"{ch}:[{', '.join(map(str,bits[i]))}]" for i,ch in enumerate(info["payload"]))
            print(bit_dump)
    finally:
        kill(rtl)
        sock.close()
        print("⏹ done")

if __name__ == "__main__":
    main()
