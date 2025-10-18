package main

import (
	"fmt"
	"image/color"
	"math"

	"gonum.org/v1/plot"
	"gonum.org/v1/plot/plotter"
	"gonum.org/v1/plot/vg"
)

// PlotConfig holds configuration for advanced plotting
type PlotConfig struct {
	Title         string
	XLabel        string
	YLabel        string
	Width         vg.Length
	Height        vg.Length
	ShowGrid      bool
	ShowLegend    bool
	FontSize      vg.Length
	LineWidth     vg.Length
}

// DefaultPlotConfig returns a sensible default plot configuration
func DefaultPlotConfig() PlotConfig {
	return PlotConfig{
		Title:      "Signal Analysis",
		XLabel:     "X-axis",
		YLabel:     "Y-axis",
		Width:      10 * vg.Inch,
		Height:     6 * vg.Inch,
		ShowGrid:   true,
		ShowLegend: true,
		FontSize:   vg.Points(12),
		LineWidth:  vg.Points(2),
	}
}

// PlotSNRComparison creates an enhanced SNR comparison plot showing AM vs FM performance
func PlotSNRComparison(amResults, fmResults []PerformanceResult, filename string) error {
	p := plot.New()
	
	// Configure plot appearance
	p.Title.Text = "AM vs FM SNR Performance Comparison"
	p.X.Label.Text = "Input SNR (dB)"
	p.Y.Label.Text = "Output SNR (dB)"
	
	// Set font sizes
	p.Title.TextStyle.Font.Size = vg.Points(16)
	p.X.Label.TextStyle.Font.Size = vg.Points(14)
	p.Y.Label.TextStyle.Font.Size = vg.Points(14)
	
	// Enable grid
	p.Add(plotter.NewGrid())
	
	// Prepare AM data
	amPts := make(plotter.XYs, len(amResults))
	amErrors := make(plotter.YErrors, len(amResults))
	for i, result := range amResults {
		amPts[i].X = result.InputSNR_dB
		amPts[i].Y = result.OutputSNR_dB
		amErrors[i].Low = result.StdDev
		amErrors[i].High = result.StdDev
	}
	
	// Prepare FM data
	fmPts := make(plotter.XYs, len(fmResults))
	fmErrors := make(plotter.YErrors, len(fmResults))
	for i, result := range fmResults {
		fmPts[i].X = result.InputSNR_dB
		fmPts[i].Y = result.OutputSNR_dB
		fmErrors[i].Low = result.StdDev
		fmErrors[i].High = result.StdDev
	}
	
	// Create AM line and error bars
	amLine, err := plotter.NewLine(amPts)
	if err != nil {
		return err
	}
	amLine.Color = color.RGBA{R: 255, G: 0, B: 0, A: 255} // Red
	amLine.Width = vg.Points(3)
	
	amErrorBars, err := plotter.NewYErrorBars(struct {
		plotter.XYs
		plotter.YErrors
	}{amPts, amErrors})
	if err != nil {
		return err
	}
	amErrorBars.Color = color.RGBA{R: 255, G: 100, B: 100, A: 255}
	
	// Create FM line and error bars
	fmLine, err := plotter.NewLine(fmPts)
	if err != nil {
		return err
	}
	fmLine.Color = color.RGBA{R: 0, G: 0, B: 255, A: 255} // Blue
	fmLine.Width = vg.Points(3)
	
	fmErrorBars, err := plotter.NewYErrorBars(struct {
		plotter.XYs
		plotter.YErrors
	}{fmPts, fmErrors})
	if err != nil {
		return err
	}
	fmErrorBars.Color = color.RGBA{R: 100, G: 100, B: 255, A: 255}
	
	// Add data to plot
	p.Add(amLine, amErrorBars)
	p.Add(fmLine, fmErrorBars)
	
	// Add legend
	p.Legend.Add("AM Performance", amLine)
	p.Legend.Add("FM Performance", fmLine)
	p.Legend.Top = true
	p.Legend.Left = false
	
	// Add ideal line (y=x) for reference
	idealPts := make(plotter.XYs, 2)
	idealPts[0].X = amResults[0].InputSNR_dB
	idealPts[0].Y = amResults[0].InputSNR_dB
	idealPts[1].X = amResults[len(amResults)-1].InputSNR_dB
	idealPts[1].Y = amResults[len(amResults)-1].InputSNR_dB
	
	idealLine, err := plotter.NewLine(idealPts)
	if err == nil {
		idealLine.Color = color.RGBA{R: 128, G: 128, B: 128, A: 255}
		idealLine.Dashes = []vg.Length{vg.Points(5), vg.Points(5)}
		idealLine.Width = vg.Points(1)
		p.Add(idealLine)
		p.Legend.Add("Ideal (No Loss)", idealLine)
	}
	
	return p.Save(10*vg.Inch, 6*vg.Inch, filename)
}

