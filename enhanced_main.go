package main

import (
	"fmt"
	"math/rand"
	"runtime"
	"time"
)

func runEnhancedSimulation() {
	fmt.Println("🧩 AM/FM Performance Analysis - Enhanced Monte Carlo Simulation")
	fmt.Println("================================================================")
	fmt.Printf("System: %d CPUs available, Go version: %s\n", runtime.NumCPU(), runtime.Version())
	fmt.Println()

	// Define enhanced signal parameters
	amParams := SignalParams{
		SamplingRate:  10000, // 10 kHz
		Duration:      0.1,   // 100 ms
		MessageFreq:   50,    // 50 Hz
		CarrierFreq:   1000,  // 1 kHz
		MessageAmp:    1.0,
		CarrierAmp:    1.0,
		ModulationIdx: 0.5, // 50% modulation for AM
	}

	fmParams := SignalParams{
		SamplingRate:  10000, // 10 kHz
		Duration:      0.1,   // 100 ms
		MessageFreq:   50,    // 50 Hz
		CarrierFreq:   1000,  // 1 kHz
		MessageAmp:    1.0,
		CarrierAmp:    1.0,
		ModulationIdx: 200, // Higher frequency deviation for FM
	}

	// Phase 4: Enhanced Performance Measurement
	fmt.Println("📊 Phase 4: Enhanced Performance Measurement")
	fmt.Println("==========================================")

	snrRange := []float64{-10, -5, 0, 5, 10, 15, 20, 25, 30}
	numTrials := 200 // Increased for better statistics

	fmt.Printf("Testing %d SNR points with %d trials each...\n", len(snrRange), numTrials)

	// Run enhanced performance measurement
	amResults := simulateSNRPerformance(AM, amParams, snrRange, numTrials)
	fmResults := simulateSNRPerformance(FM, fmParams, snrRange, numTrials)

	// Validate results
	if err := ValidateSimulationResults(amResults); err != nil {
		fmt.Printf("AM results validation failed: %v\n", err)
		return
	}
	if err := ValidateSimulationResults(fmResults); err != nil {
		fmt.Printf("FM results validation failed: %v\n", err)
		return
	}

	// Save detailed results
	if err := savePerformanceResultsCSV(amResults, fmResults, "detailed_performance_results.csv"); err != nil {
		fmt.Printf("Error saving performance results: %v\n", err)
	}

	// Phase 5: Optimized Monte Carlo Simulation with Reproducibility Testing
	fmt.Println("\n⚡ Phase 5: Optimized Monte Carlo Simulation")
	fmt.Println("==========================================")

	// Test reproducibility
	testSeed := int64(42)
	if err := ReproducibilityTest(amParams, testSeed, 50); err != nil {
		fmt.Printf("Reproducibility test failed: %v\n", err)
		return
	}

	// Performance benchmark
	fmt.Println("Running performance benchmark...")
	PerformanceBenchmark(amParams, fmParams, 50, []float64{0, 10, 20})

	// Optimized simulation with parallel processing
	fmt.Println("\nRunning optimized Monte Carlo simulation...")
	
	config := SimulationConfig{
		Seed:          time.Now().UnixNano(), // Use current time for variety
		NumTrials:     100,                   // Balanced for speed vs accuracy
		NumWorkers:    AdaptiveWorkerCount(),
		SNRRange:      snrRange,
		UseParallel:   true,
		PrintProgress: true,
	}

	amResultsOpt, fmResultsOpt, stats, err := OptimizedMonteCarloSimulation(amParams, fmParams, config)
	if err != nil {
		fmt.Printf("Optimized simulation failed: %v\n", err)
		return
	}

	fmt.Printf("\n✅ Optimized simulation completed successfully!\n")
	fmt.Printf("Performance: %.0f trials/second using %d workers\n", stats.TrialsPerSecond, stats.WorkersUsed)

	// Phase 6: Advanced Visualization & Comparison
	fmt.Println("\n📈 Phase 6: Advanced Visualization & Comparison")
	fmt.Println("==============================================")

	// Generate sample signals for visualization
	amSignal := generateAM(amParams)
	fmSignal := generateFM(fmParams)

	// Create comprehensive visualization report
	if err := CreateComprehensiveReport(amResultsOpt, fmResultsOpt, amSignal, fmSignal); err != nil {
		fmt.Printf("Error creating visualization report: %v\n", err)
		return
	}

	// Analyze FM superiority quantitatively
	AnalyzeFMSuperiority(amResultsOpt, fmResultsOpt)

	// Summary Statistics
	fmt.Println("\n📋 Simulation Summary")
	fmt.Println("====================")
	fmt.Printf("Total simulation time: %v\n", stats.Duration)
	fmt.Printf("Total trials executed: %d\n", stats.TotalTrials)
	fmt.Printf("Memory usage: %.2f MB\n", float64(stats.MemoryUsed)/1024/1024)
	fmt.Printf("Seed used (for reproducibility): %d\n", config.Seed)

	// Performance comparison table
	fmt.Println("\n📊 Performance Summary Table")
	fmt.Println("SNR_in | AM_out | FM_out | FM_StdDev | AM_StdDev | FM_Advantage")
	fmt.Println("-------|--------|--------|-----------|-----------|-------------")
	for i := range amResultsOpt {
		advantage := fmResultsOpt[i].OutputSNR_dB - amResultsOpt[i].OutputSNR_dB
		fmt.Printf("%6.1f | %6.2f | %6.2f |   %7.3f |   %7.3f |   %+8.2f\n",
			amResultsOpt[i].InputSNR_dB,
			amResultsOpt[i].OutputSNR_dB,
			fmResultsOpt[i].OutputSNR_dB,
			fmResultsOpt[i].StdDev,
			amResultsOpt[i].StdDev,
			advantage)
	}

	fmt.Println("\n🎯 Key Findings:")
	fmt.Println("================")
	
	// Calculate overall statistics
	totalAdvantage := 0.0
	advantageCount := 0
	for i := range amResultsOpt {
		advantage := fmResultsOpt[i].OutputSNR_dB - amResultsOpt[i].OutputSNR_dB
		if advantage > 0.1 { // Small threshold to account for numerical precision
			totalAdvantage += advantage
			advantageCount++
		}
	}

	if advantageCount > 0 {
		avgAdvantage := totalAdvantage / float64(advantageCount)
		fmt.Printf("• FM shows advantage at %d out of %d SNR levels\n", advantageCount, len(amResultsOpt))
		fmt.Printf("• Average FM advantage: %.2f dB\n", avgAdvantage)
	} else {
		fmt.Println("• Current implementation shows no consistent FM advantage")
		fmt.Println("• This suggests the FM demodulator needs optimization")
	}

	fmt.Printf("• Simulation reproducible with seed: %d\n", config.Seed)
	fmt.Printf("• Peak performance: %.0f trials/second\n", stats.TrialsPerSecond)

	fmt.Println("\n📁 Output Files Generated:")
	fmt.Println("=========================")
	fmt.Println("📊 Data Files:")
	fmt.Println("  - detailed_performance_results.csv")
	fmt.Println("  - snr_results.csv")
	fmt.Println("  - baseband_signal.csv")
	fmt.Println()
	fmt.Println("📈 Visualization Files:")
	fmt.Println("  - comprehensive_snr_comparison.png")
	fmt.Println("  - fm_advantage.png")
	fmt.Println("  - spectral_comparison.png")
	fmt.Println("  - modulated_signals_comparison.png")
	fmt.Println()
	fmt.Println("✅ Enhanced AM/FM Performance Analysis Complete!")
	fmt.Println("Check the generated files for detailed analysis and visualization.")
}

func runEnhanced() {
	// Set random seed for reproducibility demonstration
	rand.Seed(time.Now().UnixNano())
	
	// Run the enhanced simulation
	runEnhancedSimulation()
}
