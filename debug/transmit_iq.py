import SoapySDR
from SoapySDR import *  # SOAPY_SDR_ constants
from SoapySDR import SOAPY_SDR_TX, SOAPY_SDR_CF32  # Explicitly import needed constants
import numpy as np
import time

# Parameters
FREQ = 161.975e6       # AIS channel 1
RATE = 960000          # Match IQ sample rate in your file
GAIN = 50              # Transmit gain (0-70)
IQ_FILE = "multi_ship_ais.iq"

# Load IQ file (float32 interleaved I/Q)
iq_data = np.fromfile(IQ_FILE, dtype=np.float32)
iq_complex = iq_data[0::2] + 1j * iq_data[1::2]

# Create LimeSDR device
args = dict(driver="lime")
sdr = SoapySDR.Device(args)

# Setup TX stream
sdr.setSampleRate(SOAPY_SDR_TX, 0, RATE)
sdr.setFrequency(SOAPY_SDR_TX, 0, FREQ)
sdr.setGain(SOAPY_SDR_TX, 0, GAIN)
sdr.setAntenna(SOAPY_SDR_TX, 0, "BAND1")

txStream = sdr.setupStream(SOAPY_SDR_TX, SOAPY_SDR_CF32)
sdr.activateStream(txStream)

# Send IQ data in chunks
CHUNK = 4096
num_sent = 0
for i in range(0, len(iq_complex), CHUNK):
    samples = iq_complex[i:i+CHUNK]
    sr = sdr.writeStream(txStream, [samples.astype(np.complex64)], len(samples))
    num_sent += sr.ret
    time.sleep(CHUNK / RATE)

sdr.deactivateStream(txStream)
sdr.closeStream(txStream)

print(f"Transmitted {num_sent} samples at {RATE} Hz")
