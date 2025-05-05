import copy
import random
import re
import string
from enum import Enum
from abc import ABC, abstractmethod


class SIPMessageType(Enum):
    REQUEST = 1
    RESPONSE = 2


class SIPMethod(Enum):
    REGISTER = "REGISTER"
    INVITE = "INVITE"
    ACK = "ACK"
    BYE = "BYE"
    OPTIONS = "OPTIONS"


class SIPCallState(Enum):
    WAITING_AUTH = "WAITING AUTH"

    TRYING = "TRYING"
    RINGING = "RINGING"
    WAITING_ACK = "WAITING ACK"
    IN_CALL = "IN CALL"

    INIT_CANCEL = "INIT CANCEL"
    TRYING_CANCEL = "TRYING CANCEL"


class SIPCallType(Enum):
    REGISTER = 'REGISTER'
    INVITE = 'INVITE'


class SIPStatusCode(Enum):
    # 1xx - Informational
    TRYING = (100, "Trying")
    RINGING = (180, "Ringing")
    CALL_FORWARDED = (181, "Call is Being Forwarded")
    QUEUED = (182, "Queued")
    SESSION_PROGRESS = (183, "Session Progress")

    # 2xx - Success
    OK = (200, "OK")
    ACCEPTED = (202, "Accepted")

    # 3xx - Redirection
    MULTIPLE_CHOICES = (300, "Multiple Choices")
    MOVED_PERMANENTLY = (301, "Moved Permanently")
    MOVED_TEMPORARILY = (302, "Moved Temporarily")
    USE_PROXY = (305, "Use Proxy")
    ALTERNATIVE_SERVICE = (380, "Alternative Service")

    # 4xx - Client Error
    BAD_REQUEST = (400, "Bad Request")
    UNAUTHORIZED = (401, "Unauthorized")
    PAYMENT_REQUIRED = (402, "Payment Required")
    FORBIDDEN = (403, "Forbidden")
    NOT_FOUND = (404, "Not Found")
    METHOD_NOT_ALLOWED = (405, "Method Not Allowed")
    NOT_ACCEPTABLE = (406, "Not Acceptable")
    PROXY_AUTHENTICATION_REQUIRED = (407, "Proxy Authentication Required")
    REQUEST_TIMEOUT = (408, "Request Timeout")
    REQUEST_TERMINATED = (487, "Request Terminated")

    # 5xx - Server Error
    SERVER_INTERNAL_ERROR = (500, "Server Internal Error")
    NOT_IMPLEMENTED = (501, "Not Implemented")
    BAD_GATEWAY = (502, "Bad Gateway")
    SERVICE_UNAVAILABLE = (503, "Service Unavailable")
    SERVER_TIMEOUT = (504, "Server Time-out")
    VERSION_NOT_SUPPORTED = (505, "Version Not Supported")

    # 6xx - Global Failure
    BUSY_EVERYWHERE = (600, "Busy Everywhere")
    DECLINE = (603, "Decline")
    DOES_NOT_EXIST_ANYWHERE = (604, "Does Not Exist Anywhere")
    NOT_ACCEPTABLE_ANYWHERE = (606, "Not Acceptable")


SIP_MSG_PATTERN = r"^.*?\r\n([^:]+:[^\r\n]*\r\n)+\r\n"
REQUEST_START_LINE_PATTERN = r'^[A-Z]+\ssip:.+\sSIP/\d\.\d'
RESPONSE_START_LINE_PATTERN = r'^SIP/\d\.\d\s\d+\s[A-Za-z\s]+'
REQUIRED_HEADERS = {'to', 'from', 'call-id', 'cseq', 'content-length'}


# required headers for sip in my use case: To, From, call-id, cseq, content-length
# To - where to send
# from - sent from where
# call-id - identifies 1 dialog (1 logical call/string of actions)
# cseq - identifies each msg, incremints by uac only
# content-length - length of body

def generate_random_call_id():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))


