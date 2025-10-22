# AM/FM Performance Analysis - Monte Carlo Simulation

This project implements a comprehensive comparative analysis of Amplitude Modulation (AM) and Frequency Modulation (FM) systems under various noise conditions using Monte Carlo simulation in Go. **Now with full custom parameter support!**

## 🎯 Objective

To simulate AM and FM communication systems under noisy channel conditions, analyze their Signal-to-Noise Ratio (SNR) performance, and demonstrate how FM exhibits better noise immunity compared to AM. Users can now customize all simulation parameters for detailed analysis.

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
```

### 🎯 **Basic Usage Options**

#### **1. Default Simulation**
```bash
# Run with default parameters
go run main.go results.go
```

#### **2. Interactive Custom Mode**
```bash
# Step-by-step interactive configuration
go run main.go results.go custom
```

#### **3. Command-Line Custom Parameters**
```bash
# Custom parameters via command line
go run main.go results.go --message-freq=100 --carrier-freq=2000 --snr-range="0,10,20" --trials=50
```

#### **4. Help System**
```bash
# Show comprehensive usage guide
go run main.go results.go help
```

### 🔧 **Custom Parameter Options**

| Parameter | Command Line | Description | Default | Example |
|-----------|-------------|-------------|---------|---------|
| **Sampling Rate** | `--sampling-rate=N` | Sampling rate in Hz | 10000 | `--sampling-rate=20000` |
| **Duration** | `--duration=N` | Signal duration in seconds | 0.1 | `--duration=0.2` |
| **Message Frequency** | `--message-freq=N` | Message frequency in Hz | 50 | `--message-freq=100` |
| **Carrier Frequency** | `--carrier-freq=N` | Carrier frequency in Hz | 1000 | `--carrier-freq=5000` |
| **Message Amplitude** | `--message-amp=N` | Message amplitude | 1.0 | `--message-amp=1.5` |
| **Carrier Amplitude** | `--carrier-amp=N` | Carrier amplitude | 1.0 | `--carrier-amp=2.0` |
| **AM Modulation** | `--am-mod=N` | AM modulation index (0-1) | 0.5 | `--am-mod=0.8` |
| **FM Deviation** | `--fm-dev=N` | FM frequency deviation in Hz | 200 | `--fm-dev=400` |
| **SNR Range** | `--snr-range="N1,N2,N3"` | SNR range in dB | -5,0,5,10,15,20,25,30 | `--snr-range="0,10,20,30"` |
| **Trials** | `--trials=N` | Number of trials per SNR point | 100 | `--trials=500` |

### 📊 **Usage Examples**

#### **High-Frequency Analysis**
```bash
go run main.go results.go --message-freq=1000 --carrier-freq=10000 --snr-range="0,10,20,30"
```

#### **Low-SNR Analysis**
```bash
go run main.go results.go --snr-range="-20,-10,0,10" --trials=500
```

#### **High-Speed Sampling**
```bash
go run main.go results.go --sampling-rate=50000 --duration=0.05 --trials=200
```

#### **Custom Modulation Analysis**
```bash
go run main.go results.go --am-mod=0.8 --fm-dev=400 --snr-range="5,15,25" --trials=300
```

#### **Interactive Configuration**
```bash
go run main.go results.go custom
# Follow the prompts to configure each parameter
```

### 🧪 **Testing and Validation**

```bash
# Run tests
go test -v

# Run benchmarks
go test -bench=.
```

## 🆕 **New Features - Custom Parameter Support**

### **Interactive Mode**
The interactive mode allows step-by-step configuration of all simulation parameters:

```bash
go run main.go results.go custom
```

**Interactive prompts include:**
- Sampling Rate (Hz)
- Signal Duration (seconds)
- Message Frequency (Hz)
- Carrier Frequency (Hz)
- Message Amplitude
- Carrier Amplitude
- AM Modulation Index (0-1)
- FM Frequency Deviation (Hz)
- SNR Range (comma-separated values)
- Number of trials per SNR point

### **Command-Line Customization**
All parameters can be set via command-line arguments for automation and scripting:

```bash
# Example: High-frequency analysis with custom parameters
go run main.go results.go \
  --sampling-rate=20000 \
  --duration=0.2 \
  --message-freq=1000 \
  --carrier-freq=10000 \
  --am-mod=0.8 \
  --fm-dev=400 \
  --snr-range="0,10,20,30" \
  --trials=200
```

### **Parameter Validation**
- All inputs are validated with sensible defaults
- Invalid values fall back to defaults
- Error handling for malformed inputs
- Range checking for critical parameters

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

## 📊 **Comprehensive Usage Examples**

### **Example 1: Basic Analysis**
```bash
# Default parameters - good for general analysis
go run main.go results.go
```

### **Example 2: High-Frequency Analysis**
```bash
# Analyze high-frequency signals
go run main.go results.go \
  --message-freq=1000 \
  --carrier-freq=10000 \
  --sampling-rate=50000 \
  --snr-range="0,10,20,30"
```

### **Example 3: Low-SNR Analysis**
```bash
# Focus on low SNR performance
go run main.go results.go \
  --snr-range="-20,-10,0,10" \
  --trials=500
```

### **Example 4: Custom Modulation Analysis**
```bash
# Test different modulation parameters
go run main.go results.go \
  --am-mod=0.8 \
  --fm-dev=400 \
  --snr-range="5,15,25" \
  --trials=300
