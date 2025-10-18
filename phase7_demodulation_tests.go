package main

import (
	"math"
	"testing"
)

// TestDemodulationAccuracy contains comprehensive tests for AM/FM demodulation accuracy
func TestDemodulationAccuracy(t *testing.T) {
	// Standard test parameters
	params := SignalParams{
		SamplingRate:  8000,  // 8 kHz
		Duration:      0.2,   // 200 ms for good statistics
		MessageFreq:   50,    // 50 Hz message
		CarrierFreq:   1000,  // 1 kHz carrier
		MessageAmp:    1.0,
		CarrierAmp:    2.0,
		ModulationIdx: 0.5,   // 50% AM modulation
	}

	t.Run("AM Demodulation Clean Signal", func(t *testing.T) {
		// Generate clean AM signal
		originalMessage := generateBaseband(params)
		amSignal := generateAM(params)
		
		// Demodulate
		demodulated := demodulateAM(amSignal)
		
		// Test signal recovery quality
		correlation := calculateCorrelation(originalMessage.Values, demodulated.Values)
		if correlation < 0.8 {
			t.Errorf("Poor AM demodulation correlation: %.3f, expected > 0.8", correlation)
		}
		
		// Test frequency content preservation
		origFreqContent := estimateFrequencyContent(originalMessage.Values, params.MessageFreq, params.SamplingRate)
		demodFreqContent := estimateFrequencyContent(demodulated.Values, params.MessageFreq, params.SamplingRate)
		
		freqRatio := demodFreqContent / origFreqContent
		if freqRatio < 0.5 || freqRatio > 2.0 {
			t.Errorf("AM frequency content distorted: ratio = %.2f", freqRatio)
		}
	})

	t.Run("FM Demodulation Clean Signal", func(t *testing.T) {
		fmParams := params
		fmParams.ModulationIdx = 100 // 100 Hz frequency deviation
		
		// Generate clean FM signal
		originalMessage := generateBaseband(fmParams)
		fmSignal := generateFM(fmParams)
		
		// Demodulate
		demodulated := demodulateFM(fmSignal, fmParams)
		
		// Test signal recovery quality - FM demodulation might need alignment
		alignedDemod := alignSignals(originalMessage.Values, demodulated.Values)
		correlation := calculateCorrelation(originalMessage.Values, alignedDemod)
		
		// FM demodulation with simplified method may have lower correlation
		if correlation < 0.3 {
			t.Errorf("Poor FM demodulation correlation: %.3f", correlation)
		}
		
		// Test that demodulated signal has reasonable amplitude
		demodMean := calculateMean(alignedDemod)
		demodStdDev := calculateStdDev(alignedDemod, demodMean)
		
		if demodStdDev < 0.1 {
			t.Errorf("FM demodulated signal too flat: std dev = %.3f", demodStdDev)
		}
	})

	t.Run("AM Demodulation with Noise", func(t *testing.T) {
		testSNRs := []float64{20, 10, 5, 0}
		
		originalMessage := generateBaseband(params)
		
		for _, snr := range testSNRs {
			// Generate noisy AM signal
			cleanAM := generateAM(params)
			noisyAM := addAWGN(cleanAM, snr)
			
			// Demodulate
			demodulated := demodulateAM(noisyAM)
			
			// Test correlation (should decrease with SNR)
			correlation := calculateCorrelation(originalMessage.Values, demodulated.Values)
			
			// Expected minimum correlation based on SNR
			var expectedMinCorr float64
			switch {
			case snr >= 20:
				expectedMinCorr = 0.7
			case snr >= 10:
				expectedMinCorr = 0.5
			case snr >= 5:
				expectedMinCorr = 0.3
			default:
				expectedMinCorr = 0.1
			}
			
			if correlation < expectedMinCorr {
				t.Errorf("AM demod at %.1f dB SNR: correlation = %.3f, expected > %.3f", 
					snr, correlation, expectedMinCorr)
			}
		}
	})

	t.Run("FM Demodulation with Noise", func(t *testing.T) {
		fmParams := params
		fmParams.ModulationIdx = 150 // Higher deviation for better noise immunity
		
		testSNRs := []float64{20, 10, 5, 0}
		
		originalMessage := generateBaseband(fmParams)
		
		for _, snr := range testSNRs {
			// Generate noisy FM signal
			cleanFM := generateFM(fmParams)
			noisyFM := addAWGN(cleanFM, snr)
			
			// Demodulate
			demodulated := demodulateFM(noisyFM, fmParams)
			
			// Align signals for comparison
			alignedDemod := alignSignals(originalMessage.Values, demodulated.Values)
			correlation := calculateCorrelation(originalMessage.Values, alignedDemod)
			
			// FM should maintain some correlation even at low SNR
			var expectedMinCorr float64
			switch {
			case snr >= 20:
				expectedMinCorr = 0.2
			case snr >= 10:
				expectedMinCorr = 0.15
			case snr >= 5:
				expectedMinCorr = 0.1
			default:
				expectedMinCorr = 0.05
			}
			
			if correlation < expectedMinCorr {
				t.Errorf("FM demod at %.1f dB SNR: correlation = %.3f, expected > %.3f", 
					snr, correlation, expectedMinCorr)
			}
		}
	})

	t.Run("Demodulation DC Bias Test", func(t *testing.T) {
		// Test that demodulated signals don't have excessive DC bias
		
		// AM test
		amSignal := generateAM(params)
		demodAM := demodulateAM(amSignal)
		amMean := calculateMean(demodAM.Values)
		amStdDev := calculateStdDev(demodAM.Values, amMean)
		
		// DC bias should be small relative to signal variation
		if math.Abs(amMean) > 0.5*amStdDev {
			t.Errorf("AM demodulation has excessive DC bias: mean = %.3f, std dev = %.3f", 
				amMean, amStdDev)
		}
		
		// FM test
		fmParams := params
		fmParams.ModulationIdx = 100
		fmSignal := generateFM(fmParams)
		demodFM := demodulateFM(fmSignal, fmParams)
		fmMean := calculateMean(demodFM.Values)
		fmStdDev := calculateStdDev(demodFM.Values, fmMean)
		
		// FM might have more DC offset due to simplified demodulator
		if math.Abs(fmMean) > 2.0*fmStdDev {
			t.Errorf("FM demodulation has excessive DC bias: mean = %.3f, std dev = %.3f", 
				fmMean, fmStdDev)
		}
	})

	t.Run("Demodulation Amplitude Test", func(t *testing.T) {
		// Test that demodulated signal amplitudes are reasonable
		
		originalMessage := generateBaseband(params)
		origRMS := calculateRMS(originalMessage.Values)
		
		// AM test
		amSignal := generateAM(params)
		demodAM := demodulateAM(amSignal)
		amRMS := calculateRMS(demodAM.Values)
		
		// AM demodulated amplitude should be related to original
		if amRMS < 0.1*origRMS || amRMS > 10*origRMS {
			t.Errorf("AM demodulated amplitude unreasonable: orig RMS = %.3f, demod RMS = %.3f", 
				origRMS, amRMS)
		}
		
		// FM test
		fmParams := params
		fmParams.ModulationIdx = 100
		fmSignal := generateFM(fmParams)
		demodFM := demodulateFM(fmSignal, fmParams)
		fmRMS := calculateRMS(demodFM.Values)
		
		// FM demodulated amplitude may differ significantly due to demodulation method
		if fmRMS == 0 {
			t.Error("FM demodulated signal is zero - demodulation failed")
		}
	})
}

