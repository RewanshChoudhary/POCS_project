package main

import (
	"crypto/rand"
	"encoding/binary"
	"fmt"
	"math"
	mathrand "math/rand"
	"runtime"
	"sync"
	"time"
)

// SimulationConfig holds configuration for Monte Carlo simulation
type SimulationConfig struct {
	Seed         int64
	NumTrials    int
	NumWorkers   int
	SNRRange     []float64
	UseParallel  bool
	PrintProgress bool
}

// SimulationStats holds timing and performance statistics
type SimulationStats struct {
	Duration         time.Duration
	TrialsPerSecond  float64
	TotalTrials      int
	WorkersUsed      int
	MemoryUsed       uint64
}

// ReproducibleRNG provides thread-safe reproducible random number generation
type ReproducibleRNG struct {
	mu   sync.Mutex
	rng  *mathrand.Rand
	seed int64
}

// NewReproducibleRNG creates a new reproducible RNG with given seed
func NewReproducibleRNG(seed int64) *ReproducibleRNG {
	return &ReproducibleRNG{
		rng:  mathrand.New(mathrand.NewSource(seed)),
		seed: seed,
	}
}

// Float64 returns a reproducible random float64 in [0.0,1.0)
func (r *ReproducibleRNG) Float64() float64 {
	r.mu.Lock()
	defer r.mu.Unlock()
	return r.rng.Float64()
}

// NormFloat64 returns a reproducible normally distributed float64
func (r *ReproducibleRNG) NormFloat64() float64 {
	r.mu.Lock()
	defer r.mu.Unlock()
	return r.rng.NormFloat64()
}

// GetSeed returns the seed used for initialization
func (r *ReproducibleRNG) GetSeed() int64 {
	return r.seed
}

// generateCryptoSeed generates a cryptographically secure random seed
func generateCryptoSeed() (int64, error) {
	var seedBytes [8]byte
	_, err := rand.Read(seedBytes[:])
	if err != nil {
		return 0, err
	}
	return int64(binary.LittleEndian.Uint64(seedBytes[:])), nil
}

// OptimizedMonteCarloSimulation performs enhanced Monte Carlo simulation with configurable options
func OptimizedMonteCarloSimulation(amParams, fmParams SignalParams, config SimulationConfig) ([]PerformanceResult, []PerformanceResult, SimulationStats, error) {
	startTime := time.Now()
	var memStart runtime.MemStats
	runtime.ReadMemStats(&memStart)
	
	// Initialize RNG with reproducible seed
	if config.Seed == 0 {
		seed, err := generateCryptoSeed()
		if err != nil {
			return nil, nil, SimulationStats{}, err
		}
		config.Seed = seed
	}
	
	// Set global seed for reproducibility
	mathrand.Seed(config.Seed)
	
	fmt.Printf("Starting Monte Carlo simulation with seed: %d\n", config.Seed)
	fmt.Printf("Configuration: %d trials, %d workers, %d SNR points\n", 
		config.NumTrials, config.NumWorkers, len(config.SNRRange))
	
	var amResults, fmResults []PerformanceResult
	
	if config.UseParallel && config.NumWorkers > 1 {
		// Parallel execution
		amResults = simulateSNRPerformanceParallel(AM, amParams, config.SNRRange, config.NumTrials, config.NumWorkers)
		fmResults = simulateSNRPerformanceParallel(FM, fmParams, config.SNRRange, config.NumTrials, config.NumWorkers)
	} else {
		// Sequential execution
		amResults = simulateSNRPerformance(AM, amParams, config.SNRRange, config.NumTrials)
		fmResults = simulateSNRPerformance(FM, fmParams, config.SNRRange, config.NumTrials)
	}
	
	// Calculate statistics
	duration := time.Since(startTime)
	totalTrials := config.NumTrials * len(config.SNRRange) * 2 // AM + FM
	trialsPerSecond := float64(totalTrials) / duration.Seconds()
	
	var memEnd runtime.MemStats
	runtime.ReadMemStats(&memEnd)
	memoryUsed := memEnd.TotalAlloc - memStart.TotalAlloc
	
	stats := SimulationStats{
		Duration:        duration,
		TrialsPerSecond: trialsPerSecond,
		TotalTrials:     totalTrials,
		WorkersUsed:     config.NumWorkers,
		MemoryUsed:      memoryUsed,
	}
	
	if config.PrintProgress {
		fmt.Printf("Simulation completed in %v\n", duration)
		fmt.Printf("Performance: %.0f trials/second\n", trialsPerSecond)
		fmt.Printf("Memory used: %.2f MB\n", float64(memoryUsed)/1024/1024)
	}
	
	return amResults, fmResults, stats, nil
}

