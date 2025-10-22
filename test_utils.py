"""Unit tests for utility functions and performance analysis."""

import unittest
import numpy as np
import tempfile
import os

from config import SimulationParams
from utils import calculate_output_snr, run_monte_carlo_trial, save_results_csv, save_results_json
from utils import PerformanceResults


class TestUtilsFunctions(unittest.TestCase):
    """Test utility functions."""
    
    def setUp(self):
        """Set up test parameters."""
        self.params = SimulationParams(
            sampling_rate=10000.0,
            duration=0.1,
            message_freq=1000.0,
            carrier_freq=5000.0,
            am_index=0.5,
            fm_deviation=2000.0,
            snr_min=0.0,
            snr_max=20.0,
            snr_step=5.0,
            trials=10,
            message_amplitude=1.0,
            carrier_amplitude=1.0
        )
    
    def test_output_snr_calculation(self):
        """Test output SNR calculation."""
        # Create test signals
        original = np.sin(2 * np.pi * 1000 * np.linspace(0, 0.1, 1000))
        demodulated = original + 0.1 * np.random.randn(1000)  # Add noise
        
        snr_db = calculate_output_snr(original, demodulated)
        
        # Should be a reasonable SNR value
        self.assertIsInstance(snr_db, float)
        self.assertGreater(snr_db, 0)
        self.assertLess(snr_db, 100)  # Should not be unreasonably high
    
    def test_output_snr_perfect_reconstruction(self):
        """Test output SNR with perfect reconstruction."""
        original = np.sin(2 * np.pi * 1000 * np.linspace(0, 0.1, 1000))
        demodulated = original.copy()  # Perfect reconstruction
        
        snr_db = calculate_output_snr(original, demodulated)
        
        # Should be infinite SNR for perfect reconstruction
        self.assertEqual(snr_db, float('inf'))
    
    def test_output_snr_different_lengths(self):
        """Test output SNR with signals of different lengths."""
        original = np.sin(2 * np.pi * 1000 * np.linspace(0, 0.1, 1000))
        demodulated = original[:500] + 0.1 * np.random.randn(500)  # Shorter signal
        
        snr_db = calculate_output_snr(original, demodulated)
        
        # Should handle different lengths gracefully
        self.assertIsInstance(snr_db, float)
        self.assertGreater(snr_db, 0)
    
    def test_monte_carlo_trial(self):
        """Test single Monte Carlo trial."""
        result = run_monte_carlo_trial(self.params, 10.0, 0)
        
        # Check that result has correct structure
        self.assertEqual(result.input_snr_db, 10.0)
        self.assertEqual(result.trial_id, 0)
        self.assertIsInstance(result.output_snr_am_db, float)
        self.assertIsInstance(result.output_snr_fm_db, float)
        
        # Check that output SNRs are reasonable
        self.assertGreater(result.output_snr_am_db, 0)
        self.assertGreater(result.output_snr_fm_db, 0)
        self.assertLess(result.output_snr_am_db, 100)
        self.assertLess(result.output_snr_fm_db, 100)
    
    def test_monte_carlo_trial_reproducibility(self):
        """Test that Monte Carlo trials are reproducible with same parameters."""
        result1 = run_monte_carlo_trial(self.params, 10.0, 42)
        result2 = run_monte_carlo_trial(self.params, 10.0, 42)
        
        # Should be identical with same trial ID (seed)
        self.assertAlmostEqual(result1.output_snr_am_db, result2.output_snr_am_db, places=10)
        self.assertAlmostEqual(result1.output_snr_fm_db, result2.output_snr_fm_db, places=10)
    
    def test_save_results_csv(self):
        """Test saving results to CSV."""
        # Create mock results
        results = PerformanceResults(
            snr_levels=[0.0, 5.0, 10.0],
            am_results={0.0: [1.0, 2.0], 5.0: [3.0, 4.0], 10.0: [5.0, 6.0]},
            fm_results={0.0: [1.5, 2.5], 5.0: [3.5, 4.5], 10.0: [5.5, 6.5]},
            am_means={0.0: 1.5, 5.0: 3.5, 10.0: 5.5},
            fm_means={0.0: 2.0, 5.0: 4.0, 10.0: 6.0},
            am_stds={0.0: 0.5, 5.0: 0.5, 10.0: 0.5},
            fm_stds={0.0: 0.5, 5.0: 0.5, 10.0: 0.5}
        )
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            temp_path = f.name
        
        try:
            save_results_csv(results, temp_path)
            
            # Check that file was created and has content
            self.assertTrue(os.path.exists(temp_path))
            with open(temp_path, 'r') as f:
                content = f.read()
                self.assertIn('Input_SNR_dB', content)
                self.assertIn('AM_Mean_Output_SNR_dB', content)
                self.assertIn('FM_Mean_Output_SNR_dB', content)
        finally:
            os.unlink(temp_path)
    
    def test_save_results_json(self):
        """Test saving results to JSON."""
        # Create mock results
        results = PerformanceResults(
            snr_levels=[0.0, 5.0, 10.0],
            am_results={0.0: [1.0, 2.0], 5.0: [3.0, 4.0], 10.0: [5.0, 6.0]},
            fm_results={0.0: [1.5, 2.5], 5.0: [3.5, 4.5], 10.0: [5.5, 6.5]},
            am_means={0.0: 1.5, 5.0: 3.5, 10.0: 5.5},
            fm_means={0.0: 2.0, 5.0: 4.0, 10.0: 6.0},
            am_stds={0.0: 0.5, 5.0: 0.5, 10.0: 0.5},
            fm_stds={0.0: 0.5, 5.0: 0.5, 10.0: 0.5}
        )
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            save_results_json(results, temp_path)
            
            # Check that file was created and has content
            self.assertTrue(os.path.exists(temp_path))
            with open(temp_path, 'r') as f:
                content = f.read()
                self.assertIn('snr_levels', content)
                self.assertIn('am_means', content)
                self.assertIn('fm_means', content)
        finally:
            os.unlink(temp_path)
    
    def test_edge_cases(self):
        """Test edge cases for utility functions."""
        # Test with very short signals
        short_original = np.array([1.0, 2.0, 3.0])
        short_demodulated = np.array([1.1, 2.1, 3.1])
        
        snr_db = calculate_output_snr(short_original, short_demodulated)
        self.assertIsInstance(snr_db, float)
        
        # Test with identical signals
        identical_signal = np.array([1.0, 2.0, 3.0, 4.0])
        snr_db_identical = calculate_output_snr(identical_signal, identical_signal)
        self.assertEqual(snr_db_identical, float('inf'))
        
        # Test with zero signal
        zero_signal = np.zeros(100)
        snr_db_zero = calculate_output_snr(zero_signal, zero_signal)
        self.assertEqual(snr_db_zero, float('inf'))


if __name__ == '__main__':
    unittest.main()
