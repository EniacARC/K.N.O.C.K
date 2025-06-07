from client.rtp_logic.rtp_manager import RTPManager
from client.sip_logic.sip_client import SIPHandler
from .mediator_connect import MediatorInterface

class Mediator(MediatorInterface):
    def __init__(self):
        self.gui = None
        self.rtp_manager: RTPManager = None
        self.sip_client: SIPHandler = None

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

    # === SIP -> RTPManager ===

    def set_remote_ip(self, ip):
        """
        Set the remote IP address for the RTP stream.
        """
        self._ensure_rtp_manager()
        self.rtp_manager.set_ip(ip)

    def set_send_audio(self, audio_port):
        """
        Set the audio port to send audio to.
        """
        self._ensure_rtp_manager()
        self.rtp_manager.set_send_audio(audio_port)

    def set_send_video(self, video_port):
        """
        Set the video port to send video to.
        """
        self._ensure_rtp_manager()
        self.rtp_manager.set_send_video(video_port)

    def set_recv_ports(self, audio=False, video=False):
        """
        Set which types of media (audio/video) the RTP manager should receive.
        """
        self._ensure_rtp_manager()
        self.rtp_manager.set_recv_ports(audio=audio, video=video)

    def get_recv_audio_port(self):
        """
        Get the audio port used to receive audio.
        """
        self._ensure_rtp_manager()
        return self.rtp_manager.get_recv_audio()

    def get_recv_video_port(self):
        """
        Get the video port used to receive video.
        """
        self._ensure_rtp_manager()
        return self.rtp_manager.get_recv_video()

    def clear_rtp_ports(self):
        """
        Clear all RTP ports and reset state.
        """
        self._ensure_rtp_manager()
        self.rtp_manager.clear_ports()

    # === SIP -> All ===

    def start_stream(self):
        """
        Start RTP communication and show the video screen.
        """
        self._ensure_rtp_manager()
        self.rtp_manager.start_rtp_comms()
        self._show_gui_screen('video')

    def stop_stream(self):
        """
        Stop RTP communication and return to the call screen.
        """
        self._ensure_rtp_manager()
        self.rtp_manager.stop()
        self._show_gui_screen('make call')

    # === SIP -> GUI ===

    def ask_for_call_answer(self, uri_call):
        """
        Notify the GUI of an incoming call and show the answer screen.
        """
        self.gui.model.call.uri = uri_call
        self._show_gui_screen('answer call')

    def response_for_login(self, success):
        """
        Send login response status to the GUI controller.
        """
        self.gui.trigger_function_mediator(
            lambda: self.gui.current_controller.sign_in_answer(success)
        )

    def response_for_signup(self, success):
        """
        Send signup response status to the GUI controller.
        """
        self.gui.trigger_function_mediator(
            lambda: self.gui.current_controller.signup_answer(success)
        )

    # === GUI -> RTPManager ===

    def get_next_audio_frame(self):
        """
        Get the next audio frame for playback or transmission.
        """
        self._ensure_rtp_manager()
        return self.rtp_manager.get_next_audio_frame()

    def get_next_video_frame(self):
        """
        Get the next video frame for playback or transmission.
        """
        self._ensure_rtp_manager()
        return self.rtp_manager.get_next_video_frame()

    # === GUI -> SIP ===

    def answer_call(self, answer):
        """
        Send a SIP response (answer) to the incoming call.
        """
        self.sip_client.answer_call(answer)

    def login(self, username, password):
        """
        Log in to the SIP service using the provided credentials.
        """
        self.sip_client.uri = username
        self.sip_client.password = password
        self.sip_client.register()

    # === GUI -> All ===

    def call(self, uri):
        """
        Initiate a SIP call to the given URI and show dialing screen.
        """
        self.sip_client.invite(uri)
        self._show_gui_screen('dialing')

    def end_call_request(self):
        """
        End the current call and send a SIP BYE request.
        """
        self.sip_client.send_bye()

    # === Helper Methods ===

    def _ensure_rtp_manager(self):
        if not self.rtp_manager:
            raise RuntimeError("RTP manager not registered")

    def _show_gui_screen(self, screen_name):
        self.gui.trigger_function_mediator(lambda: self.gui.show_screen(screen_name))

    # defin gui -> rtp_manager


    # define sip_client -> gui

    # in get answer it's two different func because it's event based
    # def answer_call(self, msg):
    #     answer = self.gui.answer_call()
    #     self.sip_client.answer_call(msg, answer)


