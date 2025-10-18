package main

import (
	"fmt"
	"math"
	"runtime"
	"testing"
	"time"
)

// TestPhase7ComprehensiveValidation runs all Phase 7 validation tests
func TestPhase7ComprehensiveValidation(t *testing.T) {
	t.Run("System Integration Test", func(t *testing.T) {
		// Test complete pipeline from signal generation to final results
		runner := NewPhases5And6Runner()
		
		// Use smaller parameters for testing
		testConfig := MonteCarloConfig{
			NumIterations:  20,
			SNRRange:      []float64{0, 10, 20},
			Seed:          12345,
			UseParallel:   false,
			NumWorkers:    1,
			ProgressReport: false,
		}
		
		// Run reduced Phase 5 simulation
		results, err := RunPhase5MonteCarloSimulation(runner.AMParams, runner.FMParams, testConfig)
		if err != nil {
			t.Fatalf("Phase 5 integration test failed: %v", err)
		}
		
		// Validate all components worked correctly
		if len(results.AMResults) == 0 || len(results.FMResults) == 0 {
			t.Error("No results generated from integration test")
		}
		
		// Test Phase 6 visualization integration
		err = CreatePhase6ComprehensiveReport(results)
		if err != nil {
			t.Errorf("Phase 6 integration test failed: %v", err)
		}
	})

	t.Run("Error Handling and Robustness", func(t *testing.T) {
		// Test with invalid parameters
		invalidParams := SignalParams{
			SamplingRate: -1000, // Invalid
			Duration:     0.1,
			MessageFreq:  100,
			CarrierFreq:  1000,
			MessageAmp:   1.0,
			CarrierAmp:   1.0,
		}
		
		// Should handle gracefully (might produce empty signals but not crash)
		signal := generateBaseband(invalidParams)
		if len(signal.Values) != 0 {
			// If it generates something, ensure it's valid
			for i, v := range signal.Values {
				if math.IsNaN(v) || math.IsInf(v, 0) {
					t.Errorf("Invalid signal value at index %d: %v", i, v)
					break
				}
			}
		}
	})

	t.Run("Memory Usage and Leaks", func(t *testing.T) {
		var memStart, memEnd runtime.MemStats
		runtime.GC()
		runtime.ReadMemStats(&memStart)
		
		// Run memory-intensive operations
		params := SignalParams{
			SamplingRate:  44100, // High sample rate
			Duration:      1.0,   // Long duration
			MessageFreq:   1000,
			CarrierFreq:   10000,
			MessageAmp:    1.0,
			CarrierAmp:    1.0,
			ModulationIdx: 0.5,
		}
		
		// Generate large signals multiple times
		for i := 0; i < 10; i++ {
			amSignal := generateAM(params)
			noisySignal := addAWGN(amSignal, 10.0)
			_ = demodulateAM(noisySignal)
		}
		
		runtime.GC()
		runtime.ReadMemStats(&memEnd)
		
		memUsed := memEnd.TotalAlloc - memStart.TotalAlloc
		t.Logf("Memory used: %.2f MB", float64(memUsed)/1024/1024)
		
		// Memory usage should be reasonable (not more than 100MB for this test)
		if memUsed > 100*1024*1024 {
			t.Errorf("Excessive memory usage: %.2f MB", float64(memUsed)/1024/1024)
		}
	})

	t.Run("Thread Safety", func(t *testing.T) {
		// Test parallel execution safety
		params := SignalParams{
			SamplingRate:  8000,
			Duration:      0.1,
			MessageFreq:   100,
			CarrierFreq:   1000,
			MessageAmp:    1.0,
			CarrierAmp:    1.0,
			ModulationIdx: 0.5,
		}
		
		numGoroutines := 10
		done := make(chan bool, numGoroutines)
		errors := make(chan error, numGoroutines)
		
		// Run concurrent signal processing
		for i := 0; i < numGoroutines; i++ {
			go func(id int) {
				defer func() {
					if r := recover(); r != nil {
						errors <- &ThreadSafetyError{GoRoutineID: id, PanicValue: r}
					} else {
						done <- true
					}
				}()
				
				// Each goroutine does complete signal processing
				originalMessage := generateBaseband(params)
				amSignal := generateAM(params)
				noisySignal := addAWGN(amSignal, 10.0)
				demodulated := demodulateAM(noisySignal)
				_ = calculateSNR(originalMessage, demodulated)
			}(i)
		}
		
		// Wait for completion
		completed := 0
		for completed < numGoroutines {
			select {
			case <-done:
				completed++
			case err := <-errors:
				t.Errorf("Thread safety issue: %v", err)
				completed++
			case <-time.After(5 * time.Second):
				t.Error("Thread safety test timeout")
				return
			}
		}
	})
}

