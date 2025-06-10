import random
import socket
import multiprocessing
import time
import queue

import cv2

from client.mediator_connect import *
from .rtp_handler import RTPHandler
from .audio_capture import AudioInput
from .video_capture import VideoInput, VideoEncoder, VideoDecoder


def _send_audio_process(send_ip, send_audio, running_event):
    """
       Audio sending process function that reads audio data from input and sends RTP packets.

       :param send_ip: The IP address to send audio packets to
       :type send_ip: str
       :param send_audio: The UDP port to send audio packets to
       :type send_audio: int
       :param running_event: A multiprocessing.Event controlling the process lifetime
       :type running_event: multiprocessing.Event

       :returns: None
       """
    """Audio sending process function"""
    audio_io = AudioInput()
    sender = RTPHandler(send_ip, send_port=send_audio)
    sender.start()


    try:
        frame_count = 0
        start_time = time.time()
        frame_interval = 1.0 / 50.0

        while running_event.is_set():
            loop_start = time.time()

            audio_data = audio_io.read()
            sender.send_packet(audio_data)

            # FPS counting
            # frame_count += 1
            # elapsed = time.time() - start_time
            # if elapsed >= 1.0:
            #     print(f"AUDIO FPS: {frame_count}")
            #     frame_count = 0
            #     start_time = time.time()

            # Sleep to cap at 50 FPS
            elapsed_loop = time.time() - loop_start
            sleep_time = frame_interval - elapsed_loop
            if sleep_time > 0:
                time.sleep(sleep_time)
    finally:
        sender.stop()
        audio_io.close()


def _recv_audio_process(send_ip, recv_audio, recv_audio_queue, running_event):
    """
        Audio receiving process function that listens for incoming RTP audio packets
        and places decoded audio frames into a multiprocessing queue.

        :param send_ip: The IP address to bind for receiving audio
        :type send_ip: str
        :param recv_audio: The UDP port to listen for incoming audio packets
        :type recv_audio: int
        :param recv_audio_queue: Queue to put received audio frames (timestamp, payload)
        :type recv_audio_queue: multiprocessing.Queue
        :param running_event: A multiprocessing.Event controlling the process lifetime
        :type running_event: multiprocessing.Event

        :returns: None
        """

    receiver = RTPHandler(send_ip, listen_port=recv_audio)
    receiver.start()

    try:
        while running_event.is_set():
            try:
                frame = receiver.receive_queue.get(timeout=1)
                recv_audio_queue.put((frame.timestamp, frame.payload))
            except queue.Empty:
                continue
            except Exception:
                continue
    finally:
        receiver.stop()


def _send_video_process(send_ip, send_video, running_event):
    """
    Video sending process function that reads video frames, encodes them,
    and sends RTP packets at a capped frame rate (30 FPS).

    :param send_ip: The IP address to send video packets to
    :type send_ip: str
    :param send_video: The UDP port to send video packets to
    :type send_video: int
    :param running_event: A multiprocessing.Event controlling the process lifetime
    :type running_event: multiprocessing.Event

    :returns: None
    """
    video_io = VideoInput()
    encoder = VideoEncoder()

    # Hard coding fps for now
    frame_interval = 1.0 / 30.0  # 30 frames per second
    sender = RTPHandler(send_ip, send_port=send_video)
    sender.start()

    try:
        while running_event.is_set():
            start_time = time.time()

            video_frame = video_io.get_frame()
            encoded_frame = encoder.encode(video_frame)
            for frame in encoded_frame:
                sender.send_packet(bytes(frame))

            # SEND MAX 30 FPS
            elapsed = time.time() - start_time
            sleep_time = max(0.0, frame_interval - elapsed)
            time.sleep(sleep_time)
    except Exception as err:
        print(err)
    finally:
        sender.stop()


def _recv_video_process(send_ip, recv_video, recv_video_queue, running_event):
    """
    Video receiving process function that listens for incoming RTP video packets,
    decodes them, and places decoded frames into a multiprocessing queue.

    :param send_ip: The IP address to bind for receiving video
    :type send_ip: str
    :param recv_video: The UDP port to listen for incoming video packets
    :type recv_video: int
    :param recv_video_queue: Queue to put received video frames (timestamp, frame as ndarray)
    :type recv_video_queue: multiprocessing.Queue
    :param running_event: A multiprocessing.Event controlling the process lifetime
    :type running_event: multiprocessing.Event

    :returns: None
    """
    receiver = RTPHandler(send_ip, listen_port=recv_video)
    decoder = VideoDecoder()
    receiver.start()

    try:
        while running_event.is_set():
            try:
                encoded_data = receiver.receive_queue.get(timeout=1)
                decoded_frames = decoder.decode(encoded_data.payload)
                for frame in decoded_frames:
                    f = frame.to_ndarray(format='bgr24')
                    recv_video_queue.put((encoded_data.timestamp, f))
            except queue.Empty:
                continue
            except Exception:
                continue
    finally:
        receiver.stop()


