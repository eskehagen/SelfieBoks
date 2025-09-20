# main.py

from async_tkinter_loop import async_mainloop
from main_ui import AppGui
from main_controller import AppController

# Importer kun det nødvendige til opstart
try:
    from led_commands import start_bluetooth_manager, BLUETOOTH_ENABLED
except ImportError:
    BLUETOOTH_ENABLED = False


    def start_bluetooth_manager():
        pass

if __name__ == "__main__":
    # Start Bluetooth i baggrunden hvis aktiveret
    if BLUETOOTH_ENABLED:
        start_bluetooth_manager()

    # 1. Opret GUI (View)
    gui = AppGui()

    # 2. Opret Controller og giv den en reference til GUI
    controller = AppController(view=gui)

    # 3. Giv GUI en reference til Controlleren
    gui.set_controller(controller)

    # 4. Start kameraet via controlleren efter GUI er initialiseret
    gui.after(100, controller.start_camera)

    # Kør appen i fuldskærm for en kiosk-oplevelse
    gui.attributes('-fullscreen', True)

    # 5. Start applikationens hoved-loop
    async_mainloop(gui)