from __future__ import annotations

import argparse
import os
import sys

from config import parse_args_and_get_params, print_summary
from signals import generate_time_vector, message_signal, carrier_signal, am_modulate, fm_modulate
from utils import run_monte_carlo_simulation, save_results_csv, save_results_json, print_performance_summary
from plots import generate_all_plots, plot_snr_comparison, plot_signal_evolution, plot_noise_effects


def main() -> None:
    parser = argparse.ArgumentParser(description="AM/FM Monte Carlo Simulation")
    parser.add_argument("--run-simulation", action="store_true", help="Run full Monte Carlo simulation")
    parser.add_argument("--plot-signals", action="store_true", help="Generate signal evolution plots")
    parser.add_argument("--plot-noise", action="store_true", help="Generate noise effects plots")
    parser.add_argument("--plot-all", action="store_true", help="Generate all visualization plots")
    parser.add_argument("--output-dir", type=str, default="outputs", help="Output directory for results and plots")
    parser.add_argument("--output-csv", type=str, default="monte_carlo_results.csv", help="CSV output filename")
    parser.add_argument("--output-json", type=str, default="monte_carlo_results.json", help="JSON output filename")
    parser.add_argument("--mode", choices=["default", "interactive", "cli"], default="default", 
                       help="Execution mode: default (smoke test), interactive (prompts), cli (arguments)")
    
    args, remaining_args = parser.parse_known_args()
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Parse simulation parameters from remaining args
    sys.argv = ['main.py'] + remaining_args
    params, _ = parse_args_and_get_params()
    print_summary(params)

    results = None
    
    if args.run_simulation:
        print("\nRunning Monte Carlo simulation...")
        results = run_monte_carlo_simulation(params)
        
        # Save results to output directory
        csv_path = os.path.join(args.output_dir, args.output_csv)
        json_path = os.path.join(args.output_dir, args.output_json)
        save_results_csv(results, csv_path)
        save_results_json(results, json_path)
        print(f"\nResults saved to {csv_path} and {json_path}")
        
        # Print summary
        print_performance_summary(results)
    
    if args.plot_all:
        print("\nGenerating all visualization plots...")
        generate_all_plots(params, results, args.output_dir)
    else:
        if args.plot_signals:
            print("\nGenerating signal evolution plots...")
            plot_signal_evolution(params, os.path.join(args.output_dir, "signal_evolution.png"))
        
        if args.plot_noise:
            print("\nGenerating noise effects plots...")
            plot_noise_effects(params, save_path=os.path.join(args.output_dir, "noise_effects.png"))
        
        if results is not None:
            plot_snr_comparison(results, os.path.join(args.output_dir, "snr_comparison.png"))
    
    if not any([args.run_simulation, args.plot_signals, args.plot_noise, args.plot_all]):
        # Quick smoke test for generation and modulation (no I/O side effects)
        print("\nRunning smoke test...")
        t = generate_time_vector(params.sampling_rate, params.duration)
        m = message_signal(t, params.message_freq, params.message_amplitude)
        c = carrier_signal(t, params.carrier_freq, params.carrier_amplitude)
        _ = am_modulate(m, t, params.carrier_freq, params.carrier_amplitude, params.am_index)
        _ = fm_modulate(m, t, params.carrier_freq, params.carrier_amplitude, params.fm_deviation, params.sampling_rate)
        print("Smoke test completed successfully!")


if __name__ == "__main__":
    main()
