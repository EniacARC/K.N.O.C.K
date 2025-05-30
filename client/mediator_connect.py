# use a mediator in the client to avoid tight coupling
from abc import ABC, abstractmethod
class MediatorInterface(ABC):
    class Mediator:
        # define sip_client -> rtp
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

        # sip -> gui
        @abstractmethod
        def ask_for_call_answer(self, uri_call): pass # trigger screen change in gui

        @abstractmethod
        def response_for_login(self, success): pass# tell gui whether login was successful

        # not necessary in my code
        # @abstractmethod
        # def notify_cancel(self): pass # notify the request has been canceled


        # sip client -> all
        @abstractmethod
        def start_stream(self): pass

        @abstractmethod
        def stop_rtp_stream(self): pass

        # define gui -> rtp_manager
        @abstractmethod
        def get_next_audio_frame(self): pass

        @abstractmethod
        def get_next_video_frame(self): pass

        # gui -> all
        @abstractmethod
        def end_call_request(self): pass # send bye request


        # gui -> sip
        @abstractmethod
        def answer_call(self, answer): pass # whether to answer incoming call

        @abstractmethod
        def login(self, username, password): pass # send register request

        @abstractmethod
        def call(self, uri): pass # send invite request

class ControllerAware:
    def __init__(self):
        self.controller = None

    def set_controller(self, controller: MediatorInterface):
        self.controller = controller