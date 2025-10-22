from __future__ import annotations

import numpy as np


def add_gaussian_noise(signal: np.ndarray, snr_db: float, seed: int | None = None) -> np.ndarray:
    """
    Add Gaussian noise to a signal to achieve desired SNR in dB.
    
    Args:
        signal: Input signal array
        snr_db: Desired signal-to-noise ratio in dB
        seed: Random seed for reproducibility (optional)
    
    Returns:
        Noisy signal with the specified SNR
    """
    if seed is not None:
        np.random.seed(seed)
    
    # Convert SNR from dB to linear scale
    snr_linear = 10.0 ** (snr_db / 10.0)
    
    # Calculate signal power
    signal_power = np.mean(signal ** 2)
    
    # Calculate required noise power
    noise_power = signal_power / snr_linear
    
    # Generate Gaussian noise with the required power
    noise_std = np.sqrt(noise_power)
    noise = np.random.normal(0, noise_std, size=signal.shape)
    
    # Add noise to signal
    noisy_signal = signal + noise
    
    return noisy_signal


def calculate_signal_power(signal: np.ndarray) -> float:
    """Calculate the average power of a signal."""
    return float(np.mean(signal ** 2))


def calculate_noise_power(clean_signal: np.ndarray, noisy_signal: np.ndarray) -> float:
    """Calculate the power of the noise component."""
    noise = noisy_signal - clean_signal
    return calculate_signal_power(noise)


def calculate_snr_db(signal_power: float, noise_power: float) -> float:
    """Calculate SNR in dB from signal and noise powers."""
    if noise_power <= 0:
        return float('inf')
    return 10.0 * np.log10(signal_power / noise_power)
