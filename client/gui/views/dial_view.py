import tkinter as tk
class DialingView(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.dial_label = tk.Label(self, text="DIALING", font=("Arial", 20))
        self.dial_label.grid(row=0, column=0, pady=60)

        self.dots_label = tk.Label(self, text="", font=("Arial", 20))
        self.dots_label.grid(row=0, column=1, pady=60)

        self.calling_label = tk.Label(self, text="(Calling [username])")
        self.calling_label.grid(row=1, column=0)
        self.cancel_btn = tk.Button(self, text="Cancel")
        self.cancel_btn.grid(row=2, column=0)

# +--------------------------------+
# |            Dialing...(\)       |
# |                                |
# |       (Calling [username])     |
# |                                |
# |        [Cancel Button]         |
# +--------------------------------+