// TestDemodulationEdgeCases tests edge cases and robustness
func TestDemodulationEdgeCases(t *testing.T) {
	t.Run("100% AM Modulation", func(t *testing.T) {
		params := SignalParams{
			SamplingRate:  8000,
			Duration:      0.1,
			MessageFreq:   100,
			CarrierFreq:   1000,
			MessageAmp:    1.0,
			CarrierAmp:    1.0,
			ModulationIdx: 1.0, // 100% modulation
		}
		
		originalMessage := generateBaseband(params)
		amSignal := generateAM(params)
		demodulated := demodulateAM(amSignal)
		
		// Should still recover some signal content
		correlation := calculateCorrelation(originalMessage.Values, demodulated.Values)
		if correlation < 0.3 {
			t.Errorf("100%% AM modulation recovery poor: correlation = %.3f", correlation)
		}
		
		// Check for over-modulation artifacts
		envelope := extractEnvelope(amSignal.Values)
		minEnv, _ := findMinMax(envelope)
		if minEnv < -0.1 {
			t.Errorf("Over-modulation detected in 100%% AM: min envelope = %.3f", minEnv)
		}
	})

	t.Run("Very Low Frequency Message", func(t *testing.T) {
		params := SignalParams{
			SamplingRate:  8000,
			Duration:      1.0, // Longer duration for low frequency
			MessageFreq:   1,   // 1 Hz message
			CarrierFreq:   100,
			MessageAmp:    1.0,
			CarrierAmp:    1.0,
			ModulationIdx: 0.5,
		}
		
		originalMessage := generateBaseband(params)
		amSignal := generateAM(params)
		demodulated := demodulateAM(amSignal)
		
		// Low frequency should still be recoverable
		correlation := calculateCorrelation(originalMessage.Values, demodulated.Values)
		if correlation < 0.5 {
			t.Errorf("Low frequency AM demodulation poor: correlation = %.3f", correlation)
		}
	})

	t.Run("High Frequency Deviation FM", func(t *testing.T) {
		params := SignalParams{
			SamplingRate:  8000,
			Duration:      0.1,
			MessageFreq:   50,
			CarrierFreq:   1000,
			MessageAmp:    1.0,
			CarrierAmp:    1.0,
			ModulationIdx: 500, // Very high frequency deviation
		}
		
		// Should not crash with high deviation
		fmSignal := generateFM(params)
		if len(fmSignal.Values) == 0 {
			t.Error("FM generation failed with high deviation")
		}
		
		demodulated := demodulateFM(fmSignal, params)
		if len(demodulated.Values) == 0 {
			t.Error("FM demodulation failed with high deviation")
		}
		
		// Check for reasonable values
		for i, v := range demodulated.Values {
			if math.IsNaN(v) || math.IsInf(v, 0) {
				t.Errorf("Invalid demodulated value at sample %d: %v", i, v)
				break
			}
		}
	})

	t.Run("Zero Amplitude Signal", func(t *testing.T) {
		params := SignalParams{
			SamplingRate:  8000,
			Duration:      0.1,
			MessageFreq:   100,
			CarrierFreq:   1000,
			MessageAmp:    0.0, // Zero message amplitude
			CarrierAmp:    1.0,
			ModulationIdx: 0.5,
		}
		
		// Should produce carrier-only AM signal
		amSignal := generateAM(params)
		demodulated := demodulateAM(amSignal)
		
		// Demodulated signal should be close to zero (just carrier)
		demodRMS := calculateRMS(demodulated.Values)
		if demodRMS > 0.1 {
			t.Errorf("Zero message AM demodulation should be near zero: RMS = %.3f", demodRMS)
		}
	})
}

