from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np

from config import SimulationParams
from noise import calculate_signal_power, calculate_noise_power, calculate_snr_db


@dataclass
class TrialResult:
    """Results from a single Monte Carlo trial."""
    input_snr_db: float
    output_snr_am_db: float
    output_snr_fm_db: float
    trial_id: int


@dataclass
class PerformanceResults:
    """Aggregated performance results."""
    snr_levels: List[float]
    am_results: Dict[float, List[float]]  # input_snr -> list of output_snrs
    fm_results: Dict[float, List[float]]
    am_means: Dict[float, float]  # input_snr -> mean output_snr
    fm_means: Dict[float, float]
    am_stds: Dict[float, float]  # input_snr -> std output_snr
    fm_stds: Dict[float, float]


def calculate_output_snr(original_message: np.ndarray, demodulated_message: np.ndarray) -> float:
    """
    Calculate output SNR in dB from original and demodulated messages.
    
    Args:
        original_message: Original message signal
        demodulated_message: Demodulated message signal
    
    Returns:
        Output SNR in dB
    """
    # Ensure signals are the same length
    min_len = min(len(original_message), len(demodulated_message))
    original = original_message[:min_len]
    demodulated = demodulated_message[:min_len]
    
    # Calculate signal and noise powers
    signal_power = calculate_signal_power(original)
    noise_power = calculate_noise_power(original, demodulated)
    
    # Calculate SNR in dB
    snr_db = calculate_snr_db(signal_power, noise_power)
    
    return snr_db


def run_monte_carlo_trial(params: SimulationParams, input_snr_db: float, trial_id: int) -> TrialResult:
    """
    Run a single Monte Carlo trial for both AM and FM.
    
    Args:
        params: Simulation parameters
        input_snr_db: Input SNR in dB
        trial_id: Trial identifier
    
    Returns:
        Trial results for both AM and FM
    """
    from signals import generate_time_vector, message_signal, am_modulate, fm_modulate
    from noise import add_gaussian_noise
    from demod import am_demodulate_envelope, fm_demodulate_instantaneous_frequency
    
    # Generate signals
    t = generate_time_vector(params.sampling_rate, params.duration)
    original_message = message_signal(t, params.message_freq, params.message_amplitude)
    
    # AM modulation and demodulation
    am_signal = am_modulate(original_message, t, params.carrier_freq, 
                           params.carrier_amplitude, params.am_index)
    am_noisy = add_gaussian_noise(am_signal, input_snr_db, seed=trial_id)
    am_demodulated = am_demodulate_envelope(am_noisy, t, params.carrier_freq, 
                                          params.carrier_amplitude)
    
    # FM modulation and demodulation
    fm_signal = fm_modulate(original_message, t, params.carrier_freq, 
                           params.carrier_amplitude, params.fm_deviation, params.sampling_rate)
    fm_noisy = add_gaussian_noise(fm_signal, input_snr_db, seed=trial_id + 1000)
    fm_demodulated = fm_demodulate_instantaneous_frequency(fm_noisy, t, params.carrier_freq, 
                                                          params.fm_deviation)
    
    # Calculate output SNRs
    output_snr_am = calculate_output_snr(original_message, am_demodulated)
    output_snr_fm = calculate_output_snr(original_message, fm_demodulated)
    
    return TrialResult(
        input_snr_db=input_snr_db,
        output_snr_am_db=output_snr_am,
        output_snr_fm_db=output_snr_fm,
        trial_id=trial_id
    )


def run_monte_carlo_simulation(params: SimulationParams) -> PerformanceResults:
    """
    Run complete Monte Carlo simulation for all SNR levels.
    
    Args:
        params: Simulation parameters
    
    Returns:
        Aggregated performance results
    """
    # Generate SNR levels
    snr_levels = np.arange(params.snr_min, params.snr_max + params.snr_step, params.snr_step)
    snr_levels = np.round(snr_levels, 1)  # Round to avoid floating point issues
    
    am_results = {snr: [] for snr in snr_levels}
    fm_results = {snr: [] for snr in snr_levels}
    
    print(f"Running Monte Carlo simulation with {params.trials} trials per SNR level...")
    print(f"SNR levels: {snr_levels}")
    
    for snr_db in snr_levels:
        print(f"Processing SNR = {snr_db:.1f} dB...")
        
        for trial in range(params.trials):
            result = run_monte_carlo_trial(params, snr_db, trial)
            am_results[snr_db].append(result.output_snr_am_db)
            fm_results[snr_db].append(result.output_snr_fm_db)
    
    # Calculate statistics
    am_means = {snr: np.mean(results) for snr, results in am_results.items()}
    fm_means = {snr: np.mean(results) for snr, results in fm_results.items()}
    am_stds = {snr: np.std(results) for snr, results in am_results.items()}
    fm_stds = {snr: np.std(results) for snr, results in fm_results.items()}
    
    return PerformanceResults(
        snr_levels=list(snr_levels),
        am_results=am_results,
        fm_results=fm_results,
        am_means=am_means,
        fm_means=fm_means,
        am_stds=am_stds,
        fm_stds=fm_stds
    )


def save_results_csv(results: PerformanceResults, filename: str = "monte_carlo_results.csv") -> None:
    """Save results to CSV file."""
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Input_SNR_dB', 'AM_Mean_Output_SNR_dB', 'AM_Std_Output_SNR_dB', 
                        'FM_Mean_Output_SNR_dB', 'FM_Std_Output_SNR_dB'])
        
        for snr in results.snr_levels:
            writer.writerow([
                snr,
                results.am_means[snr],
                results.am_stds[snr],
                results.fm_means[snr],
                results.fm_stds[snr]
            ])


def save_results_json(results: PerformanceResults, filename: str = "monte_carlo_results.json") -> None:
    """Save results to JSON file."""
    data = {
        'snr_levels': results.snr_levels,
        'am_means': results.am_means,
        'am_stds': results.am_stds,
        'fm_means': results.fm_means,
        'fm_stds': results.fm_stds,
        'am_results': {str(k): v for k, v in results.am_results.items()},
        'fm_results': {str(k): v for k, v in results.fm_results.items()}
    }
    
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)


def print_performance_summary(results: PerformanceResults) -> None:
    """Print a summary of performance results."""
    print("\n" + "="*60)
    print("MONTE CARLO SIMULATION RESULTS")
    print("="*60)
    print(f"{'Input SNR (dB)':<12} {'AM Mean':<10} {'AM Std':<10} {'FM Mean':<10} {'FM Std':<10}")
    print("-"*60)
    
    for snr in results.snr_levels:
        print(f"{snr:<12.1f} {results.am_means[snr]:<10.2f} {results.am_stds[snr]:<10.2f} "
              f"{results.fm_means[snr]:<10.2f} {results.fm_stds[snr]:<10.2f}")
    
    print("="*60)
