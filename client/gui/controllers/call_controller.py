import time

import cv2
from PIL import Image, ImageTk

from audio_capture import AudioOutput
from .base_controller import BaseController
import threading


class CallController(BaseController):
    def __init__(self, app_controller, view, model):
        super().__init__(app_controller, view, model)
        self.model = self.app_model.call

        #streaming logic
        self.running = False
        self.thread = None

        # maybe don't need model for this - (change default settings)?
        self.is_audio = self.model.mic_on
        self.is_video = self.model.camera_on

        self.audio_out = AudioOutput()
        self.imgtk = None

        self.bind()
        self.start_stream()

    def bind(self):
        self.view.mute_btn.config(command=self.on_mute)
        self.view.end_call_btn.config(command=self.end_call)

    def start_stream(self):
        self.running = True
        self.thread = threading.Thread(target=self.data_loop, daemon=True)
        self.thread.start()

    def data_loop(self):
        while self.running:
            video_frame = self.app.mediator.get_next_video_frame()
            audio_frame = self.app.mediator.get_next_audio_frame()
            if audio_frame:
                self.temp_play_audio(audio_frame[1])
            if video_frame:
                self.temp_play_video(video_frame[1])

            # time.sleep(0.05)


        print("stopped")

    def on_mute(self):
        # turn
        self.is_audio = not self.is_audio

        if self.is_audio:
            self.view.mute_btn.config(text="mute")
        else:
            self.view.mute_btn.config(text="unmute")

    def end_call(self):
        self.running = False
        # self.thread.join() # freezes main thread
        print("ended")

    def temp_play_video(self, frame):
        img_cv2 = frame.to_ndarray(format='bgr24')
        # Convert frame to PIL Image and then to ImageTk.PhotoImage
        img = Image.fromarray(cv2.cvtColor(img_cv2, cv2.COLOR_BGR2RGB))
        # Resize image exactly to 640x480 to keep resolution consistent (optional)
        img = img.resize((640, 480), Image.Resampling.LANCZOS)
        imgtk = ImageTk.PhotoImage(image=img)

        def update():
            self.view.video_box.imgtk = imgtk
            self.view.video_box.config(image=imgtk)

        self.view.video_box.after(0, update)

    def temp_play_audio(self, frame):
        self.audio_out.write(frame)

