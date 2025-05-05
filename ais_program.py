#!/usr/bin/env python3
"""
ais_tx.py

Transmit custom AIS messages via LimeSDR‑Mini.

Dependencies:
  • SoapySDR (with the lime driver) – e.g. `apt install soapysdr-module-lms7 python3-soapysdr`
  • numpy
  • scipy

Usage examples:
  # 1) Send raw bit-string:
  python ais_tx.py \
    --payload-bits 011000110... \
    --frequency 161.975e6 \
    --gain 30

  # 2) Send a standard AIS NMEA sentence:
  python ais_tx.py \
    --nmea "!AIVDM,1,1,,A,13aG?P0000G?tO0PD5@<4?wN0<0,0*3D" \
    --frequency 162.025e6 \
    --gain 25

⚠️ **Warning**: Transmitting on VHF AIS channels without an appropriate license is illegal in most countries. Use this code only on a shielded test setup or with permission.
"""

import argparse
import sys
import numpy as np
from scipy.signsl import convolve
import SoapySDR
from SoapySDR import SOAPY_SDR_TX, SOAPY_SDR_CF32

def parse_args():
    p = argparse.ArgumentParser(description="AIS TX via LimeSDR‑Mini")
    grp = p.add_mutually_exclusive_group(required=True)
    grp.add_argument('--payload-bits', '-p', type=str,
                     help='Raw AIS payload bits, e.g. "011001..."')
    grp.add_argument('--nmea', '-n', type=str,
                     help='AIS NMEA sentence, e.g. !AIVDM,...')
    p.add_argument('--frequency', '-f', type=float, default=161.975e6,
                   help='Transmit center frequency in Hz (default: 161.975e6)')
    p.add_argument('--sample-rate', '-sr', type=float, default=192e3,
                   help='SDR sample rate in Hz (default: 192e3)')
    p.add_argument('--gain', '-g', type=float, default=30,
                   help='TX gain in dB (default: 30)')
    p.add_argument('--bt', type=float, default=0.3,
                   help='GMSK Gaussian filter BT product (default: 0.3)')
    p.add_argument('--sps', type=int, default=20,
                   help='Samples per symbol (default: 20 → 20×9.6 kbaud=192 kHz)')
    p.add_argument('--duration', '-d', type=float, default=5.0,
                   help='Transmit duration in seconds (default: 5)')
    return p.parse_args()

def nmea_to_bits(nmea):
    """
    Parse a !AIVDM NMEA sentence into its binary payload bits,
    removing the fill bits.
    """
    fields = nmea.strip().split(',')
    if not fields[0].startswith('!AIVDM'):
        raise ValueError("Not a valid !AIVDM sentence")
    payload = fields[5]
    fill_bits = int(fields[6].split('*')[0])
    bits = []
    for ch in payload:
        v = ord(ch) - 48
        if v > 40: v -= 8
        for i in range(5, -1, -1):
            bits.append((v >> i) & 1)
    if fill_bits:
        bits = bits[:-fill_bits]
    return bits

def gaussian_filter(bt, sps, span=4):
    """
    Create a Gaussian impulse response for GMSK:
      bt = bandwidth-symbol product
      sps = samples per symbol
      span = filter length in symbol durations
    """
    N = int(span * sps)
    t = np.linspace(-span/2, span/2, N)
    alpha = np.sqrt(np.log(2)) / (bt * sps)
    h = np.exp(- (t**2) / (2 * alpha**2))
    return h / np.sum(h)

def gmsk_modulate(bits, sps, bt):
    """
    Simple GMSK modulator:
      • NRZ map: 0→-1, 1→+1
      • Upsample, Gaussian filter, integrate → phase
      • Output complex baseband
    """
    # NRZ mapping
    data = np.array(bits)*2 - 1
    # Upsample
    up = np.repeat(data, sps)
    # Gaussian filter
    h = gaussian_filter(bt, sps)
    # Integrate to phase
    phase = np.pi * np.cumsum(convolve(up, h, mode='same')) / sps
    return np.exp(1j*phase).astype(np.complex64)

def build_frame(payload_bits):
    """
    Build the AIS HDLC frame:
      • 24-bit preamble (0101…)
      • 8-bit flag 0x7E (01111110)
      • payload with bit-stuffing (after 5 ones insert 0)
      • closing flag
    """
    # 24-bit preamble: 010101...
    pre = [i % 2 for i in range(24)]
    flag = [0,1,1,1,1,1,1,0]
    stuffed = []
    cnt = 0
    for b in payload_bits:
        stuffed.append(b)
        if b == 1:
            cnt += 1
            if cnt == 5:
                stuffed.append(0)
                cnt = 0
        else:
            cnt = 0
    return pre + flag + stuffed + flag

def main():
    args = parse_args()

    # 1) get payload bits
    if args.nmea:
        bits = nmea_to_bits(args.nmea)
    else:
        bits = [int(b) for b in args.payload_bits.strip()]
    # 2) frame + bit-stuffing
    frame = build_frame(bits)
    # 3) GMSK modulate
    tx_wave = gmsk_modulate(frame, args.sps, args.bt)

    # repeat to fill duration
    total_samples = int(args.sample_rate * args.duration)
    reps = int(np.ceil(total_samples / len(tx_wave)))
    tx_wave = np.tile(tx_wave, reps)[:total_samples]

    # 4) setup SoapySDR
    sdr = SoapySDR.Device({'driver':'lime'})
    sdr.setSampleRate(SOAPY_SDR_TX, 0, args.sample_rate)
    sdr.setFrequency(SOAPY_SDR_TX, 0, args.frequency)
    sdr.setGain(SOAPY_SDR_TX, 0, args.gain)
    sdr.setAntenna(SOAPY_SDR_TX, 0, "TRX")

    tx_stream = sdr.setupStream(SOAPY_SDR_TX, SOAPY_SDR_CF32, [0])
    sdr.activateStream(tx_stream)
    print(f"Transmitting on {args.frequency/1e6:.3f} MHz for {args.duration}s ...")

    # send in one burst
    sr = sdr.writeStream(tx_stream, [tx_wave], len(tx_wave))
    if sr.ret != len(tx_wave):
        print(f"Warning: only wrote {sr.ret} of {len(tx_wave)} samples", file=sys.stderr)

    sdr.deactivateStream(tx_stream)
    sdr.closeStream(tx_stream)
    print("Done.")

if __name__ == "__main__":
    main()

