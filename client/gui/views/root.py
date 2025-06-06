from tkinter import Tk

class Root(Tk):
    def __init__(self):
        super().__init__()

        start_width = 700
        min_width = 400
        start_height = 700
        min_height = 250

        self.geometry(f"{start_width}x{start_height}")
        self.minsize(width=min_width, height=min_height)
        self.title("Voip App")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)