package main

import (
	"fmt"
	"math"
	"math/rand"
	"runtime"
	"sync"
	"time"
)

// MonteCarloConfig holds configuration for Phase 5 simulation
type MonteCarloConfig struct {
	NumIterations    int       // N iterations per SNR point (e.g., 1000)
	SNRRange        []float64 // SNR points to test
	Seed            int64     // For reproducibility
	UseParallel     bool      // Enable parallel processing
	NumWorkers      int       // Number of goroutines
	ProgressReport  bool      // Show progress updates
	SaveDetailed    bool      // Save detailed trial data
}

// DefaultMonteCarloConfig returns recommended configuration for Phase 5
func DefaultMonteCarloConfig() MonteCarloConfig {
	return MonteCarloConfig{
		NumIterations:   1000,  // 1000 iterations per SNR point as recommended
		SNRRange:       []float64{-10, -5, 0, 5, 10, 15, 20, 25, 30, 35},
		Seed:           42,     // Fixed seed for reproducibility
		UseParallel:    true,
		NumWorkers:     runtime.NumCPU(),
		ProgressReport: true,
		SaveDetailed:   false,
	}
}

// Phase5MonteCarloResults holds complete Phase 5 results
type Phase5MonteCarloResults struct {
	AMResults       []PerformanceResult
	FMResults       []PerformanceResult
	Config          MonteCarloConfig
	Stats           Phase5Stats
	DetailedTrials  []SNRMeasurement // Optional detailed trial data
}

// Phase5Stats holds comprehensive statistics
type Phase5Stats struct {
	TotalTrials        int
	Duration          time.Duration
	TrialsPerSecond   float64
	MemoryUsed        uint64
	WorkersUsed       int
	ReproducibilitySeed int64
	ParallelEfficiency float64 // Parallel speedup factor
}

// RunPhase5MonteCarloSimulation executes the complete Phase 5 simulation
func RunPhase5MonteCarloSimulation(amParams, fmParams SignalParams, config MonteCarloConfig) (*Phase5MonteCarloResults, error) {
	fmt.Println("🎯 Phase 5: Monte Carlo Simulation")
	fmt.Println("=================================")
	fmt.Printf("Configuration: %d iterations per SNR point, %d SNR levels\n", 
		config.NumIterations, len(config.SNRRange))
	fmt.Printf("Seed: %d (for reproducibility)\n", config.Seed)
	fmt.Printf("Workers: %d, Parallel: %v\n", config.NumWorkers, config.UseParallel)

	startTime := time.Now()
	var memStart runtime.MemStats
	runtime.ReadMemStats(&memStart)

	// Set seed for reproducibility
	rand.Seed(config.Seed)

	// Run simulation
	var amResults, fmResults []PerformanceResult
	var detailedTrials []SNRMeasurement

	if config.UseParallel {
		amResults, fmResults, detailedTrials = runParallelMonteCarloSimulation(
			amParams, fmParams, config)
	} else {
		amResults, fmResults, detailedTrials = runSequentialMonteCarloSimulation(
			amParams, fmParams, config)
	}

	// Calculate statistics
	duration := time.Since(startTime)
	totalTrials := config.NumIterations * len(config.SNRRange) * 2 // AM + FM
	trialsPerSecond := float64(totalTrials) / duration.Seconds()

	var memEnd runtime.MemStats
	runtime.ReadMemStats(&memEnd)
	memoryUsed := memEnd.TotalAlloc - memStart.TotalAlloc

	stats := Phase5Stats{
		TotalTrials:        totalTrials,
		Duration:          duration,
		TrialsPerSecond:   trialsPerSecond,
		MemoryUsed:        memoryUsed,
		WorkersUsed:       config.NumWorkers,
		ReproducibilitySeed: config.Seed,
	}

	results := &Phase5MonteCarloResults{
		AMResults:      amResults,
		FMResults:      fmResults,
		Config:         config,
		Stats:          stats,
		DetailedTrials: detailedTrials,
	}

	fmt.Printf("✅ Phase 5 completed in %v\n", duration)
	fmt.Printf("Performance: %.0f trials/second\n", trialsPerSecond)
	fmt.Printf("Memory usage: %.2f MB\n", float64(memoryUsed)/1024/1024)

	return results, nil
}

