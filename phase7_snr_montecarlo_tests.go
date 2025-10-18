package main

import (
	"math"
	"math/rand"
	"testing"
)

// TestSNRMeasurement contains comprehensive tests for SNR calculation accuracy
func TestSNRMeasurement(t *testing.T) {
	t.Run("SNR Analytical Verification", func(t *testing.T) {
		// Test SNR calculation with known analytical cases
		params := SignalParams{
			SamplingRate: 8000,
			Duration:     0.1,
			MessageFreq:  100,
			CarrierFreq:  1000,
			MessageAmp:   1.0,
			CarrierAmp:   1.0,
		}

		cleanSignal := generateCarrier(params)
		
		// Test various SNR levels with analytical verification
		testSNRs := []float64{-10, 0, 10, 20, 30}
		
		for _, targetSNR := range testSNRs {
			noisySignal := addAWGN(cleanSignal, targetSNR)
			measuredSNR := calculateSNR(cleanSignal, noisySignal)
			
			// SNR measurement should match target within reasonable tolerance
			tolerance := 0.5 // 0.5 dB tolerance for finite length signals
			if math.Abs(measuredSNR-targetSNR) > tolerance {
				t.Errorf("SNR mismatch: target = %.1f dB, measured = %.2f dB (diff = %.2f dB)", 
					targetSNR, measuredSNR, measuredSNR-targetSNR)
			}
		}
	})

	t.Run("SNR Power-Based Verification", func(t *testing.T) {
		// Create signals with known power ratios
		params := SignalParams{
			SamplingRate: 8000,
			Duration:     0.2,
			MessageFreq:  100,
			CarrierFreq:  1000,
			MessageAmp:   2.0, // Known amplitude
			CarrierAmp:   1.0,
		}

		signal := generateCarrier(params)
		
		// Calculate theoretical signal power
		theoreticalPower := params.CarrierAmp * params.CarrierAmp / 2.0 // RMS power of sinusoid
		measuredPower := calculateSignalPower(signal.Values)
		
		// Verify power calculation
		powerRatio := measuredPower / theoreticalPower
		if math.Abs(powerRatio-1.0) > 0.1 {
			t.Errorf("Power calculation error: theoretical = %.3f, measured = %.3f (ratio = %.3f)", 
				theoreticalPower, measuredPower, powerRatio)
		}

		// Test SNR calculation with controlled noise power
		targetSNR := 15.0
		noisySignal := addAWGN(signal, targetSNR)
		
		// Calculate SNR components separately
		signalPower := calculateSignalPower(signal.Values)
		noise := make([]float64, len(signal.Values))
		for i := range noise {
			noise[i] = noisySignal.Values[i] - signal.Values[i]
		}
		noisePower := calculateSignalPower(noise)
		
		manualSNR := 10 * math.Log10(signalPower/noisePower)
		autoSNR := calculateSNR(signal, noisySignal)
		
		if math.Abs(manualSNR-autoSNR) > 0.1 {
			t.Errorf("SNR calculation inconsistency: manual = %.2f dB, auto = %.2f dB", 
				manualSNR, autoSNR)
		}
	})

	t.Run("SNR Consistency Across Signal Types", func(t *testing.T) {
		// Test SNR consistency with different signal types
		params := SignalParams{
			SamplingRate: 8000,
			Duration:     0.1,
			MessageFreq:  100,
			CarrierFreq:  1000,
			MessageAmp:   1.0,
			CarrierAmp:   1.0,
		}

		signals := map[string]Signal{
			"Carrier":  generateCarrier(params),
			"Baseband": generateBaseband(params),
			"AM":       generateAM(params),
			"FM":       generateFM(params),
		}

		targetSNR := 12.0
		
		for signalType, signal := range signals {
			noisySignal := addAWGN(signal, targetSNR)
			measuredSNR := calculateSNR(signal, noisySignal)
			
			tolerance := 1.0 // Larger tolerance for different signal types
			if math.Abs(measuredSNR-targetSNR) > tolerance {
				t.Errorf("%s SNR inconsistent: target = %.1f dB, measured = %.2f dB", 
					signalType, targetSNR, measuredSNR)
			}
		}
	})

	t.Run("SNR Edge Cases", func(t *testing.T) {
		params := SignalParams{
			SamplingRate: 1000,
			Duration:     0.1,
			MessageFreq:  10,
			CarrierFreq:  100,
			MessageAmp:   1.0,
			CarrierAmp:   1.0,
		}

		// Test with zero noise (infinite SNR)
		cleanSignal := generateCarrier(params)
		infiniteSNR := calculateSNR(cleanSignal, cleanSignal)
		
		if !math.IsInf(infiniteSNR, 1) && infiniteSNR < 100 {
			t.Errorf("Zero noise should give very high/infinite SNR, got %.1f dB", infiniteSNR)
		}

		// Test with very high noise
		veryLowSNR := -30.0
		veryNoisySignal := addAWGN(cleanSignal, veryLowSNR)
		measuredSNR := calculateSNR(cleanSignal, veryNoisySignal)
		
		if math.Abs(measuredSNR-veryLowSNR) > 2.0 {
			t.Errorf("Very low SNR measurement inaccurate: target = %.1f dB, measured = %.1f dB", 
				veryLowSNR, measuredSNR)
		}
	})
}

