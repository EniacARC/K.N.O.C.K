# use a mediator in the client to avoid tight coupling
from abc import ABC, abstractmethod
class MediatorInterface(ABC):
    # class Mediator:
        # define sip_client -> rtp
        @abstractmethod
        def set_remote_ip(self, ip):
            """
            Set the remote IP address for RTP streaming.

            :param ip: the IP address of the remote peer
            :type ip: str
            """
            pass

        @abstractmethod
        def set_send_audio(self, audio_port):

            """
            Set the local port for sending audio RTP packets.

            :param audio_port: the port to send audio on
            :type audio_port: int
            """
            pass

        @abstractmethod
        def set_send_video(self, video_port):
            """
            Set the local port for sending video RTP packets.

            :param video_port: the port to send video on
            :type video_port: int
            """
            pass

        @abstractmethod
        def set_recv_ports(self, audio=False, video=False):
            """
            Allocate local ports for receiving audio and/or video.

            :param audio: whether to allocate audio receiving port
            :type audio: bool

            :param video: whether to allocate video receiving port
            :type video: bool
            """
            pass

        # @abstractmethod
        # def get_recv_audio_port(self):
        #
        #     pass
        #
        # @abstractmethod
        # def get_recv_video_port(self):
        #     pass

        @abstractmethod
        def clear_rtp_ports(self):
            """
            Clear or release any allocated RTP ports.

            :returns: none
            """
            pass

        # sip -> gui
        @abstractmethod
        def ask_for_call_answer(self, uri_call):
            """
            Notify GUI that an incoming call is waiting for an answer.

            :param uri_call: the URI of the caller
            :type uri_call: str
            """
            pass # trigger screen change in gui

        @abstractmethod
        def response_for_login(self, success):
            """
            Notify GUI whether login was successful.

            :param success: login result
            :type success: bool
            """
            pass# tell gui whether login was successful

        # not necessary in my code
        # @abstractmethod
        # def notify_cancel(self): pass # notify the request has been canceled


        # sip client -> all
        @abstractmethod
        def start_stream(self):
            """
            Start audio and video streaming.

            :returns: none
            """
            pass

        @abstractmethod
        def stop_rtp_stream(self):
            """
            Stop the RTP audio and video streaming.

            :returns: none
            """
            pass

        # define gui -> rtp_manager
        @abstractmethod
        def get_next_audio_frame(self):
            """
            Retrieve the next decoded audio frame from the RTP stream.

            :return: audio frame data
            :rtype: bytes
            """
            pass

        @abstractmethod
        def get_next_video_frame(self):
            """
            Retrieve the next decoded video frame from the RTP stream.

            :return: video frame data
            :rtype: numpy.ndarray
            """
            pass

        # gui -> all
        @abstractmethod
        def end_call_request(self):
            """
            End the current call and send a SIP BYE request.

            :returns: none
            """
            pass # send bye request


        # gui -> sip
        @abstractmethod
        def answer_call(self, answer):
            """
            Send an answer to an incoming call.

            :param answer: whether to accept the call
            :type answer: bool
            """
            pass # whether to answer incoming call

        @abstractmethod
        def login(self, username, password):
            """
            Attempt to log in to the SIP server with provided credentials.

            :param username: user's SIP username
            :type username: str

            :param password: user's SIP password
            :type password: str
            """
            pass # send register request

        @abstractmethod
        def call(self, uri):
            """
            Initiate a call to the given SIP URI.

            :param uri: SIP URI to call
            :type uri: str
            """
            pass # send invite request

class ControllerAware(ABC):
    def __init__(self):
        self.controller = None

    def set_controller(self, controller: MediatorInterface):
        """
        Set the controller used by this object.

        :param controller: an instance implementing MediatorInterface
        :type controller: MediatorInterface

        :returns: none
        """
        self.controller = controller