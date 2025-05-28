from .base_controller import BaseController

class SignupController(BaseController):
    def __init__(self, view, app_controller, model):
        self.view = view # dialing view
        self.app = app_controller
        self.model = model # user model
        # may need to add a model to tell who are we dialing(?)
        self.bind()

    def bind(self):
        self.view.signup_button.config(command=self.on_signup)

    def on_signup(self):
        username = self.view.username_entry.get()
        password = self.view.password_entry.get()

        # if username and password:
        #     self.model.username = username
        #     self.model.password = password
        #     self.app.mediator.signup(username, password)