// ThreadSafetyError represents a thread safety test error
type ThreadSafetyError struct {
	GoRoutineID int
	PanicValue  interface{}
}

func (e *ThreadSafetyError) Error() string {
	return fmt.Sprintf("goroutine %d panicked: %v", e.GoRoutineID, e.PanicValue)
}

// TestPerformanceBenchmarks runs comprehensive performance tests
func TestPerformanceBenchmarks(t *testing.T) {
	t.Run("Scalability Test", func(t *testing.T) {
		// Test performance with different signal lengths
		durations := []float64{0.01, 0.1, 0.5, 1.0}
		
		for _, duration := range durations {
			params := SignalParams{
				SamplingRate:  8000,
				Duration:      duration,
				MessageFreq:   100,
				CarrierFreq:   1000,
				MessageAmp:    1.0,
				CarrierAmp:    1.0,
				ModulationIdx: 0.5,
			}
			
			start := time.Now()
			
			// Complete signal processing pipeline
			originalMessage := generateBaseband(params)
			amSignal := generateAM(params)
			noisySignal := addAWGN(amSignal, 10.0)
			demodulated := demodulateAM(noisySignal)
			_ = calculateSNR(originalMessage, demodulated)
			
			elapsed := time.Since(start)
			samplesPerSecond := float64(len(amSignal.Values)) / elapsed.Seconds()
			
			t.Logf("Duration: %.2fs, Samples: %d, Processing rate: %.0f samples/sec", 
				duration, len(amSignal.Values), samplesPerSecond)
			
			// Should process at least 100k samples per second
			if samplesPerSecond < 100000 {
				t.Errorf("Poor processing performance: %.0f samples/sec for duration %.2fs", 
					samplesPerSecond, duration)
			}
		}
	})

	t.Run("Parallel Efficiency Test", func(t *testing.T) {
		config := MonteCarloConfig{
			NumIterations:  10,
			SNRRange:      []float64{0, 10},
			Seed:          12345,
			ProgressReport: false,
		}
		
		params := SignalParams{
			SamplingRate:  8000,
			Duration:      0.1,
			MessageFreq:   100,
			CarrierFreq:   1000,
			MessageAmp:    1.0,
			CarrierAmp:    1.0,
			ModulationIdx: 0.5,
		}
		
		// Sequential timing
		config.UseParallel = false
		config.NumWorkers = 1
		
		start := time.Now()
		_, err := RunPhase5MonteCarloSimulation(params, params, config)
		if err != nil {
			t.Fatalf("Sequential test failed: %v", err)
		}
		sequentialTime := time.Since(start)
		
		// Parallel timing
		config.UseParallel = true
		config.NumWorkers = runtime.NumCPU()
		
		start = time.Now()
		_, err = RunPhase5MonteCarloSimulation(params, params, config)
		if err != nil {
			t.Fatalf("Parallel test failed: %v", err)
		}
		parallelTime := time.Since(start)
		
		speedup := sequentialTime.Seconds() / parallelTime.Seconds()
		efficiency := speedup / float64(config.NumWorkers)
		
		t.Logf("Sequential: %v, Parallel (%d workers): %v, Speedup: %.2fx, Efficiency: %.2f", 
			sequentialTime, config.NumWorkers, parallelTime, speedup, efficiency)
		
		// Should show some speedup (at least 1.5x for multi-core systems)
		if config.NumWorkers > 1 && speedup < 1.5 {
			t.Errorf("Poor parallel speedup: %.2fx with %d workers", speedup, config.NumWorkers)
		}
	})
}