class SIPMsg(ABC):
    def __init__(self):
        self.version = None
        self.headers = {}  # {'to': '', 'from': '', 'call-id': '', 'cseq': (0, ''), 'content-length': 0}
        self.body = None

    @abstractmethod
    def _can_parse_start_line(self, start_line):
        pass

    @abstractmethod
    def _parse_start_line(self, start_line):
        pass

    @abstractmethod
    def _build_start_line(self):
        pass

    @abstractmethod
    def can_build(self):
        pass

    @staticmethod
    def is_request(msg):
        return not bool(re.match(r"^SIP", msg))

    def can_parse(self, msg):
        try:
            """checks validity not logic (if headers match what they need"""
            if re.match(SIP_MSG_PATTERN, msg):
                headers_part, body_part = msg.split("\r\n\r\n", 1)
                lines = headers_part.split("\r\n")
                if self._can_parse_start_line(lines[0]):
                    key_set = set()
                    value_set = set()
                    for item in lines[1:]:
                        key, value = item.split(": ", 1)  # Split on the first occurrence of ": "
                        key = key.lower()
                        key_set.add(key)  # Add the key to the key set
                        value_set.add(value)  # Add the value to the value set
                    # key_list = set(item.split(": ") for item in lines[1:])
                    empty_values = {value for value in value_set if value.strip() == ""}
                    # REQUIRED_HEADERS.issubset(key_set) and not
                    if not empty_values:
                        return True

        except Exception as err:
            print(f"something went wrong: {err}")
        return False

    def _strip_essential_headers(self):
        # transform <sip:uri> to uri
        if 'to' in self.headers:
            self.headers['to'] = self.headers['to'][1:-1].removeprefix("sip:")
        if 'from' in self.headers:
            self.headers['from'] = self.headers['from'][1:-1].removeprefix("sip:")

        # transform "num METHOD" to (int(num), METHOD)
        if 'cseq' in self.headers:
            self.headers['cseq'] = self.headers['cseq'].split()
            self.headers['cseq'][0] = int(self.headers['cseq'][0])
            self.headers['cseq'][1] = self.headers['cseq'][1].upper()

        if 'content-length' in self.headers:
            self.headers['content-length'] = int(self.headers['content-length'])

    def _build_headers(self):
        headers_copy = copy.deepcopy(self.headers)

        try:
            # transform uri to <sip:uri>
            if 'to' in headers_copy:
                headers_copy['to'] = "<sip:" + headers_copy['to'] + ">"
            if 'from' in headers_copy:
                headers_copy['from'] = "<sip:" + headers_copy['from'] + ">"

            # transform (int(num), METHOD) to "num METHOD"
            if 'cseq' in headers_copy:
                headers_copy['cseq'][0] = str(headers_copy['cseq'][0])
                headers_copy['cseq'] = " ".join(headers_copy['cseq'])

            if 'content-length' in headers_copy:
                headers_copy['content-length'] = int(headers_copy['content-length'])

            return headers_copy
        except ValueError as err:
            print(err)
            return False

    def parse(self, msg):
        if self.can_parse(msg):
            headers_part, self.body = msg.split("\r\n\r\n", 1)
            lines = headers_part.split("\r\n")
            self._parse_start_line(lines[0])
            self.headers = dict(item.lower().split(": ") for item in lines[1:])
            self._strip_essential_headers()
            return True
        else:
            return False

    def __str__(self):
        if not self.can_build():
            print("cannot build")
            return ""
        msg = self._build_start_line()
        transformed_headers = self._build_headers()
        if transformed_headers:
            for key, value in transformed_headers.items():
                msg += f"{key}: {value}\r\n"
            msg += "\r\n"
            if self.body:
                msg += self.body
            return msg

    # manage headers/body
    def set_header(self, key, value):
        if key and value:
            self.headers[key] = value

    def delete_header(self, key):
        if key in self.headers:
            del self.headers[key]

    def get_header(self, key):
        if key in self.headers:
            return self.headers[key]
        return None

    def set_body(self, body):
        self.body = body
        self.headers['content-length'] = len(body)


class SIPRequest(SIPMsg):
    def __init__(self):
        super().__init__()
        self.method = None
        self.uri = None

    def _can_parse_start_line(self, start_line):
        return bool(re.match(REQUEST_START_LINE_PATTERN, start_line))

    def _parse_start_line(self, start_line):
        self.method, self.uri, self.version = start_line.split()
        self.uri = self.uri.removeprefix("sip:")

    def _build_start_line(self):
        if self.method and self.uri and self.version:
            return f"{self.method} sip:{self.uri} {self.version}\r\n"
        return ""

    def can_build(self):
        if not self.method or not self.version or not self.uri:
            return False
        # if not set(self.headers.keys()).issubset(REQUIRED_HEADERS):
        #     return False
        return True


class SIPResponse(SIPMsg):
    def __init__(self):
        super().__init__()
        self.status_code = None

    def _can_parse_start_line(self, start_line):
        return bool(re.match(RESPONSE_START_LINE_PATTERN, start_line))

    def _parse_start_line(self, start_line):
        self.version, code, msg = start_line.split(" ", 2)
        code_num = int(code)
        for member in SIPStatusCode:
            if member.value[0] == code_num:
                self.status_code = member

    def _build_start_line(self):
        if self.status_code and self.version:
            return f"{self.version} {self.status_code.value[0]} {self.status_code.value[1]}\r\n"
        else:
            return ""

    def can_build(self):
        if not self.status_code or not self.version:
            return False
        # if not set(self.headers.keys()).issubset(REQUIRED_HEADERS):
        #     return False
        return True


