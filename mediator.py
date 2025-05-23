from rtp_manager import RTPManager
from sip_client import SIPHandler
from mediator_connect import MediatorInterface

class Mediator(MediatorInterface):
    def __init__(self):
        self.gui = None
        self.rtp_manager: RTPManager = None
        self.sip_client: SIPHandler = None

    def register_gui(self, gui):
        self.gui = gui
        gui.set_controller(self)  # So GUI can call back to controller

    def register_sip(self, sip_client):
        self.sip_client = sip_client
        sip_client.set_controller(self)

    def register_rtp(self, rtp_manager):
        self.rtp_manager = rtp_manager
        rtp_manager.set_controller(self)

    # define sip_client -> rtp_manager interactions
    def set_remote_ip(self, ip):
        if not self.rtp_manager:
            raise RuntimeError("RTP manager not registered")
        self.rtp_manager.set_ip(ip)
    def set_send_audio(self, audio_port):
        if not self.rtp_manager:
            raise RuntimeError("RTP manager not registered")
        self.rtp_manager.set_send_audio(audio_port)
    def set_send_video(self, video_port):
        if not self.rtp_manager:
            raise RuntimeError("RTP manager not registered")
        self.rtp_manager.set_send_video(video_port)
    def set_recv_ports(self, audio=False, video=False):
        if not self.rtp_manager:
            raise RuntimeError("RTP manager not registered")
        self.rtp_manager.set_recv_ports(audio=audio, video=video)
    def get_recv_audio_port(self):
        if not self.rtp_manager:
            raise RuntimeError("RTP manager not registered")
        return self.rtp_manager.get_recv_audio()
    def get_recv_video_port(self):
        if not self.rtp_manager:
            raise RuntimeError("RTP manager not registered")
        return self.rtp_manager.get_recv_video()

    def clear_rtp_ports(self):
        if not self.rtp_manager:
            raise RuntimeError("RTP manager not registered")
        self.rtp_manager.clear_ports()

    def start_stream(self):
        print("started stream")
        # self.rtp_manager.start_rtp_comms()
    def stop_rtp_stream(self):
        self.rtp_manager.stop()

    # define gui -> rtp_manager
    def get_next_audio_frame(self):
        return self.rtp_manager.get_next_audio_frame() # this is blocking

    # define sip_client -> gui

    # in get answer it's two different func because it's event based
    # def answer_call(self, msg):
    #     answer = self.gui.answer_call()
    #     self.sip_client.answer_call(msg, answer)