class RTPManager(ControllerAware):
    def __init__(self):
        super().__init__()
        self.used_ports = []

        # remote ports
        self.send_ip = None
        self.send_audio = None
        self.send_video = None

        # my ports
        self.recv_audio = None
        self.recv_video = None

        self.running_event = None
        self.processes = []

        # Use multiprocessing queues for inter-process communication
        self.recv_audio_queue = multiprocessing.Queue()  # (timestamp, frame)
        self.recv_video_queue = multiprocessing.Queue()  # (timestamp, frame)

    def allocate_port(self):
        """
        Allocates a random free UDP port for use.

        :returns: A free port number
        :rtype: int
        """
        for _ in range(100):
            port = random.randint(10000, 60000)
            if port not in self.used_ports and self._is_port_free(port):
                self.used_ports.append(port)
                return port
        raise RuntimeError("Failed to allocate free port")

    def _is_port_free(self, port):
        """
        Checks if a port is free by trying to bind a UDP socket.

        :param port: The port number to check
        :type port: int

        :returns: True if the port is free, False otherwise
        :rtype: bool
        """
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            try:
                sock.bind(('0.0.0.0', port))
                return True
            except Exception:
                return False

    def set_ip(self, ip):
        """
        Sets the target IP address for sending RTP streams.

        :param ip: The destination IP address
        :type ip: str
        """
        self.send_ip = ip

    def set_send_audio(self, audio):
        """
        Sets the port used to send audio RTP packets.

        :param audio: The port number for audio sending
        :type audio: int
        """
        if self.send_ip:
            self.send_audio = audio

    def set_send_video(self, video):
        """
        Sets the port used to send video RTP packets.

        :param video: The port number for video sending
        :type video: int
        """
        if self.send_ip:
            self.send_video = video

    def set_recv_ports(self, video=False, audio=False):
        """
        Allocates ports for receiving audio and/or video.

        :param video: Whether to allocate a video port
        :type video: bool
        :param audio: Whether to allocate an audio port
        :type audio: bool
        """
        if audio:
            self.recv_audio = self.allocate_port()
            print(self.recv_audio)
        if video:
            self.recv_video = self.allocate_port()

    def get_recv_audio(self):
        """
        Gets the allocated port for receiving audio.

        :returns: The audio receiving port
        :rtype: int
        """
        return self.recv_audio

    def get_recv_video(self):
        """
        Gets the allocated port for receiving video.

        :returns: The video receiving port
        :rtype: int
        """
        return self.recv_video

    def clear_ports(self):
        """
        Resets and clears all port assignments and process references.

        :returns: None
        """
        self.used_ports = []
        self.processes = []
        self.running_event = None
        self.send_ip = None
        self.send_audio = None
        self.send_video = None
        self.recv_audio = None
        self.recv_video = None

    def start_rtp_comms(self):
        """
        Starts all configured RTP sender and receiver processes.

        :returns: None
        """
        self.running_event = multiprocessing.Event()
        self.running_event.set()

        print(str(self))

        if self.send_audio:
            print("send audio")
            p = multiprocessing.Process(
                target=_send_audio_process,
                args=(self.send_ip, self.send_audio, self.running_event)
            )
            self.processes.append(p)

        if self.recv_audio:
            p = multiprocessing.Process(
                target=_recv_audio_process,
                args=(self.send_ip, self.recv_audio, self.recv_audio_queue, self.running_event)
            )
            self.processes.append(p)

        if self.send_video:
            print("send video")
            p = multiprocessing.Process(
                target=_send_video_process,
                args=(self.send_ip, self.send_video, self.running_event)
            )
            self.processes.append(p)

        if self.recv_video:
            p = multiprocessing.Process(
                target=_recv_video_process,
                args=(self.send_ip, self.recv_video, self.recv_video_queue, self.running_event)
            )
            self.processes.append(p)

        for process in self.processes:
            process.start()

    def get_next_audio_frame(self):
        """
        Retrieves the next audio frame from the receiving queue.

        :returns: A tuple of (timestamp, audio_data) or None if queue is empty
        :rtype: tuple or None
        """
        try:
            return self.recv_audio_queue.get_nowait()  # Non-blocking
        except queue.Empty:
            return None

    def get_next_video_frame(self):
        """
        Retrieves the next video frame from the receiving queue.

        :returns: A tuple of (timestamp, video_frame) or None if queue is empty
        :rtype: tuple or None
        """
        try:
            return self.recv_video_queue.get_nowait()  # Non-blocking
        except queue.Empty:
            return None

    def stop(self):
        """
        Stops all running RTP processes and clears configuration.

        :returns: None
        """

        print("stopping rtp")
        if self.running_event:
            self.running_event.clear()

        for process in self.processes:
            process.join(timeout=5.0)  # Wait up to 5 seconds for graceful shutdown
            if process.is_alive():
                print(f"Force terminating process {process.pid}")
                process.terminate()
                process.join()

        self.clear_ports()

    def __str__(self):
        """
        Returns a human-readable string representation of RTPManager state.

        :returns: A status string
        :rtype: str
        """
        running_processes = sum(1 for p in self.processes if p.is_alive()) if self.processes else 0
        return (
            f"RTPManager Status:\n"
            f"  Running: {self.running_event.is_set() if self.running_event else False}\n"
            f"  Used Ports: {self.used_ports}\n"
            f"  Send IP: {self.send_ip}\n"
            f"  Send Audio Port: {self.send_audio}\n"
            f"  Send Video Port: {self.send_video}\n"
            f"  Receive Audio Port: {self.recv_audio}\n"
            f"  Receive Video Port: {self.recv_video}\n"
            f"  Audio Queue Size: {self.recv_audio_queue.qsize()}\n"
            f"  Video Queue Size: {self.recv_video_queue.qsize()}\n"
            f"  Processes Running: {running_processes}"
        )

    def __del__(self):
        """
        Ensures all resources are cleaned up when the object is deleted.

        :returns: None
        """
        self.stop()