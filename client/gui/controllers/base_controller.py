# logic for what to do when the view is shown or destroyed
# by default does nothing but each controller may add logic if needed

from abc import ABC, abstractmethod
class BaseController(ABC):
    def on_destroy(self): pass

    def bind(self): pass

    def on_show(self, view): pass