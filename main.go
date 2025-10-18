package main

import (
	"fmt"
	"math"
	"math/rand"
	"os"
	"time"

	"gonum.org/v1/gonum/stat/distuv"
	"gonum.org/v1/plot"
	"gonum.org/v1/plot/plotter"
	"gonum.org/v1/plot/plotutil"
	"gonum.org/v1/plot/vg"
)

// Signal parameters
type SignalParams struct {
	SamplingRate  float64 // Hz
	Duration      float64 // seconds
	MessageFreq   float64 // Hz
	CarrierFreq   float64 // Hz
	MessageAmp    float64
	CarrierAmp    float64
	ModulationIdx float64 // ka for AM, kf for FM
}

// Signal represents a digital signal
type Signal struct {
	Time   []float64
	Values []float64
}

// Phase 1: Signal Model Implementation

// generateTimeVector creates time samples for the given duration
func generateTimeVector(params SignalParams) []float64 {
	numSamples := int(params.SamplingRate * params.Duration)
	time := make([]float64, numSamples)
	dt := 1.0 / params.SamplingRate
	
	for i := 0; i < numSamples; i++ {
		time[i] = float64(i) * dt
	}
	return time
}

// generateBaseband creates a baseband sine wave: m(t) = Am * sin(2π * fm * t)
func generateBaseband(params SignalParams) Signal {
	time := generateTimeVector(params)
	values := make([]float64, len(time))
	
	for i, t := range time {
		values[i] = params.MessageAmp * math.Sin(2*math.Pi*params.MessageFreq*t)
	}
	
	return Signal{Time: time, Values: values}
}

// generateCarrier creates a carrier wave: c(t) = Ac * sin(2π * fc * t)
func generateCarrier(params SignalParams) Signal {
	time := generateTimeVector(params)
	values := make([]float64, len(time))
	
	for i, t := range time {
		values[i] = params.CarrierAmp * math.Sin(2*math.Pi*params.CarrierFreq*t)
	}
	
	return Signal{Time: time, Values: values}
}

// generateAM creates AM signal: s_AM(t) = Ac * (1 + ka * m(t)) * sin(2π * fc * t)
func generateAM(params SignalParams) Signal {
	time := generateTimeVector(params)
	values := make([]float64, len(time))
	
	for i, t := range time {
		message := params.MessageAmp * math.Sin(2*math.Pi*params.MessageFreq*t)
		modulated := params.CarrierAmp * (1 + params.ModulationIdx*message) * 
			math.Sin(2*math.Pi*params.CarrierFreq*t)
		values[i] = modulated
	}
	
	return Signal{Time: time, Values: values}
}

// generateFM creates FM signal: s_FM(t) = Ac * sin(2π * fc * t + kf * ∫m(t)dt)
func generateFM(params SignalParams) Signal {
	time := generateTimeVector(params)
	values := make([]float64, len(time))
	dt := 1.0 / params.SamplingRate
	
	// Compute the integral of m(t) using cumulative sum (trapezoidal integration)
	integral := 0.0
	
	for i, t := range time {
		message := params.MessageAmp * math.Sin(2*math.Pi*params.MessageFreq*t)
		
		// Update integral using trapezoidal rule
		if i > 0 {
			prevMessage := params.MessageAmp * math.Sin(2*math.Pi*params.MessageFreq*time[i-1])
			integral += (message + prevMessage) * dt / 2.0
		}
		
		// FM modulation
		instantaneousPhase := 2*math.Pi*params.CarrierFreq*t + params.ModulationIdx*integral
		values[i] = params.CarrierAmp * math.Sin(instantaneousPhase)
	}
	
	return Signal{Time: time, Values: values}
}

// Phase 2: Noise Model

// addAWGN adds Additive White Gaussian Noise to the signal
func addAWGN(signal Signal, snrDB float64) Signal {
	noisySignal := Signal{
		Time:   make([]float64, len(signal.Time)),
		Values: make([]float64, len(signal.Values)),
	}
	
	copy(noisySignal.Time, signal.Time)
	
	// Calculate signal power
	signalPower := 0.0
	for _, val := range signal.Values {
		signalPower += val * val
	}
	signalPower /= float64(len(signal.Values))
	
	// Convert SNR from dB to linear
	snrLinear := math.Pow(10, snrDB/10.0)
	
	// Calculate noise variance
	noiseVariance := signalPower / snrLinear
	noiseStdDev := math.Sqrt(noiseVariance)
	
	// Generate Gaussian noise
	normal := distuv.Normal{Mu: 0, Sigma: noiseStdDev}
	
	for i, val := range signal.Values {
		noise := normal.Rand()
		noisySignal.Values[i] = val + noise
	}
	
	return noisySignal
}

