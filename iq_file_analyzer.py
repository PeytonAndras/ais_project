# This script reads a binary IQ file and plots the time-domain and frequency-domain representations of the signal.



import numpy as np
import matplotlib.pyplot as plt

def read_iq_file(file_path):
    # Read binary IQ data from the file
    iq_data = np.fromfile(file_path, dtype=np.complex64)
    return iq_data

def plot_time_domain(iq_data):
    # Plot the time-domain representation of the IQ data
    plt.figure(figsize=(10, 6))
    plt.subplot(2, 1, 1)
    plt.plot(np.real(iq_data), label='In-phase (I)')
    plt.plot(np.imag(iq_data), label='Quadrature (Q)')
    plt.title("Time Domain (IQ) Signal")
    plt.xlabel("Sample Index")
    plt.ylabel("Amplitude")
    plt.legend()

def plot_frequency_domain(iq_data, sample_rate):
    # Plot the frequency-domain representation using FFT
    n = len(iq_data)
    freqs = np.fft.fftfreq(n, d=1/sample_rate)
    fft_data = np.fft.fft(iq_data)
    plt.subplot(2, 1, 2)
    plt.plot(freqs[:n//2], np.abs(fft_data)[:n//2])  # Only plot the positive frequencies
    plt.title("Frequency Domain (FFT of IQ Signal)")
    plt.xlabel("Frequency (Hz)")
    plt.ylabel("Magnitude")

def main():
    file_path = "ais_transmission_20250522_175916.iq"  # Path to your IQ file
    sample_rate = 2e6  # Set the sample rate (e.g., 2 MHz for typical SDRs)
    
    iq_data = read_iq_file(file_path)
    
    # Plot the signal in time domain and frequency domain
    plt.figure(figsize=(10, 12))
    plot_time_domain(iq_data)
    plot_frequency_domain(iq_data, sample_rate)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()
