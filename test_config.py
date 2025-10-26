"""Unit tests for configuration functions."""

import unittest
import sys
from unittest.mock import patch

from config import SimulationParams, validate_params, choose_params, summarize_params


class TestConfigFunctions(unittest.TestCase):
    """Test configuration functions."""
    
    def setUp(self):
        """Set up test parameters."""
        self.default_params = SimulationParams()
    
    def test_default_parameters(self):
        """Test that default parameters are reasonable."""
        params = SimulationParams()
        
        # Check that all parameters are positive where expected
        self.assertGreater(params.sampling_rate, 0)
        self.assertGreater(params.duration, 0)
        self.assertGreater(params.message_freq, 0)
        self.assertGreater(params.carrier_freq, 0)
        self.assertGreaterEqual(params.am_index, 0)
        self.assertLessEqual(params.am_index, 1)
        self.assertGreater(params.fm_deviation, 0)
        self.assertGreater(params.trials, 0)
        self.assertGreater(params.message_amplitude, 0)
        self.assertGreater(params.carrier_amplitude, 0)
    
    def test_parameter_validation(self):
        """Test parameter validation."""
        # Test with valid parameters
        valid_params = SimulationParams(
            sampling_rate=10000.0,
            duration=0.1,
            message_freq=1000.0,
            carrier_freq=5000.0,
            am_index=0.5,
            fm_deviation=2000.0,
            snr_min=0.0,
            snr_max=20.0,
            snr_step=5.0,
            trials=100,
            message_amplitude=1.0,
            carrier_amplitude=1.0
        )
        
        validated = validate_params(valid_params)
        self.assertEqual(validated.sampling_rate, 10000.0)
        self.assertEqual(validated.duration, 0.1)
        self.assertEqual(validated.trials, 100)
    
    def test_parameter_validation_invalid_inputs(self):
        """Test parameter validation with invalid inputs."""
        # Test with negative sampling rate
        invalid_params = SimulationParams(sampling_rate=-1000.0)
        validated = validate_params(invalid_params)
        self.assertGreater(validated.sampling_rate, 0)  # Should be corrected to default
        
        # Test with AM index > 1
        invalid_params = SimulationParams(am_index=1.5)
        validated = validate_params(invalid_params)
        self.assertLessEqual(validated.am_index, 1.0)  # Should be clamped
        
        # Test with negative trials
        invalid_params = SimulationParams(trials=-10)
        validated = validate_params(invalid_params)
        self.assertGreater(validated.trials, 0)  # Should be corrected to default
    
    def test_parameter_validation_nyquist(self):
        """Test Nyquist frequency validation."""
        # Test with carrier frequency above Nyquist
        invalid_params = SimulationParams(sampling_rate=10000.0, carrier_freq=6000.0)
        validated = validate_params(invalid_params)
        self.assertLess(validated.carrier_freq, validated.sampling_rate / 2.0)
        
        # Test with message frequency above Nyquist
        invalid_params = SimulationParams(sampling_rate=10000.0, message_freq=6000.0)
        validated = validate_params(invalid_params)
        self.assertLess(validated.message_freq, validated.sampling_rate / 2.0)
    
    def test_summarize_params(self):
        """Test parameter summary generation."""
        summary = summarize_params(self.default_params)
        
        # Check that summary contains key information
        self.assertIn('fs:', summary)
        self.assertIn('duration:', summary)
        self.assertIn('fm:', summary)
        self.assertIn('fc:', summary)
        # String matches current summary format
        self.assertIn('AM index ka:', summary)
        self.assertIn('FM deviation:', summary)
        self.assertIn('SNR range (dB):', summary)
        self.assertIn('trials:', summary)
    
    def test_choose_params_with_args(self):
        """Test parameter selection with command line arguments."""
        # Mock command line arguments
        test_args = [
            'main.py',
            '--fs', '20000',
            '--duration', '0.2',
            '--trials', '50',
            '--snr-min', '0',
            '--snr-max', '30'
        ]
        
        with patch.object(sys, 'argv', test_args):
            params = choose_params()
            
            # Check that parameters were set correctly
            self.assertEqual(params.sampling_rate, 20000.0)
            self.assertEqual(params.duration, 0.2)
            self.assertEqual(params.trials, 50)
            self.assertEqual(params.snr_min, 0.0)
            self.assertEqual(params.snr_max, 30.0)
    
    def test_choose_params_validation(self):
        """Test that choose_params validates parameters."""
        # Test with invalid arguments that should be corrected
        test_args = [
            'main.py',
            '--fs', '-1000',  # Invalid negative sampling rate
            '--am-index', '2.0',  # Invalid AM index > 1
            '--trials', '-10'  # Invalid negative trials
        ]
        
        with patch.object(sys, 'argv', test_args):
            params = choose_params()
            
            # Check that invalid parameters were corrected
            self.assertGreater(params.sampling_rate, 0)
            self.assertLessEqual(params.am_index, 1.0)
            self.assertGreater(params.trials, 0)
    
    def test_edge_cases(self):
        """Test edge cases for configuration."""
        # Test with very small values
        small_params = SimulationParams(
            sampling_rate=100.0,
            duration=0.001,
            message_freq=10.0,
            carrier_freq=50.0,
            trials=1
        )
        
        validated = validate_params(small_params)
        self.assertGreater(validated.sampling_rate, 0)
        self.assertGreater(validated.duration, 0)
        self.assertGreater(validated.trials, 0)
        
        # Test with very large values
        large_params = SimulationParams(
            sampling_rate=1000000.0,
            duration=10.0,
            message_freq=10000.0,
            carrier_freq=100000.0,
            trials=10000
        )
        
        validated = validate_params(large_params)
        self.assertGreater(validated.sampling_rate, 0)
        self.assertGreater(validated.duration, 0)
        self.assertGreater(validated.trials, 0)


if __name__ == '__main__':
    unittest.main()