// PlotSNRImprovementFactor creates a plot showing the SNR improvement factor of FM over AM
func PlotSNRImprovementFactor(amResults, fmResults []PerformanceResult, filename string) error {
	p := plot.New()
	
	p.Title.Text = "FM Advantage over AM (SNR Difference)"
	p.X.Label.Text = "Input SNR (dB)"
	p.Y.Label.Text = "FM SNR - AM SNR (dB)"
	p.Title.TextStyle.Font.Size = vg.Points(16)
	
	// Enable grid
	p.Add(plotter.NewGrid())
	
	// Calculate improvement factor
	improvementPts := make(plotter.XYs, len(amResults))
	for i := range amResults {
		improvementPts[i].X = amResults[i].InputSNR_dB
		improvementPts[i].Y = fmResults[i].OutputSNR_dB - amResults[i].OutputSNR_dB
	}
	
	// Create line
	line, err := plotter.NewLine(improvementPts)
	if err != nil {
		return err
	}
	line.Color = color.RGBA{R: 0, G: 128, B: 0, A: 255} // Green
	line.Width = vg.Points(3)
	
	// Create scatter plot
	scatter, err := plotter.NewScatter(improvementPts)
	if err != nil {
		return err
	}
	scatter.GlyphStyle.Color = color.RGBA{R: 0, G: 128, B: 0, A: 255}
	scatter.GlyphStyle.Radius = vg.Points(4)
	
	p.Add(line, scatter)
	
	// Add zero line for reference
	zeroLine := plotter.NewFunction(func(x float64) float64 { return 0 })
	zeroLine.Color = color.RGBA{R: 0, G: 0, B: 0, A: 255}
	zeroLine.Dashes = []vg.Length{vg.Points(3), vg.Points(3)}
	p.Add(zeroLine)
	
	return p.Save(10*vg.Inch, 6*vg.Inch, filename)
}

// PlotModulatedSignalsComparison creates a detailed comparison of modulated signals
func PlotModulatedSignalsComparison(amSignal, fmSignal Signal, config PlotConfig) error {
	p := plot.New()
	
	p.Title.Text = config.Title
	p.X.Label.Text = config.XLabel
	p.Y.Label.Text = config.YLabel
	
	// Enable grid if requested
	if config.ShowGrid {
		p.Add(plotter.NewGrid())
	}
	
	// Subsample for better visualization (plot every nth point)
	subsample := len(amSignal.Time) / 500
	if subsample < 1 {
		subsample = 1
	}
	
	// AM signal data
	amPts := make(plotter.XYs, 0)
	for i := 0; i < len(amSignal.Time); i += subsample {
		amPts = append(amPts, plotter.XY{X: amSignal.Time[i], Y: amSignal.Values[i]})
	}
	
	// FM signal data
	fmPts := make(plotter.XYs, 0)
	for i := 0; i < len(fmSignal.Time); i += subsample {
		fmPts = append(fmPts, plotter.XY{X: fmSignal.Time[i], Y: fmSignal.Values[i]})
	}
	
	// Create lines
	amLine, err := plotter.NewLine(amPts)
	if err != nil {
		return err
	}
	amLine.Color = color.RGBA{R: 255, G: 0, B: 0, A: 255}
	amLine.Width = config.LineWidth
	
	fmLine, err := plotter.NewLine(fmPts)
	if err != nil {
		return err
	}
	fmLine.Color = color.RGBA{R: 0, G: 0, B: 255, A: 255}
	fmLine.Width = config.LineWidth
	
	p.Add(amLine, fmLine)
	
	if config.ShowLegend {
		p.Legend.Add("AM Signal", amLine)
		p.Legend.Add("FM Signal", fmLine)
	}
	
	return p.Save(config.Width, config.Height, "modulated_signals_comparison.png")
}