// TestMonteCarloStability tests Monte Carlo averaging stability and convergence
func TestMonteCarloStability(t *testing.T) {
	t.Run("Monte Carlo Convergence Test", func(t *testing.T) {
		params := SignalParams{
			SamplingRate:  8000,
			Duration:      0.1,
			MessageFreq:   100,
			CarrierFreq:   1000,
			MessageAmp:    1.0,
			CarrierAmp:    1.0,
			ModulationIdx: 0.5,
		}

		// Test convergence with increasing number of trials
		trialCounts := []int{10, 50, 100, 500}
		targetSNR := 10.0

		rand.Seed(12345) // Fixed seed for reproducibility

		for _, numTrials := range trialCounts {
			// Run Monte Carlo simulation
			snrSum := 0.0
			
			for trial := 0; trial < numTrials; trial++ {
				originalMessage := generateBaseband(params)
				amSignal := generateAM(params)
				noisySignal := addAWGN(amSignal, targetSNR)
				demodulated := demodulateAM(noisySignal)
				
				outputSNR := calculateSNR(originalMessage, demodulated)
				if !math.IsNaN(outputSNR) && !math.IsInf(outputSNR, 0) {
					snrSum += outputSNR
				}
			}
			
			meanSNR := snrSum / float64(numTrials)
			
			// As number of trials increases, result should stabilize
			t.Logf("Trials: %4d, Mean SNR: %6.2f dB", numTrials, meanSNR)
			
			// Check that results are within reasonable bounds
			if math.IsNaN(meanSNR) || math.IsInf(meanSNR, 0) {
				t.Errorf("Invalid mean SNR with %d trials: %f", numTrials, meanSNR)
			}
			
			if math.Abs(meanSNR) > 50.0 { // Very broad sanity check
				t.Errorf("Unreasonable mean SNR with %d trials: %.2f dB", numTrials, meanSNR)
			}
		}
	})

	t.Run("Statistical Stability Test", func(t *testing.T) {
		// Test that multiple runs with same seed give identical results
		params := SignalParams{
			SamplingRate:  8000,
			Duration:      0.1,
			MessageFreq:   100,
			CarrierFreq:   1000,
			MessageAmp:    1.0,
			CarrierAmp:    1.0,
			ModulationIdx: 0.5,
		}

		numTrials := 50
		targetSNR := 5.0
		seed := int64(54321)

		// Run 1
		rand.Seed(seed)
		results1 := runMonteCarloTrial(params, targetSNR, numTrials)

		// Run 2 with same seed
		rand.Seed(seed)
		results2 := runMonteCarloTrial(params, targetSNR, numTrials)

		// Results should be identical
		if math.Abs(results1-results2) > 1e-10 {
			t.Errorf("Monte Carlo not reproducible: run1 = %.6f, run2 = %.6f", results1, results2)
		}
	})

	t.Run("Standard Deviation Convergence", func(t *testing.T) {
		params := SignalParams{
			SamplingRate:  8000,
			Duration:      0.1,
			MessageFreq:   100,
			CarrierFreq:   1000,
			MessageAmp:    1.0,
			CarrierAmp:    1.0,
			ModulationIdx: 0.5,
		}

		numTrials := 200
		targetSNR := 8.0
		
		// Collect individual trial results
		results := make([]float64, 0, numTrials)
		
		rand.Seed(98765)
		
		for trial := 0; trial < numTrials; trial++ {
			originalMessage := generateBaseband(params)
			amSignal := generateAM(params)
			noisySignal := addAWGN(amSignal, targetSNR)
			demodulated := demodulateAM(noisySignal)
			
			outputSNR := calculateSNR(originalMessage, demodulated)
			if !math.IsNaN(outputSNR) && !math.IsInf(outputSNR, 0) && math.Abs(outputSNR) < 100 {
				results = append(results, outputSNR)
			}
		}

		if len(results) < numTrials/2 {
			t.Errorf("Too many invalid results: %d valid out of %d trials", len(results), numTrials)
		}

		// Calculate statistics
		mean := calculateMean(results)
		stdDev := calculateStdDev(results, mean)
		
		t.Logf("Monte Carlo statistics: mean = %.2f dB, std dev = %.2f dB, trials = %d", 
			mean, stdDev, len(results))
		
		// Standard deviation should be reasonable (not too small or too large)
		if stdDev < 0.1 {
			t.Errorf("Standard deviation too small: %.3f", stdDev)
		}
		if stdDev > 20.0 {
			t.Errorf("Standard deviation too large: %.3f", stdDev)
		}
	})

	t.Run("Different Modulation Stability", func(t *testing.T) {
		params := SignalParams{
			SamplingRate:  8000,
			Duration:      0.1,
			MessageFreq:   100,
			CarrierFreq:   1000,
			MessageAmp:    1.0,
			CarrierAmp:    1.0,
			ModulationIdx: 0.5,
		}

		numTrials := 100
		targetSNR := 10.0
		
		// Test AM stability
		amResults := make([]float64, 10) // 10 independent runs
		for run := 0; run < 10; run++ {
			rand.Seed(int64(1000 + run)) // Different seeds for each run
			amResults[run] = runMonteCarloTrial(params, targetSNR, numTrials)
		}
		
		// Test FM stability  
		fmParams := params
		fmParams.ModulationIdx = 100
		fmResults := make([]float64, 10)
		for run := 0; run < 10; run++ {
			rand.Seed(int64(1000 + run))
			fmResults[run] = runMonteCarloTrialFM(fmParams, targetSNR, numTrials)
		}

		// Calculate run-to-run variation
		amMean := calculateMean(amResults)
		amStdDev := calculateStdDev(amResults, amMean)
		
		fmMean := calculateMean(fmResults)
		fmStdDev := calculateStdDev(fmResults, fmMean)
		
		t.Logf("AM runs: mean = %.2f, std dev = %.2f", amMean, amStdDev)
		t.Logf("FM runs: mean = %.2f, std dev = %.2f", fmMean, fmStdDev)
		
		// Run-to-run variation should be small compared to individual trial variation
		if amStdDev > 5.0 {
			t.Errorf("AM run-to-run variation too high: %.2f dB", amStdDev)
		}
		if fmStdDev > 5.0 {
			t.Errorf("FM run-to-run variation too high: %.2f dB", fmStdDev)
		}
	})
}

