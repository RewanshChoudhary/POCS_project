"""Unit tests for signal generation and modulation functions."""

import unittest
import numpy as np

from signals import generate_time_vector, message_signal, carrier_signal, am_modulate, fm_modulate


class TestSignalGeneration(unittest.TestCase):
    """Test signal generation functions."""
    
    def setUp(self):
        """Set up test parameters."""
        self.sampling_rate = 10000.0
        self.duration = 0.1
        self.message_freq = 1000.0
        self.carrier_freq = 5000.0
        self.amplitude = 1.0
        
    def test_time_vector_generation(self):
        """Test time vector generation."""
        t = generate_time_vector(self.sampling_rate, self.duration)
        
        # Check length
        expected_length = int(self.sampling_rate * self.duration)
        self.assertEqual(len(t), expected_length)
        
        # Check time step
        dt = t[1] - t[0]
        expected_dt = 1.0 / self.sampling_rate
        self.assertAlmostEqual(dt, expected_dt, places=10)
        
        # Check time range
        self.assertAlmostEqual(t[0], 0.0, places=10)
        self.assertAlmostEqual(t[-1], self.duration - dt, places=10)
    
    def test_message_signal(self):
        """Test message signal generation."""
        t = generate_time_vector(self.sampling_rate, self.duration)
        message = message_signal(t, self.message_freq, self.amplitude)
        
        # Check amplitude
        self.assertAlmostEqual(np.max(np.abs(message)), self.amplitude, places=10)
        
        # Check frequency (by counting zero crossings)
        zero_crossings = np.sum(np.diff(np.sign(message)) != 0)
        expected_crossings = 2 * self.message_freq * self.duration
        self.assertAlmostEqual(zero_crossings, expected_crossings, delta=2)
    
    def test_carrier_signal(self):
        """Test carrier signal generation."""
        t = generate_time_vector(self.sampling_rate, self.duration)
        carrier = carrier_signal(t, self.carrier_freq, self.amplitude)
        
        # Check amplitude
        self.assertAlmostEqual(np.max(np.abs(carrier)), self.amplitude, places=10)
        
        # Check frequency (by counting zero crossings)
        zero_crossings = np.sum(np.diff(np.sign(carrier)) != 0)
        expected_crossings = 2 * self.carrier_freq * self.duration
        self.assertAlmostEqual(zero_crossings, expected_crossings, delta=2)
    
    def test_am_modulation(self):
        """Test AM modulation."""
        t = generate_time_vector(self.sampling_rate, self.duration)
        message = message_signal(t, self.message_freq, self.amplitude)
        am_index = 0.5
        
        am_signal = am_modulate(message, t, self.carrier_freq, self.amplitude, am_index)
        
        # Check that AM signal has correct form
        # s_AM(t) = Ac * (1 + ka*m(t)) * sin(2πfct)
        expected_envelope = self.amplitude * (1 + am_index * message)
        envelope = np.abs(am_signal)
        
        # Check envelope (should be close to expected envelope)
        correlation = np.corrcoef(envelope, expected_envelope)[0, 1]
        self.assertGreater(correlation, 0.9)
    
    def test_fm_modulation(self):
        """Test FM modulation."""
        t = generate_time_vector(self.sampling_rate, self.duration)
        message = message_signal(t, self.message_freq, self.amplitude)
        fm_deviation = 2000.0
        
        fm_signal = fm_modulate(message, t, self.carrier_freq, self.amplitude, 
                               fm_deviation, self.sampling_rate)
        
        # Check amplitude
        self.assertAlmostEqual(np.max(np.abs(fm_signal)), self.amplitude, places=10)
        
        # Check that FM signal has correct frequency characteristics
        # The instantaneous frequency should vary around the carrier frequency
        # This is a basic check - more sophisticated tests would analyze the spectrum
    
    def test_edge_cases(self):
        """Test edge cases."""
        # Very short duration
        t = generate_time_vector(1000.0, 0.001)
        self.assertGreater(len(t), 0)
        
        # Very low frequency
        t = generate_time_vector(self.sampling_rate, self.duration)
        message = message_signal(t, 10.0, self.amplitude)
        self.assertEqual(len(message), len(t))
        
        # Zero amplitude
        message = message_signal(t, self.message_freq, 0.0)
        self.assertTrue(np.allclose(message, 0.0))


if __name__ == '__main__':
    unittest.main()