// Phase 3: Demodulation

// demodulateAM performs envelope detection for AM signals
func demodulateAM(signal Signal) Signal {
	demodulated := Signal{
		Time:   make([]float64, len(signal.Time)),
		Values: make([]float64, len(signal.Values)),
	}
	
	copy(demodulated.Time, signal.Time)
	
	// Envelope detection using rectification + low-pass filter (moving average)
	windowSize := 20 // Moving average window size
	
	// First, rectify the signal
	rectified := make([]float64, len(signal.Values))
	for i, val := range signal.Values {
		rectified[i] = math.Abs(val)
	}
	
	// Apply moving average filter
	for i := range signal.Values {
		sum := 0.0
		count := 0
		
		start := i - windowSize/2
		end := i + windowSize/2
		
		if start < 0 {
			start = 0
		}
		if end >= len(rectified) {
			end = len(rectified) - 1
		}
		
		for j := start; j <= end; j++ {
			sum += rectified[j]
			count++
		}
		
		demodulated.Values[i] = sum / float64(count)
	}
	
	return demodulated
}

// demodulateFM performs frequency discrimination for FM signals using quadrature detection
func demodulateFM(signal Signal, params SignalParams) Signal {
	demodulated := Signal{
		Time:   make([]float64, len(signal.Time)),
		Values: make([]float64, len(signal.Values)),
	}
	
	copy(demodulated.Time, signal.Time)
	dt := 1.0 / params.SamplingRate
	
	// Create quadrature (90-degree phase shifted) version of the signal
	// by delaying by one sample (approximate)
	quadSignal := make([]float64, len(signal.Values))
	for i := 1; i < len(signal.Values); i++ {
		quadSignal[i] = signal.Values[i-1]
	}
	quadSignal[0] = signal.Values[0]
	
	// Compute instantaneous frequency using quadrature detection
	for i := 1; i < len(signal.Values); i++ {
		// Current and previous I/Q samples
		I_curr := signal.Values[i]
		Q_curr := quadSignal[i]
		I_prev := signal.Values[i-1]
		Q_prev := quadSignal[i-1]
		
		// Calculate frequency using cross-product formula
		// f_inst = (1/2π) * (I * dQ/dt - Q * dI/dt) / (I² + Q²)
		dI := I_curr - I_prev
		dQ := Q_curr - Q_prev
		
		numerator := I_curr*dQ - Q_curr*dI
		denominator := I_curr*I_curr + Q_curr*Q_curr
		
		if denominator > 1e-10 { // Avoid division by zero
			instantFreq := numerator / (2 * math.Pi * dt * denominator)
			// Scale by modulation index to recover original message
			demodulated.Values[i] = instantFreq / params.ModulationIdx
		} else {
			demodulated.Values[i] = 0.0
		}
	}
	
	// Set first value
	demodulated.Values[0] = 0.0
	
	// Apply low-pass filtering to smooth the demodulated signal
	windowSize := 20
	filtered := make([]float64, len(demodulated.Values))
	
	for i := range demodulated.Values {
		sum := 0.0
		count := 0
		
		start := i - windowSize/2
		end := i + windowSize/2
		
		if start < 0 {
			start = 0
		}
		if end >= len(demodulated.Values) {
			end = len(demodulated.Values) - 1
		}
		
		for j := start; j <= end; j++ {
			sum += demodulated.Values[j]
			count++
		}
		
		filtered[i] = sum / float64(count)
	}
	
	copy(demodulated.Values, filtered)
	return demodulated
}

// Utility functions for analysis

// calculateSNR computes the SNR between original and noisy signals
func calculateSNR(original, noisy Signal) float64 {
	signalPower := 0.0
	noisePower := 0.0
	
	for i := range original.Values {
		signalPower += original.Values[i] * original.Values[i]
		noise := noisy.Values[i] - original.Values[i]
		noisePower += noise * noise
	}
	
	signalPower /= float64(len(original.Values))
	noisePower /= float64(len(original.Values))
	
	if noisePower == 0 {
		return math.Inf(1)
	}
	
	return 10 * math.Log10(signalPower/noisePower)
}

