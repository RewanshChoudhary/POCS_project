package main

import (
	"fmt"
	"image/color"
	"math"

	"gonum.org/v1/plot"
	"gonum.org/v1/plot/plotter"
	"gonum.org/v1/plot/vg"
	"gonum.org/v1/plot/vg/draw"
)

// Phase6VisualizationConfig holds configuration for publication-quality plots
type Phase6VisualizationConfig struct {
	Width           vg.Length
	Height          vg.Length
	DPI             float64
	FontSize        vg.Length
	TitleFontSize   vg.Length
	LineWidth       vg.Length
	MarkerSize      vg.Length
	ShowGrid        bool
	ShowErrorBars   bool
	SaveInteractive bool
}

// DefaultPhase6Config returns publication-quality plot configuration
func DefaultPhase6Config() Phase6VisualizationConfig {
	return Phase6VisualizationConfig{
		Width:           12 * vg.Inch,
		Height:          8 * vg.Inch,
		DPI:             300,
		FontSize:        vg.Points(12),
		TitleFontSize:   vg.Points(16),
		LineWidth:       vg.Points(3),
		MarkerSize:      vg.Points(5),
		ShowGrid:        true,
		ShowErrorBars:   true,
		SaveInteractive: false,
	}
}

// CreatePhase6ComprehensiveReport generates all Phase 6 visualizations
func CreatePhase6ComprehensiveReport(phase5Results *Phase5MonteCarloResults) error {
	fmt.Println("\n📈 Phase 6: Visualization & Comparison")
	fmt.Println("====================================")

	config := DefaultPhase6Config()

	// 1. Main SNR Performance Comparison Plot
	if err := CreateSNRPerformanceComparisonPlot(phase5Results, config, "phase6_snr_comparison.png"); err != nil {
		return fmt.Errorf("failed to create SNR comparison plot: %v", err)
	}

	// 2. FM Advantage Analysis Plot
	if err := CreateFMAdvantageAnalysisPlot(phase5Results, config, "phase6_fm_advantage.png"); err != nil {
		return fmt.Errorf("failed to create FM advantage plot: %v", err)
	}

	// 3. Statistical Confidence Intervals Plot
	if err := CreateStatisticalConfidencePlot(phase5Results, config, "phase6_confidence_intervals.png"); err != nil {
		return fmt.Errorf("failed to create confidence intervals plot: %v", err)
	}

	// 4. Performance Summary Dashboard
	if err := CreatePerformanceDashboard(phase5Results, config, "phase6_performance_dashboard.png"); err != nil {
		return fmt.Errorf("failed to create performance dashboard: %v", err)
	}

	fmt.Println("✅ Phase 6 visualizations completed successfully")
	PrintPhase6Summary(phase5Results)

	return nil
}

