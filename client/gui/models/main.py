from .call_model import CallModel
from .user_model import UserModel
from .error_model import ErrorModel
class Model:
    def __init__(self):
        self.user = UserModel()
        self.call = CallModel()
        self.error = ErrorModel()