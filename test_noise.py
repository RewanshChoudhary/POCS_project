"""Unit tests for noise addition functions."""

import unittest
import numpy as np

from noise import add_gaussian_noise, calculate_signal_power, calculate_noise_power, calculate_snr_db


class TestNoiseFunctions(unittest.TestCase):
    """Test noise addition and SNR calculation functions."""
    
    def setUp(self):
        """Set up test parameters."""
        self.signal_length = 1000
        self.test_signal = np.ones(self.signal_length)  # DC signal for easy testing
        self.snr_db = 10.0
        
    def test_signal_power_calculation(self):
        """Test signal power calculation."""
        # Test with known signal
        signal = np.array([1.0, 2.0, 3.0, 4.0])
        expected_power = np.mean(signal**2)
        calculated_power = calculate_signal_power(signal)
        self.assertAlmostEqual(calculated_power, expected_power, places=10)
        
        # Test with DC signal
        dc_signal = np.ones(100) * 2.0
        expected_power = 4.0
        calculated_power = calculate_signal_power(dc_signal)
        self.assertAlmostEqual(calculated_power, expected_power, places=10)
    
    def test_noise_power_calculation(self):
        """Test noise power calculation."""
        clean_signal = np.ones(100)
        noisy_signal = clean_signal + 0.1 * np.ones(100)  # Add constant noise
        noise_power = calculate_noise_power(clean_signal, noisy_signal)
        expected_noise_power = 0.01  # (0.1)^2
        self.assertAlmostEqual(noise_power, expected_noise_power, places=10)
    
    def test_snr_calculation(self):
        """Test SNR calculation in dB."""
        signal_power = 1.0
        noise_power = 0.1
        snr_db = calculate_snr_db(signal_power, noise_power)
        expected_snr_db = 10.0  # 10*log10(1.0/0.1) = 10*log10(10) = 10
        self.assertAlmostEqual(snr_db, expected_snr_db, places=10)
        
        # Test with zero noise power
        snr_db_inf = calculate_snr_db(signal_power, 0.0)
        self.assertEqual(snr_db_inf, float('inf'))
    
    def test_gaussian_noise_addition(self):
        """Test Gaussian noise addition."""
        # Test with deterministic seed
        noisy_signal = add_gaussian_noise(self.test_signal, self.snr_db, seed=42)
        
        # Check that noise was added
        self.assertFalse(np.allclose(noisy_signal, self.test_signal))
        
        # Check that the signal length is preserved
        self.assertEqual(len(noisy_signal), len(self.test_signal))
        
        # Check that the noise has approximately the right power
        noise = noisy_signal - self.test_signal
        noise_power = calculate_signal_power(noise)
        signal_power = calculate_signal_power(self.test_signal)
        expected_noise_power = signal_power / (10**(self.snr_db/10))
        
        # Allow for some variance due to random noise
        self.assertAlmostEqual(noise_power, expected_noise_power, delta=expected_noise_power*0.5)
    
    def test_noise_reproducibility(self):
        """Test that noise addition is reproducible with same seed."""
        noisy1 = add_gaussian_noise(self.test_signal, self.snr_db, seed=123)
        noisy2 = add_gaussian_noise(self.test_signal, self.snr_db, seed=123)
        
        # Should be identical with same seed
        self.assertTrue(np.allclose(noisy1, noisy2))
        
        # Should be different with different seeds
        noisy3 = add_gaussian_noise(self.test_signal, self.snr_db, seed=456)
        self.assertFalse(np.allclose(noisy1, noisy3))
    
    def test_different_snr_levels(self):
        """Test noise addition with different SNR levels."""
        snr_levels = [0, 10, 20, 30]
        
        for snr_db in snr_levels:
            noisy_signal = add_gaussian_noise(self.test_signal, snr_db, seed=42)
            
            # Calculate actual SNR
            noise = noisy_signal - self.test_signal
            signal_power = calculate_signal_power(self.test_signal)
            noise_power = calculate_signal_power(noise)
            actual_snr_db = calculate_snr_db(signal_power, noise_power)
            
            # Should be close to requested SNR (allow for some variance)
            self.assertAlmostEqual(actual_snr_db, snr_db, delta=2.0)
    
    def test_edge_cases(self):
        """Test edge cases."""
        # Zero signal
        zero_signal = np.zeros(100)
        noisy_zero = add_gaussian_noise(zero_signal, 10.0, seed=42)
        self.assertEqual(len(noisy_zero), len(zero_signal))
        
        # Very high SNR (should be close to original)
        high_snr_signal = add_gaussian_noise(self.test_signal, 60.0, seed=42)
        self.assertTrue(np.allclose(high_snr_signal, self.test_signal, atol=1e-6))
        
        # Very low SNR
        low_snr_signal = add_gaussian_noise(self.test_signal, -10.0, seed=42)
        # Should be very noisy
        noise_power = calculate_signal_power(low_snr_signal - self.test_signal)
        signal_power = calculate_signal_power(self.test_signal)
        self.assertGreater(noise_power, signal_power)


if __name__ == '__main__':
    unittest.main()
