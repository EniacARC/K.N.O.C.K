import re

PATTERN_REQUEST = r'^[A-Z]+\ssip:[^ ]+SIP/\d\.\d\r\n'
PATTERN_RESPONSE = r'^SIP\d\.\d\s\d+\s[A-Za-z]+'


# class SIPMsg    :
#
#     def __init__(self):
#         # msg = str
#         self.msg = ""
#
#         self.method = ""
#         self.uri = ""
#         self.version = -1
#
#         self.headers = {}
#         self.body = ""
#
#     def can_parse_msg(self):
#         return bool(re.match(PATTERN, self.msg))
#
#     def parse_start_line(self, start_line):
#         params = start_line.split(' ')
#         self.method = params[0]
#         self.uri = params[1]
#         self.version = float(params[2].split("SIP/", 1)[1])
#
#     def parse_headers(self, headers):
#         self.headers = {key: value for key, value in (x.split(": ") for x in self.msg.split("\n"))}
#
#     def parse_msg(self, msg):
#         if self.can_parse_msg():
#             start_line, headers, self.body = self.msg.split(r"\r\n")
#             self.parse_start_line(start_line)
#             self.parse_headers(headers)

# diff between req and res:
# start line - args

class SIPMsg:
    def __init__(self):
        self.version = "SIP/2.0"
        self.headers = {}
        self.body = ""

    def _parse_start_line(self, start_line):
        pass

    def _parse_headers(self, headers_raw):
        self.headers = {key: value for key, value in (x.split(": ") for x in headers_raw.split("\r\n"))}

    def parse_msg(self, raw_msg):
        # Split the message into lines
        lines = raw_msg.split("\r\n\r\n")
        if not lines:
            raise ValueError("Empty SIP message")
        metadata, body = lines
        metadata = metadata.split("\r\n")
        if not metadata:
            raise ValueError("Empty SIP message")

        # Parse the first line (start line)
        start_line = metadata[0]
        self._parse_start_line(start_line)
        self._parse_headers(metadata[1:])

    def build_start_line(self, start_line):
        pass

    def set_header(self, key, value):
        self.headers[key] = value

    def delete_header(self, key):
        if key in self.headers:
            del self.headers[key]

    def set_body(self, body):
        self.body = body
        self.headers['content-length'] = str(len(body))

    def build_msg(self):
        lines = []
        start_line = self.build_start_line()
        lines.append(start_line)

        for key, value in self.headers:
            lines.append(f"{key}: {value}")

        lines.append("\r\n")  # empty line sep

        msg = "\r\n".join(lines)
        if self.body:
            msg = msg + self.body
        return msg


class SIPResponse(SIPMsg):
    def __init__(self, status_code=None, version=None, msg=None):
        super().__init__()
        self.status_code = status_code
        self.version = version

        if msg:
            self.parse_msg(msg)

    def can_parse(self, msg):
        return bool(re.match(PATTERN_RESPONSE, msg))

    def _parse_start_line(self, start_line):
        if self.can_parse(start_line):
            args = start_line.split(' ', 1)
            self.version = args[0]
            self.status_code = args[1]

    def build_start_line(self, start_line):
        if not self.status_code:
            raise ValueError("error! missing status code to build response")
        return f"{self.version} {self.status_code}"


class SIPRequest(SIPMsg):
    def __init__(self, method=None, uri=None, version=None, msg=None):
        super().__init__()
        self.method = method
        self.uri = uri
        self.version = version
        if msg:
            self.parse_msg(msg)

    def can_parse_msg(self, msg):
        return bool(re.match(PATTERN_REQUEST, msg))

    def parse_start_line(self, start_line):
        if self.can_parse_msg(start_line):
            args = start_line.split(' ')
            self.method = args[0]
            self.uri = args[1]
            self.version = args[2]

    def build_start_line(self, start_line):
        if not self.method or self.uri:
            raise ValueError("error! missing params to build request")
        return f"{self.method} {self.uri} {self.version}"