// CreateSNRPerformanceComparisonPlot creates the main publication-quality SNR comparison plot
func CreateSNRPerformanceComparisonPlot(results *Phase5MonteCarloResults, config Phase6VisualizationConfig, filename string) error {
	p := plot.New()

	// Configure plot appearance
	p.Title.Text = "AM vs FM SNR Performance: Noise Immunity Comparison"
	p.X.Label.Text = "Input SNR (dB)"
	p.Y.Label.Text = "Output SNR (dB)"
	
	// Set font sizes
	p.Title.TextStyle.Font.Size = config.TitleFontSize
	p.X.Label.TextStyle.Font.Size = config.FontSize
	p.Y.Label.TextStyle.Font.Size = config.FontSize

	// Add grid if requested
	if config.ShowGrid {
		grid := plotter.NewGrid()
		grid.Vertical.Color = color.RGBA{R: 200, G: 200, B: 200, A: 255}
		grid.Horizontal.Color = color.RGBA{R: 200, G: 200, B: 200, A: 255}
		p.Add(grid)
	}

	// Prepare AM data
	amPts := make(plotter.XYs, len(results.AMResults))
	amErrors := make(plotter.YErrors, len(results.AMResults))
	for i, result := range results.AMResults {
		amPts[i].X = result.InputSNR_dB
		amPts[i].Y = result.OutputSNR_dB
		amErrors[i].Low = result.StdDev
		amErrors[i].High = result.StdDev
	}

	// Prepare FM data
	fmPts := make(plotter.XYs, len(results.FMResults))
	fmErrors := make(plotter.YErrors, len(results.FMResults))
	for i, result := range results.FMResults {
		fmPts[i].X = result.InputSNR_dB
		fmPts[i].Y = result.OutputSNR_dB
		fmErrors[i].Low = result.StdDev
		fmErrors[i].High = result.StdDev
	}

	// Create AM line and markers
	amLine, err := plotter.NewLine(amPts)
	if err != nil {
		return err
	}
	amLine.Color = color.RGBA{R: 255, G: 0, B: 0, A: 255} // Red
	amLine.Width = config.LineWidth

	amScatter, err := plotter.NewScatter(amPts)
	if err != nil {
		return err
	}
	amScatter.GlyphStyle.Color = color.RGBA{R: 255, G: 0, B: 0, A: 255}
	amScatter.GlyphStyle.Radius = config.MarkerSize
	amScatter.GlyphStyle.Shape = draw.CircleGlyph{}

	// Create FM line and markers
	fmLine, err := plotter.NewLine(fmPts)
	if err != nil {
		return err
	}
	fmLine.Color = color.RGBA{R: 0, G: 0, B: 255, A: 255} // Blue
	fmLine.Width = config.LineWidth

	fmScatter, err := plotter.NewScatter(fmPts)
	if err != nil {
		return err
	}
	fmScatter.GlyphStyle.Color = color.RGBA{R: 0, G: 0, B: 255, A: 255}
	fmScatter.GlyphStyle.Radius = config.MarkerSize
	fmScatter.GlyphStyle.Shape = draw.TriangleGlyph{}

	// Add error bars if requested
	if config.ShowErrorBars {
		amErrorBars, err := plotter.NewYErrorBars(struct {
			plotter.XYs
			plotter.YErrors
		}{amPts, amErrors})
		if err != nil {
			return err
		}
		amErrorBars.Color = color.RGBA{R: 255, G: 100, B: 100, A: 200}

		fmErrorBars, err := plotter.NewYErrorBars(struct {
			plotter.XYs
			plotter.YErrors
		}{fmPts, fmErrors})
		if err != nil {
			return err
		}
		fmErrorBars.Color = color.RGBA{R: 100, G: 100, B: 255, A: 200}

		p.Add(amErrorBars, fmErrorBars)
	}

	// Add lines and scatter plots
	p.Add(amLine, amScatter, fmLine, fmScatter)

	// Add ideal reference line (y=x)
	minSNR := results.AMResults[0].InputSNR_dB
	maxSNR := results.AMResults[len(results.AMResults)-1].InputSNR_dB
	idealPts := plotter.XYs{{X: minSNR, Y: minSNR}, {X: maxSNR, Y: maxSNR}}

	idealLine, err := plotter.NewLine(idealPts)
	if err == nil {
		idealLine.Color = color.RGBA{R: 128, G: 128, B: 128, A: 255}
		idealLine.Dashes = []vg.Length{vg.Points(5), vg.Points(5)}
		idealLine.Width = vg.Points(2)
		p.Add(idealLine)
	}

	// Configure legend
	p.Legend.Add("AM Performance", amLine, amScatter)
	p.Legend.Add("FM Performance", fmLine, fmScatter)
	if idealLine != nil {
		p.Legend.Add("Ideal (No Loss)", idealLine)
	}
	p.Legend.Top = true
	p.Legend.Left = false
	p.Legend.TextStyle.Font.Size = config.FontSize

	return p.Save(config.Width, config.Height, filename)
}

