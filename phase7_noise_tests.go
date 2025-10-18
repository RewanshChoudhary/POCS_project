package main

import (
	"math"
	"math/rand"
	"testing"
	"time"
)

// TestAWGNNoise contains comprehensive tests for AWGN noise generation and properties
func TestAWGNNoise(t *testing.T) {
	// Test signal for noise addition
	params := SignalParams{
		SamplingRate: 8000,
		Duration:     0.5, // Longer duration for better statistics
		MessageFreq:  100,
		CarrierFreq:  1000,
		MessageAmp:   1.0,
		CarrierAmp:   2.0,
	}

	cleanSignal := generateCarrier(params)

	t.Run("AWGN Mean Test", func(t *testing.T) {
		testSNRs := []float64{0, 10, 20, 30}
		
		for _, snr := range testSNRs {
			noisySignal := addAWGN(cleanSignal, snr)
			
			// Extract noise component
			noise := make([]float64, len(cleanSignal.Values))
			for i := range noise {
				noise[i] = noisySignal.Values[i] - cleanSignal.Values[i]
			}
			
			// Calculate mean of noise
			noiseMean := calculateMean(noise)
			
			// AWGN should have mean ≈ 0
			tolerance := 0.1 // Allow small deviation due to finite samples
			if math.Abs(noiseMean) > tolerance {
				t.Errorf("SNR %.1f dB: Noise mean = %.4f, expected ≈ 0 (tolerance ±%.2f)", 
					snr, noiseMean, tolerance)
			}
		}
	})

	t.Run("AWGN Standard Deviation Test", func(t *testing.T) {
		testSNRs := []float64{0, 10, 20, 30}
		
		for _, snr := range testSNRs {
			noisySignal := addAWGN(cleanSignal, snr)
			
			// Calculate theoretical noise standard deviation
			signalPower := calculateSignalPower(cleanSignal.Values)
			snrLinear := math.Pow(10, snr/10.0)
			noiseVariance := signalPower / snrLinear
			expectedStdDev := math.Sqrt(noiseVariance)
			
			// Extract actual noise
			noise := make([]float64, len(cleanSignal.Values))
			for i := range noise {
				noise[i] = noisySignal.Values[i] - cleanSignal.Values[i]
			}
			
			// Calculate actual noise standard deviation
			noiseMean := calculateMean(noise)
			actualStdDev := calculateStdDev(noise, noiseMean)
			
			// Check if actual matches expected (within statistical tolerance)
			relativeTolerance := 0.05 // 5% tolerance
			tolerance := expectedStdDev * relativeTolerance
			if math.Abs(actualStdDev-expectedStdDev) > tolerance {
				t.Errorf("SNR %.1f dB: Noise std dev = %.4f, expected %.4f (±%.4f)", 
					snr, actualStdDev, expectedStdDev, tolerance)
			}
		}
	})

	t.Run("AWGN Gaussian Distribution Test", func(t *testing.T) {
		// Use high SNR for cleaner noise statistics
		noisySignal := addAWGN(cleanSignal, 10.0)
		
		// Extract noise component
		noise := make([]float64, len(cleanSignal.Values))
		for i := range noise {
			noise[i] = noisySignal.Values[i] - cleanSignal.Values[i]
		}
		
		// Test Gaussian distribution properties
		noiseMean := calculateMean(noise)
		noiseStdDev := calculateStdDev(noise, noiseMean)
		
		// Test empirical rule (68-95-99.7 rule)
		within1Sigma := 0
		within2Sigma := 0
		within3Sigma := 0
		
		for _, n := range noise {
			deviation := math.Abs(n - noiseMean)
			if deviation <= noiseStdDev {
				within1Sigma++
			}
			if deviation <= 2*noiseStdDev {
				within2Sigma++
			}
			if deviation <= 3*noiseStdDev {
				within3Sigma++
			}
		}
		
		total := float64(len(noise))
		pct1Sigma := float64(within1Sigma) / total
		pct2Sigma := float64(within2Sigma) / total
		pct3Sigma := float64(within3Sigma) / total
		
		// Check 68-95-99.7 rule with reasonable tolerance
		if math.Abs(pct1Sigma-0.68) > 0.05 {
			t.Errorf("Within 1σ: %.2f%%, expected ~68%% (±5%%)", pct1Sigma*100)
		}
		if math.Abs(pct2Sigma-0.95) > 0.03 {
			t.Errorf("Within 2σ: %.2f%%, expected ~95%% (±3%%)", pct2Sigma*100)
		}
		if math.Abs(pct3Sigma-0.997) > 0.01 {
			t.Errorf("Within 3σ: %.2f%%, expected ~99.7%% (±1%%)", pct3Sigma*100)
		}
	})

	t.Run("AWGN Reproducibility with Seed", func(t *testing.T) {
		// Test that same seed produces same noise
		testSeed := int64(12345)
		
		// First run
		rand.Seed(testSeed)
		noisy1 := addAWGN(cleanSignal, 10.0)
		
		// Second run with same seed
		rand.Seed(testSeed)
		noisy2 := addAWGN(cleanSignal, 10.0)
		
		// Should be identical
		for i := range noisy1.Values {
			if math.Abs(noisy1.Values[i]-noisy2.Values[i]) > 1e-10 {
				t.Errorf("Non-reproducible noise at sample %d: %.10f vs %.10f", 
					i, noisy1.Values[i], noisy2.Values[i])
				break
			}
		}
	})

	t.Run("AWGN Independence Test", func(t *testing.T) {
		// Test that noise samples are independent (low autocorrelation)
		noisySignal := addAWGN(cleanSignal, 5.0)
		
		// Extract noise
		noise := make([]float64, len(cleanSignal.Values))
		for i := range noise {
			noise[i] = noisySignal.Values[i] - cleanSignal.Values[i]
		}
		
		// Calculate autocorrelation at lag 1
		autocorr := calculateAutocorrelation(noise, 1)
		
		// Should be close to zero for white noise
		if math.Abs(autocorr) > 0.1 {
			t.Errorf("High autocorrelation at lag 1: %.3f, expected ≈ 0", autocorr)
		}
	})

	t.Run("SNR Accuracy Verification", func(t *testing.T) {
		testSNRs := []float64{-10, 0, 10, 20, 30}
		
		for _, targetSNR := range testSNRs {
			noisySignal := addAWGN(cleanSignal, targetSNR)
			
			// Measure actual SNR
			actualSNR := calculateSNR(cleanSignal, noisySignal)
			
			// Should match target SNR within reasonable tolerance
			tolerance := 0.5 // 0.5 dB tolerance
			if math.Abs(actualSNR-targetSNR) > tolerance {
				t.Errorf("Target SNR %.1f dB: actual = %.2f dB (diff = %.2f dB)", 
					targetSNR, actualSNR, actualSNR-targetSNR)
			}
		}
	})
}

