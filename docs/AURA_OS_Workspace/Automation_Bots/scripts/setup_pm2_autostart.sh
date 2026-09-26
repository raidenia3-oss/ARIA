#!/bin/bash
# AURA PM2 Autostart Setup (Linux/macOS)
# Run with: sudo ./setup_pm2_autostart.sh

PM2_PATH="/usr/local/bin/pm2"

if ! command -v pm2 &> /dev/null; then
    echo "PM2 not found. Installing..."
    npm install -g pm2
fi

cd /home/user/AURA

echo "Starting AURA with PM2..."
$PM2_PATH start ecosystem.config.js --name aura-ecosystem

echo "Configuring PM2 autostart..."
$PM2_PATH save
$PM2_PATH startup systemd -u $USER --hp /home/user

echo "✅ AURA will start automatically on system reboot"
echo "Manage with: pm2 start/stop/restart/logs aura-servidor-ame"
