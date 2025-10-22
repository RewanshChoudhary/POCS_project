from __future__ import annotations

import numpy as np


def generate_time_vector(sampling_rate: float, duration: float) -> np.ndarray:
    num_samples = int(np.round(sampling_rate * duration))
    if num_samples <= 0:
        raise ValueError("Number of samples must be positive")
    t = np.arange(num_samples, dtype=float) / sampling_rate
    return t


def message_signal(t: np.ndarray, message_freq: float, amplitude: float = 1.0, phase: float = 0.0) -> np.ndarray:
    return amplitude * np.sin(2.0 * np.pi * message_freq * t + phase)


def carrier_signal(t: np.ndarray, carrier_freq: float, amplitude: float = 1.0, phase: float = 0.0) -> np.ndarray:
    return amplitude * np.sin(2.0 * np.pi * carrier_freq * t + phase)


def am_modulate(m: np.ndarray, t: np.ndarray, carrier_freq: float, carrier_amplitude: float = 1.0, am_index: float = 0.5) -> np.ndarray:
    # s_AM(t) = Ac * (1 + ka*m(t)) * sin(2π f_c t)
    return carrier_amplitude * (1.0 + am_index * m) * np.sin(2.0 * np.pi * carrier_freq * t)


def fm_modulate(m: np.ndarray, t: np.ndarray, carrier_freq: float, carrier_amplitude: float = 1.0, fm_deviation_hz: float = 5_000.0, sampling_rate: float | None = None) -> np.ndarray:
    # s_FM(t) = Ac * sin(2π f_c t + 2π*Δf * ∫ m(τ) dτ)
    if sampling_rate is None:
        # Derive from time vector assuming uniform spacing
        if len(t) < 2:
            raise ValueError("Time vector must have at least two samples")
        dt = float(np.mean(np.diff(t)))
    else:
        dt = 1.0 / float(sampling_rate)
    integral_m = np.cumsum(m) * dt
    phase = 2.0 * np.pi * carrier_freq * t + 2.0 * np.pi * fm_deviation_hz * integral_m
    return carrier_amplitude * np.sin(phase)
