import random
import re
import string


class SDP:
    REQUIRED = {'v', 'o', 'c', 'm'}
    SDP_FORMAT = r'^[v,o,c,m].*?=.*'

    def __init__(self, version, ip, session_id, video_port=None, video_format=None, audio_port=None, audio_format=None):
        self.version = version # usually 0
        self.ip = ip
        self.video_port = video_port
        self.video_format = video_format
        self.audio_port = audio_port
        self.audio_format = audio_format
        self.session_id = session_id

    @staticmethod
    def can_parse(msg):
        try:
            if not re.match(SDP.SDP_FORMAT, msg):
                return False
            lines = msg.split("\n")
            key_set = set()
            value_set = set()
            for item in lines:
                if not item.strip():
                    continue
                key, value = item.split("=", 1)
                key = key.lower()
                key_set.add(key)
                value_set.add(value)
            empty_values = {value for value in value_set if value.strip() == ""}
            return SDP.REQUIRED.issubset(key_set) and not empty_values
        except Exception as err:
            print(f"Parsing error: {err}")
            return False

    @staticmethod
    def parse(msg):
        if not SDP.can_parse(msg):
            return None
        try:
            version = None
            ip = None
            session_id = None
            video_port = None
            video_format = None
            audio_port = None
            audio_format = None

            lines = msg.split("\n")
            for line in lines:
                if not line.strip():
                    continue
                key, value = line.split("=", 1)
                key = key.lower()
                if key == 'v':
                    version = value.strip()
                    try:
                        version = int(version)
                        if version != 0:
                            return None
                    except ValueError:
                        return None
                elif key == 'o':
                    params = value.split()
                    if len(params) != 5:
                        return None
                    session_id = params[1]
                    if not ip:
                        ip = params[4]
                    elif ip != params[4]:
                        return None
                elif key == 'c':
                    params = value.split()
                    if len(params) != 3:
                        return None
                    if not ip:
                        ip = params[2]
                    elif ip != params[2]:
                        return None
                elif key == 'm':
                    parts = value.split()
                    if len(parts) < 4:
                        return None
                    media_type = parts[0]
                    port = parts[1]
                    format_ids = parts[3:]
                    if media_type == 'audio':
                        audio_port = int(port)
                        audio_format = ' '.join(format_ids)
                    elif media_type == 'video':
                        video_port = int(port)
                        video_format = ' '.join(format_ids)

            if not all([version, ip, session_id]):
                return None

            return SDP(version, ip, session_id, video_port, video_format, audio_port, audio_format)
        except Exception as err:
            print(f"Parse error: {err}")
            return None

    def to_string(self):
        lines = [f"v={self.version}", f"o=- {self.session_id} IN IP4 {self.ip}", f"c=IN IP4 {self.ip}"]
        if self.audio_port and self.audio_format:
            lines.append(f"m=audio {self.audio_port} RTP/AVP {self.audio_format}")
        if self.video_port and self.video_format:
            lines.append(f"m=video {self.video_port} RTP/AVP {self.video_format}")
        return "\n".join(lines)

    @staticmethod
    def generate_session_id():
        ''.join(random.choices(string.digits, k=16))