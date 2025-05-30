from .base_controller import BaseController

class MakeCallController(BaseController):
    def __init__(self, app_controller, view, model):
        print("init")
        super().__init__(app_controller, view, model)
        self.model = self.app_model.call  # call model
        # may need to add a model to tell who are we dialing(?)
        self.bind()

    def bind(self):
        print("binding")
        self.view.call_btn.config(command=self.on_call)


    def on_call(self):
        uri = self.view.target_entry.get()
        if uri:
            self.model.uri = uri
            self.app.show_screen("video")

            # alert mediator to start a call
                # self.app.mediator.start_call(uri)
                # self.app.switch_screen("dialing")

        # else error?