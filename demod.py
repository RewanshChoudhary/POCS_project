from __future__ import annotations

import numpy as np
from scipy import signal


def am_demodulate_envelope(am_signal: np.ndarray, t: np.ndarray, carrier_freq: float, 
                          carrier_amplitude: float = 1.0, smoothing: bool = True,
                          message_freq: float | None = None) -> np.ndarray:
    """
    AM demodulation using envelope detection.
    
    Args:
        am_signal: AM modulated signal
        t: Time vector
        carrier_freq: Carrier frequency (for optional filtering)
        carrier_amplitude: Expected carrier amplitude
        smoothing: Whether to apply low-pass filtering
    
    Returns:
        Demodulated message signal
    """
    # Envelope detection: absolute value
    envelope = np.abs(am_signal)
    
    if smoothing:
        # Low-pass to message band; if message_freq provided, prefer ~2.5*fm
        nyquist = 1.0 / (2.0 * np.mean(np.diff(t)))
        if message_freq is not None:
            cutoff_freq = min(0.45 * nyquist, 2.5 * float(message_freq))
        else:
            cutoff_freq = min(0.45 * nyquist, carrier_freq / 5.0)
        normalized_cutoff = cutoff_freq / nyquist
        if 0.0 < normalized_cutoff < 1.0:
            b, a = signal.butter(4, normalized_cutoff, btype='low')
            envelope = signal.filtfilt(b, a, envelope)
    
    # Remove DC offset and scale
    envelope = envelope - np.mean(envelope)
    envelope = envelope / carrier_amplitude
    
    return envelope


def fm_demodulate_instantaneous_frequency(fm_signal: np.ndarray, t: np.ndarray, 
                                        carrier_freq: float, fm_deviation: float) -> np.ndarray:
    """
    FM demodulation using instantaneous frequency estimation.
    
    Args:
        fm_signal: FM modulated signal
        t: Time vector
        carrier_freq: Carrier frequency
        fm_deviation: FM frequency deviation
    
    Returns:
        Demodulated message signal
    """
    # Method 1: Quadrature demodulation (Hilbert transform approach)
    # This is more robust than simple differentiation
    
    # Create analytic signal using Hilbert transform
    analytic_signal = signal.hilbert(fm_signal)
    
    # Calculate instantaneous phase
    phase = np.angle(analytic_signal)
    
    # Unwrap phase to avoid 2π jumps
    phase_unwrapped = np.unwrap(phase)
    
    # Calculate instantaneous frequency as derivative of phase
    dt = np.mean(np.diff(t))
    instantaneous_freq = np.gradient(phase_unwrapped) / (2.0 * np.pi * dt)
    
    # Remove carrier frequency to get frequency deviation
    freq_deviation = instantaneous_freq - carrier_freq
    
    # Convert frequency deviation to message signal
    message = freq_deviation / fm_deviation
    
    return message


def fm_demodulate_quadrature(fm_signal: np.ndarray, t: np.ndarray, 
                           carrier_freq: float, fm_deviation: float) -> np.ndarray:
    """
    FM demodulation using quadrature method.
    
    Args:
        fm_signal: FM modulated signal
        t: Time vector
        carrier_freq: Carrier frequency
        fm_deviation: FM frequency deviation
    
    Returns:
        Demodulated message signal
    """
    # Create quadrature components
    in_phase = fm_signal * np.cos(2.0 * np.pi * carrier_freq * t)
    quadrature = fm_signal * np.sin(2.0 * np.pi * carrier_freq * t)
    
    # Low-pass filter to remove high-frequency components
    cutoff_freq = carrier_freq / 10.0
    nyquist = 1.0 / (2.0 * np.mean(np.diff(t)))
    normalized_cutoff = cutoff_freq / nyquist
    
    if normalized_cutoff < 1.0:
        b, a = signal.butter(4, normalized_cutoff, btype='low')
        in_phase = signal.filtfilt(b, a, in_phase)
        quadrature = signal.filtfilt(b, a, quadrature)
    
    # Calculate instantaneous frequency
    # d/dt(arctan(Q/I)) = (I*dQ/dt - Q*dI/dt) / (I^2 + Q^2)
    dt = np.mean(np.diff(t))
    dI_dt = np.gradient(in_phase) / dt
    dQ_dt = np.gradient(quadrature) / dt
    
    instantaneous_freq = (in_phase * dQ_dt - quadrature * dI_dt) / (in_phase**2 + quadrature**2 + 1e-10)
    instantaneous_freq = instantaneous_freq / (2.0 * np.pi)
    
    # Remove carrier frequency and scale
    freq_deviation = instantaneous_freq - carrier_freq
    message = freq_deviation / fm_deviation
    
    return message
