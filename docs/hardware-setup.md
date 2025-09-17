# Hardware Setup Guide

This guide provides detailed instructions for setting up the hardware components for Chatty Friend.

## Required Hardware

### Raspberry Pi Setup
- **Raspberry Pi 5** (4GB or 8GB RAM recommended)
  - 4GB minimum for stable operation
  - 8GB recommended for better performance
- **MicroSD Card** (16GB minimum, industrial grade recommended)
  - 64GB recommended for logs and audio caching
  - Use reputable brands and lookout for counterfeit cards (SanDisk, Samsung)
- **Power Supply**
  - Official Raspberry Pi USB-C Power Supply with 10 Watts to spare for the speakerphone (45 watt total tested)
  - Avoid underpowered supplies - causes audio issues
- **Case with Cooling** (recommended)
  - Passive cooling minimum
  - Active cooling for 24/7 operation

### Audio Hardware

#### Recommended USB Speakerphones
1. **Jabra Speak 410** (Tested & Recommended)
   - Excellent noise cancellation
   - Clear audio pickup from 360°
   - Plug-and-play with Raspberry Pi
   - Price: ~$80-100

2. **Jabra Speak 510** 
   - Bluetooth + USB capabilities
   - Slightly better audio quality than 410
   - Price: ~$100-150

3. **Alternative Options (untested) **
   - eMeet M0/M1/M2 series
   - Anker PowerConf S3
   - Any USB speakerphone with Linux support

#### What to Avoid
- Bluetooth-only devices (connectivity issues)
- 3.5mm jack microphones (poor quality)
- Separate mic/speaker setups (echo problems)

## Physical Setup

### Optimal Placement
1. **Central Location**
   - Place in main living area
   - Avoid corners (echo/reverb)
   - 3-6 feet from primary seating
   - Away from TV/radio speakers

2. **Surface Requirements**
   - Stable, flat surface
   - Away from vibration sources
   - Good ventilation around Pi
   - Easy access to power

3. **Acoustic Considerations**
   - Minimize background noise
   - Soft furnishings help reduce echo
   - Keep away from windows (traffic noise)
   - Test different locations for best results


## Troubleshooting Hardware

Before installing Chatty Friend software:

### 1. Test Raspberry Pi Boot
```bash
# Connect monitor and keyboard temporarily
# Verify Ubuntu boots properly
# Check system info
uname -a
free -h
df -h
```

### 2. Test Audio Hardware
```bash
# List audio devices
aplay -l
arecord -l

# Your USB speakerphone should appear in both lists
# Look for something like "Jabra SPEAK 410 USB"

# Test speaker
speaker-test -t wav -c 2

# Test microphone (speak and press Ctrl+C after few seconds)
arecord -d 5 test.wav
aplay test.wav
rm test.wav
```

### 3. Set Default Audio Device
```bash
# Create/edit ALSA configuration
nano ~/.asoundrc
```

Add this configuration (adjust card number based on `aplay -l`):
```
pcm.!default {
    type asym
    playback.pcm {
        type plug
        slave.pcm "hw:2,0"  # Change 2 to your device number
    }
    capture.pcm {
        type plug
        slave.pcm "hw:2,0"  # Change 2 to your device number
    }
}
```

### 4. Network Connection Test
```bash
# Check internet connectivity
ping -c 4 8.8.8.8
ping -c 4 google.com

# Check WiFi signal strength
iwconfig wlan0
```

## Troubleshooting Hardware Issues

### No Audio Output
1. Check USB connection
2. Verify device appears in `aplay -l`
3. Test with different USB port
4. Check volume: `alsamixer`
5. Ensure speakerphone is not muted

### Poor Audio Quality
1. Move speakerphone away from walls
2. Reduce background noise
3. Check USB power (use powered hub if needed)
4. Update system: `sudo apt update && sudo apt upgrade`
5. Try different audio format in configuration

### Wake Word Not Detecting
1. Test microphone levels: `alsamixer`
2. Ensure quiet environment for training
3. Speak clearly, not too fast
4. Check speakerphone placement
5. Retrain wake word model if needed

### WiFi Connection Issues
1. Use 2.4GHz network (not 5GHz)
2. Check signal strength
3. Ensure correct password
4. Disable power management:
   ```bash
   sudo iw dev wlan0 set power_save off
   ```

### Overheating
1. Check CPU temperature:
   ```bash
   vcgencmd measure_temp
   ```
2. Improve ventilation
3. Add heatsinks or fan
4. Reduce room temperature
5. Check for dust buildup

## Performance Optimization

### Audio Latency
```bash
# Edit audio configuration
sudo nano /etc/pulse/daemon.conf

# Add/modify these lines:
default-sample-rate = 16000
default-fragments = 2
default-fragment-size-msec = 10
```

### System Performance
```bash
# Disable unnecessary services
sudo systemctl disable bluetooth
sudo systemctl disable cups

# Set governor to performance
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
```

## Next Steps

Once hardware is set up and tested:
1. Continue with [Software Installation](../README.md#-raspberry-pi-installation-guide)
2. Configure using [Web Interface Guide](web-interface-guide.md)
3. Learn about [Creating Custom Tools](tool-development.md)