// TestPhase5MonteCarloIntegration tests the full Phase 5 Monte Carlo system
func TestPhase5MonteCarloIntegration(t *testing.T) {
	t.Run("Phase 5 System Stability", func(t *testing.T) {
		// Test the actual Phase 5 implementation
		amParams := SignalParams{
			SamplingRate:  8000,
			Duration:      0.1,
			MessageFreq:   100,
			CarrierFreq:   1000,
			MessageAmp:    1.0,
			CarrierAmp:    1.0,
			ModulationIdx: 0.5,
		}

		fmParams := amParams
		fmParams.ModulationIdx = 100

		config := MonteCarloConfig{
			NumIterations:  50,  // Smaller for testing
			SNRRange:      []float64{0, 10, 20},
			Seed:          12345,
			UseParallel:   false, // Sequential for deterministic testing
			NumWorkers:    1,
			ProgressReport: false,
		}

		// Run Phase 5 simulation
		results, err := RunPhase5MonteCarloSimulation(amParams, fmParams, config)
		if err != nil {
			t.Fatalf("Phase 5 simulation failed: %v", err)
		}

		// Validate results structure
		if len(results.AMResults) != len(config.SNRRange) {
			t.Errorf("AM results length mismatch: expected %d, got %d", 
				len(config.SNRRange), len(results.AMResults))
		}
		if len(results.FMResults) != len(config.SNRRange) {
			t.Errorf("FM results length mismatch: expected %d, got %d", 
				len(config.SNRRange), len(results.FMResults))
		}

		// Validate individual results
		for i, result := range results.AMResults {
			if math.IsNaN(result.OutputSNR_dB) || math.IsInf(result.OutputSNR_dB, 0) {
				t.Errorf("Invalid AM result at index %d: %f", i, result.OutputSNR_dB)
			}
			if result.StdDev < 0 {
				t.Errorf("Negative standard deviation in AM result %d: %f", i, result.StdDev)
			}
			if result.NumTrials != config.NumIterations {
				t.Errorf("Trial count mismatch in AM result %d: expected %d, got %d", 
					i, config.NumIterations, result.NumTrials)
			}
		}

		for i, result := range results.FMResults {
			if math.IsNaN(result.OutputSNR_dB) || math.IsInf(result.OutputSNR_dB, 0) {
				t.Errorf("Invalid FM result at index %d: %f", i, result.OutputSNR_dB)
			}
			if result.StdDev < 0 {
				t.Errorf("Negative standard deviation in FM result %d: %f", i, result.StdDev)
			}
		}

		// Check statistics
		if results.Stats.TotalTrials != config.NumIterations*len(config.SNRRange)*2 {
			t.Errorf("Total trials mismatch: expected %d, got %d", 
				config.NumIterations*len(config.SNRRange)*2, results.Stats.TotalTrials)
		}

		if results.Stats.TrialsPerSecond <= 0 {
			t.Errorf("Invalid trials per second: %f", results.Stats.TrialsPerSecond)
		}
	})
}

