import tkinter as tk
class IncomingCallView(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        tk.Label(self, text="Incoming Call from").pack(pady=10)
        self.caller_label = tk.Label(self, text="")
        self.caller_label.pack()
        self.answer_btn = tk.Button(self, text="Answer")
        self.answer_btn.pack(side="left", padx=5)
        self.decline_btn = tk.Button(self, text="Decline")
        self.decline_btn.pack(side="left", padx=5)

# +--------------------------------+
# |       Incoming Call from       |
# |           [Caller Name]        |
# |                                |
# |    [Answer Button]   [Decline] |
# +--------------------------------+