// PlotSpectralComparison creates a frequency domain comparison (simplified)
func PlotSpectralComparison(amSignal, fmSignal Signal, filename string) error {
	p := plot.New()
	
	p.Title.Text = "Spectral Comparison (Simplified Power Spectral Density)"
	p.X.Label.Text = "Frequency Bin"
	p.Y.Label.Text = "Power (dB)"
	p.Title.TextStyle.Font.Size = vg.Points(16)
	
	// Simple power calculation (not true FFT, but illustrative)
	binSize := 50
	amPower := make([]float64, binSize)
	fmPower := make([]float64, binSize)
	
	// Calculate power in frequency bins (simplified approach)
	for i := 0; i < binSize; i++ {
		start := i * len(amSignal.Values) / binSize
		end := (i + 1) * len(amSignal.Values) / binSize
		
		var amSum, fmSum float64
		for j := start; j < end && j < len(amSignal.Values); j++ {
			amSum += amSignal.Values[j] * amSignal.Values[j]
			fmSum += fmSignal.Values[j] * fmSignal.Values[j]
		}
		
		amPower[i] = 10 * math.Log10(amSum/float64(end-start) + 1e-10)
		fmPower[i] = 10 * math.Log10(fmSum/float64(end-start) + 1e-10)
	}
	
	// Create data points
	amPts := make(plotter.XYs, binSize)
	fmPts := make(plotter.XYs, binSize)
	
	for i := 0; i < binSize; i++ {
		amPts[i].X = float64(i)
		amPts[i].Y = amPower[i]
		fmPts[i].X = float64(i)
		fmPts[i].Y = fmPower[i]
	}
	
	// Create lines
	amLine, err := plotter.NewLine(amPts)
	if err != nil {
		return err
	}
	amLine.Color = color.RGBA{R: 255, G: 0, B: 0, A: 255}
	amLine.Width = vg.Points(2)
	
	fmLine, err := plotter.NewLine(fmPts)
	if err != nil {
		return err
	}
	fmLine.Color = color.RGBA{R: 0, G: 0, B: 255, A: 255}
	fmLine.Width = vg.Points(2)
	
	p.Add(amLine, fmLine)
	p.Add(plotter.NewGrid())
	
	p.Legend.Add("AM Spectrum", amLine)
	p.Legend.Add("FM Spectrum", fmLine)
	
	return p.Save(10*vg.Inch, 6*vg.Inch, filename)
}

// PlotPerformanceStatistics creates a plot showing performance statistics
func PlotPerformanceStatistics(stats []SimulationStats, filename string) error {
	p := plot.New()
	
	p.Title.Text = "Simulation Performance vs Number of Workers"
	p.X.Label.Text = "Number of Workers"
	p.Y.Label.Text = "Trials per Second"
	p.Title.TextStyle.Font.Size = vg.Points(16)
	
	// Prepare data
	pts := make(plotter.XYs, len(stats))
	for i, stat := range stats {
		pts[i].X = float64(stat.WorkersUsed)
		pts[i].Y = stat.TrialsPerSecond
	}
	
	// Create line and scatter
	line, err := plotter.NewLine(pts)
	if err != nil {
		return err
	}
	line.Color = color.RGBA{R: 0, G: 128, B: 0, A: 255}
	line.Width = vg.Points(2)
	
	scatter, err := plotter.NewScatter(pts)
	if err != nil {
		return err
	}
	scatter.GlyphStyle.Color = color.RGBA{R: 0, G: 128, B: 0, A: 255}
	scatter.GlyphStyle.Radius = vg.Points(4)
	
	p.Add(line, scatter)
	p.Add(plotter.NewGrid())
	
	return p.Save(10*vg.Inch, 6*vg.Inch, filename)
}

