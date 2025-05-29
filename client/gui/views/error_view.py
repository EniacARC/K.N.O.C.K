import tkinter as tk

class ErrorView(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.error_label = tk.Label(self, text="", fg="red", font=("Arial", 14))
        self.error_label.pack(pady=10)

        self.back_button = tk.Button(self, text="Go Back")
        self.back_button.pack(pady=5)