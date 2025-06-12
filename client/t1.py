# from rtp_logic.rtp_manager import RTPManager
#
# if __name__ == '__main__':
#     man = RTPManager()
#     man.send_audio = 123
#     man.send_ip = '127.0.0.1'
#     man.start_rtp_comms()

from client.rtp_logic.rtp_manager import RTPManager
from client.gui.app_controller import AppController
from client.gui.views.main_view import View
from client.gui.models.main import Model
from client.sip_logic.sip_client import SIPHandler
from signup_client import SignupClient
from mediator import Mediator
if __name__ == '__main__':
    rtp = RTPManager()
    sip = SIPHandler()
    v = View()
    v.root.title('t1')
    gui = AppController(Model(), v)
    signup = SignupClient()
    mediator = Mediator()
    mediator.register_gui(gui)
    mediator.register_rtp(rtp)
    mediator.register_sip(sip)
    mediator.register_signup(signup)
    try:
        mediator.start('login')
    except KeyboardInterrupt:
        print("stopping")
        gui.stop()
        rtp.stop()
        sip.disconnect()