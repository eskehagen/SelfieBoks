#!/bin/bash
# run.sh — Start SelfieBoks
# Kør direkte: ./run.sh
# Kør i baggrunden: ./run.sh &

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${SCRIPT_DIR}/.venv/bin/activate"

if [ ! -f "${VENV}" ]; then
    echo "Fejl: venv ikke fundet. Kør install_pi.sh først."
    exit 1
fi

source "${VENV}"

# Sæt DISPLAY hvis ikke allerede sat (nødvend ved SSH-kørsel)
export DISPLAY="${DISPLAY:-:0}"

# Qt platform: brug Wayland hvis kører i Wayland-session, ellers X11 (xcb)
# Pi OS Bookworm bruger Wayland (labwc) som standard på desktop.
if [ -n "${WAYLAND_DISPLAY}" ]; then
    export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-wayland}"
else
    export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
fi

# Reducer Qt-logstøj (behold fejl og advarsler)
export QT_LOGGING_RULES="*.debug=false"

# Undgå __pycache__-skrivning (hurtigere på SD-kort)
export PYTHONDONTWRITEBYTECODE=1

cd "${SCRIPT_DIR}"
echo "Starter SelfieBoks (QT_QPA_PLATFORM=${QT_QPA_PLATFORM})..."
exec python main.py "$@"
