import tkinter as tk
class VideoCallView(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        tk.Label(self, text="Video Feed Here").pack(pady=10)
        self.video_box = tk.Label(self, width=640, height=480)
        self.video_box.pack(pady=10)

        self.mute_btn = tk.Button(self, text="Mute")
        self.mute_btn.pack(side="left", padx=5)
        self.end_call_btn = tk.Button(self, text="End Call")
        self.end_call_btn.pack(side="left", padx=5)

# +--------------------------------+
# |        Video Feed Here         |
# |    [Black box placeholder]     |
# |                                |
# | [Mute Button]        [End Call]|
# +--------------------------------+