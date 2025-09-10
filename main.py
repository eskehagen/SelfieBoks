import sys
import os
import asyncio
from pathlib import Path
from datetime import datetime
import cv2
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import font
from async_tkinter_loop import async_mainloop

# --- Sti Opsætning ---
BASE_DIR = Path(__file__).resolve().parent

# --- GENBRUGT LOGIK (UÆNDRET) ---
try:
    from led_commands import send_white_led_command, send_pixel_effect_command, Effect, start_bluetooth_manager

    BLUETOOTH_ENABLED = True
except ImportError:
    print("ADVARSEL: Kunne ikke importere 'led_commands'. Bluetooth-funktioner er deaktiveret.")
    BLUETOOTH_ENABLED = False


    async def send_white_led_command(on):
        pass


    async def send_pixel_effect_command(effect):
        pass


    def start_bluetooth_manager():
        pass


    class Effect:
        OFF = 'OFF'; RAINBOW = 'RAINBOW'


class DropboxManager:
    def __init__(self, access_token=None):
        self.access_token = access_token

    def upload_file(self, file_path):
        if self.access_token is None:
            print(f"[Dropbox] SIMULERING: Ville have uploadet {file_path}, men mangler access token.")
            return True
        print(f"[Dropbox] Uploader {file_path}...")
        return True


