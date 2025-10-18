# AM/FM Performance Analysis - Monte Carlo Simulation

This project implements a comparative analysis of Amplitude Modulation (AM) and Frequency Modulation (FM) systems under various noise conditions using Monte Carlo simulation in Go.

## 🎯 Objective

To simulate AM and FM communication systems under noisy channel conditions, analyze their Signal-to-Noise Ratio (SNR) performance, and demonstrate how FM exhibits better noise immunity compared to AM.

## 🏗️ Project Structure

```
am-fm-simulation/
├── main.go          # Core signal processing and simulation
├── results.go       # CSV output functionality  
├── main_test.go     # Comprehensive unit tests
├── go.mod          # Go module dependencies
├── README.md       # This documentation
└── outputs/        # Generated plots and data files
    ├── *.png       # Visualization plots
    └── *.csv       # Simulation results data
```

## 🧮 Theory

### Signal Models

**Baseband Message Signal:**
```
m(t) = Am × sin(2πfmt)
```

**Carrier Signal:**
```
c(t) = Ac × sin(2πfct)
```

**AM Modulated Signal:**
```
s_AM(t) = Ac × (1 + ka×m(t)) × sin(2πfct)
```

**FM Modulated Signal:**
```
s_FM(t) = Ac × sin(2πfct + kf × ∫m(t)dt)
```

### Noise Model

**Additive White Gaussian Noise (AWGN):**
- Converts SNR from dB to linear scale
- Computes noise variance based on signal power
- Adds zero-mean Gaussian noise samples

### Demodulation

**AM Demodulation (Envelope Detection):**
1. Rectify the received signal: `|s_AM(t)|`
2. Apply low-pass filter (moving average)

**FM Demodulation (Frequency Discrimination):**
1. Quadrature detection using I/Q components
2. Compute instantaneous frequency using cross-product formula
3. Apply low-pass filtering for smoothing

## 🚀 Usage

### Prerequisites

- Go 1.21 or later
- Gonum plotting libraries (automatically installed)

### Building and Running

```bash
# Clone or navigate to the project directory
cd am-fm-simulation

# Install dependencies
go mod tidy

# Run the simulation
go run main.go results.go

# Run tests
go test -v

# Run benchmarks
go test -bench=.
```

### Output Files

The simulation generates several output files:

**Plots (PNG):**
- `basic_signals.png` - Baseband and carrier waveforms
- `modulated_signals.png` - AM and FM modulated signals
- `noisy_signals.png` - Clean vs noisy signal comparison
- `demodulated_signals.png` - Original vs demodulated signals
- `snr_comparison.png` - SNR performance comparison

**Data (CSV):**
- `snr_results.csv` - Input/output SNR comparison data
- `baseband_signal.csv` - Sample baseband signal data

## 📊 Key Parameters

### Default Signal Parameters
```go
SignalParams{
    SamplingRate:  10000,  // 10 kHz
    Duration:      0.1,    // 100 ms
    MessageFreq:   50,     // 50 Hz (AM and FM)
    CarrierFreq:   1000,   // 1 kHz
    MessageAmp:    1.0,
    CarrierAmp:    1.0,
    ModulationIdx: 0.5,    // AM: 50% modulation
                           // FM: 200 Hz frequency deviation
}
```

### Monte Carlo Simulation
- **SNR Range:** -5 dB to 30 dB (8 points)
- **Trials:** 100 per SNR level
- **Metrics:** Output SNR for both AM and FM

## 📈 Expected Results

The simulation demonstrates that:

1. **AM Performance:** 
   - Output SNR degrades significantly with input SNR
   - Susceptible to amplitude noise
   - Simple envelope detection

2. **FM Performance:**
   - Better noise immunity at high SNRs
   - Constant envelope maintains amplitude
   - More complex demodulation required

3. **Comparison:**
   - FM shows superior performance in high SNR conditions
   - Trade-off between bandwidth and noise immunity
   - AM is simpler but less robust

## 🧪 Testing

Comprehensive unit tests cover:
- ✅ Signal generation (baseband, carrier, AM, FM)
- ✅ Noise addition with proper SNR levels
- ✅ Demodulation algorithms
- ✅ SNR calculation accuracy
- ✅ Parameter validation
- ✅ Performance benchmarks

Run tests with: `go test -v`

## 🔧 Customization

### Modify Signal Parameters
Edit the `params` and `fmParams` structures in `main.go`:

```go
params := SignalParams{
    SamplingRate:  20000,  // Higher sampling rate
    MessageFreq:   25,     // Lower message frequency
    ModulationIdx: 0.8,    // Higher AM modulation
}
```

### Change Monte Carlo Settings
Modify the simulation parameters:

```go
snrRange := []float64{-10, -5, 0, 5, 10, 15, 20, 25, 30, 35}
numTrials := 500  // More trials for better statistics
```

### Add Custom Analysis
Extend the `monteCarloSimulation` function to include:
- Bit Error Rate (BER) analysis
- Different noise models
- Additional modulation schemes

## 🚨 Known Limitations

1. **FM Demodulator:** The current implementation uses a simplified quadrature detection method. Professional FM demodulators use more sophisticated techniques like:
   - Hilbert transform for analytic signal
   - Phase-locked loops (PLL)
   - Delay-line discriminators

2. **Ideal Conditions:** The simulation assumes:
   - Perfect timing synchronization
   - No multipath fading
   - Linear channel response

3. **Limited Bandwidth Analysis:** The simulation doesn't account for:
   - Bandwidth limitations
   - Filtering effects
   - Spectral efficiency comparisons

## 📚 Educational Value

This simulation is excellent for understanding:
- Digital signal processing concepts
- Modulation/demodulation techniques  
- Noise effects in communication systems
- Monte Carlo simulation methodology
- Statistical analysis of system performance

## 🛠️ Future Enhancements

Potential improvements include:
- [ ] More sophisticated FM demodulation
- [ ] Additional modulation schemes (PSK, QAM)
- [ ] Real-time signal processing
- [ ] GUI interface for parameter adjustment
- [ ] Advanced noise models (colored noise, fading)
- [ ] Spectral analysis tools

## 📄 License

This project is provided for educational and research purposes. Feel free to modify and extend for your learning needs.

---

**Note:** This implementation prioritizes educational clarity over production optimization. For professional applications, consider using established DSP libraries and more robust algorithms.