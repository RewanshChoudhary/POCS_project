package main

import (
	"encoding/csv"
	"fmt"
	"math"
	"os"
	"strconv"
	"sync"
)

// ModulationType represents the type of modulation
type ModulationType string

const (
	AM ModulationType = "AM"
	FM ModulationType = "FM"
)

// SNRMeasurement represents a single SNR measurement
type SNRMeasurement struct {
	InputSNR_dB     float64
	OutputSNR_dB    float64
	ModulationType  ModulationType
	TrialNumber     int
}

// PerformanceResult aggregates multiple measurements
type PerformanceResult struct {
	InputSNR_dB    float64
	OutputSNR_dB   float64
	StdDev         float64
	ModulationType ModulationType
	NumTrials      int
}

// computeInputSNR calculates the input SNR at transmitter output + noise
func computeInputSNR(cleanSignal, noisySignal Signal) float64 {
	signalPower := 0.0
	noisePower := 0.0
	
	for i := range cleanSignal.Values {
		signalPower += cleanSignal.Values[i] * cleanSignal.Values[i]
		noise := noisySignal.Values[i] - cleanSignal.Values[i]
		noisePower += noise * noise
	}
	
	signalPower /= float64(len(cleanSignal.Values))
	noisePower /= float64(len(cleanSignal.Values))
	
	if noisePower == 0 {
		return math.Inf(1)
	}
	
	return 10 * math.Log10(signalPower/noisePower)
}

// computeOutputSNR calculates the output SNR after demodulation
func computeOutputSNR(originalMessage, demodulatedSignal Signal) float64 {
	return calculateSNR(originalMessage, demodulatedSignal)
}

// simulateSNRPerformance performs comprehensive SNR performance measurement
func simulateSNRPerformance(modType ModulationType, params SignalParams, snrRange []float64, numTrials int) []PerformanceResult {
	results := make([]PerformanceResult, len(snrRange))
	
	for i, targetSNR := range snrRange {
		measurements := make([]float64, numTrials)
		
		for trial := 0; trial < numTrials; trial++ {
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
			
			// Add noise to achieve target SNR
			noisySignal := addAWGN(modulatedSignal, targetSNR)
			
			// Verify actual input SNR (for debugging/validation)
			_ = computeInputSNR(modulatedSignal, noisySignal)
			
			// Demodulate signal
			var demodulatedSignal Signal
			switch modType {
			case AM:
				demodulatedSignal = demodulateAM(noisySignal)
			case FM:
				demodulatedSignal = demodulateFM(noisySignal, params)
			}
			
			// Compute output SNR
			outputSNR := computeOutputSNR(originalMessage, demodulatedSignal)
			measurements[trial] = outputSNR
		}
		
		// Calculate statistics
		mean := 0.0
		for _, val := range measurements {
			mean += val
		}
		mean /= float64(numTrials)
		
		variance := 0.0
		for _, val := range measurements {
			diff := val - mean
			variance += diff * diff
		}
		variance /= float64(numTrials - 1)
		stdDev := math.Sqrt(variance)
		
		results[i] = PerformanceResult{
			InputSNR_dB:    targetSNR,
			OutputSNR_dB:   mean,
			StdDev:         stdDev,
			ModulationType: modType,
			NumTrials:      numTrials,
		}
	}
	
	return results
}