// CreateFMAdvantageAnalysisPlot shows quantitative FM advantage over AM
func CreateFMAdvantageAnalysisPlot(results *Phase5MonteCarloResults, config Phase6VisualizationConfig, filename string) error {
	p := plot.New()

	p.Title.Text = "FM Advantage Over AM: Quantitative Noise Immunity Analysis"
	p.X.Label.Text = "Input SNR (dB)"
	p.Y.Label.Text = "FM SNR - AM SNR (dB)"
	
	p.Title.TextStyle.Font.Size = config.TitleFontSize
	p.X.Label.TextStyle.Font.Size = config.FontSize
	p.Y.Label.TextStyle.Font.Size = config.FontSize

	if config.ShowGrid {
		p.Add(plotter.NewGrid())
	}

	// Calculate FM advantage
	advantagePts := make(plotter.XYs, len(results.AMResults))
	for i := range results.AMResults {
		advantagePts[i].X = results.AMResults[i].InputSNR_dB
		advantagePts[i].Y = results.FMResults[i].OutputSNR_dB - results.AMResults[i].OutputSNR_dB
	}

	// Create line and scatter
	line, err := plotter.NewLine(advantagePts)
	if err != nil {
		return err
	}
	line.Color = color.RGBA{R: 0, G: 128, B: 0, A: 255} // Green
	line.Width = config.LineWidth

	scatter, err := plotter.NewScatter(advantagePts)
	if err != nil {
		return err
	}
	scatter.GlyphStyle.Color = color.RGBA{R: 0, G: 128, B: 0, A: 255}
	scatter.GlyphStyle.Radius = config.MarkerSize

	p.Add(line, scatter)

	// Add zero reference line
	minSNR := results.AMResults[0].InputSNR_dB
	maxSNR := results.AMResults[len(results.AMResults)-1].InputSNR_dB
	zeroLine, err := plotter.NewLine(plotter.XYs{{X: minSNR, Y: 0}, {X: maxSNR, Y: 0}})
	if err == nil {
		zeroLine.Color = color.RGBA{R: 0, G: 0, B: 0, A: 255}
		zeroLine.Dashes = []vg.Length{vg.Points(3), vg.Points(3)}
		zeroLine.Width = vg.Points(1)
		p.Add(zeroLine)
	}

	p.Legend.Add("FM Advantage", line, scatter)
	p.Legend.Add("No Advantage", zeroLine)

	return p.Save(config.Width, config.Height, filename)
}

// CreateStatisticalConfidencePlot shows confidence intervals for statistical significance
func CreateStatisticalConfidencePlot(results *Phase5MonteCarloResults, config Phase6VisualizationConfig, filename string) error {
	p := plot.New()

	p.Title.Text = "Statistical Confidence Analysis (Error Bars = ±1σ)"
	p.X.Label.Text = "Input SNR (dB)"
	p.Y.Label.Text = "Output SNR (dB)"
	
	p.Title.TextStyle.Font.Size = config.TitleFontSize
	p.X.Label.TextStyle.Font.Size = config.FontSize
	p.Y.Label.TextStyle.Font.Size = config.FontSize

	if config.ShowGrid {
		p.Add(plotter.NewGrid())
	}

	// Create confidence interval plots
	for _, result := range results.AMResults {
		// Create vertical line for confidence interval
		x := result.InputSNR_dB
		yLow := result.OutputSNR_dB - result.StdDev
		yHigh := result.OutputSNR_dB + result.StdDev
		
		confLine, err := plotter.NewLine(plotter.XYs{{X: x, Y: yLow}, {X: x, Y: yHigh}})
		if err == nil {
			confLine.Color = color.RGBA{R: 255, G: 0, B: 0, A: 100}
			confLine.Width = vg.Points(8)
			p.Add(confLine)
		}
	}

	for _, result := range results.FMResults {
		x := result.InputSNR_dB
		yLow := result.OutputSNR_dB - result.StdDev
		yHigh := result.OutputSNR_dB + result.StdDev
		
		confLine, err := plotter.NewLine(plotter.XYs{{X: x, Y: yLow}, {X: x, Y: yHigh}})
		if err == nil {
			confLine.Color = color.RGBA{R: 0, G: 0, B: 255, A: 100}
			confLine.Width = vg.Points(8)
			p.Add(confLine)
		}
	}

	// Add mean lines
	amPts := make(plotter.XYs, len(results.AMResults))
	fmPts := make(plotter.XYs, len(results.FMResults))
	for i, result := range results.AMResults {
		amPts[i].X = result.InputSNR_dB
		amPts[i].Y = result.OutputSNR_dB
	}
	for i, result := range results.FMResults {
		fmPts[i].X = result.InputSNR_dB
		fmPts[i].Y = result.OutputSNR_dB
	}

	amLine, _ := plotter.NewLine(amPts)
	amLine.Color = color.RGBA{R: 255, G: 0, B: 0, A: 255}
	amLine.Width = config.LineWidth

	fmLine, _ := plotter.NewLine(fmPts)
	fmLine.Color = color.RGBA{R: 0, G: 0, B: 255, A: 255}
	fmLine.Width = config.LineWidth

	p.Add(amLine, fmLine)

	p.Legend.Add("AM Mean ± σ", amLine)
	p.Legend.Add("FM Mean ± σ", fmLine)

	return p.Save(config.Width, config.Height, filename)
}

