import tkinter as tk
class DialingView(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        tk.Label(self, text="Dialing...").pack(pady=10)
        self.calling_label = tk.Label(self, text="(Calling [username])")
        self.calling_label.pack(pady=10)
        self.cancel_btn = tk.Button(self, text="Cancel")
        self.cancel_btn.pack()

# +--------------------------------+
# |            Dialing...(\)       |
# |                                |
# |       (Calling [username])     |
# |                                |
# |        [Cancel Button]         |
# +--------------------------------+