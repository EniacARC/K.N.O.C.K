from .controllers.dial_controller import DialingController
from .controllers.login_controller import LoginController
from .controllers.signup_controller import SignupController
from .controllers.make_call_controller import MakeCallController
from .controllers.incoming_view_controller import IncomingCallController
from .controllers.call_controller import CallController
from .controllers.error_controller import ErrorController

from client.mediator_connect import ControllerAware

class AppController(ControllerAware):
    def __init__(self, mediator, model, view):
        super().__init__()
        self.mediator = mediator
        self.model = model
        self.view = view
        # Controllers
        self.controllers = {
            "login": LoginController,
            "signup": SignupController,
            "make call": MakeCallController,
            "incoming call": IncomingCallController,
            "dialing": DialingController,
            "video": CallController,
            "error": ErrorController
        }

        self.current_controller = None
        self.current_screen = ""

    def show_screen(self, screen_name):
        if self.current_screen != "": # if this is not the first screen
            self.current_controller.on_destroy()

        self.current_screen = screen_name
        self.view.switch(screen_name)
        view_obj = self.view.current_view

        self.current_controller = self.controllers[screen_name](self, view_obj, self.model)
        # not need for on_show. the on_show is now the constractor
    def display_error(self, msg, return_to):
        self.model.error.set_error(msg, return_to)
        self.show_screen('error')

    # mediator funcs
    def start(self):
        self.show_screen("login")
        self.view.start_mainloop()

    # mediator is called from another thread. we need tp update in a thread safe way
    def switch_screen_mediator(self, screen_name):
        self.view.root.after(0, lambda: self.show_screen(screen_name))

