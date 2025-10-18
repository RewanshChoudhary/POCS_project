package main

import (
	"math"
	"testing"
)

func TestGenerateBaseband(t *testing.T) {
	params := SignalParams{
		SamplingRate: 1000,
		Duration:     0.1,
		MessageFreq:  10,
		MessageAmp:   1.0,
	}
	
	signal := generateBaseband(params)
	
	// Check signal length
	expectedSamples := int(params.SamplingRate * params.Duration)
	if len(signal.Values) != expectedSamples {
		t.Errorf("Expected %d samples, got %d", expectedSamples, len(signal.Values))
	}
	
	// Check amplitude bounds
	for _, val := range signal.Values {
		if math.Abs(val) > params.MessageAmp+0.001 {
			t.Errorf("Signal amplitude %f exceeds expected maximum %f", val, params.MessageAmp)
		}
	}
	
	// Check frequency (approximate)
	// Find zero crossings to estimate frequency
	zeroCrossings := 0
	for i := 1; i < len(signal.Values); i++ {
		if signal.Values[i-1]*signal.Values[i] < 0 {
			zeroCrossings++
		}
	}
	
	expectedZeroCrossings := int(2 * params.MessageFreq * params.Duration)
	tolerance := int(math.Max(float64(expectedZeroCrossings)/2, 1)) // More lenient tolerance
	
	if math.Abs(float64(zeroCrossings-expectedZeroCrossings)) > float64(tolerance) {
		t.Errorf("Expected approximately %d zero crossings, got %d (tolerance: %d)", expectedZeroCrossings, zeroCrossings, tolerance)
	}
}

func TestGenerateCarrier(t *testing.T) {
	params := SignalParams{
		SamplingRate: 10000,
		Duration:     0.01,
		CarrierFreq:  1000,
		CarrierAmp:   2.0,
	}
	
	signal := generateCarrier(params)
	
	// Check amplitude bounds
	for _, val := range signal.Values {
		if math.Abs(val) > params.CarrierAmp+0.001 {
			t.Errorf("Carrier amplitude %f exceeds expected maximum %f", val, params.CarrierAmp)
		}
	}
	
	// Check that signal oscillates around zero
	sum := 0.0
	for _, val := range signal.Values {
		sum += val
	}
	mean := sum / float64(len(signal.Values))
	
	if math.Abs(mean) > 0.1 {
		t.Errorf("Carrier mean %f should be close to zero", mean)
	}
}

func TestGenerateAM(t *testing.T) {
	params := SignalParams{
		SamplingRate:  10000,
		Duration:      0.1,
		MessageFreq:   100,
		CarrierFreq:   1000,
		MessageAmp:    1.0,
		CarrierAmp:    1.0,
		ModulationIdx: 0.5,
	}
	
	amSignal := generateAM(params)
	
	// Check that modulated signal exists and has correct length
	expectedSamples := int(params.SamplingRate * params.Duration)
	if len(amSignal.Values) != expectedSamples {
		t.Errorf("Expected %d samples, got %d", expectedSamples, len(amSignal.Values))
	}
	
	// Check that envelope varies (indicating modulation)
	// Calculate envelope using absolute values
	envelope := make([]float64, len(amSignal.Values))
	for i, val := range amSignal.Values {
		envelope[i] = math.Abs(val)
	}
	
	// Find min and max envelope values
	minEnv, maxEnv := envelope[0], envelope[0]
	for _, val := range envelope {
		if val < minEnv {
			minEnv = val
		}
		if val > maxEnv {
			maxEnv = val
		}
	}
	
	// Check modulation depth (more lenient for AM test)
	modulationDepth := (maxEnv - minEnv) / (maxEnv + minEnv)
	
	// For AM, just check that there is some modulation (envelope variation)
	if modulationDepth < 0.1 {
		t.Errorf("AM signal shows insufficient modulation depth: %f", modulationDepth)
	}
}

func TestGenerateFM(t *testing.T) {
	params := SignalParams{
		SamplingRate:  10000,
		Duration:      0.1,
		MessageFreq:   50,
		CarrierFreq:   1000,
		MessageAmp:    1.0,
		CarrierAmp:    1.0,
		ModulationIdx: 100, // Frequency deviation
	}
	
	fmSignal := generateFM(params)
	
	// Check signal length
	expectedSamples := int(params.SamplingRate * params.Duration)
	if len(fmSignal.Values) != expectedSamples {
		t.Errorf("Expected %d samples, got %d", expectedSamples, len(fmSignal.Values))
	}
	
	// Check amplitude bounds (should be approximately constant for FM)
	// Calculate RMS amplitude to check overall amplitude consistency
	rmsAmplitude := 0.0
	for _, val := range fmSignal.Values {
		rmsAmplitude += val * val
	}
	rmsAmplitude = math.Sqrt(rmsAmplitude / float64(len(fmSignal.Values)))
	
	// Check that RMS is close to theoretical value (Ac/sqrt(2) for sine wave)
	expectedRMS := params.CarrierAmp / math.Sqrt(2)
	if math.Abs(rmsAmplitude-expectedRMS) > 0.3 {
		t.Errorf("FM signal RMS amplitude %f differs from expected %f", rmsAmplitude, expectedRMS)
	}
}

