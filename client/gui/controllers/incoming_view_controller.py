from .base_controller import BaseController

class IncomingCallController(BaseController):
    def __init__(self, app_controller, view, model):
        super().__init__(app_controller, view, model)
        self.model = self.app_model.call # call model
        # may need to add a model to tell who are we dialing(?)
        self.bind()

        self.display_caller()

    def bind(self):
        self.view.answer_btn.config(command=self.on_answer)
        self.view.decline_btn.config(command=self.on_decline)

    def display_caller(self):
        self.view.caller_label.config(text=self.model.uri) # set uri to the caller uri

    def on_answer(self):
        # self.app.show_screen("video")
        self.app.controller.answer_call(True)

    def on_decline(self):
        self.app.controller.answer_call(False)