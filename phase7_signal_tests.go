package main

import (
	"math"
	"testing"
)

// TestSignalGeneration contains comprehensive tests for AM/FM signal generation
func TestSignalGeneration(t *testing.T) {
	// Standard test parameters
	params := SignalParams{
		SamplingRate:  8000,  // 8 kHz
		Duration:      0.1,   // 100 ms
		MessageFreq:   100,   // 100 Hz
		CarrierFreq:   1000,  // 1 kHz
		MessageAmp:    1.0,
		CarrierAmp:    2.0,
		ModulationIdx: 0.5,
	}

	t.Run("Baseband Signal Generation", func(t *testing.T) {
		signal := generateBaseband(params)
		
		// Test basic properties
		expectedSamples := int(params.SamplingRate * params.Duration)
		if len(signal.Values) != expectedSamples {
			t.Errorf("Expected %d samples, got %d", expectedSamples, len(signal.Values))
		}

		// Test amplitude bounds
		maxAmp, minAmp := findMinMax(signal.Values)
		expectedMaxAmp := params.MessageAmp
		expectedMinAmp := -params.MessageAmp

		if math.Abs(maxAmp-expectedMaxAmp) > 0.1 {
			t.Errorf("Max amplitude: expected ~%.2f, got %.2f", expectedMaxAmp, maxAmp)
		}
		if math.Abs(minAmp-expectedMinAmp) > 0.1 {
			t.Errorf("Min amplitude: expected ~%.2f, got %.2f", expectedMinAmp, minAmp)
		}

		// Test frequency content using zero-crossing analysis
		zeroCrossings := countZeroCrossings(signal.Values, 1.0/params.SamplingRate)
		expectedCrossings := 2.0 * params.MessageFreq * params.Duration
		tolerance := expectedCrossings * 0.1 // 10% tolerance

		if math.Abs(float64(zeroCrossings)-expectedCrossings) > tolerance {
			t.Errorf("Zero crossings: expected ~%.0f, got %d", expectedCrossings, zeroCrossings)
		}
	})

	t.Run("AM Signal Generation", func(t *testing.T) {
		amSignal := generateAM(params)
		
		// Test envelope characteristics
		envelope := extractEnvelope(amSignal.Values)
		
		// Check modulation depth
		maxEnv, minEnv := findMinMax(envelope)
		modulationDepth := (maxEnv - minEnv) / (maxEnv + minEnv)
		expectedDepth := params.ModulationIdx
		
		if math.Abs(modulationDepth-expectedDepth) > 0.1 {
			t.Errorf("Modulation depth: expected %.2f, got %.2f", expectedDepth, modulationDepth)
		}

		// Test carrier frequency using spectral analysis
		carrierPower := estimateCarrierPower(amSignal.Values, params.CarrierFreq, params.SamplingRate)
		if carrierPower < 0.5 { // Should have significant power at carrier
			t.Errorf("Insufficient carrier power: %.3f", carrierPower)
		}

		// Test for proper AM modulation (DSB-LC)
		sidebandPower := estimateSidebandPower(amSignal.Values, params.CarrierFreq, 
			params.MessageFreq, params.SamplingRate)
		if sidebandPower < 0.1 { // Should have sideband energy
			t.Errorf("Insufficient sideband power: %.3f", sidebandPower)
		}
	})

	t.Run("FM Signal Generation", func(t *testing.T) {
		fmParams := params
		fmParams.ModulationIdx = 100 // Frequency deviation in Hz
		
		fmSignal := generateFM(fmParams)
		
		// Test constant envelope property
		envelope := extractEnvelope(fmSignal.Values)
		envMean := calculateMean(envelope)
		envStdDev := calculateStdDev(envelope, envMean)
		
		// FM should have nearly constant envelope
		coefficientOfVariation := envStdDev / envMean
		if coefficientOfVariation > 0.1 { // Should be < 10%
			t.Errorf("FM envelope not constant: CV = %.3f", coefficientOfVariation)
		}

		// Test instantaneous frequency deviation
		instFreq := estimateInstantaneousFrequency(fmSignal.Values, params.SamplingRate)
		freqDeviation := calculateFrequencyDeviation(instFreq, params.CarrierFreq)
		
		// Should be within reasonable bounds of expected deviation
		if freqDeviation > fmParams.ModulationIdx*2 {
			t.Errorf("Excessive frequency deviation: %.1f Hz", freqDeviation)
		}

		// Test spectral characteristics - FM should have broader spectrum than AM
		fmBandwidth := estimateBandwidth(fmSignal.Values, params.SamplingRate)
		amSignal := generateAM(params)
		amBandwidth := estimateBandwidth(amSignal.Values, params.SamplingRate)
		
		if fmBandwidth <= amBandwidth {
			t.Errorf("FM bandwidth (%.1f) should exceed AM bandwidth (%.1f)", 
				fmBandwidth, amBandwidth)
		}
	})

	t.Run("Carrier Signal Generation", func(t *testing.T) {
		carrier := generateCarrier(params)
		
		// Test amplitude
		maxAmp, minAmp := findMinMax(carrier.Values)
		expectedMaxAmp := params.CarrierAmp
		expectedMinAmp := -params.CarrierAmp

		if math.Abs(maxAmp-expectedMaxAmp) > 0.1 {
			t.Errorf("Carrier max amplitude: expected %.2f, got %.2f", expectedMaxAmp, maxAmp)
		}
		if math.Abs(minAmp-expectedMinAmp) > 0.1 {
			t.Errorf("Carrier min amplitude: expected %.2f, got %.2f", expectedMinAmp, minAmp)
		}

		// Test frequency using zero-crossing analysis
		zeroCrossings := countZeroCrossings(carrier.Values, 1.0/params.SamplingRate)
		expectedCrossings := 2.0 * params.CarrierFreq * params.Duration
		tolerance := expectedCrossings * 0.05 // 5% tolerance for carrier

		if math.Abs(float64(zeroCrossings)-expectedCrossings) > tolerance {
			t.Errorf("Carrier zero crossings: expected ~%.0f, got %d", expectedCrossings, zeroCrossings)
		}
	})
}

