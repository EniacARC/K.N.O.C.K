import tkinter as tk
from tkinter import messagebox


# === Models ===

class UserModel:
    def __init__(self):
        self.username = None
        self.email = None
        self.password = None

class CameraModel:
    def __init__(self):
        self.camera_on = True

    def is_camera_on(self):
        return self.camera_on

    def set_camera_on(self, state: bool):
        self.camera_on = state

# === Mediator Stub ===

class Mediator:
    def __init__(self):
        self.gui_controller = None

    def register_gui(self, gui_controller):
        self.gui_controller = gui_controller

    def answer_call(self, answer: bool):
        print(f"Mediator: answer_call({answer})")

    def start_video_stream(self):
        print("Mediator: start_video_stream")

    def stop_video_stream(self):
        print("Mediator: stop_video_stream")

    def get_next_video_frame(self):
        return "Video Frame Data"

    def login(self, username, password):
        print(f"Mediator: login({username}, {password})")
        return username == "user" and password == "pass"

    def signup(self, username, email, password):
        print(f"Mediator: signup({username}, {email}, {password})")
        return True

    def make_call(self, target):
        print(f"Mediator: make_call({target})")

    def decline_call(self):
        print("Mediator: decline_call")


# === Views ===

class BaseView(tk.Frame):
    def __init__(self, master):
        super().__init__(master)

    def on_show(self, **kwargs):
        pass

    def on_hide(self, **kwargs):
        pass

class LoginView(BaseView):
    def __init__(self, master):
        super().__init__(master)
        tk.Label(self, text="Login").pack(pady=10)
        tk.Label(self, text="Username:").pack()
        self.username_entry = tk.Entry(self)
        self.username_entry.pack()
        tk.Label(self, text="Password:").pack()
        self.password_entry = tk.Entry(self, show="*")
        self.password_entry.pack()
        self.login_btn = tk.Button(self, text="Login")
        self.login_btn.pack(pady=5)
        self.goto_signup_btn = tk.Button(self, text="Go to Signup Screen")
        self.goto_signup_btn.pack()


class SignupView(BaseView):
    def __init__(self, master):
        super().__init__(master)
        tk.Label(self, text="Signup").pack(pady=10)
        tk.Label(self, text="Username:").pack()
        self.username_entry = tk.Entry(self)
        self.username_entry.pack()
        tk.Label(self, text="Email:").pack()
        self.email_entry = tk.Entry(self)
        self.email_entry.pack()
        tk.Label(self, text="Password:").pack()
        self.password_entry = tk.Entry(self, show="*")
        self.password_entry.pack()
        self.signup_btn = tk.Button(self, text="Signup")
        self.signup_btn.pack(pady=5)
        self.goto_login_btn = tk.Button(self, text="Go to Login Screen")
        self.goto_login_btn.pack()


class MakeCallView(BaseView):
    def __init__(self, master):
        super().__init__(master)
        tk.Label(self, text="Make a Call").pack(pady=10)
        tk.Label(self, text="Enter username or number:").pack()
        self.target_entry = tk.Entry(self)
        self.target_entry.pack()
        self.call_btn = tk.Button(self, text="Call")
        self.call_btn.pack()


class IncomingCallView(BaseView):
    def __init__(self, master):
        super().__init__(master)
        tk.Label(self, text="Incoming Call from").pack(pady=10)
        self.caller_label = tk.Label(self, text="[Caller Name]")
        self.caller_label.pack()
        self.answer_btn = tk.Button(self, text="Answer")
        self.answer_btn.pack(side="left", padx=5)
        self.decline_btn = tk.Button(self, text="Decline")
        self.decline_btn.pack(side="left", padx=5)


class DialingView(BaseView):
    def __init__(self, master):
        super().__init__(master)
        tk.Label(self, text="Dialing...").pack(pady=10)
        self.calling_label = tk.Label(self, text="(Calling [username])")
        self.calling_label.pack(pady=10)
        self.cancel_btn = tk.Button(self, text="Cancel")
        self.cancel_btn.pack()


class VideoCallView(BaseView):
    def __init__(self, master):
        super().__init__(master)
        tk.Label(self, text="Video Feed Here").pack(pady=10)
        self.video_box = tk.Label(self, bg="black", width=40, height=10, fg="white", text="Video Stream")
        self.video_box.pack(pady=10)
        self.mute_btn = tk.Button(self, text="Mute")
        self.mute_btn.pack(side="left", padx=5)
        self.end_call_btn = tk.Button(self, text="End Call")
        self.end_call_btn.pack(side="left", padx=5)

