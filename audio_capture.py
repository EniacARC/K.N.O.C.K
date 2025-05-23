from queue import Queue
from abc import ABC, abstractmethod
import pyaudio

# Audio config
CHUNK = 1024  # Frame size in bytes
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100  # Sampling rate in Hz

class AudioIO(ABC):
    def __init__(self):
        self.audio = pyaudio.PyAudio()
        self.stream = None

    # @abstractmethod
    # def process(self, *args, **kwargs):
    #     """Process method must be implemented by subclasses"""
    #     pass

    def close(self):
        if self.stream:
            self.stream.close()
        self.audio.terminate()

class AudioInput(AudioIO):
    def __init__(self):
        super().__init__()
        self.stream = self.audio.open(format=FORMAT,
                                      channels=CHANNELS,
                                      rate=RATE,
                                      input=True,
                                      frames_per_buffer=CHUNK)
    def read(self):
        return self.stream.read(CHUNK, exception_on_overflow=False)

class AudioOutput(AudioIO):
    def __init__(self):
        super().__init__()
        self.stream = self.audio.open(format=FORMAT,
                                    channels=CHANNELS,
                                    rate=RATE,
                                    output=True,
                                    frames_per_buffer=CHUNK)
    def write(self, audio_data):
        self.stream.write(audio_data)



# class AudioHandler2:
#     def __init__(self, is_encoder=True):
#         self.audio = pyaudio.PyAudio()
#         self.is_encoder = is_encoder
#         if self.is_encoder:
#             self.stream = self.audio.open(format=FORMAT,
#                                 channels=CHANNELS,
#                                 rate=RATE,
#                                 input=True,
#                                 frames_per_buffer=CHUNK)
#         else:
#             self.stream = self.audio.open(format=FORMAT,
#                                 channels=CHANNELS,
#                                 rate=RATE,
#                                 output=True,
#                                 frames_per_buffer=CHUNK)
#         self.read_queue = Queue.queue()
#
#     def encode(self):
#         if self.is_encoder:
#             return self.stream.read(CHUNK, exception_on_overflow=False)
#         else:
#             raise RuntimeError("cannot encode in decode mode")
#
#     def decoder(self, audio_data):
#         if not self.is_encoder:
#             self.stream.write(audio_data)
#         else:
#             raise RuntimeError("cannot decode in encode mode")
#
#     def close(self):
#         self.stream.close()
#         self.audio.terminate()
#
#
# import opuslib
#
# class AudioCodec:
#     def __init__(self, sample_rate=48000, channels=1, application='audio', frame_size=960):
#         self.sample_rate = sample_rate
#         self.channels = channels
#         self.frame_size = frame_size  # Typically 20ms @ 48kHz = 960 samples
#         self.encoder = opuslib.Encoder(sample_rate, channels, application)
#         self.decoder = opuslib.Decoder(sample_rate, channels)
#
#     def encode(self, pcm_data: bytes) -> bytes:
#         # Convert PCM data to 16-bit samples (little-endian)
#         pcm_samples = opuslib.api.array.from_buffer(pcm_data, 'h')
#         return self.encoder.encode(pcm_samples, self.frame_size)
#
#     def decode(self, encoded_data: bytes) -> bytes:
#         decoded = self.decoder.decode(encoded_data, self.frame_size)
#         return decoded.tobytes()

