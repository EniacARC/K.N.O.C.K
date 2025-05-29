from .base_controller import BaseController
import threading
class CallController(BaseController):
    def __init__(self, app_controller, model):
        self.view = None # dialing view
        self.app = app_controller
        self.model = model # user model
        self.running = False
        self.thread = None



    def bind(self):
        self.view.mute_btn.config(command=self.on_mute)
        self.view.end_call_btn.config(command=self.end_call)

    def on_show(self, view):
        self.view = view
        self.bind()
        self.running = True
        self.thread = threading.Thread(target=self.main_loop)
        self.thread.start()

    def data_loop(self):
        frame_color = 0
        while self.running:
            gray_value = 20 + (frame_color % 20) * 12
            color = f"#{gray_value:02x}{gray_value:02x}{gray_value:02x}"
            frame_color += 1

            self.view.after(0, lambda: self.update_window(color))

    def update_window(self, color):
        self.view.video_box.config(bg=color)

    def on_mute(self):
        pass

    def end_call(self):
        self.running = False
        self.thread.join()
        print("ended")


