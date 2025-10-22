from __future__ import annotations

import os
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, List, Optional

from config import SimulationParams
from utils import PerformanceResults


def plot_baseband_and_carrier(params: SimulationParams, save_path: Optional[str] = None) -> None:
    """Plot baseband message and carrier signals."""
    from signals import generate_time_vector, message_signal, carrier_signal
    
    t = generate_time_vector(params.sampling_rate, params.duration)
    message = message_signal(t, params.message_freq, params.message_amplitude)
    carrier = carrier_signal(t, params.carrier_freq, params.carrier_amplitude)
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    
    # Show first 0.01 seconds or 1000 samples, whichever is smaller
    max_samples = min(1000, int(0.01 * params.sampling_rate))
    
    ax1.plot(t[:max_samples], message[:max_samples], 'b-', linewidth=2, label='Message Signal')
    ax1.set_title('Baseband Message Signal')
    ax1.set_ylabel('Amplitude')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    ax2.plot(t[:max_samples], carrier[:max_samples], 'r-', linewidth=2, label='Carrier Signal')
    ax2.set_title('Carrier Signal')
    ax2.set_xlabel('Time (s)')
    ax2.set_ylabel('Amplitude')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.show()


def plot_modulated_signals(params: SimulationParams, save_path: Optional[str] = None) -> None:
    """Plot AM and FM modulated signals."""
    from signals import generate_time_vector, message_signal, am_modulate, fm_modulate
    
    t = generate_time_vector(params.sampling_rate, params.duration)
    message = message_signal(t, params.message_freq, params.message_amplitude)
    
    am_signal = am_modulate(message, t, params.carrier_freq, params.carrier_amplitude, params.am_index)
    fm_signal = fm_modulate(message, t, params.carrier_freq, params.carrier_amplitude, 
                           params.fm_deviation, params.sampling_rate)
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    
    # Show first 0.01 seconds or 1000 samples, whichever is smaller
    max_samples = min(1000, int(0.01 * params.sampling_rate))
    
    ax1.plot(t[:max_samples], am_signal[:max_samples], 'g-', linewidth=2, label='AM Modulated')
    ax1.set_title('AM Modulated Signal')
    ax1.set_ylabel('Amplitude')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    ax2.plot(t[:max_samples], fm_signal[:max_samples], 'm-', linewidth=2, label='FM Modulated')
    ax2.set_title('FM Modulated Signal')
    ax2.set_xlabel('Time (s)')
    ax2.set_ylabel('Amplitude')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.show()


