from views.main_view import View
from .controllers.dial_controller import DialingController
from .controllers.login_controller import LoginController
from .controllers.signup_controller import SignupController
from .controllers.make_call_controller import MakeCallController
from .controllers.incoming_view_controller import IncomingCallController
from .controllers.call_controller import VideoCallController
from .controllers.error_controller import ErrorController

class AppController:
    def __init__(self, mediator, model, view):
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
            "video": VideoCallController,
            "error": ErrorController
        }

        self.current_controller = None

        self.show_screen("login")
        self.current_screen = ""
    def show_screen(self, screen_name):
        if self.current_screen != "": # if this is not the first screen
            self.current_controller.on_destroy()

        self.current_screen = screen_name
        self.view.switch(screen_name)
        view_obj = self.view.current_view

        self.current_controller = self.controllers[screen_name](self, view_obj, self.model)
        # not need for on_show. the on_show is now the constractor


        # if self.current_screen:
        #     self.current_controller.on_destroy()
        # self.current_screen = screen_name
        # try:
        #     self.view.switch(screen_name)
        #     self.controllers[screen_name].on_show(current_view_object)
        # except Exception as err:
        #     print(f"could not switch to screen '{screen_name}' - {err}")
        #     self.current_screen = None

    def display_error(self, msg, return_to):
        self.controllers['error'].set_error(msg, return_to)
        self.show_screen('error')