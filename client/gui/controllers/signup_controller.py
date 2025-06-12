from .base_controller import BaseController
from tkinter import messagebox


class SignupController(BaseController):
    def __init__(self, app_controller, view, model):
        super().__init__(app_controller, view, model)
        self.model = self.app_model.user # user model
        # may need to add a model to tell who are we dialing(?)
        self.bind()

    def bind(self):
        self.view.signup_btn.config(command=self.on_signup)
        self.view.login_btn.config(command=self.on_goto_sign_in)

    def on_goto_sign_in(self):
        self.app.show_screen('login')

    def on_signup(self):
        username = self.view.username_entry.get()
        password = self.view.password_entry.get()

        if username and password:
            self.model.username = username
            self.model.password = password
            self.app.controller.signup(username, password)

    def signup_answer(self, success):
        if success == '':
            messagebox.showinfo(title="signup popup", message="Signup successful!")
            self.app.show_screen("login")
        else:
            # Show error with return screen "signup"
            self.app.display_error(success, "signup") # sets the controller msg and return func then displays