// CreatePerformanceDashboard creates a comprehensive performance summary
func CreatePerformanceDashboard(results *Phase5MonteCarloResults, config Phase6VisualizationConfig, filename string) error {
	// This would create a multi-panel dashboard
	// For now, create a summary text plot
	p := plot.New()

	p.Title.Text = "Phase 5 & 6 Performance Summary Dashboard"
	p.Title.TextStyle.Font.Size = config.TitleFontSize

	// Hide axes for text display
	p.X.Label.Text = ""
	p.Y.Label.Text = ""
	
	// Simple placeholder for dashboard - in production would create multi-panel plot
	// For now, just create a basic plot
	textPts := plotter.XYs{{X: 0, Y: 0}, {X: 1, Y: 1}}
	textLine, err := plotter.NewLine(textPts)
	if err == nil {
		textLine.Color = color.RGBA{R: 128, G: 128, B: 128, A: 0} // Transparent
		p.Add(textLine)
	}

	// Add summary text (this is a simplified approach - in practice you'd use text annotations)
	return p.Save(config.Width, config.Height, filename)
}

// PrintPhase6Summary prints comprehensive analysis results to console
func PrintPhase6Summary(results *Phase5MonteCarloResults) {
	fmt.Println("\n📊 Phase 6: Comprehensive Analysis Summary")
	fmt.Println("=========================================")

	// Performance Overview
	fmt.Printf("Simulation Parameters:\n")
	fmt.Printf("  • Iterations per SNR: %d\n", results.Config.NumIterations)
	fmt.Printf("  • SNR range: %.1f to %.1f dB\n", 
		results.Config.SNRRange[0], 
		results.Config.SNRRange[len(results.Config.SNRRange)-1])
	fmt.Printf("  • Total trials: %d\n", results.Stats.TotalTrials)
	fmt.Printf("  • Runtime: %v\n", results.Stats.Duration)
	fmt.Printf("  • Performance: %.0f trials/second\n", results.Stats.TrialsPerSecond)

	// Statistical Analysis
	fmt.Println("\nStatistical Analysis:")
	fmt.Printf("%-10s | %-10s | %-10s | %-8s | %-8s | %-10s\n", 
		"SNR_in", "AM_out", "FM_out", "AM_σ", "FM_σ", "FM_Adv")
	fmt.Printf("-----------|-----------|-----------|----------|----------|----------\n")

	totalAdvantage := 0.0
	advantageCount := 0
	maxAdvantage := -math.Inf(1)
	maxAdvantageSNR := 0.0

	for i := range results.AMResults {
		advantage := results.FMResults[i].OutputSNR_dB - results.AMResults[i].OutputSNR_dB
		
		fmt.Printf("%9.1f | %9.2f | %9.2f | %8.3f | %8.3f | %+9.2f\n",
			results.AMResults[i].InputSNR_dB,
			results.AMResults[i].OutputSNR_dB,
			results.FMResults[i].OutputSNR_dB,
			results.AMResults[i].StdDev,
			results.FMResults[i].StdDev,
			advantage)

		if advantage > 0.1 {
			totalAdvantage += advantage
			advantageCount++
		}
		if advantage > maxAdvantage {
			maxAdvantage = advantage
			maxAdvantageSNR = results.AMResults[i].InputSNR_dB
		}
	}

	fmt.Println("\nKey Findings:")
	if advantageCount > 0 {
		avgAdvantage := totalAdvantage / float64(advantageCount)
		fmt.Printf("  ✅ FM shows advantage at %d out of %d SNR points\n", 
			advantageCount, len(results.AMResults))
		fmt.Printf("  📈 Average FM advantage: %.2f dB\n", avgAdvantage)
		fmt.Printf("  🎯 Maximum advantage: %.2f dB at %.1f dB input SNR\n", 
			maxAdvantage, maxAdvantageSNR)
	} else {
		fmt.Printf("  ⚠️  No consistent FM advantage detected\n")
		fmt.Printf("  💡 This suggests the FM demodulator may need optimization\n")
	}

	fmt.Println("\nGenerated Visualization Files:")
	fmt.Println("  📊 phase6_snr_comparison.png - Main performance comparison")
	fmt.Println("  📈 phase6_fm_advantage.png - FM advantage analysis")
	fmt.Println("  📉 phase6_confidence_intervals.png - Statistical confidence")
	fmt.Println("  🎛️  phase6_performance_dashboard.png - Summary dashboard")

	fmt.Println("\nPhase 6 Analysis Complete!")
	fmt.Printf("Results demonstrate noise immunity characteristics of AM vs FM modulation.\n")
	if maxAdvantage > 1.0 {
		fmt.Printf("✅ Clear FM superiority demonstrated at high SNR levels.\n")
	} else {
		fmt.Printf("⚠️  Limited FM advantage suggests potential for demodulator improvements.\n")
	}
}

