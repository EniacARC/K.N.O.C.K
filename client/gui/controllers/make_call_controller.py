from .base_controller import BaseController

class MakeCallController(BaseController):
    def __init__(self, view, app_controller, model):
        self.view = view  # make call view
        self.app = app_controller
        self.model = model  # call model
        # may need to add a model to tell who are we dialing(?)
        self.bind()

    def bind(self):
        self.view.call_btn.config(command=self.on_call)

    def on_call(self):
        uri = self.view.target_entry.get()
        if uri:
            pass
            # self.model.uri = uri
            # self.app.mediator.start_call(uri)
            # self.app.switch_screen("dialing")

        # else error?
        pass
