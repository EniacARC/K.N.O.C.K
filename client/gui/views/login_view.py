import tkinter as tk
class LoginView(tk.Frame):
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

# +--------------------------------+
# |           Login                |
# |                                |
# | Username:  [______________]    |
# | Password:  [______________]    |
# |                                |
# |       [Login Button]           |
# |  [Go to Signup Screen Button]  |
# +--------------------------------+