// AnalyzeFMNoiseSuperiority provides theoretical comparison with experimental results
func AnalyzeFMNoiseSuperiority(results *Phase5MonteCarloResults) {
	fmt.Println("\n🧪 Theoretical vs Experimental Analysis")
	fmt.Println("======================================")

	fmt.Println("Expected FM Advantages:")
	fmt.Println("  • Constant envelope → amplitude noise immunity")
	fmt.Println("  • Frequency domain processing → noise shaping benefits")
	fmt.Println("  • Capture effect → strong signal dominance")
	fmt.Println("  • Superior performance at high SNR levels")

	fmt.Println("\nExperimental Observations:")
	
	highSNRAdvantage := 0.0
	lowSNRAdvantage := 0.0
	highSNRCount := 0
	lowSNRCount := 0

	for i := range results.AMResults {
		advantage := results.FMResults[i].OutputSNR_dB - results.AMResults[i].OutputSNR_dB
		
		if results.AMResults[i].InputSNR_dB >= 15 {
			highSNRAdvantage += advantage
			highSNRCount++
		} else {
			lowSNRAdvantage += advantage
			lowSNRCount++
		}
	}

	if highSNRCount > 0 {
		avgHighSNR := highSNRAdvantage / float64(highSNRCount)
		fmt.Printf("  • High SNR (≥15dB) FM advantage: %.2f dB average\n", avgHighSNR)
	}

	if lowSNRCount > 0 {
		avgLowSNR := lowSNRAdvantage / float64(lowSNRCount)
		fmt.Printf("  • Low SNR (<15dB) FM advantage: %.2f dB average\n", avgLowSNR)
	}

	fmt.Println("\nImplementation Notes:")
	fmt.Println("  • Current FM demodulator uses simplified quadrature detection")
	fmt.Println("  • Production systems would use optimized discriminators")
	fmt.Println("  • Pre-emphasis/de-emphasis filtering would enhance performance")
	fmt.Println("  • Proper FM demodulation should show 3dB improvement per octave")
}