// TestNumericalStability tests numerical precision and stability
func TestNumericalStability(t *testing.T) {
	t.Run("High Precision SNR", func(t *testing.T) {
		params := SignalParams{
			SamplingRate: 8000,
			Duration:     1.0, // Long signal for precision
			MessageFreq:  100,
			CarrierFreq:  1000,
			MessageAmp:   1.0,
			CarrierAmp:   1.0,
		}
		
		cleanSignal := generateCarrier(params)
		
		// Test very high SNR precision
		highSNR := 60.0
		noisySignal := addAWGN(cleanSignal, highSNR)
		measuredSNR := calculateSNR(cleanSignal, noisySignal)
		
		// Should be accurate even at high SNR
		if math.Abs(measuredSNR-highSNR) > 1.0 {
			t.Errorf("High SNR precision loss: target = %.1f, measured = %.2f", 
				highSNR, measuredSNR)
		}
	})

	t.Run("Very Low Signal Levels", func(t *testing.T) {
		params := SignalParams{
			SamplingRate: 8000,
			Duration:     0.1,
			MessageFreq:  100,
			CarrierFreq:  1000,
			MessageAmp:   1e-6, // Very low amplitude
			CarrierAmp:   1e-6,
		}
		
		// Should handle very small signals without numerical issues
		signal := generateCarrier(params)
		if len(signal.Values) == 0 {
			t.Error("Failed to generate very low level signal")
		}
		
		// Check for numerical stability
		for i, v := range signal.Values {
			if math.IsNaN(v) || math.IsInf(v, 0) {
				t.Errorf("Numerical instability with low signal at sample %d: %v", i, v)
				break
			}
		}
	})

	t.Run("Large Signal Levels", func(t *testing.T) {
		params := SignalParams{
			SamplingRate: 8000,
			Duration:     0.1,
			MessageFreq:  100,
			CarrierFreq:  1000,
			MessageAmp:   1e6, // Very high amplitude
			CarrierAmp:   1e6,
		}
		
		// Should handle very large signals without overflow
		signal := generateCarrier(params)
		if len(signal.Values) == 0 {
			t.Error("Failed to generate very high level signal")
		}
		
		// Check for numerical stability
		for i, v := range signal.Values {
			if math.IsNaN(v) || math.IsInf(v, 0) {
				t.Errorf("Numerical overflow with high signal at sample %d: %v", i, v)
				break
			}
		}
	})
}

// TestEdgeCasesAndBoundaryConditions tests system limits
func TestEdgeCasesAndBoundaryConditions(t *testing.T) {
	t.Run("Extreme Parameter Ranges", func(t *testing.T) {
		testCases := []struct {
			name   string
			params SignalParams
		}{
			{
				name: "Very High Sample Rate",
				params: SignalParams{
					SamplingRate: 192000, // 192 kHz
					Duration:     0.01,   // Short to limit memory
					MessageFreq:  1000,
					CarrierFreq:  10000,
				},
			},
			{
				name: "Very Low Sample Rate",
				params: SignalParams{
					SamplingRate: 1000, // 1 kHz
					Duration:     0.1,
					MessageFreq:  10,  // Well below Nyquist
					CarrierFreq:  100, // Well below Nyquist
				},
			},
			{
				name: "Very Short Duration",
				params: SignalParams{
					SamplingRate: 8000,
					Duration:     0.001, // 1 ms
					MessageFreq:  100,
					CarrierFreq:  1000,
				},
			},
		}
		
		for _, tc := range testCases {
			t.Run(tc.name, func(t *testing.T) {
				tc.params.MessageAmp = 1.0
				tc.params.CarrierAmp = 1.0
				tc.params.ModulationIdx = 0.5
				
				// Should not crash with extreme parameters
				signal := generateAM(tc.params)
				
				if len(signal.Values) > 0 {
					// If signal is generated, it should be valid
					allValid := true
					for _, v := range signal.Values {
						if math.IsNaN(v) || math.IsInf(v, 0) {
							allValid = false
							break
						}
					}
					if !allValid {
						t.Errorf("Invalid values in signal with %s", tc.name)
					}
				}
			})
		}
	})

	t.Run("Boundary SNR Values", func(t *testing.T) {
		params := SignalParams{
			SamplingRate: 8000,
			Duration:     0.1,
			MessageFreq:  100,
			CarrierFreq:  1000,
			MessageAmp:   1.0,
			CarrierAmp:   1.0,
		}
		
		signal := generateCarrier(params)
		
		extremeSNRs := []float64{-100, -50, 50, 100}
		
		for _, snr := range extremeSNRs {
			noisySignal := addAWGN(signal, snr)
			
			// Should not produce invalid values
			allValid := true
			for _, v := range noisySignal.Values {
				if math.IsNaN(v) || math.IsInf(v, 0) {
					allValid = false
					break
				}
			}
			if !allValid {
				t.Errorf("Invalid noisy signal values at SNR %.1f dB", snr)
			}
			
			// SNR calculation should work
			measuredSNR := calculateSNR(signal, noisySignal)
			if math.IsNaN(measuredSNR) || math.IsInf(measuredSNR, 0) {
				t.Errorf("Invalid SNR calculation at target SNR %.1f dB: got %f", snr, measuredSNR)
			}
		}
	})
}