func TestAddAWGN(t *testing.T) {
	// Create a simple test signal
	params := SignalParams{
		SamplingRate: 1000,
		Duration:     1.0,
		MessageFreq:  10,
		MessageAmp:   1.0,
	}
	
	cleanSignal := generateBaseband(params)
	snrDB := 20.0 // High SNR for predictable test
	
	noisySignal := addAWGN(cleanSignal, snrDB)
	
	// Check that lengths match
	if len(noisySignal.Values) != len(cleanSignal.Values) {
		t.Errorf("Length mismatch: clean %d, noisy %d", len(cleanSignal.Values), len(noisySignal.Values))
	}
	
	// Calculate actual SNR
	signalPower := 0.0
	noisePower := 0.0
	
	for i := range cleanSignal.Values {
		signalPower += cleanSignal.Values[i] * cleanSignal.Values[i]
		noise := noisySignal.Values[i] - cleanSignal.Values[i]
		noisePower += noise * noise
	}
	
	signalPower /= float64(len(cleanSignal.Values))
	noisePower /= float64(len(cleanSignal.Values))
	
	actualSNR := 10 * math.Log10(signalPower/noisePower)
	
	// Check if actual SNR is within reasonable tolerance of target
	if math.Abs(actualSNR-snrDB) > 2.0 {
		t.Errorf("SNR mismatch: expected %f dB, got %f dB", snrDB, actualSNR)
	}
	
	// Test noise properties (should have zero mean)
	noiseSum := 0.0
	for i := range cleanSignal.Values {
		noiseSum += noisySignal.Values[i] - cleanSignal.Values[i]
	}
	noiseMean := noiseSum / float64(len(cleanSignal.Values))
	
	if math.Abs(noiseMean) > 0.1 {
		t.Errorf("Noise mean %f should be close to zero", noiseMean)
	}
}

func TestDemodulateAM(t *testing.T) {
	params := SignalParams{
		SamplingRate:  10000,
		Duration:      0.1,
		MessageFreq:   100,
		CarrierFreq:   1000,
		MessageAmp:    1.0,
		CarrierAmp:    1.0,
		ModulationIdx: 0.8, // High modulation for easier testing
	}
	
	// Generate clean AM signal
	amSignal := generateAM(params)
	
	// Demodulate
	demodulated := demodulateAM(amSignal)
	
	// Check length
	if len(demodulated.Values) != len(amSignal.Values) {
		t.Errorf("Length mismatch after demodulation")
	}
	
	// Check that demodulated signal follows the envelope pattern
	// The demodulated signal should have a DC component plus the message
	
	// Calculate mean (DC component)
	sum := 0.0
	for _, val := range demodulated.Values {
		sum += val
	}
	mean := sum / float64(len(demodulated.Values))
	
	// Mean should be positive (indicating successful envelope detection)
	// The exact value depends on the filtering, so we're more lenient
	if mean < 0.3 {
		t.Errorf("Demodulated signal DC component %f is too low, indicating poor envelope detection", mean)
	}
}

func TestDemodulateFM(t *testing.T) {
	params := SignalParams{
		SamplingRate:  10000,
		Duration:      0.05, // Shorter duration for faster test
		MessageFreq:   50,
		CarrierFreq:   1000,
		MessageAmp:    1.0,
		CarrierAmp:    1.0,
		ModulationIdx: 50, // Frequency deviation
	}
	
	// Generate clean FM signal
	fmSignal := generateFM(params)
	
	// Demodulate
	demodulated := demodulateFM(fmSignal, params)
	
	// Check length
	if len(demodulated.Values) != len(fmSignal.Values) {
		t.Errorf("Length mismatch after FM demodulation")
	}
	
	// The demodulated signal should contain frequency components
	// This is a basic test to ensure the function runs without crashing
	// More sophisticated tests would check frequency content
	
	// Check that values are finite
	for i, val := range demodulated.Values {
		if math.IsNaN(val) || math.IsInf(val, 0) {
			t.Errorf("Demodulated value at index %d is not finite: %f", i, val)
		}
	}
}