// runParallelMonteCarloSimulation runs the simulation using goroutines
func runParallelMonteCarloSimulation(amParams, fmParams SignalParams, config MonteCarloConfig) (
	[]PerformanceResult, []PerformanceResult, []SNRMeasurement) {

	amResults := make([]PerformanceResult, len(config.SNRRange))
	fmResults := make([]PerformanceResult, len(config.SNRRange))
	var detailedTrials []SNRMeasurement

	// Use work pool pattern
	type job struct {
		snrIndex int
		targetSNR float64
	}

	jobs := make(chan job, len(config.SNRRange))
	amResultsChan := make(chan struct{ index int; result PerformanceResult }, len(config.SNRRange))
	fmResultsChan := make(chan struct{ index int; result PerformanceResult }, len(config.SNRRange))

	// Start workers
	var wg sync.WaitGroup
	for w := 0; w < config.NumWorkers; w++ {
		wg.Add(1)
		go func(workerID int) {
			defer wg.Done()
			// Each worker gets its own RNG for thread safety
			workerRand := rand.New(rand.NewSource(config.Seed + int64(workerID)))
			
			for j := range jobs {
				// Process AM
				amResult := runSingleSNRSimulation(AM, amParams, j.targetSNR, 
					config.NumIterations, workerRand)
				amResult.InputSNR_dB = j.targetSNR
				amResultsChan <- struct{ index int; result PerformanceResult }{
					index: j.snrIndex, result: amResult}

				// Process FM  
				fmResult := runSingleSNRSimulation(FM, fmParams, j.targetSNR, 
					config.NumIterations, workerRand)
				fmResult.InputSNR_dB = j.targetSNR
				fmResultsChan <- struct{ index int; result PerformanceResult }{
					index: j.snrIndex, result: fmResult}
			}
		}(w)
	}

	// Send jobs
	for i, snr := range config.SNRRange {
		jobs <- job{snrIndex: i, targetSNR: snr}
	}
	close(jobs)

	// Collect results
	go func() {
		wg.Wait()
		close(amResultsChan)
		close(fmResultsChan)
	}()

	// Collect AM results
	for result := range amResultsChan {
		amResults[result.index] = result.result
	}

	// Collect FM results
	for result := range fmResultsChan {
		fmResults[result.index] = result.result
	}

	return amResults, fmResults, detailedTrials
}

// runSequentialMonteCarloSimulation runs simulation sequentially
func runSequentialMonteCarloSimulation(amParams, fmParams SignalParams, config MonteCarloConfig) (
	[]PerformanceResult, []PerformanceResult, []SNRMeasurement) {

	amResults := make([]PerformanceResult, len(config.SNRRange))
	fmResults := make([]PerformanceResult, len(config.SNRRange))
	var detailedTrials []SNRMeasurement

	mainRand := rand.New(rand.NewSource(config.Seed))

	for i, snr := range config.SNRRange {
		if config.ProgressReport {
			fmt.Printf("Processing SNR %.1f dB (%d/%d)...\n", snr, i+1, len(config.SNRRange))
		}

		// AM simulation
		amResult := runSingleSNRSimulation(AM, amParams, snr, config.NumIterations, mainRand)
		amResult.InputSNR_dB = snr
		amResults[i] = amResult

		// FM simulation
		fmResult := runSingleSNRSimulation(FM, fmParams, snr, config.NumIterations, mainRand)
		fmResult.InputSNR_dB = snr
		fmResults[i] = fmResult
	}

	return amResults, fmResults, detailedTrials
}

// runSingleSNRSimulation runs multiple trials for a single SNR point
func runSingleSNRSimulation(modType ModulationType, params SignalParams, 
	targetSNR float64, numIterations int, rng *rand.Rand) PerformanceResult {

	measurements := make([]float64, numIterations)

	for trial := 0; trial < numIterations; trial++ {
		// Generate original message
		originalMessage := generateBaseband(params)

		// Generate modulated signal
		var modulatedSignal Signal
		switch modType {
		case AM:
			modulatedSignal = generateAM(params)
		case FM:
			modulatedSignal = generateFM(params)
		}

		// Add noise with custom RNG
		noisySignal := addAWGNWithRNG(modulatedSignal, targetSNR, rng)

		// Demodulate
		var demodulatedSignal Signal
		switch modType {
		case AM:
			demodulatedSignal = demodulateAM(noisySignal)
		case FM:
			demodulatedSignal = demodulateFM(noisySignal, params)
		}

		// Calculate output SNR
		outputSNR := computeOutputSNR(originalMessage, demodulatedSignal)
		measurements[trial] = outputSNR
	}

	// Calculate statistics
	mean := calculateMean(measurements)
	stdDev := calculateStdDev(measurements, mean)

	return PerformanceResult{
		InputSNR_dB:    targetSNR,
		OutputSNR_dB:   mean,
		StdDev:         stdDev,
		ModulationType: modType,
		NumTrials:      numIterations,
	}
}

