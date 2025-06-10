import itertools

from .base_controller import BaseController

class DialingController(BaseController):
    def __init__(self, app_controller, view, model):
        super().__init__(app_controller, view, model)
        # self.call_model = self.model.call

        self.dots_cycle = itertools.cycle([".", "..", "..."])
        self.animate_start = True
        self.animation_id = None

        self.bind()

        self.animate()

    def bind(self):
        self.view.cancel_btn.config(command=self.on_cancel)
        # self.view.after(3000, self.app.show_screen('video'))
        # self.view.after(200, lambda: self.app.show_screen('video'))

    def animate(self):
        dots = next(self.dots_cycle)
        self.view.dots_label.config(text=f"{dots}")
        if self.animate_start:
            self.animation_id = self.view.after(200, self.animate)

    def on_destroy(self):
        self.animate_start = False

        if self.animation_id:
            # cancel pending animate func cally
            self.view.after_cancel(self.animation_id)
            self.animation_id = None


    def on_cancel(self):
        # send event to app
        # self.app.show_screen("make_call")
        self.animate_start = False
        print("cancel")

