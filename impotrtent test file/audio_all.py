# Audio config
import threading
import traceback

import cv2
import pyaudio

from client.mediator import Mediator
from client.rtp_logic.audio_capture import AudioOutput, AudioInput
from client.rtp_logic.rtp_handler import RTPHandler
from client.rtp_logic.rtp_manager import RTPManager
from client.gui.views.main_view import View
from client.gui.models.main import Model
from client.gui.app_controller import AppController
from client.mediator import Mediator


def audio_receiver():
    med = Mediator()
    manager_1 = RTPManager()
    manager_1.send_ip = '127.0.0.1'
    manager_1.recv_audio = 3344
    manager_1.recv_video = 1235
    manager_1.send_audio = 4567
    # manager_1.send_video = 7456
    # Setup RTP receiver
    # receiver = RTPHandler(send_ip='127.0.0.1', listen_port=3233)
    # manager_1.start_rtp_comms()
    med.register_rtp(manager_1)

    # Setup PyAudio playback
    # audio = pyaudio.PyAudio()
    # for i in range(audio.get_device_count()):
    #     info = audio.get_device_info_by_index(i)
    #     print(
    #         f"{i}: {info['name']} - Input Channels: {info['maxInputChannels']} | Output Channels: {info['maxOutputChannels']}")
    # return
    # stream = audio.open(format=FORMAT,
    #                     channels=CHANNELS,
    #                     rate=RATE,
    #                     output=True,
    #                     frames_per_buffer=CHUNK)
    # a_out = AudioOutput()
    con = AppController(med, Model(), View())
    med.register_gui(con)
    con.show_screen('dialing')
    manager_1.start_rtp_comms()

    print("Receiving audio... Press Ctrl+C to stop.")
    try:
        con.view.start_mainloop()
        # while True:
        #
        #     print(manager_1.recv_audio_queue)
        #     print(manager_1.recv_video_queue)
        #     if not manager_1.recv_audio_queue.empty():
        #
        #         pkt = manager_1.recv_audio_queue.get()
        #         audio_data = pkt[1]
        #
        #         # Write to audio output stream
        #         a_out.write(audio_data)
        #     if not manager_1.recv_video_queue.empty():
        #         pkt = manager_1.recv_video_queue.get()
        #         video_data = pkt[1]
        #         img_cv2 = video_data.to_ndarray(format='bgr24')
        #         cv2.imshow('camera', img_cv2)
        #         if cv2.waitKey(1) & 0xFF == ord('q'):
        #             break
        #
        #     else:
        #         continue  # Avoid busy waiting
    except Exception as er:
        print(er)
    finally:
        # audio.terminate()
        manager_1.stop()
        print("closed")

def audio_sender():
    # Initialize RTP sender for audio
    manager_1 = RTPManager()
    manager_1.send_ip = '127.0.0.1'
    manager_1.send_audio = 3344
    manager_1.send_video = 1235
    manager_1.recv_audio = 4567
    # manager_1.recv_video = 7456
    # Setup RTP receiver
    # receiver = RTPHandler(send_ip='127.0.0.1', listen_port=3233)
    manager_1.start_rtp_comms()

    print("Streaming audio... Press Ctrl+C to stop.")
    try:
        while True:

            # print(manager_1.recv_audio_queue)
            # print(manager_1.recv_video_queue)
            if not manager_1.recv_audio_queue.empty():

                pkt = manager_1.recv_audio_queue.get()
                audio_data = pkt[1]

                # Write to audio output stream
                # a_out.write(audio_data)
            if not manager_1.recv_video_queue.empty():
                pkt = manager_1.recv_video_queue.get()
                video_data = pkt[1]
                cv2.imshow('camera', video_data)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

            else:
                continue  # Avoid busy waiting
    except Exception as er:
        print("expetion")

        print(er)
        traceback.print_exc()
    finally:
        # audio.terminate()
        manager_1.stop()
        print("closed")

if __name__ == '__main__':
    threading.Thread(target=audio_sender).start()
    threading.Thread(target=audio_receiver).start()

