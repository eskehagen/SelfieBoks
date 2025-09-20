# app_controller.py

import os
import asyncio
from pathlib import Path
from datetime import datetime
import cv2
from PIL import Image, ImageTk, ImageOps

from dropbox_manager import DropboxManager

# Importer Bluetooth-logik (uændret)
try:
    from led_commands import send_white_led_command, send_pixel_effect_command, Effect, BLUETOOTH_ENABLED
except ImportError:
    # Fallback-definitioner hvis Bluetooth ikke er tilgængeligt
    BLUETOOTH_ENABLED = False


    async def send_white_led_command(on):
        pass


    async def send_pixel_effect_command(effect):
        pass


    class Effect:
        OFF = 'OFF'; RAINBOW = 'RAINBOW'


class AppController:
    def __init__(self, view):
        self.view = view  # Reference til GUI-klassen

        # --- Applikations-variabler (flyttet fra App-klassen) ---
        self.photos_dir = Path.home() / "Pictures" / "SelfieBoks"
        self.photos_dir.mkdir(parents=True, exist_ok=True)
        self.cap = None
        self.current_frame = None
        self.captured_image_path = None
        self.dropbox_manager = DropboxManager(access_token=None)

    def start_camera(self):
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            print("Fejl: Kunne ikke åbne kamera.")
            # Ideelt set, vis en fejl i GUI'en her
            return

        print("OpenCV kamera startet.")
        if BLUETOOTH_ENABLED:
            asyncio.create_task(send_pixel_effect_command(effect=Effect.RAINBOW))

        self.update_frame()  # Start kamera-loopet

    def update_frame(self):
        if not self.cap: return
        ret, frame = self.cap.read()
        if ret:
            self.current_frame = frame.copy()
            # ... (flip og convert til RGB er uændret)
            flipped_frame = cv2.flip(frame, 1)
            rgb_image = cv2.cvtColor(flipped_frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb_image)

            # --- ÆNDRING HER ---
            # Få den faktiske skærmstørrelse fra GUI-vinduet
            screen_w, screen_h = self.view.winfo_width(), self.view.winfo_height()

            # Brug ImageOps.fit til at skalere og beskære billedet til skærmstørrelsen
            # Dette fjerner sorte kanter ved at zoome en smule ind og croppe.
            # centering=(0.5, 0.5) sikrer, at den cropper ligeligt fra alle sider.
            pil_img = ImageOps.fit(pil_img, (screen_w, screen_h), Image.Resampling.LANCZOS, centering=(0.5, 0.5))
            # Den gamle linje: pil_img.thumbnail((screen_w, screen_h), Image.Resampling.LANCZOS)

            tk_img = ImageTk.PhotoImage(image=pil_img)

            self.view.update_camera_feed(tk_img)

        self.view.after(1000 // 30, self.update_frame)

    def start_countdown(self):
        print("Starter nedtælling...")
        self.view.hide_capture_button()  # Bed GUI om at skjule knappen

        if BLUETOOTH_ENABLED:
            asyncio.create_task(send_white_led_command(on=True))
            asyncio.create_task(send_pixel_effect_command(effect=Effect.OFF))

        self.view.after(3000, self.take_photo)

    def take_photo(self):
        print("Tager billede...")
        if self.current_frame is not None:
            # ... (logik for at gemme fil er uændret)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.captured_image_path = str(self.photos_dir / f"SELFIE_{timestamp}.jpg")
            cv2.imwrite(self.captured_image_path, self.current_frame)
            print(f"Billede gemt: {self.captured_image_path}")

            pil_img = Image.open(self.captured_image_path)

            # --- ÆNDRING HER (samme som før) ---
            screen_w, screen_h = self.view.winfo_width(), self.view.winfo_height()
            pil_img = ImageOps.fit(pil_img, (screen_w, screen_h), Image.Resampling.LANCZOS, centering=(0.5, 0.5))
            # Den gamle linje: pil_img.thumbnail((screen_w, screen_h), Image.Resampling.LANCZOS)

            tk_img = ImageTk.PhotoImage(pil_img)

            self.view.show_preview(tk_img)
        else:
            print("Fejl: Intet billede at gemme.")
            self.go_back_to_camera()

    def save_image(self):
        if self.captured_image_path:
            print(f"Gemmer og uploader: {self.captured_image_path}")
            self.dropbox_manager.upload_file(self.captured_image_path)
        self.go_back_to_camera()

    def delete_image(self):
        if self.captured_image_path and os.path.exists(self.captured_image_path):
            print(f"Sletter: {self.captured_image_path}")
            os.remove(self.captured_image_path)
        self.go_back_to_camera()

    def go_back_to_camera(self):
        self.captured_image_path = None
        self.view.show_capture_view()  # Bed GUI om at gå tilbage til kamera-siden
        if BLUETOOTH_ENABLED:
            asyncio.create_task(send_pixel_effect_command(effect=Effect.RAINBOW))
            asyncio.create_task(send_white_led_command(on=False))

    def on_closing(self):
        print("App lukker... frigiver kamera.")
        if self.cap:
            self.cap.release()