// BenchmarkFullPipeline benchmarks the complete signal processing pipeline
func BenchmarkFullPipeline(b *testing.B) {
	params := SignalParams{
		SamplingRate:  8000,
		Duration:      0.1,
		MessageFreq:   100,
		CarrierFreq:   1000,
		MessageAmp:    1.0,
		CarrierAmp:    1.0,
		ModulationIdx: 0.5,
	}

	b.Run("Complete AM Pipeline", func(b *testing.B) {
		for i := 0; i < b.N; i++ {
			originalMessage := generateBaseband(params)
			amSignal := generateAM(params)
			noisySignal := addAWGN(amSignal, 10.0)
			demodulated := demodulateAM(noisySignal)
			_ = calculateSNR(originalMessage, demodulated)
		}
	})

	b.Run("Complete FM Pipeline", func(b *testing.B) {
		fmParams := params
		fmParams.ModulationIdx = 100
		
		for i := 0; i < b.N; i++ {
			originalMessage := generateBaseband(fmParams)
			fmSignal := generateFM(fmParams)
			noisySignal := addAWGN(fmSignal, 10.0)
			demodulated := demodulateFM(noisySignal, fmParams)
			aligned := alignSignals(originalMessage.Values, demodulated.Values)
			alignedSignal := Signal{Time: originalMessage.Time, Values: aligned}
			_ = calculateSNR(originalMessage, alignedSignal)
		}
	})
}

// TestResultValidation validates all test results and generates summary
func TestResultValidation(t *testing.T) {
	t.Run("Phase 7 Summary Validation", func(t *testing.T) {
		// This test summarizes all Phase 7 validations
		validationResults := map[string]bool{
			"Signal Generation": true,
			"AWGN Noise":        true,
			"Demodulation":      true,
			"SNR Measurement":   true,
			"Monte Carlo":       true,
		}
		
		// Run quick validation of each component
		params := SignalParams{
			SamplingRate:  8000,
			Duration:      0.1,
			MessageFreq:   100,
			CarrierFreq:   1000,
			MessageAmp:    1.0,
			CarrierAmp:    1.0,
			ModulationIdx: 0.5,
		}
		
		// Test signal generation
		amSignal := generateAM(params)
		if len(amSignal.Values) == 0 {
			validationResults["Signal Generation"] = false
		}
		
		// Test AWGN
		noisySignal := addAWGN(amSignal, 10.0)
		if len(noisySignal.Values) != len(amSignal.Values) {
			validationResults["AWGN Noise"] = false
		}
		
		// Test demodulation
		demodulated := demodulateAM(noisySignal)
		if len(demodulated.Values) == 0 {
			validationResults["Demodulation"] = false
		}
		
		// Test SNR measurement
		originalMessage := generateBaseband(params)
		snr := calculateSNR(originalMessage, demodulated)
		if math.IsNaN(snr) || math.IsInf(snr, 0) {
			validationResults["SNR Measurement"] = false
		}
		
		// Test Monte Carlo (simplified)
		config := MonteCarloConfig{
			NumIterations:  5,
			SNRRange:      []float64{10},
			Seed:          12345,
			UseParallel:   false,
			NumWorkers:    1,
			ProgressReport: false,
		}
		_, err := RunPhase5MonteCarloSimulation(params, params, config)
		if err != nil {
			validationResults["Monte Carlo"] = false
		}
		
		// Summary report
		t.Log("Phase 7 Validation Summary:")
		t.Log("==========================")
		allPassed := true
		for component, passed := range validationResults {
			status := "✅ PASS"
			if !passed {
				status = "❌ FAIL"
				allPassed = false
			}
			t.Logf("%s: %s", component, status)
		}
		
		if !allPassed {
			t.Error("Some Phase 7 validations failed")
		} else {
			t.Log("\n🎉 All Phase 7 validations passed successfully!")
		}
	})
}