import tkinter as tk
from .base_controller import BaseController


class ErrorController(BaseController):
    def __init__(self, app_controller):
        self.view = None  # error view
        self.app = app_controller

        self.error_msg = ""
        self.return_screen = "login"

    def bind(self):
        self.view.back_button.config(command=self.on_go_back)

    def on_show(self, view):
        self.view = view
        self.bind()

        self.view.error_label.config(text=self.error_msg)

    def on_go_back(self):
        self.app.show_screen(self.return_screen)



    def set_error(self, msg, return_to):
        self.error_msg = msg
        self.return_screen = return_to