// TestAWGNEdgeCases tests edge cases and robustness
func TestAWGNEdgeCases(t *testing.T) {
	params := SignalParams{
		SamplingRate: 1000,
		Duration:     0.1,
		MessageFreq:  10,
		CarrierFreq:  100,
		MessageAmp:   1.0,
		CarrierAmp:   1.0,
	}

	cleanSignal := generateCarrier(params)

	t.Run("Very High SNR", func(t *testing.T) {
		highSNR := 60.0 // Very high SNR
		noisySignal := addAWGN(cleanSignal, highSNR)
		
		// Should be very close to original signal
		actualSNR := calculateSNR(cleanSignal, noisySignal)
		
		if actualSNR < 50.0 { // Should be at least 50 dB
			t.Errorf("High SNR test failed: actual SNR = %.1f dB", actualSNR)
		}
		
		// Check for numerical stability
		for i, v := range noisySignal.Values {
			if math.IsNaN(v) || math.IsInf(v, 0) {
				t.Errorf("Invalid value at sample %d: %v", i, v)
				break
			}
		}
	})

	t.Run("Very Low SNR", func(t *testing.T) {
		lowSNR := -20.0 // Very low SNR
		noisySignal := addAWGN(cleanSignal, lowSNR)
		
		// Should be dominated by noise
		actualSNR := calculateSNR(cleanSignal, noisySignal)
		
		if actualSNR > -15.0 { // Should be very low
			t.Errorf("Low SNR test failed: actual SNR = %.1f dB", actualSNR)
		}
	})

	t.Run("Zero Signal Power", func(t *testing.T) {
		// Create zero signal
		zeroSignal := Signal{
			Time:   cleanSignal.Time,
			Values: make([]float64, len(cleanSignal.Values)),
		}
		
		// Adding noise to zero signal should not crash
		noisySignal := addAWGN(zeroSignal, 10.0)
		
		// Should be pure noise
		if len(noisySignal.Values) != len(zeroSignal.Values) {
			t.Error("Zero signal AWGN failed")
		}
		
		// Noise should have reasonable power
		noisePower := calculateSignalPower(noisySignal.Values)
		if noisePower < 1e-6 {
			t.Errorf("Insufficient noise power: %e", noisePower)
		}
	})

	t.Run("Single Sample Signal", func(t *testing.T) {
		singleSample := Signal{
			Time:   []float64{0},
			Values: []float64{1.0},
		}
		
		// Should not crash
		noisySignal := addAWGN(singleSample, 10.0)
		
		if len(noisySignal.Values) != 1 {
			t.Error("Single sample AWGN failed")
		}
		
		if math.IsNaN(noisySignal.Values[0]) || math.IsInf(noisySignal.Values[0], 0) {
			t.Errorf("Invalid single sample result: %v", noisySignal.Values[0])
		}
	})
}

