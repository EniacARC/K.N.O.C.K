import tkinter as tk
class SignupView(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        tk.Label(self, text="Signup").pack(pady=10)
        tk.Label(self, text="Username:").pack()
        self.username_entry = tk.Entry(self)
        self.username_entry.pack()
        tk.Label(self, text="Password:").pack()
        self.password_entry = tk.Entry(self, show="*")
        self.password_entry.pack()
        self.signup_btn = tk.Button(self, text="Signup")
        self.signup_btn.pack(pady=5)
        self.login_btn = tk.Button(self, text="Go to Login Screen")
        self.login_btn.pack()

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