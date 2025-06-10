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

        # Pre-computed synchronization delays (in seconds)
        self.sync_window = 0.02  # Acceptable sync window in seconds (e.g. 100ms)
        self.drift_correction_rate = 0.01  # How aggressively to correct

        # These are initial values and will adapt
        self.audio_base_delay = 0.045
        self.video_base_delay = 0.095

        self.audio_out = AudioOutput()
        self.imgtk = None

        self.bind()
        self.start_stream()

    def bind(self):
        """
        Bind GUI buttons to their corresponding event handlers.

        :params: none
        :returns: none
        """
        self.view.mute_btn.config(command=self.on_mute)
        self.view.end_call_btn.config(command=self.end_call)

    def start_stream(self):
        """
        Start the background thread for audio/video playback.

        :params: none
        :returns: none
        """
        self.running = True
        self.thread = threading.Thread(target=self.data_loop, daemon=True)
        self.thread.start()

    def data_loop(self):
        """
        Main loop to fetch and synchronize audio/video frames, then play them.

        :params: none
        :returns: none
        """
        while self.running:
            audio_frame = self.app.controller.get_next_audio_frame()
            video_frame = self.app.controller.get_next_video_frame()

            now = time.time()

            if audio_frame and video_frame:
                audio_ts, audio_data = audio_frame
                video_ts, video_data = video_frame

                # --- Calculate drift between streams ---
                drift = (video_ts + self.video_base_delay) - (audio_ts + self.audio_base_delay)

                # --- Adjust delays to reduce drift ---
                if abs(drift) > self.sync_window:
                    correction = self.drift_correction_rate * drift
                    self.audio_base_delay += correction
                    self.video_base_delay -= correction
                    print(
                        f"Adjusting delays: audio_delay={self.audio_base_delay:.3f}, video_delay={self.video_base_delay:.3f}")

                # Calculate actual playout times
                target_audio_time = audio_ts + self.audio_base_delay
                target_video_time = video_ts + self.video_base_delay
                target_time = max(target_audio_time, target_video_time)


                sleep_time = target_time - now
                if sleep_time > 0:
                    time.sleep(sleep_time)

                self.temp_play_audio(audio_data)
                self.temp_play_video(video_data)

            elif audio_frame:
                audio_ts, audio_data = audio_frame
                target_time = audio_ts + self.audio_base_delay
                sleep_time = target_time - now
                if sleep_time > 0:
                    time.sleep(sleep_time)
                self.temp_play_audio(audio_data)

            elif video_frame:
                video_ts, video_data = video_frame
                target_time = video_ts + self.video_base_delay
                sleep_time = target_time - now
                if sleep_time > 0:
                    time.sleep(sleep_time)
                self.temp_play_video(video_data)

            else:
                time.sleep(0.01)

        time.sleep(1)

        print("stopped")

    def on_mute(self):
        """
        Toggle audio mute/unmute and update button label accordingly.

        :params: none
        :returns: none
        """
        # turn
        self.is_audio = not self.is_audio

        if self.is_audio:
            self.view.mute_btn.config(text="mute")
        else:
            self.view.mute_btn.config(text="unmute")

    def end_call(self):
        """
        End the current call and return to the 'make call' screen.

        :params: none
        :returns: none
        """
        self.running = False
        # self.thread.join() # freezes main thread
        print("ended")
        self.app.controller.end_call_request()

    def temp_play_video(self, frame):
        """
        Display a video frame in the video UI component.

        :param frame: raw BGR video frame from decoder
        :type frame: numpy.ndarray

        :returns: none
        """
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
        """
        Play an audio frame using the audio output device.

        :param frame: raw audio data
        :type frame: bytes

        :returns: none
        """
        self.audio_out.write(frame)

