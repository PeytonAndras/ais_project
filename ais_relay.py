# relay script that captures AIS signals into .iq files and replays them using HackRF to the same frequency.
# for hackrf setup testing and AIS transmission testing.

#!/usr/bin/env python3
import subprocess
import time
import os
import signal

# ──────────────── CONFIGURATION ─────────────────

# AIS channel frequency (Hz)
FREQ        = 161_975_000

# Sample rate (Hz)
SAMPLE_RATE = 2_400_000

# RTL-SDR gain (dB)
RTL_GAIN    = 48

# HackRF TX gain (dB; 0–47)
TX_GAIN     = 30

# How many seconds to record per chunk
CAPTURE_SECS = 5

# Temporary IQ filename
IQ_FILE = "ais_capture.iq"


# ──────────────── HELPER FUNCTIONS ─────────────────

def capture_chunk():
    """
    Runs rtl_sdr for CAPTURE_SECS seconds and writes
    raw I/Q into IQ_FILE.
    """
    # Calculate number of samples = sample_rate * seconds
    n_samples = SAMPLE_RATE * CAPTURE_SECS

    cmd = [
        "rtl_sdr",
        "-f", str(FREQ),
        "-s", str(SAMPLE_RATE),
        "-g", str(RTL_GAIN),
        "-n", str(n_samples),
        IQ_FILE
    ]
    print(f"[CAPTURE] {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def replay_chunk():
    """
    Uses hackrf_transfer to feed the IQ_FILE back out
    on the same frequency.
    """
    cmd = [
        "hackrf_transfer",
        "-t", IQ_FILE,
        "-f", str(FREQ),
        "-s", str(SAMPLE_RATE),
        "-x", str(TX_GAIN),
        # continuous transmit until EOF of IQ_FILE
    ]
    print(f"[REPLAY] {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


# ──────────────── MAIN LOOP ─────────────────

def main():
    print("Press Ctrl-C to stop.")
    try:
        while True:
            # 1) Capture a few seconds of AIS IQ
            capture_chunk()

            # 2) Immediately replay it
            replay_chunk()

            # 3) Quick pause so we don’t thrash disks
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\nExiting, cleaning up…")
    finally:
        # remove the temp file
        if os.path.exists(IQ_FILE):
            os.remove(IQ_FILE)


if __name__ == "__main__":
    main()