```

### **Example 5: Interactive Configuration**
```bash
# Step-by-step parameter configuration
go run main.go results.go custom
```

### **Example 6: High-Speed Sampling**
```bash
# High-speed sampling for detailed analysis
go run main.go results.go \
  --sampling-rate=100000 \
  --duration=0.05 \
  --trials=200
```

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
- **Default SNR Range:** -5 dB to 30 dB (8 points)
- **Default Trials:** 100 per SNR level
- **Customizable:** All parameters can be customized
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

## 🔧 **Advanced Customization**

### **Command-Line Parameter Reference**
All parameters can be customized via command-line arguments:

```bash
# Complete parameter list
go run main.go results.go \
  --sampling-rate=20000 \
  --duration=0.2 \
  --message-freq=100 \
  --carrier-freq=5000 \
  --message-amp=1.5 \
  --carrier-amp=2.0 \
  --am-mod=0.8 \
  --fm-dev=400 \
  --snr-range="0,10,20,30" \
  --trials=500
```

### **Interactive Mode Features**
The interactive mode provides:
- Step-by-step parameter configuration
- Input validation with defaults
- Configuration summary before execution
- Error handling for invalid inputs

### **Parameter Guidelines**

#### **Sampling Rate**
- **Minimum:** 2 × (Carrier Frequency + Message Frequency)
- **Recommended:** 2.5 × Carrier Frequency (minimum for proper demodulation)
- **Optimal:** 10 × Carrier Frequency
- **Example:** For 5 kHz carrier, use ≥ 12.5 kHz sampling
- **⚠️ Warning:** Insufficient sampling rate causes aliasing and incorrect AM demodulation

#### **SNR Range**
- **Low SNR:** -20 to 0 dB (noisy conditions)
- **Medium SNR:** 0 to 20 dB (typical conditions)
- **High SNR:** 20 to 40 dB (clean conditions)

#### **Modulation Index**
- **AM:** 0.0 to 1.0 (1.0 = 100% modulation)
- **FM:** Frequency deviation in Hz (typically 50-500 Hz)

### **Performance Optimization**
- **High Trials:** Use 500+ trials for statistical accuracy
- **Parallel Processing:** Automatically uses multiple CPU cores
- **Memory Management:** Efficient for large simulations

## 🚨 **Troubleshooting**

### **Common Issues and Solutions**

#### **1. Invalid Parameter Values**
```bash
# Problem: Invalid parameter causes fallback to defaults
# Solution: Check parameter ranges and formats
go run main.go results.go --am-mod=1.5  # Invalid: should be 0-1
go run main.go results.go --am-mod=0.8  # Correct: valid range
```

#### **2. SNR Range Format**
```bash
# Problem: Incorrect SNR range format
# Solution: Use comma-separated values in quotes
go run main.go results.go --snr-range=0,10,20        # Wrong
go run main.go results.go --snr-range="0,10,20"      # Correct
```

#### **3. Sampling Rate Issues**
```bash
# Problem: Aliasing due to low sampling rate causes AM output SNR = 0.00
# Solution: Ensure sampling rate ≥ 2.5 × carrier frequency
go run main.go results.go --carrier-freq=5000 --sampling-rate=10000  # Too low (2.0x ratio)
go run main.go results.go --carrier-freq=5000 --sampling-rate=15000  # Correct (3.0x ratio)

# The system will warn you about insufficient sampling rates:
# ⚠️ Warning: Sampling rate (10000 Hz) may be too low for carrier frequency (5000 Hz)
#    Recommended: Sampling rate ≥ 2.5 × Carrier frequency
```

#### **4. Memory Issues with Large Simulations**
```bash
# Problem: Out of memory with high trial counts
# Solution: Reduce trials or use shorter duration
go run main.go results.go --trials=10000 --duration=1.0  # May cause issues
go run main.go results.go --trials=1000 --duration=0.1   # More manageable
```

### **Performance Tips**

#### **Fast Analysis**
```bash
# Quick analysis with fewer trials
go run main.go results.go --trials=50 --snr-range="0,10,20"
```

#### **High-Accuracy Analysis**
```bash
# High-accuracy analysis with more trials
go run main.go results.go --trials=1000 --snr-range="-10,0,10,20,30"
```

#### **Interactive Mode for Complex Configurations**
```bash
# Use interactive mode for complex parameter combinations
go run main.go results.go custom
```

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

## 🚀 **Quick Reference**

### **Most Common Commands**
```bash
# Default simulation
go run main.go results.go

# Interactive configuration
go run main.go results.go custom

# Help and examples
go run main.go results.go help

# High-frequency analysis
go run main.go results.go --message-freq=1000 --carrier-freq=10000

# Low-SNR analysis
go run main.go results.go --snr-range="-20,-10,0,10" --trials=500
```

### **Parameter Quick Reference**
| Parameter | Command | Default | Range |
|-----------|---------|---------|-------|
| Sampling Rate | `--sampling-rate` | 10000 | > 2×(carrier+message) |
| Duration | `--duration` | 0.1 | 0.01-1.0 |
| Message Freq | `--message-freq` | 50 | 1-10000 |
| Carrier Freq | `--carrier-freq` | 1000 | 100-100000 |
| AM Mod Index | `--am-mod` | 0.5 | 0.0-1.0 |
| FM Deviation | `--fm-dev` | 200 | 50-1000 |
| Trials | `--trials` | 100 | 10-10000 |

**Note:** This implementation prioritizes educational clarity over production optimization. For professional applications, consider using established DSP libraries and more robust algorithms.