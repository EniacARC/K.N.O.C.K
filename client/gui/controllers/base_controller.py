# logic for what to do when the view is shown or destroyed
# by default does nothing but each controller may add logic if needed

class BaseController:
    def on_show(self): pass

    def on_destroy(self): pass