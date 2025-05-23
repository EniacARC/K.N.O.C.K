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
            # Check if the message matches the expected format
            if not re.match(SDP.SDP_FORMAT, msg):
                print("Parse failed: Message doesn't match expected format (SDP_FORMAT).")
                return False

            lines = msg.split("\n")
            key_set = set()
            value_set = set()

            for item in lines:
                if not item.strip():
                    continue
                try:
                    key, value = item.split("=", 1)
                except ValueError:
                    print(f"Parse failed: Line missing '=' character → '{item}'")
                    return False

                key = key.lower()
                key_set.add(key)
                value_set.add(value)

            empty_values = {value for value in value_set if value.strip() == ""}
            if empty_values:
                print(f"Parse failed: Empty values found → {empty_values}")
                return False

            # Check if the required keys are present
            if not SDP.REQUIRED.issubset(key_set):
                print(f"Parse failed: Missing required keys → {SDP.REQUIRED - key_set}")
                return False

            return True

        except Exception as err:
            print(f"Parsing error (unexpected): {err}")
            return False

    @staticmethod
    def parse(msg):
        if not SDP.can_parse(msg):
            print("Parse failed: Message cannot be parsed (failed can_parse check).")
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
                try:
                    key, value = line.split("=", 1)
                except ValueError:
                    print(f"Parse failed: Line missing '=' character → '{line}'")
                    return None

                key = key.lower()
                if key == 'v':
                    version = value.strip()
                    try:
                        version = int(version)
                        if version != 0:
                            print(f"Parse failed: Unsupported version '{version}'")
                            return None
                    except ValueError:
                        print(f"Parse failed: Version is not an integer → '{version}'")
                        return None

                elif key == 'o':
                    params = value.split()
                    if len(params) < 5:
                        print(f"Parse failed: 'o=' line must have at least 5 parts → '{value}'")
                        return None
                    session_id = params[1]
                    ip_candidate = params[4]
                    if not ip:
                        ip = ip_candidate
                    elif ip != ip_candidate:
                        print(f"Parse failed: IP mismatch between lines → '{ip}' vs '{ip_candidate}'")
                        return None

                elif key == 'c':
                    params = value.split()
                    if len(params) != 3:
                        print(f"Parse failed: 'c=' line must have 3 parts → '{value}'")
                        return None
                    ip_candidate = params[2]
                    if not ip:
                        ip = ip_candidate
                    elif ip != ip_candidate:
                        print(f"Parse failed: IP mismatch between lines → '{ip}' vs '{ip_candidate}'")
                        return None

                elif key == 'm':
                    parts = value.split()
                    if len(parts) < 4:
                        print(f"Parse failed: 'm=' line must have at least 4 parts → '{value}'")
                        return None
                    media_type = parts[0]
                    try:
                        port = int(parts[1])
                    except ValueError:
                        print(f"Parse failed: Port is not an integer → '{parts[1]}'")
                        return None
                    format_ids = parts[3:]
                    fmt = ' '.join(format_ids)
                    if media_type == 'audio':
                        audio_port = port
                        audio_format = fmt
                    elif media_type == 'video':
                        video_port = port
                        video_format = fmt
                    else:
                        print(f"Parse failed: Unknown media type → '{media_type}'")
                        return None

            if version is None:
                print("Parse failed: Missing version ('v=')")
                return None
            if ip is None:
                print("Parse failed: Missing IP address")
                return None
            if session_id is None:
                print("Parse failed: Missing session ID")
                return None

            return SDP(version, ip, session_id, video_port, video_format, audio_port, audio_format)

        except Exception as err:
            print(f"Parse error (unexpected): {err}")
            return None

    def __str__(self):
        lines = [f"v={self.version}", f"o=- {self.session_id} IN IP4 {self.ip}", f"c=IN IP4 {self.ip}"]
        if self.audio_port and self.audio_format:
            lines.append(f"m=audio {self.audio_port} RTP/AVP {self.audio_format}")
        if self.video_port and self.video_format:
            lines.append(f"m=video {self.video_port} RTP/AVP {self.video_format}")
        return "\n".join(lines)

    @staticmethod
    def generate_session_id():
        return ''.join(random.choices(string.digits, k=16))