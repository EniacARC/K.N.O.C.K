from tkinter import messagebox

from .controllers.dial_controller import DialingController
from .controllers.login_controller import LoginController
from .controllers.signup_controller import SignupController
from .controllers.make_call_controller import MakeCallController
from .controllers.incoming_view_controller import IncomingCallController
from .controllers.call_controller import CallController
from .controllers.error_controller import ErrorController

from client.mediator_connect import ControllerAware

class AppController(ControllerAware):
    def __init__(self, model, view):
        super().__init__()
        self.model = model
        self.view = view
        self.view.root.protocol("WM_DELETE_WINDOW", self.on_closing)
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
        self.default_screen = "login"

    def show_screen(self, screen_name):
        """
        Show the screen specified by screen_name, initializing its controller.

        :param screen_name: name of the screen to switch to
        :type screen_name: str

        :returns: none
        """
        if self.current_screen != "": # if this is not the first screen
            self.current_controller.on_destroy()

        self.current_screen = screen_name
        self.view.switch(screen_name)
        view_obj = self.view.current_view

        self.current_controller = self.controllers[screen_name](self, view_obj, self.model)
        # not need for on_show. the on_show is now the constractor
    def display_error(self, msg, return_to=''):
        """
        Display an error message and navigate to the error screen.

        :param msg: the error message to display
        :type msg: str

        :param return_to: screen name to return to after error
        :type return_to: str

        :returns: none
        """

        # only controller/sip can call this event which must mean there is a current_screen. add default just in case
        self.model.error.set_error(msg, return_to)
        if return_to != '':
            self.model.error.set_error(msg, return_to)
        else:
            if self.current_screen != '':
                self.model.error.set_error(msg, self.current_screen)
            else:
                self.model.error.set_error(msg, self.default_screen)
        self.show_screen('error')

    def on_closing(self):
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            self.controller.stop()
            # self.view.root.quit()
    # mediator funcs
    def start(self, screen_name=''):
        """
        Start the application by showing the login screen and starting the GUI loop.

        :params: none
        :returns: none
        """
        if screen_name != '':
            self.show_screen(screen_name)
        else:
            self.show_screen(self.default_screen)
        self.view.start_mainloop()

    def stop(self):
        # clear references
        if self.current_screen != "": # if this is not the first screen
            self.current_controller.on_destroy()
        self.current_screen = ""
        self.view.current_view = None
        self.current_controller = None
        self.view.root.quit()

    # mediator is called from another thread. we need tp update in a thread safe way
    def trigger_function_mediator(self, func):
        """
        Switch screen from a different thread using thread-safe call.

        :param func: callback function to trigger in a thread safe way
        :type func: function

        :returns: none
        """
        self.view.root.after(0, func)