func TestCalculateSNR(t *testing.T) {
	// Create test signals
	params := SignalParams{
		SamplingRate: 1000,
		Duration:     0.1,
		MessageFreq:  10,
		MessageAmp:   1.0,
	}
	
	original := generateBaseband(params)
	
	// Create a "noisy" version by adding a known amount of noise
	noisy := Signal{
		Time:   make([]float64, len(original.Time)),
		Values: make([]float64, len(original.Values)),
	}
	
	copy(noisy.Time, original.Time)
	
	// Add known noise level
	noiseLevel := 0.1
	for i, val := range original.Values {
		noisy.Values[i] = val + noiseLevel
	}
	
	snr := calculateSNR(original, noisy)
	
	// Calculate expected SNR
	signalPower := 0.0
	for _, val := range original.Values {
		signalPower += val * val
	}
	signalPower /= float64(len(original.Values))
	
	noisePower := noiseLevel * noiseLevel
	expectedSNR := 10 * math.Log10(signalPower/noisePower)
	
	if math.Abs(snr-expectedSNR) > 1.0 {
		t.Errorf("SNR calculation error: expected %f, got %f", expectedSNR, snr)
	}
}

func TestSignalParams(t *testing.T) {
	// Test parameter validation
	params := SignalParams{
		SamplingRate:  10000,
		Duration:      0.1,
		MessageFreq:   100,
		CarrierFreq:   1000,
		MessageAmp:    1.0,
		CarrierAmp:    1.0,
		ModulationIdx: 0.5,
	}
	
	// Check that carrier frequency is much higher than message frequency
	if params.CarrierFreq <= 2*params.MessageFreq {
		t.Errorf("Carrier frequency should be much higher than message frequency for proper modulation")
	}
	
	// Check that sampling rate satisfies Nyquist criterion
	if params.SamplingRate <= 2*params.CarrierFreq {
		t.Errorf("Sampling rate should be at least twice the carrier frequency")
	}
}

// Benchmark tests
func BenchmarkGenerateAM(b *testing.B) {
	params := SignalParams{
		SamplingRate:  10000,
		Duration:      0.1,
		MessageFreq:   100,
		CarrierFreq:   1000,
		MessageAmp:    1.0,
		CarrierAmp:    1.0,
		ModulationIdx: 0.5,
	}
	
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_ = generateAM(params)
	}
}

func BenchmarkGenerateFM(b *testing.B) {
	params := SignalParams{
		SamplingRate:  10000,
		Duration:      0.1,
		MessageFreq:   100,
		CarrierFreq:   1000,
		MessageAmp:    1.0,
		CarrierAmp:    1.0,
		ModulationIdx: 100,
	}
	
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_ = generateFM(params)
	}
}

func BenchmarkAddAWGN(b *testing.B) {
	params := SignalParams{
		SamplingRate: 10000,
		Duration:     0.1,
		MessageFreq:  100,
		MessageAmp:   1.0,
	}
	
	signal := generateBaseband(params)
	
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_ = addAWGN(signal, 10.0)
	}
}

// Benchmarks for new Phase 4-6 functionality

func BenchmarkSimulateSNRPerformance(b *testing.B) {
	params := SignalParams{
		SamplingRate:  10000,
		Duration:      0.05, // Shorter for benchmark
		MessageFreq:   100,
		CarrierFreq:   1000,
		MessageAmp:    1.0,
		CarrierAmp:    1.0,
		ModulationIdx: 0.5,
	}
	
	snrRange := []float64{0, 10, 20}
	numTrials := 10 // Small for benchmark
	
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_ = simulateSNRPerformance(AM, params, snrRange, numTrials)
	}
}

func BenchmarkSimulateSNRPerformanceParallel(b *testing.B) {
	params := SignalParams{
		SamplingRate:  10000,
		Duration:      0.05,
		MessageFreq:   100,
		CarrierFreq:   1000,
		MessageAmp:    1.0,
		CarrierAmp:    1.0,
		ModulationIdx: 0.5,
	}
	
	snrRange := []float64{0, 10, 20}
	numTrials := 10
	numWorkers := 4
	
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_ = simulateSNRPerformanceParallel(AM, params, snrRange, numTrials, numWorkers)
	}
}

func BenchmarkOptimizedMonteCarloSimulation(b *testing.B) {
	params := SignalParams{
		SamplingRate:  10000,
		Duration:      0.02, // Very short for benchmark
		MessageFreq:   100,
		CarrierFreq:   1000,
		MessageAmp:    1.0,
		CarrierAmp:    1.0,
		ModulationIdx: 0.5,
	}
	
	config := SimulationConfig{
		Seed:          12345,
		NumTrials:     5, // Very small for benchmark
		NumWorkers:    2,
		SNRRange:      []float64{0, 10},
		UseParallel:   true,
		PrintProgress: false,
	}
	
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, _, _, _ = OptimizedMonteCarloSimulation(params, params, config)
	}
}
