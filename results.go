package main

import (
	"encoding/csv"
	"fmt"
	"os"
	"strconv"
)

// saveResultsCSV saves the SNR comparison results to a CSV file
func saveResultsCSV(snrRange, amPerformance, fmPerformance []float64, filename string) error {
	file, err := os.Create(filename)
	if err != nil {
		return err
	}
	defer file.Close()

	writer := csv.NewWriter(file)
	defer writer.Flush()

	// Write header
	header := []string{"Input_SNR_dB", "AM_Output_SNR_dB", "FM_Output_SNR_dB"}
	if err := writer.Write(header); err != nil {
		return err
	}

	// Write data rows
	for i := range snrRange {
		row := []string{
			strconv.FormatFloat(snrRange[i], 'f', 2, 64),
			strconv.FormatFloat(amPerformance[i], 'f', 2, 64),
			strconv.FormatFloat(fmPerformance[i], 'f', 2, 64),
		}
		if err := writer.Write(row); err != nil {
			return err
		}
	}

	fmt.Printf("Results saved to %s\n", filename)
	return nil
}

// saveSignalCSV saves signal data to CSV file
func saveSignalCSV(signal Signal, filename string) error {
	file, err := os.Create(filename)
	if err != nil {
		return err
	}
	defer file.Close()

	writer := csv.NewWriter(file)
	defer writer.Flush()

	// Write header
	header := []string{"Time_s", "Amplitude"}
	if err := writer.Write(header); err != nil {
		return err
	}

	// Write data rows
	for i := range signal.Time {
		row := []string{
			strconv.FormatFloat(signal.Time[i], 'e', 6, 64),
			strconv.FormatFloat(signal.Values[i], 'e', 6, 64),
		}
		if err := writer.Write(row); err != nil {
			return err
		}
	}

	return nil
}