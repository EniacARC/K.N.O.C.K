import tkinter

from .base_controller import BaseController
import tkinter as tk
class LoginController(BaseController):
    def __init__(self, app_controller, view, model):
        super().__init__(app_controller, view, model)
        self.model = self.app_model.user # user model
        # may need to add a model to tell who are we dialing(?)

        self.bind()
        self.fill_info()

    def bind(self):
        self.view.login_btn.config(command=self.on_sign_in)
        self.view.goto_signup_btn.config(command=self.on_goto_signup)

    def fill_info(self):
        if self.model.username is not None:
            self.view.username_entry.insert(tk.END, self.model.username)
        if self.model.password is not None:
            self.view.password_entry.insert(tk.END, self.model.password)

    def on_goto_signup(self):
        self.app.show_screen("signup")

    def on_sign_in(self):
        username = self.view.username_entry.get()
        password = self.view.password_entry.get()

        if username and password:
            self.model.username = username
            self.model.password = password
            self.app.mediator.signin(username, password)

    def sign_in_answer(self, success, error_msg=None):
        if success:
            self.app.show_screen("make call")
        else:
            # Show error with return screen "signin"
            self.app.display_error("error login msg", "login") # sets the controller msg and return func then displays