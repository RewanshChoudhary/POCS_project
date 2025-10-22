from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Tuple

from rich import print as rprint


@dataclass
class SimulationParams:
    sampling_rate: float = 100_000.0  # Hz
    duration: float = 0.1  # seconds
    message_freq: float = 1_000.0  # Hz
    carrier_freq: float = 10_000.0  # Hz
    am_index: float = 0.5  # 0..1 typical
    fm_deviation: float = 5_000.0  # Hz per unit amplitude of m(t)
    snr_min: float = 0.0  # dB
    snr_max: float = 30.0  # dB
    snr_step: float = 5.0  # dB
    trials: int = 100
    message_amplitude: float = 1.0
    carrier_amplitude: float = 1.0


# ----------------------- Validation helpers -----------------------

def _clamp(value: float, min_val: float, max_val: float, default: float) -> float:
    try:
        v = float(value)
    except Exception:
        return default
    if not (min_val <= v <= max_val):
        return default
    return v


def _positive(value: float, default: float) -> float:
    try:
        v = float(value)
    except Exception:
        return default
    if v <= 0:
        return default
    return v


def _positive_int(value: int, default: int) -> int:
    try:
        v = int(value)
    except Exception:
        return default
    if v <= 0:
        return default
    return v


def validate_params(p: SimulationParams) -> SimulationParams:
    p.sampling_rate = _positive(p.sampling_rate, 100_000.0)
    p.duration = _positive(p.duration, 0.1)
    p.message_freq = _positive(p.message_freq, 1_000.0)
    p.carrier_freq = _positive(p.carrier_freq, 10_000.0)
    p.am_index = _clamp(p.am_index, 0.0, 1.0, 0.5)
    p.fm_deviation = _positive(p.fm_deviation, 5_000.0)
    # SNR range
    if p.snr_step <= 0:
        p.snr_step = 5.0
    if p.snr_min > p.snr_max:
        p.snr_min, p.snr_max = p.snr_max, p.snr_min
    p.trials = _positive_int(p.trials, 100)
    p.message_amplitude = _positive(p.message_amplitude, 1.0)
    p.carrier_amplitude = _positive(p.carrier_amplitude, 1.0)
    # Additional sanity: Nyquist - keep carrier and message below fs/2
    nyquist = p.sampling_rate / 2.0
    if p.carrier_freq >= nyquist:
        p.carrier_freq = max(100.0, nyquist * 0.4)
    if p.message_freq >= nyquist:
        p.message_freq = max(10.0, nyquist * 0.1)
    return p


# ----------------------- Argument parsing -----------------------

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AM/FM Monte Carlo Simulation Parameters")
    parser.add_argument("--fs", "--sampling-rate", dest="sampling_rate", type=float, help="Sampling rate (Hz)")
    parser.add_argument("--duration", type=float, help="Signal duration (s)")
    parser.add_argument("--fm", "--message-freq", dest="message_freq", type=float, help="Message frequency (Hz)")
    parser.add_argument("--fc", "--carrier-freq", dest="carrier_freq", type=float, help="Carrier frequency (Hz)")
    parser.add_argument("--ka", "--am-index", dest="am_index", type=float, help="AM modulation index (0..1)")
    parser.add_argument("--fd", "--fm-deviation", dest="fm_deviation", type=float, help="FM frequency deviation (Hz)")
    parser.add_argument("--snr-min", dest="snr_min", type=float, help="Minimum SNR (dB)")
    parser.add_argument("--snr-max", dest="snr_max", type=float, help="Maximum SNR (dB)")
    parser.add_argument("--snr-step", dest="snr_step", type=float, help="SNR step (dB)")
    parser.add_argument("--trials", dest="trials", type=int, help="Number of Monte Carlo trials")
    parser.add_argument("--Am", dest="message_amplitude", type=float, help="Message amplitude")
    parser.add_argument("--Ac", dest="carrier_amplitude", type=float, help="Carrier amplitude")
    parser.add_argument("-i", "--interactive", action="store_true", help="Prompt for parameters interactively")
    return parser


def _prompt_float(prompt: str, default: float, validator) -> float:
    try:
        raw = input(f"{prompt} [{default}]: ").strip()
        if raw == "":
            return default
        value = float(raw)
    except Exception:
        return default
    value = validator(value)
    return value