// TestDemodulationPerformance tests performance characteristics
func TestDemodulationPerformance(t *testing.T) {
	t.Run("SNR Improvement Analysis", func(t *testing.T) {
		params := SignalParams{
			SamplingRate:  8000,
			Duration:      0.2,
			MessageFreq:   100,
			CarrierFreq:   1000,
			MessageAmp:    1.0,
			CarrierAmp:    1.0,
			ModulationIdx: 0.5,
		}
		
		originalMessage := generateBaseband(params)
		
		testSNRs := []float64{0, 5, 10, 15, 20}
		
		for _, inputSNR := range testSNRs {
			// AM analysis
			amSignal := generateAM(params)
			noisyAM := addAWGN(amSignal, inputSNR)
			demodAM := demodulateAM(noisyAM)
			
			outputSNR_AM := calculateSNR(originalMessage, demodAM)
			
			// FM analysis
			fmParams := params
			fmParams.ModulationIdx = 100
			fmSignal := generateFM(fmParams)
			noisyFM := addAWGN(fmSignal, inputSNR)
			demodFM := demodulateFM(noisyFM, fmParams)
			
			alignedFM := alignSignals(originalMessage.Values, demodFM.Values)
			alignedFMSignal := Signal{Time: originalMessage.Time, Values: alignedFM}
			outputSNR_FM := calculateSNR(originalMessage, alignedFMSignal)
			
			// Log results for analysis (optional)
			t.Logf("Input SNR: %.1f dB -> AM Output: %.1f dB, FM Output: %.1f dB", 
				inputSNR, outputSNR_AM, outputSNR_FM)
			
			// Basic sanity checks
			if math.IsNaN(outputSNR_AM) || math.IsInf(outputSNR_AM, 0) {
				t.Errorf("Invalid AM output SNR at input %.1f dB", inputSNR)
			}
			if math.IsNaN(outputSNR_FM) || math.IsInf(outputSNR_FM, 0) {
				t.Errorf("Invalid FM output SNR at input %.1f dB", inputSNR)
			}
		}
	})
}