// Helper functions for signal analysis

// findMinMax returns the minimum and maximum values in a slice
func findMinMax(values []float64) (max, min float64) {
	if len(values) == 0 {
		return 0, 0
	}
	
	max, min = values[0], values[0]
	for _, v := range values {
		if v > max {
			max = v
		}
		if v < min {
			min = v
		}
	}
	return max, min
}

// countZeroCrossings counts the number of zero crossings in a signal
func countZeroCrossings(values []float64, dt float64) int {
	if len(values) < 2 {
		return 0
	}
	
	crossings := 0
	for i := 1; i < len(values); i++ {
		if (values[i-1] >= 0 && values[i] < 0) || (values[i-1] < 0 && values[i] >= 0) {
			crossings++
		}
	}
	return crossings
}

// extractEnvelope extracts the envelope of a signal using Hilbert transform approximation
func extractEnvelope(values []float64) []float64 {
	envelope := make([]float64, len(values))
	
	// Simple envelope detection using rectification + low-pass filter
	windowSize := len(values) / 100 // 1% of signal length
	if windowSize < 5 {
		windowSize = 5
	}
	
	// Rectify
	rectified := make([]float64, len(values))
	for i, v := range values {
		rectified[i] = math.Abs(v)
	}
	
	// Low-pass filter (moving average)
	for i := range values {
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
		
		envelope[i] = sum / float64(count)
	}
	
	return envelope
}

// estimateCarrierPower estimates power at the carrier frequency using DFT
func estimateCarrierPower(values []float64, carrierFreq, samplingRate float64) float64 {
	N := len(values)
	carrierBin := int(carrierFreq * float64(N) / samplingRate)
	
	// Simple DFT calculation at carrier frequency bin
	real, imag := 0.0, 0.0
	for n, x := range values {
		angle := 2.0 * math.Pi * float64(carrierBin) * float64(n) / float64(N)
		real += x * math.Cos(angle)
		imag += x * math.Sin(angle)
	}
	
	magnitude := math.Sqrt(real*real + imag*imag) / float64(N)
	return magnitude
}

// estimateSidebandPower estimates power in the sideband regions
func estimateSidebandPower(values []float64, carrierFreq, messageFreq, samplingRate float64) float64 {
	// Check power at carrier ± message frequency
	upperSideband := estimateCarrierPower(values, carrierFreq+messageFreq, samplingRate)
	lowerSideband := estimateCarrierPower(values, carrierFreq-messageFreq, samplingRate)
	
	return upperSideband + lowerSideband
}

// estimateInstantaneousFrequency estimates instantaneous frequency using phase derivative
func estimateInstantaneousFrequency(values []float64, samplingRate float64) []float64 {
	N := len(values)
	instFreq := make([]float64, N)
	dt := 1.0 / samplingRate
	
	// Simple frequency estimation using zero-crossing rate in sliding window
	windowSize := int(samplingRate * 0.01) // 10ms window
	if windowSize < 10 {
		windowSize = 10
	}
	
	for i := windowSize; i < N-windowSize; i++ {
		window := values[i-windowSize/2 : i+windowSize/2]
		crossings := countZeroCrossings(window, dt)
		instFreq[i] = float64(crossings) / (2.0 * float64(windowSize) * dt)
	}
	
	// Fill edges
	for i := 0; i < windowSize; i++ {
		instFreq[i] = instFreq[windowSize]
	}
	for i := N - windowSize; i < N; i++ {
		instFreq[i] = instFreq[N-windowSize-1]
	}
	
	return instFreq
}

