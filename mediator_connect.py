# use a mediator in the client to avoid tight coupling
from abc import ABC, abstractmethod
class MediatorInterface(ABC):
    class Mediator:
        # define sip_client -> rtp_manager interactions
        @abstractmethod
        def set_remote_ip(self, ip): pass

        @abstractmethod
        def set_send_audio(self, audio_port): pass

        @abstractmethod
        def set_send_video(self, video_port): pass

        @abstractmethod
        def set_recv_ports(self, audio=False, video=False): pass

        @abstractmethod
        def get_recv_audio_port(self): pass

        @abstractmethod
        def get_recv_video_port(self): pass

        @abstractmethod
        def clear_rtp_ports(self): pass

        @abstractmethod
        def start_stream(self): pass

        @abstractmethod
        def stop_rtp_stream(self): pass

        # define gui -> rtp_manager
        @abstractmethod
        def get_next_audio_frame(self): pass

class ControllerAware:
    def __init__(self):
        self.controller = None

    def set_controller(self, controller: MediatorInterface):
        self.controller = controller