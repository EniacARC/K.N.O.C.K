class CallModel:
    def __init__(self):
        self.uri = None
        self.call_state = None # maybe add an enum (maybe remove...)
        self.camera_on = True
        self.mic_on = True