def plot_noisy_vs_original(params: SimulationParams, snr_db: float = 10.0, 
                          save_path: Optional[str] = None) -> None:
    """Plot noisy signals vs original signals."""
    from signals import generate_time_vector, message_signal, am_modulate, fm_modulate
    from noise import add_gaussian_noise
    
    t = generate_time_vector(params.sampling_rate, params.duration)
    message = message_signal(t, params.message_freq, params.message_amplitude)
    
    am_signal = am_modulate(message, t, params.carrier_freq, params.carrier_amplitude, params.am_index)
    fm_signal = fm_modulate(message, t, params.carrier_freq, params.carrier_amplitude, 
                           params.fm_deviation, params.sampling_rate)
    
    am_noisy = add_gaussian_noise(am_signal, snr_db, seed=42)
    fm_noisy = add_gaussian_noise(fm_signal, snr_db, seed=42)
    
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    
    # Show first 0.01 seconds or 1000 samples, whichever is smaller
    max_samples = min(1000, int(0.01 * params.sampling_rate))
    
    # AM signals
    axes[0, 0].plot(t[:max_samples], am_signal[:max_samples], 'b-', linewidth=2, label='Original AM')
    axes[0, 0].set_title(f'AM Signal (Original)')
    axes[0, 0].set_ylabel('Amplitude')
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)
    
    axes[0, 1].plot(t[:max_samples], am_noisy[:max_samples], 'r-', linewidth=2, label=f'Noisy AM (SNR={snr_db}dB)')
    axes[0, 1].set_title(f'AM Signal (Noisy)')
    axes[0, 1].set_ylabel('Amplitude')
    axes[0, 1].legend()
    axes[0, 1].grid(True, alpha=0.3)
    
    # FM signals
    axes[1, 0].plot(t[:max_samples], fm_signal[:max_samples], 'b-', linewidth=2, label='Original FM')
    axes[1, 0].set_title(f'FM Signal (Original)')
    axes[1, 0].set_xlabel('Time (s)')
    axes[1, 0].set_ylabel('Amplitude')
    axes[1, 0].legend()
    axes[1, 0].grid(True, alpha=0.3)
    
    axes[1, 1].plot(t[:max_samples], fm_noisy[:max_samples], 'r-', linewidth=2, label=f'Noisy FM (SNR={snr_db}dB)')
    axes[1, 1].set_title(f'FM Signal (Noisy)')
    axes[1, 1].set_xlabel('Time (s)')
    axes[1, 1].set_ylabel('Amplitude')
    axes[1, 1].legend()
    axes[1, 1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.show()


def plot_demodulated_vs_original(params: SimulationParams, snr_db: float = 10.0, 
                                save_path: Optional[str] = None) -> None:
    """Plot demodulated signals vs original message."""
    from signals import generate_time_vector, message_signal, am_modulate, fm_modulate
    from noise import add_gaussian_noise
    from demod import am_demodulate_envelope, fm_demodulate_instantaneous_frequency
    
    t = generate_time_vector(params.sampling_rate, params.duration)
    original_message = message_signal(t, params.message_freq, params.message_amplitude)
    
    # AM path
    am_signal = am_modulate(original_message, t, params.carrier_freq, 
                           params.carrier_amplitude, params.am_index)
    am_noisy = add_gaussian_noise(am_signal, snr_db, seed=42)
    am_demodulated = am_demodulate_envelope(am_noisy, t, params.carrier_freq, 
                                          params.carrier_amplitude)
    
    # FM path
    fm_signal = fm_modulate(original_message, t, params.carrier_freq, 
                           params.carrier_amplitude, params.fm_deviation, params.sampling_rate)
    fm_noisy = add_gaussian_noise(fm_signal, snr_db, seed=42)
    fm_demodulated = fm_demodulate_instantaneous_frequency(fm_noisy, t, params.carrier_freq, 
                                                          params.fm_deviation)
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    
    # Show first 0.01 seconds or 1000 samples, whichever is smaller
    max_samples = min(1000, int(0.01 * params.sampling_rate))
    
    # AM demodulation comparison
    ax1.plot(t[:max_samples], original_message[:max_samples], 'b-', linewidth=2, label='Original Message')
    ax1.plot(t[:max_samples], am_demodulated[:max_samples], 'r-', linewidth=2, label='AM Demodulated')
    ax1.set_title(f'AM Demodulation Comparison (SNR={snr_db}dB)')
    ax1.set_ylabel('Amplitude')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # FM demodulation comparison
    ax2.plot(t[:max_samples], original_message[:max_samples], 'b-', linewidth=2, label='Original Message')
    ax2.plot(t[:max_samples], fm_demodulated[:max_samples], 'r-', linewidth=2, label='FM Demodulated')
    ax2.set_title(f'FM Demodulation Comparison (SNR={snr_db}dB)')
    ax2.set_xlabel('Time (s)')
    ax2.set_ylabel('Amplitude')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.show()


def plot_snr_comparison(results: PerformanceResults, save_path: Optional[str] = None) -> None:
    """Plot AM vs FM output SNR comparison."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    snr_levels = results.snr_levels
    am_means = [results.am_means[snr] for snr in snr_levels]
    fm_means = [results.fm_means[snr] for snr in snr_levels]
    am_stds = [results.am_stds[snr] for snr in snr_levels]
    fm_stds = [results.fm_stds[snr] for snr in snr_levels]
    
    # Plot with error bars
    ax.errorbar(snr_levels, am_means, yerr=am_stds, label='AM', marker='o', capsize=5)
    ax.errorbar(snr_levels, fm_means, yerr=fm_stds, label='FM', marker='s', capsize=5)
    
    # Plot diagonal line for reference (ideal case)
    ax.plot(snr_levels, snr_levels, 'k--', alpha=0.5, label='Ideal (1:1)')
    
    ax.set_xlabel('Input SNR (dB)')
    ax.set_ylabel('Output SNR (dB)')
    ax.set_title('AM vs FM Performance Comparison')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.show()


def generate_all_plots(params: SimulationParams, results: Optional[PerformanceResults] = None, 
                      output_dir: str = "outputs") -> None:
    """Generate all visualization plots and save to output directory."""
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Generating plots in {output_dir}/...")
    
    # Basic signal plots
    plot_baseband_and_carrier(params, os.path.join(output_dir, "baseband_and_carrier.png"))
    plot_modulated_signals(params, os.path.join(output_dir, "modulated_signals.png"))
    plot_noisy_vs_original(params, 10.0, os.path.join(output_dir, "noisy_vs_original.png"))
    plot_demodulated_vs_original(params, 10.0, os.path.join(output_dir, "demodulated_vs_original.png"))
    plot_signal_evolution(params, os.path.join(output_dir, "signal_evolution.png"))
    plot_noise_effects(params, save_path=os.path.join(output_dir, "noise_effects.png"))
    
    # Performance comparison plot (if results available)
    if results is not None:
        plot_snr_comparison(results, os.path.join(output_dir, "snr_comparison.png"))
    
    print(f"All plots saved to {output_dir}/")


def plot_signal_evolution(params: SimulationParams, save_path: Optional[str] = None) -> None:
    """Plot signal evolution through the system."""
    from signals import generate_time_vector, message_signal, am_modulate, fm_modulate
    from noise import add_gaussian_noise
    from demod import am_demodulate_envelope, fm_demodulate_instantaneous_frequency
    
    # Generate signals
    t = generate_time_vector(params.sampling_rate, params.duration)
    original_message = message_signal(t, params.message_freq, params.message_amplitude)
    
    # AM path
    am_signal = am_modulate(original_message, t, params.carrier_freq, 
                           params.carrier_amplitude, params.am_index)
    am_noisy = add_gaussian_noise(am_signal, 10.0, seed=42)  # 10 dB SNR
    am_demodulated = am_demodulate_envelope(am_noisy, t, params.carrier_freq, 
                                          params.carrier_amplitude)
    
    # FM path
    fm_signal = fm_modulate(original_message, t, params.carrier_freq, 
                           params.carrier_amplitude, params.fm_deviation, params.sampling_rate)
    fm_noisy = add_gaussian_noise(fm_signal, 10.0, seed=42)  # 10 dB SNR
    fm_demodulated = fm_demodulate_instantaneous_frequency(fm_noisy, t, params.carrier_freq, 
                                                          params.fm_deviation)
    
    # Create subplots
    fig, axes = plt.subplots(3, 2, figsize=(15, 10))
    
    # Original message
    axes[0, 0].plot(t[:1000], original_message[:1000])  # Show first 1000 samples
    axes[0, 0].set_title('Original Message')
    axes[0, 0].set_ylabel('Amplitude')
    axes[0, 0].grid(True, alpha=0.3)
    
    # AM modulated
    axes[1, 0].plot(t[:1000], am_signal[:1000])
    axes[1, 0].set_title('AM Modulated Signal')
    axes[1, 0].set_ylabel('Amplitude')
    axes[1, 0].grid(True, alpha=0.3)
    
    # AM demodulated
    axes[2, 0].plot(t[:1000], am_demodulated[:1000])
    axes[2, 0].set_title('AM Demodulated Signal')
    axes[2, 0].set_xlabel('Time (s)')
    axes[2, 0].set_ylabel('Amplitude')
    axes[2, 0].grid(True, alpha=0.3)
    
    # Original message (same for FM)
    axes[0, 1].plot(t[:1000], original_message[:1000])
    axes[0, 1].set_title('Original Message')
    axes[0, 1].set_ylabel('Amplitude')
    axes[0, 1].grid(True, alpha=0.3)
    
    # FM modulated
    axes[1, 1].plot(t[:1000], fm_signal[:1000])
    axes[1, 1].set_title('FM Modulated Signal')
    axes[1, 1].set_ylabel('Amplitude')
    axes[1, 1].grid(True, alpha=0.3)
    
    # FM demodulated
    axes[2, 1].plot(t[:1000], fm_demodulated[:1000])
    axes[2, 1].set_title('FM Demodulated Signal')
    axes[2, 1].set_xlabel('Time (s)')
    axes[2, 1].set_ylabel('Amplitude')
    axes[2, 1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.show()


def generate_all_plots(params: SimulationParams, results: Optional[PerformanceResults] = None, 
                      output_dir: str = "outputs") -> None:
    """Generate all visualization plots and save to output directory."""
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Generating plots in {output_dir}/...")
    
    # Basic signal plots
    plot_baseband_and_carrier(params, os.path.join(output_dir, "baseband_and_carrier.png"))
    plot_modulated_signals(params, os.path.join(output_dir, "modulated_signals.png"))
    plot_noisy_vs_original(params, 10.0, os.path.join(output_dir, "noisy_vs_original.png"))
    plot_demodulated_vs_original(params, 10.0, os.path.join(output_dir, "demodulated_vs_original.png"))
    plot_signal_evolution(params, os.path.join(output_dir, "signal_evolution.png"))
    plot_noise_effects(params, save_path=os.path.join(output_dir, "noise_effects.png"))
    
    # Performance comparison plot (if results available)
    if results is not None:
        plot_snr_comparison(results, os.path.join(output_dir, "snr_comparison.png"))
    
    print(f"All plots saved to {output_dir}/")


def plot_noise_effects(params: SimulationParams, snr_levels: List[float] = [0, 5, 10, 15, 20], 
                      save_path: Optional[str] = None) -> None:
    """Plot the effect of different noise levels on demodulated signals."""
    from signals import generate_time_vector, message_signal, am_modulate, fm_modulate
    from noise import add_gaussian_noise
    from demod import am_demodulate_envelope, fm_demodulate_instantaneous_frequency
    
    # Generate signals
    t = generate_time_vector(params.sampling_rate, params.duration)
    original_message = message_signal(t, params.message_freq, params.message_amplitude)
    
    fig, axes = plt.subplots(len(snr_levels), 2, figsize=(15, 3*len(snr_levels)))
    
    for i, snr_db in enumerate(snr_levels):
        # AM path
        am_signal = am_modulate(original_message, t, params.carrier_freq, 
                               params.carrier_amplitude, params.am_index)
        am_noisy = add_gaussian_noise(am_signal, snr_db, seed=42)
        am_demodulated = am_demodulate_envelope(am_noisy, t, params.carrier_freq, 
                                              params.carrier_amplitude)
        
        # FM path
        fm_signal = fm_modulate(original_message, t, params.carrier_freq, 
                               params.carrier_amplitude, params.fm_deviation, params.sampling_rate)
        fm_noisy = add_gaussian_noise(fm_signal, snr_db, seed=42)
        fm_demodulated = fm_demodulate_instantaneous_frequency(fm_noisy, t, params.carrier_freq, 
                                                              params.fm_deviation)
        
        # Plot AM
        axes[i, 0].plot(t[:1000], original_message[:1000], 'b-', alpha=0.7, label='Original')
        axes[i, 0].plot(t[:1000], am_demodulated[:1000], 'r-', alpha=0.7, label='Demodulated')
        axes[i, 0].set_title(f'AM Demodulation at {snr_db} dB SNR')
        axes[i, 0].set_ylabel('Amplitude')
        axes[i, 0].legend()
        axes[i, 0].grid(True, alpha=0.3)
        
        # Plot FM
        axes[i, 1].plot(t[:1000], original_message[:1000], 'b-', alpha=0.7, label='Original')
        axes[i, 1].plot(t[:1000], fm_demodulated[:1000], 'r-', alpha=0.7, label='Demodulated')
        axes[i, 1].set_title(f'FM Demodulation at {snr_db} dB SNR')
        axes[i, 1].set_ylabel('Amplitude')
        axes[i, 1].legend()
        axes[i, 1].grid(True, alpha=0.3)
    
    axes[-1, 0].set_xlabel('Time (s)')
    axes[-1, 1].set_xlabel('Time (s)')
    
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.show()


def generate_all_plots(params: SimulationParams, results: Optional[PerformanceResults] = None, 
                      output_dir: str = "outputs") -> None:
    """Generate all visualization plots and save to output directory."""
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Generating plots in {output_dir}/...")
    
    # Basic signal plots
    plot_baseband_and_carrier(params, os.path.join(output_dir, "baseband_and_carrier.png"))
    plot_modulated_signals(params, os.path.join(output_dir, "modulated_signals.png"))
    plot_noisy_vs_original(params, 10.0, os.path.join(output_dir, "noisy_vs_original.png"))
    plot_demodulated_vs_original(params, 10.0, os.path.join(output_dir, "demodulated_vs_original.png"))
    plot_signal_evolution(params, os.path.join(output_dir, "signal_evolution.png"))
    plot_noise_effects(params, save_path=os.path.join(output_dir, "noise_effects.png"))
    
    # Performance comparison plot (if results available)
    if results is not None:
        plot_snr_comparison(results, os.path.join(output_dir, "snr_comparison.png"))
    
    print(f"All plots saved to {output_dir}/")