// TestAWGNWithRNG tests the custom RNG version used in Monte Carlo simulations
func TestAWGNWithRNG(t *testing.T) {
	params := SignalParams{
		SamplingRate: 8000,
		Duration:     0.1,
		MessageFreq:  100,
		CarrierFreq:  1000,
		MessageAmp:   1.0,
		CarrierAmp:   1.0,
	}

	cleanSignal := generateCarrier(params)

	t.Run("Custom RNG Reproducibility", func(t *testing.T) {
		seed := int64(54321)
		rng1 := rand.New(rand.NewSource(seed))
		rng2 := rand.New(rand.NewSource(seed))
		
		noisy1 := addAWGNWithRNG(cleanSignal, 10.0, rng1)
		noisy2 := addAWGNWithRNG(cleanSignal, 10.0, rng2)
		
		// Should be identical
		for i := range noisy1.Values {
			if math.Abs(noisy1.Values[i]-noisy2.Values[i]) > 1e-10 {
				t.Errorf("Custom RNG not reproducible at sample %d", i)
				break
			}
		}
	})

	t.Run("Custom RNG Statistics", func(t *testing.T) {
		seed := int64(98765)
		rng := rand.New(rand.NewSource(seed))
		
		noisySignal := addAWGNWithRNG(cleanSignal, 15.0, rng)
		
		// Extract noise
		noise := make([]float64, len(cleanSignal.Values))
		for i := range noise {
			noise[i] = noisySignal.Values[i] - cleanSignal.Values[i]
		}
		
		// Check statistics
		noiseMean := calculateMean(noise)
		noiseStdDev := calculateStdDev(noise, noiseMean)
		
		if math.Abs(noiseMean) > 0.1 {
			t.Errorf("Custom RNG noise mean = %.4f, expected ≈ 0", noiseMean)
		}
		
		// Verify standard deviation matches expectation
		signalPower := calculateSignalPower(cleanSignal.Values)
		expectedStdDev := math.Sqrt(signalPower / math.Pow(10, 15.0/10.0))
		
		if math.Abs(noiseStdDev-expectedStdDev) > expectedStdDev*0.1 {
			t.Errorf("Custom RNG noise std dev = %.4f, expected %.4f", 
				noiseStdDev, expectedStdDev)
		}
	})
}