class SIPMsgFactory:
    @staticmethod
    def parse(raw_msg):
        if SIPMsg.is_request(raw_msg):
            req_object = SIPRequest()
            if req_object.parse(raw_msg):
                return req_object
            return None
        else:
            res_object = SIPResponse()
            if res_object.parse(raw_msg):
                return res_object
            return None

    @staticmethod
    def create_request(method, version, to_uri, from_uri, call_id, cseq, additional_headers=None, body=None):
        req_object = SIPRequest()
        req_object.method = method.value
        req_object.uri = to_uri
        req_object.version = version

        req_object.set_header('to', to_uri)
        req_object.set_header('from', from_uri)
        req_object.set_header('call-id', call_id)
        req_object.set_header('cseq', [cseq, method.value])
        print(req_object.get_header('cseq'))
        if additional_headers:
            for key, value in additional_headers:
                req_object.set_header(key, value)
        if body:
            req_object.set_body(body)
        else:
            # default content-length value if not body
            req_object.set_header('content-length', 0)
        return req_object

    @staticmethod
    def create_response_from_request(request, status_code, from_uri, additional_headers=None):
        print("creating response")
        res_object = SIPResponse()
        res_object.status_code = status_code
        if additional_headers:
            for key, value in additional_headers:
                res_object.set_header(key, value)

        res_object.version = request.version
        res_object.set_header('to', request.headers['from'])
        res_object.set_header('from', from_uri)
        res_object.set_header('call-id', request.headers['call-id'])
        res_object.set_header('cseq', request.headers['cseq'])

        if request.body:
            res_object.set_body(request.body)
        else:
            # default content-length value if not body
            res_object.set_header('content-length', 0)
        return res_object

    @staticmethod
    def create_response(status_code, version, method, cseq, to_uri, from_uri, call_id, additional_headers=None):
        res_object = SIPResponse()
        res_object.status_code = status_code
        if additional_headers:
            for key, value in additional_headers:
                res_object.set_header(key, value)

        res_object.version = version.version
        res_object.set_header('to', to_uri)
        res_object.set_header('from', from_uri)
        res_object.set_header('call-id', call_id)
        res_object.set_header('cseq', [cseq, method.value])
        res_object.set_header('content-length', 0)  # assume this is for errors. no body needed
        return res_object


"""
SipMsg

properties:
    - version: version of the sip msg
    - headers - dict of the headers {str: str} *must include required headers
    - body - the msg body

functions:
    can_parse(msg:str) - check if string representing sip follows requirements:
        start_line valid (diffs on req/res), headers valid + required present, CLRF, body(optional)
    parse(msg:str) - get string representing a sip msg, build a sip object from it:
            strip_essential_headers: strip all unneccery info from the required headers
    header manipulations - add/set, remove, get
    __str__ - convert into str

functions_abstract:
    start_line - can_parse, parse and build
"""

"""
SIPRequest : SIPMsg

properties:
    - method: the method of the request (enum)
    - uri: the uri of the request

functions:
    start_line - can_parse, parse, build, 
            proces_uri - strip info from uri 
"""

"""
SIPResponse : SIPMsg

properties:
    - status code: the status code of the response
functions:
    start_line - can_parse, parse, build:
        process_status_code - convert str into status code enum
"""

"""
@static class
SIPMsgFactory

functions:
    parse - takes string and invokes parse of SIPrequest or SIPResponse according to type
        identify_msg_type - return if string is req or res

    create_request - takes params and builds request: method, version, to_uri, from_uri, call-id, cseq, additional_headers, body
    build_response_from_request - take params and builds request object based on the response: 
    request object, status_code, extra_headers
    ## Copy essential headers from request
        for header in ['From', 'To', 'Call-ID', 'CSeq']:
            if header in request.headers:
                response.headers[header] = request.headers[header]
"""

raw_invite = """REGISTER sip:10.10.1.99 SIP/2.0\r
CSeq: 2 REGISTER\r
Via: SIP/2.0/UDP 10.10.1.13:5060; branch=z9hG4bK32366531-99e1-de11-8845-080027608325;rport\r
User-Agent: MySipClient/4.0.0\r
Authorization: Digest username="test13", realm="mypbx", nonce="343eb793", uri="sip:10.10.1.99", algorithm=MD5, response="6c13de87f9cde9c44e95edbb68cbdea9"\r
From: <sip:13@10.10.1.99>; tag=d60e6131-99e1-de11-8845-080027608325\r
Call-ID: \r
To: <sip:13@10.10.1.99>\r
Contact: <sip:13@10.10.1.13>;q=1\r
Allow: INVITE,ACK,OPTIONS,BYE,CANCEL,SUBSCRIBE,NOTIFY,REFER, MESSAGE,INFO,PING\r
Expires: 3600\r
Content-Length: 0\r
Max-Forwards: 70\r
Expires: 3600\r
\r\n"""
msg1 = SIPRequest()
# print(msg1.can_parse(raw_invite))
# print(msg1.parse(raw_invite))
# print(msg1.method)
