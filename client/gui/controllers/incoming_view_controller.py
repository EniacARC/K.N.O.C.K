from .base_controller import BaseController

class IncomingCallController(BaseController):
    def __init__(self, app_controller, model):
        self.view = None # dialing view
        self.app = app_controller
        self.model = model # call model
        # may need to add a model to tell who are we dialing(?)

    def bind(self):
        self.view.answer_btn.config(command=self.on_answer)
        self.view.decline_btn.config(command=self.on_decline)

    def on_show(self, view):
        self.view = view
        self.bind()

        self.view.caller_label.config(text=self.model.uri) # set uri to the caller uri

    def on_answer(self):
        # self.app.switch_screen("video call")
        pass

    def on_decline(self):
        # self.app.switch_screen("call screen")
        pass