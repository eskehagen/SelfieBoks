#!/bin/bash
# install_pi.sh — Fuld installation af SelfieBoks på Raspberry Pi 4B
# Testet på Raspberry Pi OS Bookworm (64-bit)
#
# Kør: bash install_pi.sh

set -e  # Afbryd ved fejl

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${INSTALL_DIR}/.venv"
PI_USER="${SUDO_USER:-$(whoami)}"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║      SelfieBoks — Installation       ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "Installationsmappe : ${INSTALL_DIR}"
echo "Python venv        : ${VENV_DIR}"
echo ""

# ── 1. System-pakker via apt ──────────────────────────────────────────────────
echo "[ 1/5 ] Opdaterer apt og installerer system-pakker..."
sudo apt update -qq
sudo apt install -y \
    python3-pyqt6 \
    python3-picamera2 \
    python3-numpy \
    python3-pil \
    python3-pip \
    python3-venv \
    libopenblas-dev \
    libbluetooth-dev \
    bluez

echo "[ 1/5 ] OK"

# ── 2. Bluetooth-adgang for brugeren ─────────────────────────────────────────
echo "[ 2/5 ] Giver '${PI_USER}' adgang til bluetooth-gruppen..."
sudo usermod -aG bluetooth "${PI_USER}"
echo "[ 2/5 ] OK (kræver logout/login for at træde i kraft)"

# ── 3. Python venv med system-site-packages ───────────────────────────────────
# --system-site-packages giver adgang til apt-installerede pakker:
# python3-pyqt6, python3-picamera2, python3-numpy, python3-pil m.fl.
echo "[ 3/5 ] Opretter Python venv med system-site-packages..."
if [ -d "${VENV_DIR}" ]; then
    echo "        Venv eksisterer allerede — genbrug."
else
    python3 -m venv --system-site-packages "${VENV_DIR}"
fi
echo "[ 3/5 ] OK"

# ── 4. pip-pakker ─────────────────────────────────────────────────────────────
echo "[ 4/5 ] Installerer pip-pakker fra requirements_pi.txt..."
source "${VENV_DIR}/bin/activate"
pip install --upgrade pip --quiet
pip install -r "${INSTALL_DIR}/requirements_pi.txt"
echo "[ 4/5 ] OK"

# ── 5. BLE capabilities (undgår at køre som root) ────────────────────────────
# Giver Python-binæren rettighed til at scanne BLE uden sudo.
PYTHON_BIN="$(readlink -f "${VENV_DIR}/bin/python3")"
echo "[ 5/6 ] Sætter BLE-capabilities på ${PYTHON_BIN}..."
sudo setcap 'cap_net_raw,cap_net_admin+eip' "${PYTHON_BIN}"
echo "[ 5/6 ] OK"

# ── 6. Sudoers-regel: tillad hciconfig reset uden password ───────────────────
# Bruges af bluetooth_manager.py til at rydde stale BLE-state ved opstart.
# Uden denne regel vil 'sudo hciconfig hci0 reset' kræve et password og hænge.
SUDOERS_FILE="/etc/sudoers.d/selfieboks-hci"
HCICONFIG_PATH="$(which hciconfig 2>/dev/null || echo /usr/sbin/hciconfig)"
echo "[ 6/6 ] Opretter sudoers-regel for hciconfig reset..."
echo "${PI_USER} ALL=(ALL) NOPASSWD: ${HCICONFIG_PATH} hci0 reset" | sudo tee "${SUDOERS_FILE}" > /dev/null
sudo chmod 440 "${SUDOERS_FILE}"
echo "[ 6/6 ] OK (${SUDOERS_FILE})"

# ── Gør scripts eksekverbare (nødvendigt da Windows ZIP mister +x permissions) ─
chmod +x "${INSTALL_DIR}/run.sh"
chmod +x "${INSTALL_DIR}/install_pi.sh"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║       Installation komplet!          ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "Start appen med:   ./run.sh"
echo ""
echo "Autostart (valgfri):"
echo "  sudo cp selfieboks.service /etc/systemd/system/"
echo "  sudo systemctl enable selfieboks"
echo "  sudo systemctl start selfieboks"
echo ""
echo "VIGTIGT: Log ud og ind igen for at bluetooth-gruppemedlemskab virker."
echo ""
