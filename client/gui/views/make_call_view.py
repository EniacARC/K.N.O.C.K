import tkinter as tk
class MakeCallView(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        tk.Label(self, text="Make a Call").pack(pady=10)
        tk.Label(self, text="Enter username or number:").pack()
        self.target_entry = tk.Entry(self)
        self.target_entry.pack()
        self.call_btn = tk.Button(self, text="Call")
        self.call_btn.pack()

# +--------------------------------+
# |         Make a Call            |
# |                                |
# | Enter username or number:      |
# | [__________________________]   |
# |                                |
# |          [Call Button]         |
# +--------------------------------+