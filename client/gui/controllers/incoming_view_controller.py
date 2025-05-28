from .base_controller import BaseController
class DialingController(BaseController):
    def __init__(self, view, app_controller, model):
        self.view = view # dialing view
        self.app = app_controller
        self.model = model # user model
        # may need to add a model to tell who are we dialing(?)
        self.bind()

    def bind(self):
        self.view.answer_btn.config(command=self.on_answer)
        self.view.decline_btn.config(command=self.on_decline)

    def on_show(self):
        self.view.caller_label.config(text=self.model.uri) # set uri to the caller uri

    def on_answer(self):
        # self.app.switch_screen("video call")
        pass

    def on_decline(self):
        # self.app.switch_screen("call screen")
        pass