# === Controllers ===

class LoginController:
    def __init__(self, view: LoginView, app_controller):
        self.view = view
        self.app = app_controller
        self.view.login_btn.config(command=self.on_login)
        self.view.goto_signup_btn.config(command=lambda: self.app.show_screen("signup"))

    def on_login(self):
        username = self.view.username_entry.get()
        password = self.view.password_entry.get()
        success = self.app.mediator.login(username, password)
        if success:
            self.app.user_model.username = username
            messagebox.showinfo("Login", "Login successful!")
            self.app.show_screen("make_call")
        else:
            messagebox.showerror("Login", "Invalid username or password")


class SignupController:
    def __init__(self, view: SignupView, app_controller):
        self.view = view
        self.app = app_controller
        self.view.signup_btn.config(command=self.on_signup)
        self.view.goto_login_btn.config(command=lambda: self.app.show_screen("login"))

    def on_signup(self):
        username = self.view.username_entry.get()
        email = self.view.email_entry.get()
        password = self.view.password_entry.get()
        success = self.app.mediator.signup(username, email, password)
        if success:
            messagebox.showinfo("Signup", "Signup successful! Please login.")
            self.app.show_screen("login")
        else:
            messagebox.showerror("Signup", "Signup failed")


class MakeCallController:
    def __init__(self, view: MakeCallView, app_controller):
        self.view = view
        self.app = app_controller
        self.view.call_btn.config(command=self.on_call)

    def on_call(self):
        target = self.view.target_entry.get()
        if target.strip() == "":
            messagebox.showerror("Error", "Please enter a username or number")
            return
        self.app.mediator.make_call(target)
        self.app.show_screen("dialing", username=target)


class IncomingCallController:
    def __init__(self, view: IncomingCallView, app_controller):
        self.view = view
        self.app = app_controller
        self.view.answer_btn.config(command=self.on_answer)
        self.view.decline_btn.config(command=self.on_decline)

    def on_show(self, **kwargs):
        caller_name = kwargs.get("caller_name", "Unknown")
        self.view.caller_label.config(text=caller_name)

    def on_answer(self):
        self.app.mediator.answer_call(True)
        self.app.show_screen("video")

    def on_decline(self):
        self.app.mediator.answer_call(False)
        self.app.mediator.decline_call()
        self.app.show_screen("make_call")


class DialingController:
    def __init__(self, view: DialingView, app_controller):
        self.view = view
        self.app = app_controller
        self.view.cancel_btn.config(command=self.on_cancel)

    def on_show(self, **kwargs):
        username = kwargs.get("username", "Unknown")
        self.view.calling_label.config(text=f"(Calling {username})")

    def on_cancel(self):
        self.app.show_screen("make_call")


class VideoCallController:
    def __init__(self, view: VideoCallView, app_controller, camera_model):
        self.view = view
        self.app = app_controller
        self.camera_model = camera_model
        self._video_running = False
        self.view.mute_btn.config(command=self.on_mute)
        self.view.end_call_btn.config(command=self.on_end_call)

    def on_show(self, **kwargs):
        self._video_running = True
        self.view.after(0, self.update_video_frame)
        self.app.mediator.start_video_stream()

    def update_video_frame(self):
        if not self._video_running:
            return
        if self.camera_model.is_camera_on():
            frame = self.app.mediator.get_next_video_frame()
            self.view.video_box.config(text=frame)
            self.view.after(1000, self.update_video_frame)

    def on_mute(self):
        messagebox.showinfo("Mute", "Mute button pressed")

    def toggle_camera(self):
        current = self.camera_model.is_camera_on()
        self.camera_model.set_camera_on(not current)

    def on_end_call(self):
        self._video_running = False
        self.app.mediator.stop_video_stream()
        self.app.show_screen("make_call")


# === Central App Controller ===