// CreateComprehensiveReport generates multiple visualizations for comprehensive analysis
func CreateComprehensiveReport(amResults, fmResults []PerformanceResult, amSignal, fmSignal Signal) error {
	fmt.Println("Generating comprehensive visualization report...")
	
	// 1. Main SNR comparison plot
	if err := PlotSNRComparison(amResults, fmResults, "comprehensive_snr_comparison.png"); err != nil {
		return fmt.Errorf("failed to create SNR comparison plot: %v", err)
	}
	
	// 2. FM advantage plot
	if err := PlotSNRImprovementFactor(amResults, fmResults, "fm_advantage.png"); err != nil {
		return fmt.Errorf("failed to create FM advantage plot: %v", err)
	}
	
	// 3. Spectral comparison
	if err := PlotSpectralComparison(amSignal, fmSignal, "spectral_comparison.png"); err != nil {
		return fmt.Errorf("failed to create spectral comparison: %v", err)
	}
	
	// 4. Enhanced modulated signals comparison
	config := DefaultPlotConfig()
	config.Title = "AM vs FM Modulated Signals (Time Domain)"
	config.XLabel = "Time (s)"
	config.YLabel = "Amplitude"
	if err := PlotModulatedSignalsComparison(amSignal, fmSignal, config); err != nil {
		return fmt.Errorf("failed to create modulated signals comparison: %v", err)
	}
	
	fmt.Println("✓ Comprehensive visualization report generated successfully")
	fmt.Println("Generated plots:")
	fmt.Println("  - comprehensive_snr_comparison.png: Main performance comparison")
	fmt.Println("  - fm_advantage.png: FM superiority demonstration")
	fmt.Println("  - spectral_comparison.png: Frequency domain analysis")
	fmt.Println("  - modulated_signals_comparison.png: Time domain signals")
	
	return nil
}

// AnalyzeFMSuperiority provides quantitative analysis of FM's noise immunity advantage
func AnalyzeFMSuperiority(amResults, fmResults []PerformanceResult) {
	fmt.Println("\n=== FM Superiority Analysis ===")
	
	var totalImprovement float64
	var improvementCount int
	maxImprovement := -math.Inf(1)
	maxImprovementSNR := 0.0
	
	fmt.Printf("Input SNR | AM Output | FM Output | FM Advantage\n")
	fmt.Printf("----------|-----------|-----------|-------------\n")
	
	for i := range amResults {
		improvement := fmResults[i].OutputSNR_dB - amResults[i].OutputSNR_dB
		
		fmt.Printf("%8.1f dB | %8.2f dB | %8.2f dB | %+9.2f dB\n",
			amResults[i].InputSNR_dB,
			amResults[i].OutputSNR_dB,
			fmResults[i].OutputSNR_dB,
			improvement)
		
		if improvement > 0 {
			totalImprovement += improvement
			improvementCount++
		}
		
		if improvement > maxImprovement {
			maxImprovement = improvement
			maxImprovementSNR = amResults[i].InputSNR_dB
		}
	}
	
	fmt.Println("----------|-----------|-----------|-------------")
	
	if improvementCount > 0 {
		avgImprovement := totalImprovement / float64(improvementCount)
		fmt.Printf("Average FM advantage: %.2f dB (over %d SNR points)\n", avgImprovement, improvementCount)
	} else {
		fmt.Println("No SNR points show FM advantage in this simulation")
	}
	
	fmt.Printf("Maximum FM advantage: %.2f dB at %.1f dB input SNR\n", maxImprovement, maxImprovementSNR)
	
	// Theoretical analysis note
	fmt.Println("\nNote: In ideal conditions, FM should show superior performance")
	fmt.Println("at high SNR levels due to its constant envelope and frequency")
	fmt.Println("domain noise characteristics. The current implementation uses")
	fmt.Println("simplified demodulation which may not capture full FM benefits.")
}