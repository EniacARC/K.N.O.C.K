import time

import cv2
from PIL import Image, ImageTk

from client.rtp_logic.audio_capture import AudioOutput
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
            frame = self.app.mediator.get_next_audio_frame()
            if frame:
                audio_data = frame[1]

                # Write to audio output stream
                self.temp_play_audio(audio_data)
            frame = self.app.mediator.get_next_video_frame()
            if frame:
                video_data = frame[1]
                # cv2.imshow('camera', video_data)
                # if cv2.waitKey(1) & 0xFF == ord('q'):
                #     break
                self.temp_play_video(video_data)

            else:
                time.sleep(0.01)  # Avoid busy waiting

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
        # Convert frame to PIL Image and then to ImageTk.PhotoImage
        img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        # Resize image exactly to 640x480 to keep resolution consistent (optional)
        img = img.resize((640, 480), Image.Resampling.LANCZOS)
        imgtk = ImageTk.PhotoImage(image=img)

        def update():
            self.view.video_box.imgtk = imgtk
            self.view.video_box.config(image=imgtk)

        self.view.video_box.after(0, update)

    def temp_play_audio(self, frame):
        self.audio_out.write(frame)

