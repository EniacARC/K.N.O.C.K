from root import Root
from login_view import LoginView
from signup_view import SignupView
from call_view import VideoCallView
from make_call_view import MakeCallView
from incoming_view import IncomingCallView
from dial_view import DialingView
class View:
    def __init__(self):
        self.root = Root()
        self.frames = {}

        self.views = {
            "login": LoginView,
            "signup": SignupView,
            "make call": MakeCallView,
            "incoming call": IncomingCallView,
            "dialing": DialingView,
            "video": VideoCallView
        }

        self.current_view = None
    def switch(self, name):
        new_frame = self.views[name](self.root)
        if self.current_view is not None:
            self.current_view.destroy() # destroy old frame to save memory
        self.current_view = new_frame
        self.current_view.grid(row=0, column=0, sticky="nsew") # cover the whole screen

    def start_mainloop(self):
        self.root.mainloop()