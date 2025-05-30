class ErrorModel:
    def __init__(self):
        self.error_msg = ""
        self.return_screen = "login"

    def set_error(self, msg, screen):
        self.error_msg = msg
        self.return_screen = screen
