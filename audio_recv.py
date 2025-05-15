import pyaudio
import time
from RTP_msgs import RTPPacket, PacketType
from rtp_handler import RTPHandler

# Audio playback config
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100

def audio_receiver():
    # Setup RTP receiver
    receiver = RTPHandler(send_ip='127.0.0.1', listen_port=3233, send_port=5008, msg_type=PacketType.AUDIO)
    receiver.start(receive=True, send=False)

    # Setup PyAudio playback
    audio = pyaudio.PyAudio()
    # for i in range(audio.get_device_count()):
    #     info = audio.get_device_info_by_index(i)
    #     print(
    #         f"{i}: {info['name']} - Input Channels: {info['maxInputChannels']} | Output Channels: {info['maxOutputChannels']}")
    # return
    stream = audio.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        output=True,
                        frames_per_buffer=CHUNK)

    print("Receiving audio... Press Ctrl+C to stop.")
    try:
        while True:
            if not receiver.receive_queue.empty():

                pkt = receiver.receive_queue.get()
                audio_data = pkt.payload

                # Write to audio output stream
                stream.write(audio_data)

            else:
                continue  # Avoid busy waiting

    except KeyboardInterrupt:
        print("Audio receiver stopped.")
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()
        receiver.stop()

if __name__ == '__main__':
    audio_receiver()