# --- Tkinter Brugerdefineret Animeret Widget ---
class AnimatedLabel(tk.Label):
    def __init__(self, master, path_to_frames, frame_rate=30, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.frame_rate = frame_rate
        self.frames = []
        self.current_frame_index = 0

        # Indlæs alle PNG-frames fra mappen
        frame_files = sorted(Path(path_to_frames).glob("*.png"))
        if not frame_files:
            print(f"ADVARSEL: Ingen animations-frames fundet i '{path_to_frames}'")
            # Opret et tomt billede som fallback for at undgå crash
            fallback_img = Image.new('RGBA', (400, 400), (0, 0, 0, 0))
            self.frames.append(ImageTk.PhotoImage(fallback_img))
        else:
            for frame_file in frame_files:
                img = Image.open(frame_file)
                # Skaler frames til knap-størrelsen
                img = img.resize((400, 400), Image.Resampling.LANCZOS)
                self.frames.append(ImageTk.PhotoImage(img))

        self.config(image=self.frames[0])
        self._animate()

    def _animate(self):
        if len(self.frames) > 1:
            self.current_frame_index = (self.current_frame_index + 1) % len(self.frames)
            self.config(image=self.frames[self.current_frame_index])
            self.after(1000 // self.frame_rate, self._animate)


# --- Tkinter Hovedapplikation ---
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("EpiCam Selfie Boks")
        self.geometry("1280x800")
        self.configure(bg="black")

        # --- Applikations-variabler ---
        self.photos_dir = Path.home() / "Pictures" / "SelfieBoks"
        self.photos_dir.mkdir(parents=True, exist_ok=True)
        self.cap = None
        self.current_frame = None
        self.captured_image_path = None
        self.dropbox_manager = DropboxManager(access_token=None)

        # --- Opret sider (frames) ---
        self.container = tk.Frame(self, bg="black")
        self.container.pack(fill="both", expand=True)
        self.capture_page = tk.Frame(self.container, bg="black")
        self.preview_page = tk.Frame(self.container, bg="black")

        for frame in (self.capture_page, self.preview_page):
            frame.place(relwidth=1, relheight=1)

        self.setup_capture_page()
        self.setup_preview_page()

        self.show_frame(self.capture_page)

        # RETTELSE: Kald start_camera efter mainloop er startet
        self.after(100, self.start_camera)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def show_frame(self, frame_to_show):
        frame_to_show.tkraise()

    def setup_capture_page(self):
        self.camera_label = tk.Label(self.capture_page, bg="black")
        self.camera_label.place(relwidth=1, relheight=1)

        # Container til knap og tekst i midten af skærmen
        # Størrelsen (400x400) matcher knappen for at gøre placering nem
        self.center_frame = tk.Frame(self.capture_page, bg="black", width=400, height=400)
        self.center_frame.place(relx=0.5, rely=0.5, anchor="center")
        # Forhindrer containeren i at krympe
        self.center_frame.pack_propagate(False)

        # Opret og placer den animerede knap
        animation_path = BASE_DIR / "assets" / "capture_button_frames"
        self.capture_button_animation = AnimatedLabel(self.center_frame, animation_path, bg="black", borderwidth=0)
        self.capture_button_animation.pack()
        self.capture_button_animation.bind("<Button-1>", self.start_countdown)

        # Opret og placer teksten ovenpå animationen
        self.capture_text = tk.Label(self.center_frame, text="TAG BILLEDE", fg="white", bg="#1e1e1e",
                                     font=font.Font(size=50, weight="bold"))
        self.capture_text.place(relx=0.5, rely=0.5, anchor="center")
        # Gør det muligt at klikke på teksten også
        self.capture_text.bind("<Button-1>", self.start_countdown)

    def setup_preview_page(self):
        self.preview_image_label = tk.Label(self.preview_page, bg="black")
        self.preview_image_label.place(relwidth=1, relheight=1)

        btn_font = font.Font(size=20, weight="bold")
        delete_btn = tk.Button(self.preview_page, text="SLET", command=self.delete_image, font=btn_font, width=15,
                               height=5)
        delete_btn.place(relx=0.1, rely=0.85, anchor="center")

        save_btn = tk.Button(self.preview_page, text="GEM", command=self.save_image, font=btn_font, width=15, height=5)
        save_btn.place(relx=0.9, rely=0.85, anchor="center")

    def start_camera(self):
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            self.camera_label.config(text="Fejl: Kunne ikke åbne kamera.")
            return
        self.update_frame()
        print("OpenCV kamera startet.")
        if BLUETOOTH_ENABLED:
            asyncio.create_task(send_pixel_effect_command(effect=Effect.RAINBOW))

    def update_frame(self):
        if not self.cap: return
        ret, frame = self.cap.read()
        if ret:
            self.current_frame = frame.copy()
            flipped_frame = cv2.flip(frame, 1)
            rgb_image = cv2.cvtColor(flipped_frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb_image)

            w, h = self.winfo_width(), self.winfo_height()
            pil_img.thumbnail((w, h), Image.Resampling.LANCZOS)

            tk_img = ImageTk.PhotoImage(image=pil_img)
            self.camera_label.imgtk = tk_img
            self.camera_label.config(image=tk_img)
        self.after(1000 // 30, self.update_frame)

    def start_countdown(self, event=None):
        print("Starter nedtælling...")
        # Skjul knap og tekst under nedtælling
        self.center_frame.place_forget()
        if BLUETOOTH_ENABLED:
            asyncio.create_task(send_white_led_command(on=True))
            asyncio.create_task(send_pixel_effect_command(effect=Effect.OFF))
        self.after(3000, self.take_photo)

    def take_photo(self):
        print("Tager billede...")
        if self.current_frame is not None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.captured_image_path = str(self.photos_dir / f"SELFIE_{timestamp}.jpg")
            cv2.imwrite(self.captured_image_path, self.current_frame)
            print(f"Billede gemt: {self.captured_image_path}")

            pil_img = Image.open(self.captured_image_path)
            w, h = self.winfo_width(), self.winfo_height()
            pil_img.thumbnail((w, h), Image.Resampling.LANCZOS)
            tk_img = ImageTk.PhotoImage(pil_img)

            self.preview_image_label.imgtk = tk_img
            self.preview_image_label.config(image=tk_img)
            self.show_frame(self.preview_page)
        else:
            print("Fejl: Intet billede at gemme.")

    def save_image(self):
        if self.captured_image_path:
            self.dropbox_manager.upload_file(self.captured_image_path)
        self.go_back_to_camera()

    def delete_image(self):
        if self.captured_image_path and os.path.exists(self.captured_image_path):
            os.remove(self.captured_image_path)
        self.go_back_to_camera()

    def go_back_to_camera(self):
        self.captured_image_path = None
        # Vis knappen igen
        self.center_frame.place(relx=0.5, rely=0.5, anchor="center")
        self.show_frame(self.capture_page)

    def on_closing(self):
        print("App lukker...")
        if self.cap:
            self.cap.release()
        self.destroy()


if __name__ == "__main__":
    if BLUETOOTH_ENABLED:
        start_bluetooth_manager()
    app = App()
    # Kør appen i fuldskærm for en kiosk-oplevelse
    # app.attributes('-fullscreen', True)
    async_mainloop(app)


