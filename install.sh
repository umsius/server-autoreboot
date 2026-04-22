#!/bin/bash

set -e

echo "Installing Server Auto-Reboot System for 4 servers..."

if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root"
    exit 1
fi

# Create directories
mkdir -p /opt/server-autoreboot/configs

# Copy files
cp reboot_service.py server_reboot_manager.py /opt/server-autoreboot/
cp configs/*.env /opt/server-autoreboot/configs/

# Make scripts executable
chmod +x /opt/server-autoreboot/reboot_service.py
chmod +x /opt/server-autoreboot/server_reboot_manager.py

# Install Python dependencies
pip3 install python-telegram-bot python-dotenv

# Update IP addresses in configs
for i in {1..4}; do
    CURRENT_IP=$(hostname -I | awk '{print $1}')
    sed -i "s/SERVER_IP=.*/SERVER_IP=\"$CURRENT_IP\"/" /opt/server-autoreboot/configs/server${i}.env
    sed -i "s/SERVER_NAME=.*/SERVER_NAME=\"$(hostname)-Server-0${i}\"/" /opt/server-autoreboot/configs/server${i}.env
done

# Set proper permissions
chmod 600 /opt/server-autoreboot/configs/*.env
chown -R root:root /opt/server-autoreboot

# Install systemd services for each server
for i in {1..4}; do
    cp reboot_server${i}.service /etc/systemd/system/
    cp reboot_server${i}.timer /etc/systemd/system/
    
    systemctl daemon-reload
    systemctl enable reboot_server${i}.timer
    systemctl start reboot_server${i}.timer
done

echo "Installation complete!"
echo ""
echo "To check status of all timers:"
echo "systemctl list-timers | grep reboot_server"

echo ""
echo "To manually reboot a specific server:"
echo "sudo /opt/server-autoreboot/server_reboot_manager.py reboot --server 1"

echo ""
echo "To reboot all servers:"
echo "sudo /opt/server-autoreboot/server_reboot_manager.py reboot-all"

echo ""
echo "To check status:"
echo "sudo /opt/server-autoreboot/server_reboot_manager.py status"

echo ""
echo "View logs:"
echo "journalctl -u reboot_server1.service -f"