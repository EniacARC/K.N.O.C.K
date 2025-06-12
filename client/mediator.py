from PIL.ImageChops import screen

from client.rtp_logic.rtp_manager import RTPManager
from client.sip_logic.sip_client import SIPHandler
from mediator_connect import MediatorInterface
from signup_client import SignupClient

class Mediator(MediatorInterface):
    def __init__(self):
        self.gui = None
        self.rtp_manager = None
        self.sip_client = None
        self.signup_client = None

        self.running = False

    # === Registration Methods ===

    def register_gui(self, gui):
        """
        Register the GUI and set its controller to this mediator.
        """
        self.gui = gui
        gui.set_controller(self)

    def register_sip(self, sip_client):
        """
        Register the SIP client and set its controller to this mediator.
        """
        self.sip_client = sip_client
        sip_client.set_controller(self)

    def register_rtp(self, rtp_manager):
        """
        Register the RTP manager and set its controller to this mediator.
        """
        self.rtp_manager = rtp_manager
        rtp_manager.set_controller(self)

    def register_signup(self, signup):
        self.signup_client = signup
        signup.set_controller(self)

    def start(self, screen_name):
        if self.gui and self.sip_client and self.rtp_manager and self.signup_client:
            self.sip_client.connect()
            self.sip_client.start()
            self.running = True
            self.gui.start(screen_name)

    def stop(self):
        self.gui.stop()
        self.rtp_manager.stop()
        self.sip_client.disconnect()

    # === SIP -> RTPManager ===

    def set_remote_ip(self, ip):
        """
        Set the remote IP address for the RTP stream.
        """
        self._ensure_running()
        self.rtp_manager.set_ip(ip)

    def set_send_audio(self, audio_port):
        """
        Set the audio port to send audio to.
        """
        self._ensure_running()
        self.rtp_manager.set_send_audio(audio_port)

    def set_send_video(self, video_port):
        """
        Set the video port to send video to.
        """
        self._ensure_running()
        self.rtp_manager.set_send_video(video_port)

    def set_recv_ports(self, audio=False, video=False):
        """
        Set which types of media (audio/video) the RTP manager should receive.
        """
        self._ensure_running()
        self.rtp_manager.set_recv_ports(audio=audio, video=video)

    def get_recv_audio_port(self):
        """
        Get the audio port used to receive audio.
        """
        self._ensure_running()
        return self.rtp_manager.get_recv_audio()

    def get_recv_video_port(self):
        """
        Get the video port used to receive video.
        """
        self._ensure_running()
        return self.rtp_manager.get_recv_video()

    # def clear_rtp_ports(self):
    #     """
    #     Clear all RTP ports and reset state.
    #     """
    #     self._ensure_rtp_manager()
    #     self.rtp_manager.clear_ports()

    # === SIP -> All ===

    def start_stream(self):
        """
        Start RTP communication and show the video screen.
        """
        self._ensure_running()
        self.rtp_manager.start_rtp_comms()
        self._show_gui_screen('video')

    def stop_stream(self):
        """
        Stop RTP communication and return to the call screen.
        """
        self._ensure_running()
        self.rtp_manager.stop()
        self._show_gui_screen('make call')

    def clear(self, error_msg):
        self._ensure_running()
        self.rtp_manager.stop()

        if self.sip_client.logged_in:
            send_screen = 'make call'
        else:
            send_screen = 'login'

        if error_msg == '':
            # sip doesn't want to display anything to client
            if self.gui.current_screen != send_screen:
                self._show_gui_screen(send_screen)
        else:
            # sip wants to alernt the client of something
            self.gui.trigger_function_mediator(
                lambda: self.gui.display_error(error_msg, send_screen)
            )

    # === SIP -> GUI ===

    def ask_for_call_answer(self, uri_call):
        """
        Notify the GUI of an incoming call and show the answer screen.
        """
        self._ensure_running()
        self.gui.model.call.uri = uri_call
        self._show_gui_screen('incoming call')

    def response_for_login(self, success=''):
        """
        Send login response status to the GUI controller.
        """
        self._ensure_running()
        self.gui.trigger_function_mediator(
            lambda: self.gui.current_controller.sign_in_answer(success)
        )

    # def response_for_signup(self, success=''):
    #     """
    #     Send signup response status to the GUI controller.
    #     """
    #     self._ensure_running()
    #     self.gui.trigger_function_mediator(
    #         lambda: self.gui.current_controller.signup_answer(success)
    #     )

    def trying_to_dial(self):
        self._ensure_running()
        self._show_gui_screen('dialing')

    def display_error(self, error_msg):
        self._ensure_running()
        self.gui.trigger_function_mediator(
            lambda: self.gui.display_error(error_msg)
        )

    # === GUI -> RTPManager ===

    def get_next_audio_frame(self):
        """
        Get the next audio frame for playback or transmission.
        """
        self._ensure_running()
        return self.rtp_manager.get_next_audio_frame()

    def get_next_video_frame(self):
        """
        Get the next video frame for playback or transmission.
        """
        self._ensure_running()
        return self.rtp_manager.get_next_video_frame()

    # === GUI -> SIP ===

    def answer_call(self, answer):
        """
        Send a SIP response (answer) to the incoming call.
        """
        self._ensure_running()
        self.sip_client.answer_call(answer)

    def login(self, username, password):
        """
        Log in to the SIP service using the provided credentials.
        """
        self._ensure_running()
        self.sip_client.uri = username
        self.sip_client.password = password
        self.sip_client.register()

    def signup(self, username, password):
        self._ensure_running()
        success, return_code = self.signup_client.signup(username, password)
        if success:
            return_code = '' # this is how signup controller knows we were successful
        self.gui.trigger_function_mediator(
            lambda: self.gui.current_controller.signup_answer(return_code)
        )

    # === GUI -> All ===

    def call(self, uri):
        """
        Initiate a SIP call to the given URI and show dialing screen.
        """
        self._ensure_running()
        self.sip_client.invite(uri)
        # self._show_gui_screen('dialing')

    def end_call_request(self):
        """
        End the current call and send a SIP BYE request.
        """
        self._ensure_running()
        self.sip_client.bye()

    # === Helper Methods ===

    # def _ensure_start(self):
    #     if not self.rtp_manager:
    #         raise RuntimeError("RTP manager not registered")

    def _ensure_running(self):
        if not self.running:
            raise RuntimeError("need to start mediator with all components")
    def _show_gui_screen(self, screen_name):
        self.gui.trigger_function_mediator(lambda: self.gui.show_screen(screen_name))

    # defin gui -> rtp_manager


    # define sip_client -> gui

    # in get answer it's two different func because it's event based
    # def answer_call(self, msg):
    #     answer = self.gui.answer_call()
    #     self.sip_client.answer_call(msg, answer)