def _prompt_int(prompt: str, default: int) -> int:
    try:
        raw = input(f"{prompt} [{default}]: ").strip()
        if raw == "":
            return default
        value = int(raw)
    except Exception:
        return default
    if value <= 0:
        return default
    return value


def interactive_prompt(defaults: SimulationParams) -> SimulationParams:
    p = SimulationParams(**defaults.__dict__)
    rprint("[bold cyan]Interactive parameter entry[/bold cyan] (press Enter to keep default)")
    p.sampling_rate = _prompt_float("Sampling rate (Hz)", p.sampling_rate, lambda v: _positive(v, p.sampling_rate))
    p.duration = _prompt_float("Duration (s)", p.duration, lambda v: _positive(v, p.duration))
    p.message_freq = _prompt_float("Message frequency (Hz)", p.message_freq, lambda v: _positive(v, p.message_freq))
    p.carrier_freq = _prompt_float("Carrier frequency (Hz)", p.carrier_freq, lambda v: _positive(v, p.carrier_freq))
    p.am_index = _prompt_float("AM index (0..1)", p.am_index, lambda v: _clamp(v, 0.0, 1.0, p.am_index))
    p.fm_deviation = _prompt_float("FM deviation (Hz)", p.fm_deviation, lambda v: _positive(v, p.fm_deviation))
    p.snr_min = _prompt_float("SNR min (dB)", p.snr_min, lambda v: v)
    p.snr_max = _prompt_float("SNR max (dB)", p.snr_max, lambda v: v)
    p.snr_step = _prompt_float("SNR step (dB)", p.snr_step, lambda v: _positive(v, p.snr_step))
    p.trials = _prompt_int("Trials", p.trials)
    p.message_amplitude = _prompt_float("Message amplitude Am", p.message_amplitude, lambda v: _positive(v, p.message_amplitude))
    p.carrier_amplitude = _prompt_float("Carrier amplitude Ac", p.carrier_amplitude, lambda v: _positive(v, p.carrier_amplitude))
    return validate_params(p)


def choose_params(args: argparse.Namespace | None = None) -> SimulationParams:
    defaults = SimulationParams()
    if args is None:
        parser = build_arg_parser()
        args = parser.parse_args()
    # Start from defaults, override with CLI values if provided
    p = SimulationParams(**defaults.__dict__)
    for field in p.__dataclass_fields__.keys():
        if hasattr(args, field):
            value = getattr(args, field)
            if value is not None:
                setattr(p, field, value)
    p = validate_params(p)
    if getattr(args, "interactive", False):
        p = interactive_prompt(p)
    return validate_params(p)


def summarize_params(p: SimulationParams) -> str:
    snr_range = _format_snr_range(p.snr_min, p.snr_max, p.snr_step)
    return (
        "Parameters:"\
        f"\n  fs: {p.sampling_rate:.3f} Hz"\
        f"\n  duration: {p.duration:.6f} s"\
        f"\n  fm: {p.message_freq:.3f} Hz, Am: {p.message_amplitude:.3f}"\
        f"\n  fc: {p.carrier_freq:.3f} Hz, Ac: {p.carrier_amplitude:.3f}"\
        f"\n  AM index ka: {p.am_index:.3f}"\
        f"\n  FM deviation: {p.fm_deviation:.3f} Hz"\
        f"\n  SNR range (dB): {snr_range}"\
        f"\n  trials: {p.trials}"
    )


def _format_snr_range(snr_min: float, snr_max: float, snr_step: float) -> str:
    try:
        if snr_step <= 0:
            return f"{snr_min}..{snr_max} step invalid -> 5"
        if snr_min > snr_max:
            snr_min, snr_max = snr_max, snr_min
        values = []
        v = snr_min
        # create up to 100 steps to avoid infinite loop due to float rounding
        for _ in range(100):
            if v > snr_max + 1e-9:
                break
            values.append(round(v, 3))
            v += snr_step
        return ", ".join(str(x) for x in values)
    except Exception:
        return f"{snr_min}..{snr_max}"


def print_summary(p: SimulationParams) -> None:
    rprint("[bold green]" + summarize_params(p) + "[/bold green]")


def parse_args_and_get_params() -> Tuple[SimulationParams, argparse.Namespace]:
    parser = build_arg_parser()
    args = parser.parse_args()
    params = choose_params(args)
    return params, args
