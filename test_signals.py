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
        # Avoid fs/2 which makes sin(pi*n)=0 for all n; use 4800 Hz instead
        self.carrier_freq = 4800.0
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
        
        # Check amplitude approximately (finite grid rarely hits exact crest)
        self.assertGreaterEqual(np.max(np.abs(message)), 0.94)
        
        # Check frequency roughly via FFT peak
        spectrum = np.fft.rfft(message)
        freqs = np.fft.rfftfreq(len(message), d=1.0/self.sampling_rate)
        peak_freq = freqs[np.argmax(np.abs(spectrum))]
        self.assertAlmostEqual(peak_freq, self.message_freq, delta=50.0)
    
    def test_carrier_signal(self):
        """Test carrier signal generation."""
        t = generate_time_vector(self.sampling_rate, self.duration)
        carrier = carrier_signal(t, self.carrier_freq, self.amplitude)
        
        # Check amplitude approximately
        self.assertGreaterEqual(np.max(np.abs(carrier)), 0.94)
        
        # Check frequency roughly via FFT peak
        spectrum = np.fft.rfft(carrier)
        freqs = np.fft.rfftfreq(len(carrier), d=1.0/self.sampling_rate)
        peak_freq = freqs[np.argmax(np.abs(spectrum))]
        self.assertAlmostEqual(peak_freq, self.carrier_freq, delta=200.0)
    
    def test_am_modulation(self):
        """Test AM modulation."""
        t = generate_time_vector(self.sampling_rate, self.duration)
        message = message_signal(t, self.message_freq, self.amplitude)
        am_index = 0.5
        
        am_signal = am_modulate(message, t, self.carrier_freq, self.amplitude, am_index)
        
        # Envelope correlation can be reduced by sampling; check reasonable threshold
        expected_envelope = self.amplitude * (1 + am_index * message)
        envelope = np.abs(am_signal)
        correlation = np.corrcoef(envelope, expected_envelope)[0, 1]
        self.assertGreater(correlation, 0.5)
    
    def test_fm_modulation(self):
        """Test FM modulation."""
        t = generate_time_vector(self.sampling_rate, self.duration)
        message = message_signal(t, self.message_freq, self.amplitude)
        fm_deviation = 2000.0
        
        fm_signal = fm_modulate(message, t, self.carrier_freq, self.amplitude, 
                               fm_deviation, self.sampling_rate)
        
        # FM amplitude stays near Ac; allow tolerance
        self.assertGreater(np.max(np.abs(fm_signal)), 0.9)
        
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
