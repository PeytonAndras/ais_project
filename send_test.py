import SoapySDR
from SoapySDR import SOAPY_SDR_TX
import numpy as np
import time
from pyais import decode

def crc16_ccitt(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = (crc << 1) ^ 0x1021 if crc & 0x8000 else crc << 1
            crc &= 0xFFFF
    return crc

def create_hdlc_frame(bit_str):
    bits = [int(b) for b in bit_str]

    frame_bytes = np.packbits(bits[::-1])  # AIS bit order LSB first per byte
    crc = crc16_ccitt(frame_bytes)
    crc_bytes = [(crc >> 8) & 0xFF, crc & 0xFF]

    data = np.concatenate((frame_bytes, crc_bytes))

    data_bits = np.unpackbits(data)  # Back to bits

    # Bit stuffing
    stuffed_bits, ones = [], 0
    for bit in data_bits:
        stuffed_bits.append(bit)
        ones = (ones + 1) if bit else 0
        if ones == 5:
            stuffed_bits.append(0)
            ones = 0

    return stuffed_bits

def create_packet(nmea_sentence):
    decoded_msg = decode(nmea_sentence)
    payload_bits = decoded_msg.encode_bits()

    training = [0, 1] * 12
    flag = [0,1,1,1,1,1,1,0]

    hdlc_data = create_hdlc_frame(payload_bits)

    buffer_bits = [0] * 8
    packet_bits = training + flag + hdlc_data + flag + buffer_bits

    return np.array(packet_bits)

def nrzi_encode(bits):
    encoded, state = [], 0
    for bit in bits:
        state = state if bit else 1 - state
        encoded.append(state)
    return np.array(encoded)

def gmsk_modulate(bits, sample_rate, symbol_rate=9600):
    samples_per_symbol = int(sample_rate / symbol_rate)
    symbols = 2*bits - 1
    upsampled = np.repeat(symbols, samples_per_symbol)

    bt, filter_span = 0.4, 4
    filter_length = filter_span * samples_per_symbol
    t = np.linspace(-filter_span/2, filter_span/2, filter_length)
    alpha = np.sqrt(np.log(2))/(bt/2)
    gauss_filter = np.exp(- (alpha * t)**2)
    gauss_filter /= gauss_filter.sum()

    filtered = np.convolve(upsampled, gauss_filter, mode='same')
    freq_dev = 2400
    phase = 2*np.pi*freq_dev*np.cumsum(filtered)/sample_rate

    return np.exp(1j*phase).astype(np.complex64)

def ramps(signal, sample_rate):
    ramp_samples = int(0.0005 * sample_rate)
    ramp_up = 0.5*(1-np.cos(np.pi*np.linspace(0,1,ramp_samples)))
    ramp_down = ramp_up[::-1]

    signal[:ramp_samples] *= ramp_up
    signal[-ramp_samples:] *= ramp_down

    return signal

def main():
    device = SoapySDR.Device(dict(driver="lime"))

    sample_rate, freq, gain = 2e6, 161.975e6, 20
    device.setSampleRate(SOAPY_SDR_TX, 0, sample_rate)
    device.setFrequency(SOAPY_SDR_TX, 0, freq)
    device.setGain(SOAPY_SDR_TX, 0, gain)

    nmea_msg = "!AIVDM,1,1,,A,15MvlfP000G?n@@K>OW`4?vN0<0=,0*47"
    bits = create_packet(nmea_msg)
    nrzi_bits = nrzi_encode(bits)
    signal = ramps(gmsk_modulate(nrzi_bits, sample_rate), sample_rate) * 0.3

    stream = device.setupStream(SOAPY_SDR_TX, "CF32")
    device.activateStream(stream)

    print("Start rtl_ais and press Enter")
    input()

    for i in range(20):
        tx_samples = np.concatenate((np.zeros(int(0.002*sample_rate)), signal, np.zeros(int(0.002*sample_rate))))

        chunk_size = 8192
        for j in range(0, len(tx_samples), chunk_size):
            chunk = tx_samples[j:j+chunk_size]
            device.writeStream(stream, [chunk], len(chunk))

        print(f"Transmission {i+1} complete.")
        time.sleep(5)

    device.deactivateStream(stream)
    device.closeStream(stream)

if __name__ == '__main__':
    main()