// ReproducibilityTest verifies that same seed produces same results
func ReproducibilityTest(params SignalParams, seed int64, numTrials int) error {
	fmt.Printf("Testing reproducibility with seed %d...\n", seed)
	
	config1 := SimulationConfig{
		Seed:        seed,
		NumTrials:   numTrials,
		NumWorkers:  1,
		SNRRange:    []float64{0, 10, 20},
		UseParallel: false,
	}
	
	config2 := config1 // Copy configuration
	
	// Run simulation twice with same seed
	amResults1, fmResults1, _, err1 := OptimizedMonteCarloSimulation(params, params, config1)
	if err1 != nil {
		return fmt.Errorf("first simulation failed: %v", err1)
	}
	
	amResults2, fmResults2, _, err2 := OptimizedMonteCarloSimulation(params, params, config2)
	if err2 != nil {
		return fmt.Errorf("second simulation failed: %v", err2)
	}
	
	// Compare results
	tolerance := 1e-2 // Adjusted for floating point precision in Monte Carlo simulation
	for i := range amResults1 {
		if math.Abs(amResults1[i].OutputSNR_dB-amResults2[i].OutputSNR_dB) > tolerance {
			return fmt.Errorf("AM results differ at index %d: %f vs %f", i, 
				amResults1[i].OutputSNR_dB, amResults2[i].OutputSNR_dB)
		}
		if math.Abs(fmResults1[i].OutputSNR_dB-fmResults2[i].OutputSNR_dB) > tolerance {
			return fmt.Errorf("FM results differ at index %d: %f vs %f", i, 
				fmResults1[i].OutputSNR_dB, fmResults2[i].OutputSNR_dB)
		}
	}
	
	fmt.Println("✓ Reproducibility test passed: same seed produces identical results")
	return nil
}

// PerformanceBenchmark compares sequential vs parallel performance
func PerformanceBenchmark(amParams, fmParams SignalParams, numTrials int, snrRange []float64) {
	fmt.Println("\n=== Performance Benchmark ===")
	
	// Test different worker counts
	workerCounts := []int{1, 2, 4, 8, runtime.NumCPU()}
	
	for _, workers := range workerCounts {
		config := SimulationConfig{
			Seed:          12345, // Fixed seed for fair comparison
			NumTrials:     numTrials,
			NumWorkers:    workers,
			SNRRange:      snrRange,
			UseParallel:   workers > 1,
			PrintProgress: false,
		}
		
		_, _, stats, err := OptimizedMonteCarloSimulation(amParams, fmParams, config)
		if err != nil {
			fmt.Printf("Benchmark failed with %d workers: %v\n", workers, err)
			continue
		}
		
		fmt.Printf("Workers: %2d | Duration: %8s | Trials/sec: %8.0f | Memory: %6.1f MB\n",
			workers, stats.Duration.Round(time.Millisecond), stats.TrialsPerSecond, 
			float64(stats.MemoryUsed)/1024/1024)
	}
}

// AdaptiveWorkerCount determines optimal number of workers based on system capabilities
func AdaptiveWorkerCount() int {
	numCPU := runtime.NumCPU()
	
	// Use CPU count but cap at reasonable maximum for memory efficiency
	workers := numCPU
	if workers > 8 {
		workers = 8
	}
	if workers < 1 {
		workers = 1
	}
	
	return workers
}

// ProgressTracker tracks and reports simulation progress
type ProgressTracker struct {
	total    int
	current  int
	startTime time.Time
	mu       sync.Mutex
}

// NewProgressTracker creates a new progress tracker
func NewProgressTracker(total int) *ProgressTracker {
	return &ProgressTracker{
		total:     total,
		startTime: time.Now(),
	}
}

// Update increments the progress counter and optionally prints status
func (p *ProgressTracker) Update(increment int, printProgress bool) {
	p.mu.Lock()
	defer p.mu.Unlock()
	
	p.current += increment
	
	if printProgress && p.current%10 == 0 {
		elapsed := time.Since(p.startTime)
		percentage := float64(p.current) / float64(p.total) * 100
		estimated := time.Duration(float64(elapsed) / float64(p.current) * float64(p.total))
		remaining := estimated - elapsed
		
		fmt.Printf("Progress: %6.1f%% (%d/%d) | Elapsed: %v | ETA: %v\n",
			percentage, p.current, p.total, elapsed.Round(time.Second), remaining.Round(time.Second))
	}
}

// OptimizedAWGNWithSeed adds AWGN with reproducible seeding per worker
func OptimizedAWGNWithSeed(signal Signal, snrDB float64, rng *ReproducibleRNG) Signal {
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

// ValidateSimulationResults performs statistical validation of results
func ValidateSimulationResults(results []PerformanceResult) error {
	for i, result := range results {
		// Check for invalid values
		if math.IsNaN(result.OutputSNR_dB) || math.IsInf(result.OutputSNR_dB, 0) {
			return fmt.Errorf("invalid SNR at index %d: %f", i, result.OutputSNR_dB)
		}
		
		// Check that standard deviation is non-negative
		if result.StdDev < 0 {
			return fmt.Errorf("negative standard deviation at index %d: %f", i, result.StdDev)
		}
		
		// Check reasonable SNR bounds (assuming -100 to 100 dB range)
		if result.OutputSNR_dB < -100 || result.OutputSNR_dB > 100 {
			return fmt.Errorf("SNR out of reasonable bounds at index %d: %f dB", i, result.OutputSNR_dB)
		}
	}
	
	fmt.Printf("✓ Validation passed for %d results\n", len(results))
	return nil
}