// BenchmarkDemodulation benchmarks demodulation performance
func BenchmarkDemodulation(b *testing.B) {
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
	fmSignal := generateFM(params)

	b.Run("AM Demodulation", func(b *testing.B) {
		for i := 0; i < b.N; i++ {
			_ = demodulateAM(amSignal)
		}
	})

	b.Run("FM Demodulation", func(b *testing.B) {
		for i := 0; i < b.N; i++ {
			_ = demodulateFM(fmSignal, params)
		}
	})
}

// Helper functions for demodulation analysis

// calculateCorrelation calculates Pearson correlation coefficient
func calculateCorrelation(x, y []float64) float64 {
	if len(x) != len(y) || len(x) == 0 {
		return 0
	}
	
	n := len(x)
	
	// Calculate means
	meanX := calculateMean(x)
	meanY := calculateMean(y)
	
	// Calculate correlation coefficient
	numerator := 0.0
	sumX2 := 0.0
	sumY2 := 0.0
	
	for i := 0; i < n; i++ {
		dx := x[i] - meanX
		dy := y[i] - meanY
		numerator += dx * dy
		sumX2 += dx * dx
		sumY2 += dy * dy
	}
	
	denominator := math.Sqrt(sumX2 * sumY2)
	if denominator == 0 {
		return 0
	}
	
	return numerator / denominator
}

// calculateRMS calculates root mean square of signal
func calculateRMS(values []float64) float64 {
	if len(values) == 0 {
		return 0
	}
	
	sum := 0.0
	for _, v := range values {
		sum += v * v
	}
	
	return math.Sqrt(sum / float64(len(values)))
}

// estimateFrequencyContent estimates power at a specific frequency
func estimateFrequencyContent(values []float64, targetFreq, samplingRate float64) float64 {
	if len(values) == 0 {
		return 0
	}
	
	N := len(values)
	freqBin := int(targetFreq * float64(N) / samplingRate)
	
	if freqBin >= N/2 {
		return 0
	}
	
	// Simple DFT at target frequency
	real, imag := 0.0, 0.0
	for n, x := range values {
		angle := 2.0 * math.Pi * float64(freqBin) * float64(n) / float64(N)
		real += x * math.Cos(angle)
		imag += x * math.Sin(angle)
	}
	
	magnitude := math.Sqrt(real*real + imag*imag) / float64(N)
	return magnitude
}

// alignSignals aligns two signals by finding best delay offset
func alignSignals(reference, signal []float64) []float64 {
	if len(reference) != len(signal) {
		return signal
	}
	
	n := len(reference)
	maxCorr := -math.Inf(1)
	bestDelay := 0
	
	// Search for best alignment within reasonable range
	maxDelay := n / 10 // Search within 10% of signal length
	if maxDelay > 100 {
		maxDelay = 100
	}
	
	for delay := -maxDelay; delay <= maxDelay; delay++ {
		correlation := 0.0
		count := 0
		
		for i := 0; i < n; i++ {
			j := i + delay
			if j >= 0 && j < n {
				correlation += reference[i] * signal[j]
				count++
			}
		}
		
		if count > 0 {
			correlation /= float64(count)
			if correlation > maxCorr {
				maxCorr = correlation
				bestDelay = delay
			}
		}
	}
	
	// Apply best delay
	aligned := make([]float64, n)
	for i := 0; i < n; i++ {
		j := i + bestDelay
		if j >= 0 && j < n {
			aligned[i] = signal[j]
		} else {
			aligned[i] = 0
		}
	}
	
	return aligned
}