// simulateSNRPerformanceParallel performs parallelized SNR performance measurement
func simulateSNRPerformanceParallel(modType ModulationType, params SignalParams, snrRange []float64, numTrials int, numWorkers int) []PerformanceResult {
	results := make([]PerformanceResult, len(snrRange))
	var wg sync.WaitGroup
	
	// Channel to distribute work
	jobs := make(chan int, len(snrRange))
	resultsChan := make(chan struct {
		index  int
		result PerformanceResult
	}, len(snrRange))
	
	// Start workers
	for w := 0; w < numWorkers; w++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for snrIndex := range jobs {
				targetSNR := snrRange[snrIndex]
				measurements := make([]float64, numTrials)
				
				for trial := 0; trial < numTrials; trial++ {
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
					
					// Add noise to achieve target SNR
					noisySignal := addAWGN(modulatedSignal, targetSNR)
					
					// Demodulate signal
					var demodulatedSignal Signal
					switch modType {
					case AM:
						demodulatedSignal = demodulateAM(noisySignal)
					case FM:
						demodulatedSignal = demodulateFM(noisySignal, params)
					}
					
					// Compute output SNR
					outputSNR := computeOutputSNR(originalMessage, demodulatedSignal)
					measurements[trial] = outputSNR
				}
				
				// Calculate statistics
				mean := 0.0
				for _, val := range measurements {
					mean += val
				}
				mean /= float64(numTrials)
				
				variance := 0.0
				for _, val := range measurements {
					diff := val - mean
					variance += diff * diff
				}
				variance /= float64(numTrials - 1)
				stdDev := math.Sqrt(variance)
				
				resultsChan <- struct {
					index  int
					result PerformanceResult
				}{
					index: snrIndex,
					result: PerformanceResult{
						InputSNR_dB:    targetSNR,
						OutputSNR_dB:   mean,
						StdDev:         stdDev,
						ModulationType: modType,
						NumTrials:      numTrials,
					},
				}
			}
		}()
	}
	
	// Send jobs
	for i := range snrRange {
		jobs <- i
	}
	close(jobs)
	
	// Collect results
	go func() {
		wg.Wait()
		close(resultsChan)
	}()
	
	for result := range resultsChan {
		results[result.index] = result.result
	}
	
	return results
}

// savePerformanceResultsCSV saves detailed performance results to CSV
func savePerformanceResultsCSV(amResults, fmResults []PerformanceResult, filename string) error {
	file, err := os.Create(filename)
	if err != nil {
		return err
	}
	defer file.Close()
	
	writer := csv.NewWriter(file)
	defer writer.Flush()
	
	// Write header
	header := []string{"SNR_in_dB", "SNR_out_dB", "StdDev_dB", "modulation_type", "num_trials"}
	if err := writer.Write(header); err != nil {
		return err
	}
	
	// Write AM results
	for _, result := range amResults {
		row := []string{
			strconv.FormatFloat(result.InputSNR_dB, 'f', 2, 64),
			strconv.FormatFloat(result.OutputSNR_dB, 'f', 2, 64),
			strconv.FormatFloat(result.StdDev, 'f', 2, 64),
			string(result.ModulationType),
			strconv.Itoa(result.NumTrials),
		}
		if err := writer.Write(row); err != nil {
			return err
		}
	}
	
	// Write FM results
	for _, result := range fmResults {
		row := []string{
			strconv.FormatFloat(result.InputSNR_dB, 'f', 2, 64),
			strconv.FormatFloat(result.OutputSNR_dB, 'f', 2, 64),
			strconv.FormatFloat(result.StdDev, 'f', 2, 64),
			string(result.ModulationType),
			strconv.Itoa(result.NumTrials),
		}
		if err := writer.Write(row); err != nil {
			return err
		}
	}
	
	fmt.Printf("Performance results saved to %s\n", filename)
	return nil
}

// saveDetailedMeasurementsCSV saves individual trial measurements
func saveDetailedMeasurementsCSV(measurements []SNRMeasurement, filename string) error {
	file, err := os.Create(filename)
	if err != nil {
		return err
	}
	defer file.Close()
	
	writer := csv.NewWriter(file)
	defer writer.Flush()
	
	// Write header
	header := []string{"trial_number", "SNR_in_dB", "SNR_out_dB", "modulation_type"}
	if err := writer.Write(header); err != nil {
		return err
	}
	
	// Write data rows
	for _, measurement := range measurements {
		row := []string{
			strconv.Itoa(measurement.TrialNumber),
			strconv.FormatFloat(measurement.InputSNR_dB, 'f', 2, 64),
			strconv.FormatFloat(measurement.OutputSNR_dB, 'f', 2, 64),
			string(measurement.ModulationType),
		}
		if err := writer.Write(row); err != nil {
			return err
		}
	}
	
	fmt.Printf("Detailed measurements saved to %s\n", filename)
	return nil
}