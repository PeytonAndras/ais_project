#!/usr/bin/env python3
"""
ais_decode.py – Minimal, pure-Python AIS receiver for RTL-SDR

© 2025  Peyton Andras • MIT licence
"""
import argparse, sys, time, struct, itertools, json, math, pathlib
import numpy as np
from scipy.signal import firwin, lfilter
from rtlsdr import RtlSdr
from pyais import decode as ais_parse

FS              = 2_048_000          # IQ samplerate
BIT_RATE        = 9_600
SAMPLES_PER_BIT = FS // BIT_RATE     # 213

CH_FREQS = (161_975_000, 162_025_000)   # AIS 1 + AIS 2 centre freqs
HOP_MS   = 30                           # hop interval

# ------------------------------------------------------------------ DSP helpers
def fm_demod(iq):
    # differentiate phase (quadrature FM)
    ph = np.angle(iq)
    d = np.unwrap(ph)
    return np.diff(d)

def gaussian_filter(bits, bt=0.4):
    # generate Gaussian filter used in GMSK
    tb = 4        # filter length in symbol times
    t = np.linspace(-tb/2, tb/2, tb*SAMPLES_PER_BIT, endpoint=False)
    h = np.sqrt(2*np.pi/bt) * np.exp(-2*np.pi**2 * t**2 / bt**2)
    h /= h.sum()
    return lfilter(h, 1.0, bits)

def clock_recover(samples):
    # Mueller & Müller clock recovery (very light version)
    mu = 0.0
    omega = SAMPLES_PER_BIT
    gain_mu = 0.05
    gain_omega = 0.0002
    out = []
    i = 0
    while i + 1 < len(samples):
        out.append(samples[int(i)])
        x = samples[int(i)]
        dx = samples[int(i+1)] - samples[int(i-1)] if i >= 1 else 0
        mu += omega + gain_mu * x * dx
        if mu >= 1.0:
            mu -= 1.0
            i += 1
        i += 1
        omega += gain_omega * x * dx
    return np.array(out)

# ------------------------------------------------------------------ HDLC helpers
FLAG = 0x7E

def nrzi_to_nrz(bits):
    last = 0
    out = []
    for b in bits:
        out.append(b ^ last)
        last = b
    return out

def bit_unstuff(bits):
    out = []
    ones = 0
    for b in bits:
        out.append(b)
        if b:
            ones += 1
            if ones == 5:   # skip stuffed zero
                ones = 0
                continue
        else:
            ones = 0
    return out

def bits_to_bytes(bits):
    return bytes(int("".join(str(b) for b in bits[i:i+8]), 2)
                 for i in range(0, len(bits), 8))

# CRC-16-IBM (same as AIS)
def crc16(data: bytes):
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc

# ------------------------------------------------------------------ main decode
def process_frame(bits):
    bits = nrzi_to_nrz(bits)
    bits = bit_unstuff(bits)
    if len(bits) < 208:          # shortest AIS msg ≈ 26 bytes
        return
    data = bits_to_bytes(bits)
    if crc16(data[:-2]) != int.from_bytes(data[-2:], "big"):
        return
    nmea = ais_bytes_to_nmea(data[:-2])
    try:
        msg = ais_parse(nmea)
        print(json.dumps(msg.asdict(), default=str))
    except Exception:
        print(nmea)

def ais_bytes_to_nmea(data):
    # convert binary AIS msg to 6-bit ASCII payload
    bitstr = "".join(f"{byte:08b}" for byte in data)
    # pad to 6-bit boundary
    pad = (6 - len(bitstr) % 6) % 6
    bitstr += "0" * pad
    payload = ""
    for i in range(0, len(bitstr), 6):
        v = int(bitstr[i:i+6], 2)
        payload += chr(v + 48 if v < 40 else v + 56)
    body = f"AIVDM,1,1,,A,{payload},{pad}"
    cs = 0
    for c in body:
        cs ^= ord(c)
    return f"!{body}*{cs:02X}"

# ------------------------------------------------------------------ RTL thread
def run_receiver(gain, ppm, seconds, iq_path):
    sdr = RtlSdr()
    sdr.sample_rate = FS
    sdr.freq_correction = ppm
    sdr.gain = gain

    hop_samples = int(FS * HOP_MS / 1000)
    start = time.time()

    if iq_path:
        iq_f = open(iq_path, "wb")

    try:
        while time.time() - start < seconds:
            for f in CH_FREQS:
                sdr.center_freq = f
                iq = sdr.read_samples(hop_samples).astype(np.complex64)

                if iq_path:
                    iq_f.write(iq.tobytes())

                audio = fm_demod(iq)
                audio = audio / np.max(np.abs(audio) + 1e-9)

                # Simple zero-crossing slicer
                bits = (audio > 0).astype(np.uint8)

                # crude resample to 1 sample/bit
                bits = bits[::SAMPLES_PER_BIT]

                # split by flags
                for flag_pos in np.where(bits == 0)[0]:
                    frame = bits[flag_pos+8 : flag_pos+2000]   # up to next flag
                    if len(frame) > 0 and bits[flag_pos+8] == 0:
                        process_frame(frame.tolist())
    finally:
        if iq_path:
            iq_f.close()
        sdr.close()

# ------------------------------------------------------------------ CLI
def main():
    ap = argparse.ArgumentParser(description="AIS decoder (pure Python)")
    ap.add_argument("--gain", "-g", type=float, default=36, help="RTL gain dB")
    ap.add_argument("--ppm", type=int, default=0, help="PPM correction")
    ap.add_argument("--seconds", "-t", type=int, default=30, help="Run time")
    ap.add_argument("--iq", metavar="FILE", help="Save raw IQ here")
    args = ap.parse_args()

    if args.iq:
        pathlib.Path(args.iq).expanduser().unlink(missing_ok=True)

    run_receiver(args.gain, args.ppm, args.seconds,
                 pathlib.Path(args.iq).expanduser() if args.iq else None)

if __name__ == "__main__":
    main()
