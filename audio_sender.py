import pyaudio
import time
from RTP_msgs import RTPPacket, PacketType
from rtp_handler import RTPHandler

# Audio config
CHUNK = 1024  # Frame size in bytes
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100  # Sampling rate in Hz

def audio_sender():
    # Initialize RTP sender for audio
    sender = RTPHandler(send_ip='127.0.0.1', listen_port=5008, send_port=3233, msg_type=PacketType.AUDIO)
    sender.start(receive=False, send=True)

    # Start PyAudio
    audio = pyaudio.PyAudio()
    stream = audio.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK)

    print("Streaming audio... Press Ctrl+C to stop.")
    try:
        while True:
            audio_data = stream.read(CHUNK, exception_on_overflow=False)

            # Create RTP packet
            pkt = RTPPacket(
                payload_type=PacketType.AUDIO.value,
                marker=True,
            )
            pkt.payload = audio_data

            # Send RTP packet
            with sender.send_lock:
                sender.send_queue.put(pkt)

    except KeyboardInterrupt:
        print("Audio sender stopped.")
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()
        sender.stop()

if __name__ == '__main__':
    audio_sender()