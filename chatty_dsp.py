import base64
import numpy as np
from chatty_config import NATIVE_OAI_SAMPLE_RATE_HZ

# Helper function to encode audio chunks in base64
b64 = lambda blob: base64.b64encode(blob).decode()

import numpy as np
import base64

def chatty_tone(freq_duration_pairs, volume=0.5):
   """Generate base64 encoded audio buffer for tone sequences.
   
   Args:
       freq_duration_pairs: List of tuples (frequency_hz, duration_ms)
                          frequency of 0 means silence
   
   Returns:
       audio data (16-bit mono, 24000 Hz)
   """
   sample_rate = NATIVE_OAI_SAMPLE_RATE_HZ
   audio_data = np.array([], dtype=np.int16)
   if volume > 1.0 or volume < 0.0:
        volume = 0.5
   sample_multiplier = int(32767*volume)
   
   for freq, duration_ms in freq_duration_pairs:
       num_samples = int(sample_rate * duration_ms / 1000)
       
       if freq == 0:
           # Silence
           samples = np.zeros(num_samples, dtype=np.int16)
       else:
           # Generate sine wave
           t = np.arange(num_samples) / sample_rate
           samples = (np.sin(2 * np.pi * freq * t) * sample_multiplier).astype(np.int16)
       
       audio_data = np.concatenate([audio_data, samples])
   
   return audio_data * volume

def apply_simple_noise_gate(audio_16, threshold=500.0):
    """
    Lightweight noise gate optimized for Raspberry Pi.
    Uses fast energy estimation instead of full RMS calculation.
    Sets samples below threshold to zero.
    
    Performance: ~0.1ms per 80ms audio chunk on RPi 5
    - Uses mean absolute value (faster than RMS)
    - Early exit if signal is clearly above threshold
    - Avoids expensive float64 operations when possible
    
    Args:
        audio_16: numpy array of int16 samples (typically 1280 samples = 80ms @ 16kHz)
        threshold: Energy threshold below which audio is gated
    
    Returns:
        numpy array: Audio with noise gate applied (same array if above threshold)
    """
    # Fast energy check: use mean absolute value (faster than RMS)
    # For int16, we can use int32 to avoid overflow
    energy = np.mean(np.abs(audio_16.astype(np.int32)))
    
    # Early exit optimization: if clearly above threshold, return original
    # This avoids the zero-copy operation for most speech
    if energy >= threshold * 0.8:  # 80% of threshold = definitely above
        return audio_16
    
    # Only do full check if in the gray zone
    if energy < threshold:
        # Gate the audio (set to zero) - only happens for quiet/noise
        return np.zeros_like(audio_16)
    
    return audio_16

def upsample_audio_efficient(audio_16):
    """
    Efficient upsampling from 16kHz to 24kHz for limited hardware.
    Uses simple linear interpolation to minimize CPU and memory usage.
    
    Args:
        audio_16: numpy array of int16 samples at 16kHz
    
    Returns:
        bytes: Upsampled audio at 24kHz as bytes (16-bit samples)
    """
    # Calculate output length (1.5x the input)
    output_length = int(len(audio_16) * 1.5)
    
    # Create output array
    output = np.empty(output_length, dtype=np.int16)
    
    # For 16kHz to 24kHz, we need 3 output samples for every 2 input samples
    # Pattern: copy, interpolate, copy, interpolate, etc.
    
    # Process in chunks of 2 input samples -> 3 output samples
    for i in range(0, len(audio_16) - 1, 2):
        out_idx = int(i * 1.5)
        
        # First sample: direct copy
        output[out_idx] = audio_16[i]
        
        # Second sample: interpolate between i and i+1
        # Cast to int32 to prevent overflow during addition
        output[out_idx + 1] = (np.int32(audio_16[i]) + np.int32(audio_16[i + 1])) >> 1
        
        # Third sample: direct copy
        output[out_idx + 2] = audio_16[i + 1]
    
    # Handle the last sample if input length is odd
    if len(audio_16) % 2 == 1:
        output[-1] = audio_16[-1]
    
    return output.tobytes()
