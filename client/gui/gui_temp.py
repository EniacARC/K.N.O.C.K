import tkinter as tk
from PIL import Image, ImageTk
import cv2
import numpy as np
import threading
import queue
import time
from client.rtp_logic.audio_capture import AudioOutput

# Queues to be filled externally
video_queue = queue.Queue()
audio_queue = queue.Queue()

class AVSyncManager:
    def __init__(self, video_queue, audio_queue, display_callback, running_flag):
        self.video_queue = video_queue
        self.audio_queue = audio_queue
        self.display_callback = display_callback
        self.running_flag = running_flag  # Shared flag object to stop

        self.video_buffer = []
        self.audio_buffer = []
        self.start_time = time.monotonic()

        self.sa = AudioOutput()

        self.thread = threading.Thread(target=self.sync_loop, daemon=True)
        self.thread.start()

    def sync_loop(self):
        while self.running_flag["running"]:
            now = time.monotonic() - self.start_time

            # Fill buffers
            while not self.video_queue.empty():
                frame, ts = self.video_queue.get()
                self.video_buffer.append((ts, frame))

            while not self.audio_queue.empty():
                chunk, ts = self.audio_queue.get()
                self.audio_buffer.append((ts, chunk))

            # Display video frames in sync
            while self.video_buffer: # and self.video_buffer[0][0] <= now
                ts, frame = self.video_buffer.pop(0)
                self.display_callback(frame)

            # Play audio chunks in sync
            while self.audio_buffer: #and self.audio_buffer[0][0] <= now
                ts, chunk = self.audio_buffer.pop(0)
                self.play_audio(chunk)

            time.sleep(0.005)

    def play_audio(self, chunk):
        try:
            self.sa.write(chunk)
        except Exception as e:
            print(f"Audio error: {e}")

class VideoCallFrame(tk.Frame):
    def __init__(self, master, video_queue, audio_queue, *args, **kwargs):
        super().__init__(master, *args, **kwargs)

        # Fixed size video label to match capture resolution
        self.video_label = tk.Label(self, width=640, height=480)
        self.video_label.pack(side="top")

        self.end_call_btn = tk.Button(self, text="End Call", command=self.end_call)
        self.end_call_btn.pack(pady=10)

        self.running_flag = {"running": True}

        # Sync manager handles timing
        self.sync_manager = AVSyncManager(
            video_queue=video_queue,
            audio_queue=audio_queue,
            display_callback=self.display_frame,
            running_flag=self.running_flag
        )

    def end_call(self):
        self.running_flag["running"] = False
        self.master.destroy()

    def display_frame(self, frame):
        # Convert frame to PIL Image and then to ImageTk.PhotoImage
        img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        # Resize image exactly to 640x480 to keep resolution consistent (optional)
        img = img.resize((640, 480), Image.Resampling.LANCZOS)
        imgtk = ImageTk.PhotoImage(image=img)

        def update():
            self.video_label.imgtk = imgtk
            self.video_label.config(image=imgtk)

        self.video_label.after(0, update)

class CallApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Video Call")
        self.geometry("700x700")
        self.call_frame = VideoCallFrame(self, video_queue, audio_queue)
        self.call_frame.pack(expand=True, fill="both")

def webcam_capture_thread(video_queue, running_flag):
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    if not cap.isOpened():
        print("Failed to open webcam")
        return

    start_time = time.monotonic()
    while running_flag["running"]:
        ret, frame = cap.read()
        if not ret:
            print("Failed to read frame")
            break
        timestamp = time.monotonic() - start_time
        video_queue.put((frame, timestamp))
        time.sleep(1 / 30)  # aim for ~30 FPS

    cap.release()

if __name__ == "__main__":
    running_flag = {"running": True}

    # Start webcam capture thread
    t = threading.Thread(target=webcam_capture_thread, args=(video_queue, running_flag), daemon=True)
    t.start()

    app = CallApp()
    app.mainloop()

    # Cleanup
    running_flag["running"] = False
    t.join()
