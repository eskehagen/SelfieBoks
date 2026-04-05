#!/bin/bash
# =============================================================
# Selfieboks — Installations-script til Raspberry Pi
# Køres én gang på Pi'en efter overførsel af projektfiler.
# =============================================================

set -e  # Stop ved første fejl

echo "=== Selfieboks Installer ==="

# --- System-afhængigheder (kræver sudo) ---
echo "[1/4] Installerer system-pakker..."
sudo apt-get update -y
sudo apt-get install -y \
    python3-pip \
    python3-venv \
    python3-tk \
    python3-pil \
    python3-pil.imagetk \
    libcamera-apps \
    python3-picamera2 \
    libopencv-dev \
    python3-opencv \
    libbluetooth-dev \
    bluetooth \
    bluez

# --- Opret og aktiver virtuelt miljø ---
echo "[2/4] Opretter virtuelt miljø (.venv)..."
python3 -m venv .venv --system-site-packages
# Bemærk: --system-site-packages bruges så picamera2 (system-installeret) er tilgængeligt

# --- Installer Python-pakker ---
echo "[3/4] Installerer Python-afhængigheder..."
.venv/bin/pip install --upgrade pip
# picamera2 er installeret via apt ovenfor (system-site-packages)
# Her installerer vi resten
.venv/bin/pip install \
    opencv-python \
    Pillow \
    async-tkinter-loop \
    bleak

# --- Opret autostart (valgfri) ---
echo "[4/4] Opsætter autostart via systemd..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="/etc/systemd/system/selfieboks.service"

sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Selfieboks Kiosk App
After=graphical.target bluetooth.target
Wants=bluetooth.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$SCRIPT_DIR
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/$USER/.Xauthority
ExecStart=$SCRIPT_DIR/.venv/bin/python $SCRIPT_DIR/main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable selfieboks.service

echo ""
echo "=== Installation færdig! ==="
echo ""
echo "Start appen manuelt:       .venv/bin/python main.py"
echo "Start som systemd-service: sudo systemctl start selfieboks"
echo "Se log:                    journalctl -u selfieboks -f"
echo ""
echo "Genstart Pi'en for at autostart træder i kraft."
