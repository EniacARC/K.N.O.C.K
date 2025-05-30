import tkinter as tk
from .base_controller import BaseController


class ErrorController(BaseController):
    def __init__(self, app_controller, view, model):
        super().__init__(app_controller, view, model)
        self.model = self.app_model.error

        self.error_msg = self.model.error_msg
        self.return_screen = self.model.return_screen

        self.bind()

        self.display_msg()

    def bind(self):
        self.view.back_button.config(command=self.on_go_back)

    def display_msg(self):
        self.view.error_label.config(text=self.error_msg)

    def on_go_back(self):
        self.app.show_screen(self.return_screen)


