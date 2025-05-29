from .call_model import CallModel
from .user_model import UserModel
class Model:
    def __init__(self):
        self.user = UserModel()
        self.call = CallModel()