// Helper functions for Monte Carlo testing

// runMonteCarloTrial runs a single Monte Carlo trial series for AM
func runMonteCarloTrial(params SignalParams, targetSNR float64, numTrials int) float64 {
	snrSum := 0.0
	validTrials := 0
	
	for trial := 0; trial < numTrials; trial++ {
		originalMessage := generateBaseband(params)
		amSignal := generateAM(params)
		noisySignal := addAWGN(amSignal, targetSNR)
		demodulated := demodulateAM(noisySignal)
		
		outputSNR := calculateSNR(originalMessage, demodulated)
		if !math.IsNaN(outputSNR) && !math.IsInf(outputSNR, 0) && math.Abs(outputSNR) < 100 {
			snrSum += outputSNR
			validTrials++
		}
	}
	
	if validTrials == 0 {
		return 0
	}
	
	return snrSum / float64(validTrials)
}

// runMonteCarloTrialFM runs a single Monte Carlo trial series for FM
func runMonteCarloTrialFM(params SignalParams, targetSNR float64, numTrials int) float64 {
	snrSum := 0.0
	validTrials := 0
	
	for trial := 0; trial < numTrials; trial++ {
		originalMessage := generateBaseband(params)
		fmSignal := generateFM(params)
		noisySignal := addAWGN(fmSignal, targetSNR)
		demodulated := demodulateFM(noisySignal, params)
		
		// Align signals for fair comparison
		aligned := alignSignals(originalMessage.Values, demodulated.Values)
		alignedSignal := Signal{Time: originalMessage.Time, Values: aligned}
		
		outputSNR := calculateSNR(originalMessage, alignedSignal)
		if !math.IsNaN(outputSNR) && !math.IsInf(outputSNR, 0) && math.Abs(outputSNR) < 100 {
			snrSum += outputSNR
			validTrials++
		}
	}
	
	if validTrials == 0 {
		return 0
	}
	
	return snrSum / float64(validTrials)
}

// BenchmarkSNRCalculation benchmarks SNR calculation performance
func BenchmarkSNRCalculation(b *testing.B) {
	params := SignalParams{
		SamplingRate: 10000,
		Duration:     0.1,
		MessageFreq:  100,
		CarrierFreq:  1000,
		MessageAmp:   1.0,
		CarrierAmp:   1.0,
	}

	cleanSignal := generateCarrier(params)
	noisySignal := addAWGN(cleanSignal, 10.0)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_ = calculateSNR(cleanSignal, noisySignal)
	}
}

// BenchmarkMonteCarloTrial benchmarks a single Monte Carlo trial
func BenchmarkMonteCarloTrial(b *testing.B) {
	params := SignalParams{
		SamplingRate:  10000,
		Duration:      0.05, // Shorter for benchmarking
		MessageFreq:   100,
		CarrierFreq:   1000,
		MessageAmp:    1.0,
		CarrierAmp:    1.0,
		ModulationIdx: 0.5,
	}

	rand.Seed(12345)
	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		originalMessage := generateBaseband(params)
		amSignal := generateAM(params)
		noisySignal := addAWGN(amSignal, 10.0)
		demodulated := demodulateAM(noisySignal)
		_ = calculateSNR(originalMessage, demodulated)
	}
}