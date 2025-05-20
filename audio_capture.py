from queue import Queue

import pyaudio

# Audio config
CHUNK = 1024  # Frame size in bytes
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100  # Sampling rate in Hz
class AudioHandler:
    def __init__(self, is_encoder=True):
        self.audio = pyaudio.PyAudio()
        self.is_encoder = is_encoder
        if self.is_encoder:
            self.stream = self.audio.open(format=FORMAT,
                                channels=CHANNELS,
                                rate=RATE,
                                input=True,
                                frames_per_buffer=CHUNK)
        else:
            self.stream = self.audio.open(format=FORMAT,
                                channels=CHANNELS,
                                rate=RATE,
                                output=True,
                                frames_per_buffer=CHUNK)
        self.read_queue = Queue.queue()

    def encode(self):
        if self.is_encoder:
            return self.stream.read(CHUNK, exception_on_overflow=False)
        else:
            raise RuntimeError("cannot encode in decode mode")

    def decoder(self, audio_data):
        if not self.is_encoder:
            self.stream.write(audio_data)
        else:
            raise RuntimeError("cannot decode in encode mode")

    def close(self):
        self.stream.close()
        self.audio.terminate()