// calculateFrequencyDeviation calculates the maximum frequency deviation
func calculateFrequencyDeviation(instFreq []float64, carrierFreq float64) float64 {
	maxDev := 0.0
	for _, freq := range instFreq {
		dev := math.Abs(freq - carrierFreq)
		if dev > maxDev {
			maxDev = dev
		}
	}
	return maxDev
}

// estimateBandwidth estimates the 99% power bandwidth of a signal
func estimateBandwidth(values []float64, samplingRate float64) float64 {
	N := len(values)
	
	// Compute power spectral density using FFT approximation
	powerSpectrum := make([]float64, N/2)
	
	// Simple DFT-based power spectrum estimation
	for k := 0; k < N/2; k++ {
		real, imag := 0.0, 0.0
		for n, x := range values {
			angle := 2.0 * math.Pi * float64(k) * float64(n) / float64(N)
			real += x * math.Cos(angle)
			imag += x * math.Sin(angle)
		}
		powerSpectrum[k] = (real*real + imag*imag) / float64(N*N)
	}
	
	// Find 99% power bandwidth
	totalPower := 0.0
	for _, power := range powerSpectrum {
		totalPower += power
	}
	
	targetPower := totalPower * 0.99
	cumulativePower := 0.0
	
	for k, power := range powerSpectrum {
		cumulativePower += power
		if cumulativePower >= targetPower {
			return float64(k) * samplingRate / float64(N)
		}
	}
	
	return samplingRate / 2.0 // Nyquist frequency as fallback
}

// BenchmarkSignalGeneration benchmarks signal generation performance
func BenchmarkSignalGeneration(b *testing.B) {
	params := SignalParams{
		SamplingRate:  10000,
		Duration:      0.1,
		MessageFreq:   50,
		CarrierFreq:   1000,
		MessageAmp:    1.0,
		CarrierAmp:    1.0,
		ModulationIdx: 0.5,
	}

	b.Run("Baseband", func(b *testing.B) {
		for i := 0; i < b.N; i++ {
			_ = generateBaseband(params)
		}
	})

	b.Run("AM", func(b *testing.B) {
		for i := 0; i < b.N; i++ {
			_ = generateAM(params)
		}
	})

	b.Run("FM", func(b *testing.B) {
		fmParams := params
		fmParams.ModulationIdx = 100
		for i := 0; i < b.N; i++ {
			_ = generateFM(fmParams)
		}
	})

	b.Run("Carrier", func(b *testing.B) {
		for i := 0; i < b.N; i++ {
			_ = generateCarrier(params)
		}
	})
}

// TestSignalGenerationEdgeCases tests edge cases and error conditions
func TestSignalGenerationEdgeCases(t *testing.T) {
	t.Run("Zero Duration", func(t *testing.T) {
		params := SignalParams{
			SamplingRate: 1000,
			Duration:     0,
			MessageFreq:  10,
			CarrierFreq:  100,
		}
		
		signal := generateBaseband(params)
		if len(signal.Values) != 0 {
			t.Errorf("Expected 0 samples for zero duration, got %d", len(signal.Values))
		}
	})

	t.Run("Very High Frequency", func(t *testing.T) {
		params := SignalParams{
			SamplingRate: 1000,
			Duration:     0.1,
			MessageFreq:  400, // Near Nyquist
			CarrierFreq:  450, // Above Nyquist
		}
		
		// Should not crash or produce invalid results
		signal := generateAM(params)
		if len(signal.Values) == 0 {
			t.Error("Signal generation failed for high frequencies")
		}
		
		// Check for reasonable values (no NaN or Inf)
		for i, v := range signal.Values {
			if math.IsNaN(v) || math.IsInf(v, 0) {
				t.Errorf("Invalid value at index %d: %v", i, v)
				break
			}
		}
	})

	t.Run("100% AM Modulation", func(t *testing.T) {
		params := SignalParams{
			SamplingRate:  8000,
			Duration:      0.1,
			MessageFreq:   50,
			CarrierFreq:   1000,
			MessageAmp:    1.0,
			CarrierAmp:    1.0,
			ModulationIdx: 1.0, // 100% modulation
		}
		
		amSignal := generateAM(params)
		envelope := extractEnvelope(amSignal.Values)
		
		// Should reach zero but not go negative significantly
		minEnv, _ := findMinMax(envelope)
		if minEnv < -0.1 {
			t.Errorf("Over-modulation detected: min envelope = %.3f", minEnv)
		}
	})
}