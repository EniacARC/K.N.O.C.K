# logic for what to do when the view is shown or destroyed
# by default does nothing but each controller may add logic if needed

from abc import ABC, abstractmethod
class BaseController(ABC):
    def __init__(self, app_controller, view, model):
        self.view = view
        self.app = app_controller
        self.app_model = model

    def bind(self): pass

    def on_destroy(self): pass