// BenchmarkAWGN benchmarks AWGN generation performance
func BenchmarkAWGN(b *testing.B) {
	params := SignalParams{
		SamplingRate: 10000,
		Duration:     0.1,
		MessageFreq:  100,
		CarrierFreq:  1000,
		MessageAmp:   1.0,
		CarrierAmp:   1.0,
	}

	cleanSignal := generateCarrier(params)

	b.Run("Standard AWGN", func(b *testing.B) {
		for i := 0; i < b.N; i++ {
			_ = addAWGN(cleanSignal, 10.0)
		}
	})

	b.Run("AWGN with Custom RNG", func(b *testing.B) {
		rng := rand.New(rand.NewSource(time.Now().UnixNano()))
		b.ResetTimer()
		
		for i := 0; i < b.N; i++ {
			_ = addAWGNWithRNG(cleanSignal, 10.0, rng)
		}
	})
}

// Helper functions for noise analysis

// calculateSignalPower calculates the average power of a signal
func calculateSignalPower(values []float64) float64 {
	if len(values) == 0 {
		return 0
	}
	
	power := 0.0
	for _, v := range values {
		power += v * v
	}
	return power / float64(len(values))
}

// calculateAutocorrelation calculates autocorrelation at given lag
func calculateAutocorrelation(values []float64, lag int) float64 {
	if len(values) <= lag {
		return 0
	}
	
	mean := calculateMean(values)
	
	// Remove DC component
	centered := make([]float64, len(values))
	for i, v := range values {
		centered[i] = v - mean
	}
	
	// Calculate autocorrelation
	numerator := 0.0
	denominator := 0.0
	
	N := len(centered) - lag
	for i := 0; i < N; i++ {
		numerator += centered[i] * centered[i+lag]
		denominator += centered[i] * centered[i]
	}
	
	if denominator == 0 {
		return 0
	}
	
	return numerator / denominator
}

// TestNoiseDistributionShapes tests various aspects of the noise distribution
func TestNoiseDistributionShapes(t *testing.T) {
	params := SignalParams{
		SamplingRate: 8000,
		Duration:     1.0, // Long duration for good statistics
		MessageFreq:  100,
		CarrierFreq:  1000,
		MessageAmp:   1.0,
		CarrierAmp:   1.0,
	}

	cleanSignal := generateCarrier(params)

	t.Run("Noise Distribution Moments", func(t *testing.T) {
		noisySignal := addAWGN(cleanSignal, 10.0)
		
		// Extract noise
		noise := make([]float64, len(cleanSignal.Values))
		for i := range noise {
			noise[i] = noisySignal.Values[i] - cleanSignal.Values[i]
		}
		
		// Calculate statistical moments
		mean := calculateMean(noise)
		stdDev := calculateStdDev(noise, mean)
		skewness := calculateSkewness(noise, mean, stdDev)
		kurtosis := calculateKurtosis(noise, mean, stdDev)
		
		// Gaussian distribution should have:
		// - Mean ≈ 0
		// - Skewness ≈ 0
		// - Excess kurtosis ≈ 0 (kurtosis ≈ 3)
		
		if math.Abs(mean) > 0.05 {
			t.Errorf("Noise mean = %.4f, expected ≈ 0", mean)
		}
		
		if math.Abs(skewness) > 0.2 {
			t.Errorf("Noise skewness = %.3f, expected ≈ 0", skewness)
		}
		
		excessKurtosis := kurtosis - 3.0
		if math.Abs(excessKurtosis) > 0.5 {
			t.Errorf("Noise excess kurtosis = %.3f, expected ≈ 0", excessKurtosis)
		}
	})
}

// calculateSkewness calculates the skewness of a dataset
func calculateSkewness(values []float64, mean, stdDev float64) float64 {
	if len(values) == 0 || stdDev == 0 {
		return 0
	}
	
	sum := 0.0
	for _, v := range values {
		normalized := (v - mean) / stdDev
		sum += normalized * normalized * normalized
	}
	
	return sum / float64(len(values))
}

// calculateKurtosis calculates the kurtosis of a dataset
func calculateKurtosis(values []float64, mean, stdDev float64) float64 {
	if len(values) == 0 || stdDev == 0 {
		return 0
	}
	
	sum := 0.0
	for _, v := range values {
		normalized := (v - mean) / stdDev
		sum += normalized * normalized * normalized * normalized
	}
	
	return sum / float64(len(values))
}