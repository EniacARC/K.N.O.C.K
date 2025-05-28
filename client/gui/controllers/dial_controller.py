import itertools

from .base_controller import BaseController

# class DialingScreen(tk.Frame):
#     def __init__(self, parent, controller):
#         super().__init__(parent)
#         self.controller = controller
#         self.label = tk.Label(self, text="DIALING", font=("Arial", 20))
#         self.label.grid(row=0, column=0, pady=60)
#
#         self.dots_label = tk.Label(self, text="", font=("Arial", 20))
#         self.dots_label.grid(row=0, column=1, pady=60)
#         self.dots_cycle = itertools.cycle([".", "..", "..."])
#
#         self.animate_start = False
#         self.animation_id = None
#         tk.Button(self, text="Go to Video Call", command=lambda: self.controller.switch_screen("VideoCall")).grid(row=1, column=0)
#
#
#     def on_show(self, **kwargs):
#         self.animate_start = True
#         self.animate()
#         # self.after(3000, lambda: self.controller.switch_screen("CallScreen"))
#
#     def animate(self):
#         dots = next(self.dots_cycle)
#         self.dots_label.config(text=f"{dots}")
#         if self.animate_start:
#             self.animation_id = self.after(200, self.animate)
#
#     def on_hide(self):
#         self.animate_start = False
#         if self.animation_id:
#             # cancel pending animate func cally
#             self.after_cancel(self.animation_id)
#             self.animation_id = None

class DialingController(BaseController):
    def __init__(self, view, app_controller):
        self.view = view # dialing view
        self.app = app_controller
        # may need to add a model to tell who are we dialing(?)
        self.bind()

        self.dots_cycle = itertools.cycle([".", "..", "..."])
        self.animate_start = False
        self.animation_id = None

    def bind(self):
        self.view.cancel_btn.config(command=self.on_cancel)

    def on_show(self):
        self.animate_start = True
        self.animate()
        # username = kwargs.get("username", "Unknown")
        # self.view.calling_label.config(text=f"(Calling {username})")
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
        # self.app.show_screen("make_call")
        print("cancel")

