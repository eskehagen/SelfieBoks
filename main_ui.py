# app_gui.py

import tkinter as tk
from tkinter import font
from pathlib import Path
from PIL import Image, ImageTk


# --- Animeret Widget (Uændret, men flyttet hertil) ---
class AnimatedLabel(tk.Label):
    def __init__(self, master, path_to_frames, frame_rate=30, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.frame_rate = frame_rate
        self.frames = []
        self.current_frame_index = 0
        frame_files = sorted(Path(path_to_frames).glob("*.png"))
        if not frame_files:
            print(f"ADVARSEL: Ingen animations-frames fundet i '{path_to_frames}'")
            fallback_img = Image.new('RGBA', (400, 400), (0, 0, 0, 0))
            self.frames.append(ImageTk.PhotoImage(fallback_img))
        else:
            for frame_file in frame_files:
                img = Image.open(frame_file)
                img = img.resize((400, 400), Image.Resampling.LANCZOS)
                self.frames.append(ImageTk.PhotoImage(img))
        self.config(image=self.frames[0])
        self._animate()

    def _animate(self):
        if len(self.frames) > 1:
            self.current_frame_index = (self.current_frame_index + 1) % len(self.frames)
            self.config(image=self.frames[self.current_frame_index])
            self.after(1000 // self.frame_rate, self._animate)


# --- Hoved GUI Klasse (View) ---
class AppGui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("EpiCam Selfie Boks")
        self.geometry("1280x800")
        self.configure(bg="black")

        self.controller = None  # Controlleren bliver sat fra main.py

        # --- Opret sider (frames) ---
        self.container = tk.Frame(self, bg="black")
        self.container.pack(fill="both", expand=True)
        self.capture_page = tk.Frame(self.container, bg="black")
        self.preview_page = tk.Frame(self.container, bg="black")

        for frame in (self.capture_page, self.preview_page):
            frame.place(relwidth=1, relheight=1)

        self._setup_capture_page()
        self._setup_preview_page()

        self.show_frame(self.capture_page)

        # Sæt on_closing til at kalde controllerens metode
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def set_controller(self, controller):
        """Sætter referencen til controller-klassen."""
        self.controller = controller

    def on_closing(self):
        """Kalder controllerens on_closing metode når vinduet lukkes."""
        if self.controller:
            self.controller.on_closing()
        self.destroy()

    def show_frame(self, frame_to_show):
        frame_to_show.tkraise()

    def _setup_capture_page(self):
        self.camera_label = tk.Label(self.capture_page, bg="black")
        self.camera_label.place(relwidth=1, relheight=1)

        self.center_frame = tk.Frame(self.capture_page, bg="black", width=400, height=400)
        self.center_frame.place(relx=0.5, rely=0.5, anchor="center")
        self.center_frame.pack_propagate(False)

        BASE_DIR = Path(__file__).resolve().parent
        animation_path = BASE_DIR / "assets" / "capture_button_frames"
        self.capture_button_animation = AnimatedLabel(self.center_frame, animation_path, bg="black", borderwidth=0)
        self.capture_button_animation.pack()
        # ÆNDRET: Binder nu til controlleren
        self.capture_button_animation.bind("<Button-1>", lambda e: self.controller.start_countdown())

        self.capture_text = tk.Label(self.center_frame, text="TAG BILLEDE", fg="white", bg="#1e1e1e",
                                     font=font.Font(size=50, weight="bold"))
        self.capture_text.place(relx=0.5, rely=0.5, anchor="center")
        # ÆNDRET: Binder nu til controlleren
        self.capture_text.bind("<Button-1>", lambda e: self.controller.start_countdown())

    def _setup_preview_page(self):
        self.preview_image_label = tk.Label(self.preview_page, bg="black")
        self.preview_image_label.place(relwidth=1, relheight=1)

        btn_font = font.Font(size=20, weight="bold")
        # ÆNDRET: command kalder nu metoder på controlleren
        delete_btn = tk.Button(self.preview_page, text="SLET", command=lambda: self.controller.delete_image(),
                               font=btn_font, width=15, height=5)
        delete_btn.place(relx=0.1, rely=0.85, anchor="center")

        save_btn = tk.Button(self.preview_page, text="GEM", command=lambda: self.controller.save_image(), font=btn_font,
                             width=15, height=5)
        save_btn.place(relx=0.9, rely=0.85, anchor="center")

    # --- Metoder som controlleren kan kalde for at opdatere GUI ---
    def update_camera_feed(self, tk_img):
        """Opdaterer billedet vist i kamera-label."""
        self.camera_label.imgtk = tk_img
        self.camera_label.config(image=tk_img)

    def show_preview(self, tk_img):
        """Viser det taget billede på preview-siden."""
        self.preview_image_label.imgtk = tk_img
        self.preview_image_label.config(image=tk_img)
        self.show_frame(self.preview_page)

    def show_capture_view(self):
        """Skifter tilbage til kamera-siden og viser knappen."""
        self.center_frame.place(relx=0.5, rely=0.5, anchor="center")
        self.show_frame(self.capture_page)

    def hide_capture_button(self):
        """Skjuler knappen under nedtælling."""
        self.center_frame.place_forget()