// plotSignals creates plots for signal comparison
func plotSignals(signals map[string]Signal, title, filename string) error {
	p := plot.New()
	p.Title.Text = title
	p.X.Label.Text = "Time (s)"
	p.Y.Label.Text = "Amplitude"
	
	colors := []string{"red", "blue", "green", "orange", "purple"}
	colorIdx := 0
	
	for name, signal := range signals {
		pts := make(plotter.XYs, len(signal.Time))
		for i := range signal.Time {
			pts[i].X = signal.Time[i]
			pts[i].Y = signal.Values[i]
		}
		
		line, err := plotter.NewLine(pts)
		if err != nil {
			return err
		}
		
		line.Color = plotutil.Color(colorIdx)
		p.Add(line)
		p.Legend.Add(name, line)
		
		colorIdx = (colorIdx + 1) % len(colors)
	}
	
	return p.Save(8*vg.Inch, 6*vg.Inch, filename)
}

// Monte Carlo simulation function with separate parameters for AM and FM
func monteCarloSimulationSeparate(amParams, fmParams SignalParams, snrRange []float64, numTrials int) ([]float64, []float64) {
	amSNRs := make([]float64, len(snrRange))
	fmSNRs := make([]float64, len(snrRange))
	
	for i, inputSNR := range snrRange {
		amSNRSum := 0.0
		fmSNRSum := 0.0
		
		for trial := 0; trial < numTrials; trial++ {
			// Generate original messages (use same base parameters)
			originalAM := generateBaseband(amParams)
			originalFM := generateBaseband(fmParams)
			
			// Generate AM and FM signals
			amSignal := generateAM(amParams)
			fmSignal := generateFM(fmParams)
			
			// Add noise
			noisyAM := addAWGN(amSignal, inputSNR)
			noisyFM := addAWGN(fmSignal, inputSNR)
			
			// Demodulate
			demodAM := demodulateAM(noisyAM)
			demodFM := demodulateFM(noisyFM, fmParams)
			
			// Calculate output SNRs
			amSNRSum += calculateSNR(originalAM, demodAM)
			fmSNRSum += calculateSNR(originalFM, demodFM)
		}
		
		amSNRs[i] = amSNRSum / float64(numTrials)
		fmSNRs[i] = fmSNRSum / float64(numTrials)
	}
	
	return amSNRs, fmSNRs
}

// Original Monte Carlo simulation function (kept for compatibility)
func monteCarloSimulation(params SignalParams, snrRange []float64, numTrials int) ([]float64, []float64) {
	return monteCarloSimulationSeparate(params, params, snrRange, numTrials)
}

