#!/bin/bash

# Update /etc/fstab
chattr -i /etc/fstab 2>/dev/null
cat >> /etc/fstab << 'EOF'

tmpfs /tmp tmpfs defaults,noatime,nosuid,nodev,noexec,mode=1777,size=256M 0 0
tmpfs /var/log tmpfs defaults,noatime,nosuid,nodev,noexec,mode=0755,size=256M 0 0
tmpfs /var/tmp tmpfs defaults,noatime,nosuid,nodev,size=64M 0 0
EOF
chattr +i /etc/fstab 2>/dev/null

# Update /etc/systemd/journald.conf
chattr -i /etc/systemd/journald.conf 2>/dev/null
cat >> /etc/systemd/journald.conf << 'EOF'

Storage=volatile
RuntimeMaxUse=64M
RuntimeMaxFileSize=8M
EOF
chattr +i /etc/systemd/journald.conf 2>/dev/null