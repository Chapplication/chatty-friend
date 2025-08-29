#!/bin/bash
# Setup script for Chatty Friend Voice Assistant Captive Portal
# This script installs and configures captive portal functionality

set -e  # Exit on any error

echo "🎙️ Setting up Chatty Friend Voice Assistant Captive Portal..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ This script must be run as root (use sudo)"
    exit 1
fi

# Install required packages
echo "📦 Installing required packages..."
apt-get update
apt-get install -y dnsmasq iptables-persistent flask

# Stop services that might conflict
echo "🛑 Stopping conflicting services..."
systemctl stop systemd-resolved 2>/dev/null || true
systemctl disable systemd-resolved 2>/dev/null || true

# Backup original dnsmasq config
if [ -f "/etc/dnsmasq.conf" ] && [ ! -f "/etc/dnsmasq.conf.backup" ]; then
    echo "💾 Backing up original dnsmasq configuration..."
    cp /etc/dnsmasq.conf /etc/dnsmasq.conf.backup
fi

# Install captive portal dnsmasq configuration
echo "⚙️ Installing captive portal DNS configuration..."
cp dnsmasq-captive.conf /etc/dnsmasq-captive.conf

# Note: No separate captive portal service needed
# The existing Streamlit server on port 80 + DNS hijacking provides captive portal functionality

# Create script to start captive portal mode
echo "🔧 Creating captive portal startup script..."
cat > /usr/local/bin/start-Chatty Friend-captive << 'EOF'
#!/bin/bash
# Start Chatty Friend Voice Assistant in Captive Portal mode

# Stop normal dnsmasq if running
systemctl stop dnsmasq 2>/dev/null || true

# Configure iptables for captive portal
# Redirect all HTTP traffic to our captive portal
iptables -t nat -A PREROUTING -i wlan0 -p tcp --dport 80 -j DNAT --to-destination 10.42.0.1:80
iptables -t nat -A PREROUTING -i wlan0 -p tcp --dport 443 -j DNAT --to-destination 10.42.0.1:80

# Allow traffic to our services
iptables -A INPUT -i wlan0 -p tcp --dport 80 -j ACCEPT
iptables -A INPUT -i wlan0 -p udp --dport 53 -j ACCEPT
iptables -A INPUT -i wlan0 -p udp --dport 67:68 -j ACCEPT

# Start dnsmasq with captive portal config
dnsmasq -C /etc/dnsmasq-captive.conf --pid-file=/var/run/dnsmasq-captive.pid

echo "Captive portal started successfully"
EOF

chmod +x /usr/local/bin/start-Chatty Friend-captive

# Create script to stop captive portal mode
echo "🛑 Creating captive portal stop script..."
cat > /usr/local/bin/stop-Chatty Friend-captive << 'EOF'
#!/bin/bash
# Stop Chatty Friend Voice Assistant Captive Portal mode

# Note: No separate captive portal service to stop

# Stop captive dnsmasq
if [ -f "/var/run/dnsmasq-captive.pid" ]; then
    kill $(cat /var/run/dnsmasq-captive.pid) 2>/dev/null || true
    rm -f /var/run/dnsmasq-captive.pid
fi

# Remove iptables rules
iptables -t nat -D PREROUTING -i wlan0 -p tcp --dport 80 -j DNAT --to-destination 10.42.0.1:80 2>/dev/null || true
iptables -t nat -D PREROUTING -i wlan0 -p tcp --dport 443 -j DNAT --to-destination 10.42.0.1:80 2>/dev/null || true

echo "Captive portal stopped"
EOF

chmod +x /usr/local/bin/stop-Chatty Friend-captive

# Install Flask if not present
echo "🐍 Installing Python Flask..."
pip3 install flask 2>/dev/null || pip install flask

# DNS hijacking setup complete - no services to enable

echo "✅ Captive portal setup complete!"
echo ""
echo "📋 Usage:"
echo "  Start captive portal: sudo start-Chatty Friend-captive"
echo "  Stop captive portal:  sudo stop-Chatty Friend-captive"
echo ""
echo "🔧 The Chatty Friend application will now automatically use captive portal when starting hotspot mode."
echo ""
echo "⚠️  Note: Captive portal requires root privileges to bind to port 80 and modify iptables."