// addAWGNWithRNG adds AWGN using provided random number generator
func addAWGNWithRNG(signal Signal, snrDB float64, rng *rand.Rand) Signal {
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

	// Add Gaussian noise using provided RNG
	for i, val := range signal.Values {
		noise := rng.NormFloat64() * noiseStdDev
		noisySignal.Values[i] = val + noise
	}

	return noisySignal
}

// calculateMean computes arithmetic mean
func calculateMean(values []float64) float64 {
	sum := 0.0
	for _, val := range values {
		sum += val
	}
	return sum / float64(len(values))
}

// calculateStdDev computes standard deviation
func calculateStdDev(values []float64, mean float64) float64 {
	sumSquares := 0.0
	for _, val := range values {
		diff := val - mean
		sumSquares += diff * diff
	}
	variance := sumSquares / float64(len(values)-1)
	return math.Sqrt(variance)
}

// VerifyReproducibility tests that same seed produces identical results
func VerifyReproducibility(amParams, fmParams SignalParams) error {
	fmt.Println("\n🔄 Testing Reproducibility...")
	
	testSeed := int64(12345)
	testConfig := MonteCarloConfig{
		NumIterations:  50,
		SNRRange:      []float64{0, 10, 20},
		Seed:          testSeed,
		UseParallel:   false, // Use sequential for exact reproducibility
		NumWorkers:    1,
		ProgressReport: false,
	}

	// Run first simulation
	results1, err := RunPhase5MonteCarloSimulation(amParams, fmParams, testConfig)
	if err != nil {
		return fmt.Errorf("first run failed: %v", err)
	}

	// Run second simulation with same seed
	results2, err := RunPhase5MonteCarloSimulation(amParams, fmParams, testConfig)
	if err != nil {
		return fmt.Errorf("second run failed: %v", err)
	}

	// Compare results
	tolerance := 1e-10 // Very strict tolerance for reproducibility
	for i := range results1.AMResults {
		diff := math.Abs(results1.AMResults[i].OutputSNR_dB - results2.AMResults[i].OutputSNR_dB)
		if diff > tolerance {
			return fmt.Errorf("AM results differ at SNR %.1f: %.6f vs %.6f", 
				results1.AMResults[i].InputSNR_dB, 
				results1.AMResults[i].OutputSNR_dB, 
				results2.AMResults[i].OutputSNR_dB)
		}
	}

	for i := range results1.FMResults {
		diff := math.Abs(results1.FMResults[i].OutputSNR_dB - results2.FMResults[i].OutputSNR_dB)
		if diff > tolerance {
			return fmt.Errorf("FM results differ at SNR %.1f: %.6f vs %.6f", 
				results1.FMResults[i].InputSNR_dB, 
				results1.FMResults[i].OutputSNR_dB, 
				results2.FMResults[i].OutputSNR_dB)
		}
	}

	fmt.Printf("✅ Reproducibility verified: same seed (%d) → identical results\n", testSeed)
	return nil
}

// BenchmarkPhase5Performance runs comprehensive performance benchmarks
func BenchmarkPhase5Performance(amParams, fmParams SignalParams) {
	fmt.Println("\n⚡ Phase 5 Performance Benchmark")
	fmt.Println("===============================")

	testConfig := MonteCarloConfig{
		NumIterations:  100,
		SNRRange:      []float64{0, 10, 20},
		Seed:          12345,
		ProgressReport: false,
	}

	workerCounts := []int{1, 2, 4, 8}
	if runtime.NumCPU() > 8 {
		workerCounts = append(workerCounts, runtime.NumCPU())
	}

	fmt.Printf("Workers | Duration  | Trials/sec | Memory(MB) | Speedup\n")
	fmt.Printf("--------|-----------|------------|------------|--------\n")

	var sequentialTime time.Duration
	
	for i, workers := range workerCounts {
		config := testConfig
		config.NumWorkers = workers
		config.UseParallel = workers > 1

		results, err := RunPhase5MonteCarloSimulation(amParams, fmParams, config)
		if err != nil {
			fmt.Printf("Benchmark failed with %d workers: %v\n", workers, err)
			continue
		}

		if i == 0 {
			sequentialTime = results.Stats.Duration
		}

		speedup := sequentialTime.Seconds() / results.Stats.Duration.Seconds()
		
		fmt.Printf("%7d | %9s | %10.0f | %10.2f | %6.2fx\n",
			workers,
			results.Stats.Duration.Round(time.Millisecond),
			results.Stats.TrialsPerSecond,
			float64(results.Stats.MemoryUsed)/1024/1024,
			speedup)
	}
	
	fmt.Printf("\nOptimal configuration: %d workers\n", runtime.NumCPU())
}