func main() {
	// Check command line arguments for different modes
	if len(os.Args) > 1 {
		switch os.Args[1] {
		case "enhanced":
			runEnhanced()
			return
		case "phases56":
			RunCompletePhases5And6()
			return
		case "phase5":
			// Quick Phase 5 test
			runner := NewPhases5And6Runner()
			phase5Results, err := RunPhase5MonteCarloSimulation(runner.AMParams, runner.FMParams, runner.Config)
			if err != nil {
				fmt.Printf("Phase 5 test failed: %v\n", err)
				return
			}
			fmt.Printf("Phase 5 completed: %d total trials in %v\n", phase5Results.Stats.TotalTrials, phase5Results.Stats.Duration)
			return
		case "phase6":
			fmt.Println("Run 'go run . phases56' for complete Phase 5 & 6 execution")
			return
		}
	}
	
	// Set random seed for reproducibility
	rand.Seed(time.Now().UnixNano())
	
	// Define signal parameters
	// Using different modulation indices for AM and FM
	params := SignalParams{
		SamplingRate:  10000, // 10 kHz
		Duration:      0.1,   // 100 ms
		MessageFreq:   50,    // 50 Hz (lower for better FM performance)
		CarrierFreq:   1000,  // 1 kHz
		MessageAmp:    1.0,
		CarrierAmp:    1.0,
		ModulationIdx: 0.5,   // 50% modulation for AM
	}
	
	// FM parameters with higher frequency deviation
	fmParams := SignalParams{
		SamplingRate:  10000, // 10 kHz
		Duration:      0.1,   // 100 ms
		MessageFreq:   50,    // 50 Hz
		CarrierFreq:   1000,  // 1 kHz
		MessageAmp:    1.0,
		CarrierAmp:    1.0,
		ModulationIdx: 200,   // Higher frequency deviation for FM
	}
	
	fmt.Println("AM/FM Performance Analysis - Monte Carlo Simulation")
	fmt.Println("================================================")
	
	// Phase 1: Generate and visualize basic signals
	fmt.Println("Phase 1: Generating basic signals...")
	
	baseband := generateBaseband(params)
	carrier := generateCarrier(params)
	amSignal := generateAM(params)
	fmSignal := generateFM(fmParams)
	
	// Create plots for basic signals
	basicSignals := map[string]Signal{
		"Baseband": baseband,
		"Carrier":  carrier,
	}
	
	modulatedSignals := map[string]Signal{
		"AM Signal": amSignal,
		"FM Signal": fmSignal,
	}
	
	if err := plotSignals(basicSignals, "Basic Signals", "basic_signals.png"); err != nil {
		fmt.Printf("Error creating basic signals plot: %v\n", err)
	}
	
	if err := plotSignals(modulatedSignals, "Modulated Signals", "modulated_signals.png"); err != nil {
		fmt.Printf("Error creating modulated signals plot: %v\n", err)
	}
	
	// Phase 2: Add noise and demonstrate
	fmt.Println("Phase 2: Adding noise...")
	
	testSNR := 10.0 // 10 dB
	noisyAM := addAWGN(amSignal, testSNR)
	noisyFM := addAWGN(fmSignal, testSNR)
	
	noisySignals := map[string]Signal{
		"Clean AM":  amSignal,
		"Noisy AM":  noisyAM,
		"Clean FM":  fmSignal,
		"Noisy FM":  noisyFM,
	}
	
	if err := plotSignals(noisySignals, "Clean vs Noisy Signals", "noisy_signals.png"); err != nil {
		fmt.Printf("Error creating noisy signals plot: %v\n", err)
	}
	
	// Phase 3: Demodulation
	fmt.Println("Phase 3: Demodulating signals...")
	
	demodAM := demodulateAM(noisyAM)
	demodFM := demodulateFM(noisyFM, fmParams)
	
	demodSignals := map[string]Signal{
		"Original":     baseband,
		"Demod AM":     demodAM,
		"Demod FM":     demodFM,
	}
	
	if err := plotSignals(demodSignals, "Demodulated Signals", "demodulated_signals.png"); err != nil {
		fmt.Printf("Error creating demodulated signals plot: %v\n", err)
	}
	
	// Monte Carlo Analysis
	fmt.Println("Running Monte Carlo simulation...")
	
	snrRange := []float64{-5, 0, 5, 10, 15, 20, 25, 30}
	numTrials := 100
	
	amPerformance, fmPerformance := monteCarloSimulationSeparate(params, fmParams, snrRange, numTrials)
	
	// Display results
	fmt.Println("\nSNR Performance Comparison:")
	fmt.Println("Input SNR (dB) | AM Output SNR (dB) | FM Output SNR (dB)")
	fmt.Println("---------------|-------------------|------------------")
	
	for i, inputSNR := range snrRange {
		fmt.Printf("%13.1f | %17.2f | %17.2f\n", inputSNR, amPerformance[i], fmPerformance[i])
	}
	
	// Create SNR comparison plot
	snrData := make(map[string]Signal)
	snrData["AM Performance"] = Signal{Time: snrRange, Values: amPerformance}
	snrData["FM Performance"] = Signal{Time: snrRange, Values: fmPerformance}
	
	if err := plotSignals(snrData, "SNR Performance Comparison", "snr_comparison.png"); err != nil {
		fmt.Printf("Error creating SNR comparison plot: %v\n", err)
	}
	
	// Save results to CSV
	if err := saveResultsCSV(snrRange, amPerformance, fmPerformance, "snr_results.csv"); err != nil {
		fmt.Printf("Error saving CSV results: %v\n", err)
	}
	
	// Save sample signals to CSV
	if err := saveSignalCSV(baseband, "baseband_signal.csv"); err != nil {
		fmt.Printf("Error saving baseband signal: %v\n", err)
	}
	
	fmt.Println("\nAnalysis complete! Check the generated PNG files for visualizations and CSV files for data.")
	fmt.Println("Note: The current FM demodulator implementation may need further optimization for optimal performance.")
}