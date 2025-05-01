#include <winsock2.h>
#include <iostream>
#include <thread>
#include <mutex>
#include <map>
#include <ctime> //time_t timestamp; time(&timestamp);
#include <vector>

enum SessionType{
    SESSION_AUDIO,
    SESSION_VIDEO
}    SessionType;

struct RTPSession{
    std::string call_id;
    SessionType type;
    int port1;
    int port2;
    int listen_port;
    int is_running;
};


class RTPProxy{
    private:
        SOCKET server_socket;
        std::mutex sessionLock;
        std::map<std::string, RTPSession> sessionMap;
        std::vector<int> usedPorts; // ports that are in active sessions
        std::map<int, time_t> allocated_ports; // ports that the sip server used in sdp but hasn't started the session
};


int main(){
    //https://medium.com/@tharunappu2004/creating-a-simple-tcp-server-in-c-using-winsock-b75dde86dd39

    // initialise the winsocket dll
    WSADATA wsaData;
    int wsaerr;
    WORD wVersionRequested = MAKEWORD(2,2);
    wsaerr = WSAStartup(wVersionRequested, &wsaData);
    //WSAStartup resturns 0 if it is successfull or non zero if failed
    if(wsaerr != 0){ 
        std::cout << "The Winsock dll not found!" << std::endl;
        return 0;
    } else  {
        std::cout << "The Winsock dll found" << std::endl;
        std::cout << "The status: "<< wsaData.szSystemStatus << std::endl;
    }
}