class AppController:
    def __init__(self, root, mediator):
        self.root = root
        self.mediator = mediator
        self.mediator.register_gui(self)

        # Models
        self.user_model = UserModel()
        self.camera_model = CameraModel()

        # Views
        self.views = {
            "login": LoginView(root),
            "signup": SignupView(root),
            "make_call": MakeCallView(root),
            "incoming_call": IncomingCallView(root),
            "dialing": DialingView(root),
            "video": VideoCallView(root),
        }

        # Controllers
        self.controllers = {
            "login": LoginController(self.views["login"], self),
            "signup": SignupController(self.views["signup"], self),
            "make_call": MakeCallController(self.views["make_call"], self),
            "incoming_call": IncomingCallController(self.views["incoming_call"], self),
            "dialing": DialingController(self.views["dialing"], self),
            "video": VideoCallController(self.views["video"], self, self.camera_model),
        }

        for view in self.views.values():
            view.pack_forget()

        self.current_screen = None
        self.show_screen("login")

    def show_screen(self, screen_name, **kwargs):
        if self.current_screen:
            self.views[self.current_screen].pack_forget()

        view = self.views[screen_name]
        view.pack(fill="both", expand=True)
        self.current_screen = screen_name

        controller = self.controllers.get(screen_name)
        if controller and hasattr(controller, "on_show"):
            controller.on_show(**kwargs)


# === Run app ===

if __name__ == "__main__":
    root = tk.Tk()
    root.title("App with Separate Controllers")
    mediator = Mediator()
    app = AppController(root, mediator)
    root.mainloop()



# +------------------------------------------------------------+
# |                          Application                       |
# |                                                            |
# |  +-------------------+           +---------------------+  |
# |  |   AppController    |<--------->|     Mediator        |  |
# |  | (Central Controller)|           | (Backend Interface) |  |
# |  +---------+---------+           +----------+----------+  |
# |            |                                ^             |
# |            |                                |             |
# |            v                                |             |
# |  +--------------------+                     |             |
# |  |      Controllers    |                     |             |
# |  |  (One per View)     |---------------------+             |
# |  +--+----+----+---+---+                                   |
# |     |    |    |   |                                       |
# |     v    v    v   v                                       |
# | +--------+ +--------+ +--------+ +---------+ +---------+  |
# | |Login   | |Signup  | |MakeCall| |Incoming | | Dialing |  |
# | |Controller|Controller|Controller|Controller|Controller|  |
# | +----+---+ +----+---+ +----+---+ +----+----+ +----+----+  |
# |      |          |         |          |           |         |
# |      v          v         v          v           v         |
# | +--------+ +--------+ +--------+ +---------+ +---------+  |
# | | Login  | | Signup | | Make   | | Incoming| | Dialing |  |
# | | View   | | View   | | Call   | | Call     | | View    |  |
# | +--------+ +--------+ +--------+ +---------+ +---------+  |
# |                                                            |
# |                     +----------------+                     |
# |                     | VideoCallController |                |
# |                     +---------+--------+                  |
# |                               |                            |
# |                               v                            |
# |                      +----------------+                   |
# |                      | VideoCallView  |                   |
# |                      +----------------+                   |
# |                                                            |
# +------------------------------------------------------------+

# +------------------++------------------+
# |                  Models
# |------------------   ------------------|
# | UserModel         | | CallModel       |
# | (Stores user data)| | (stores if to display camera and video)|
# |                   | | (stores the call state)                |
# +------------------+  +------------------+



# views:
# +--------------------------------+
# |           Login                |
# |                                |
# | Username:  [______________]    |
# | Password:  [______________]    |
# |                                |
# |       [Login Button]           |
# |  [Go to Signup Screen Button]  |
# +--------------------------------+
#
#
# +--------------------------------+
# |           Signup               |
# |                                |
# | Username:  [______________]    |
# | Email:     [______________]    |
# | Password:  [______________]    |
# |                                |
# |       [Signup Button]          |
# |  [Go to Login Screen Button]   |
# +--------------------------------+
#
#
# +--------------------------------+
# |         Make a Call            |
# |                                |
# | Enter username or number:      |
# | [__________________________]   |
# |                                |
# |          [Call Button]         |
# +--------------------------------+
#
#
# +--------------------------------+
# |       Incoming Call from       |
# |           [Caller Name]        |
# |                                |
# |    [Answer Button]   [Decline] |
# +--------------------------------+
#
#
# +--------------------------------+
# |            Dialing...          |
# |                                |
# |       (Calling [username])     |
# |                                |
# |        [Cancel Button]         |
# +--------------------------------+
#
#
# +--------------------------------+
# |        Video Feed Here         |
# |    [Black box placeholder]     |
# |                                |
# | [Mute Button]        [End Call]|
# +--------------------------------+

# https://nazmul-ahsan.medium.com/how-to-organize-multi-frame-tkinter-application-with-mvc-pattern-79247efbb02b