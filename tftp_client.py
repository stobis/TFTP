#!/usr/bin/env python2.7

import socket
import sys
import threading
import struct
import hashlib

# Init vars
HOST = sys.argv[1]
PORT = int(sys.argv[2])
FILE = sys.argv[3]

# Other vars
BLOCKSIZE = 512
ATTEMPTS = 5
SOCK_TIMEOUT = 1
ACK = 4
WSIZE = 32

class FileClient:
    
    def __init__(self, host, port, fname):
        # Set server info
        self.host = host
        self.port = port
        self.file = fname
        
        # Create socket to transfer
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(SOCK_TIMEOUT)
        
        # Info about req file/packets
        self.lastPacket = None
        self.data = ""
        self.checksum = hashlib.md5()
    
        # Num of successfully sent packets
        self.accepted = 0
        self.attempts = ATTEMPTS
        
        self.terminate = False
        #print("---INIT FINISHED---")
        
   
    def getMD5(self):
        print("FILE CONTENT: {}".format(self.data))
        return self.checksum.hexdigest()

    def handleTimeout(self):
        # We are counting consecutive timeouts
        self.attempts -= 1
                    
        if self.attempts <= 0:
            self.terminate = True
        else:
            # Try to send last packet
            self.sock.sendto(self.lastPacket, (self.host, self.port))
            

    def createRRQ(self):
        # Create RRQ message with given arguments
        request = str(struct.pack('!H', 1)) + self.file + str(struct.pack('!H', 0)) + "octet" + str(struct.pack('!H', 0)) + "windowsize" + str(struct.pack('!H', 0)) + str(WSIZE) + str(struct.pack('!H', 0))
        
        # Send RRQ to server
        self.lastPacket = request
        self.sock.sendto(request, (self.host, self.port))
        
        # Receive first message from server and set new communication port (TID)
        while True:
            try:
                recvData, recvFrom = self.sock.recvfrom(1024)
                self.attempts = ATTEMPTS
                
                self.host = recvFrom[0]
                self.port = recvFrom[1]
                return recvData
            
            except socket.timeout:
                self.handleTimeout()
                if self.terminate is True:
                    break
                else:
                    continue
                    
    def recv(self):
        while True:
            try:
                recvData, recvFrom = self.sock.recvfrom(1024)
                self.attempts = ATTEMPTS
                
                # Ignore unknown message
                if recvFrom[0] != self.host or recvFrom[1] != self.port:
                    continue
                
                return recvData
                
            except socket.timeout:
                self.handleTimeout()
                if self.terminate is True:
                    break
                else:
                    continue
        
    def sendACK(self):
        last = str(struct.pack('!HH', ACK, self.accepted))
        self.sock.sendto(last, (self.host, self.port))
        
    def download(self):
        
        # Init connection with server and get first data from server
        #print("BEFORE {} {}".format(self.host, self.port))
        
        act = self.createRRQ()
        
        print("CONNECTION WITH (download from): {}:{}\n".format(self.host, self.port))
        
        # Download file
        while True:
        
            error = 0
            opinfo = struct.unpack('!HH', act[:4])
            
            # Check correct packet type (data = 3)
            if opinfo[0] == 3:
                # Case 1: normal (next) data packet
                if opinfo[1] == self.accepted + 1:
                    self.accepted += 1
                    self.checksum.update(str(act[4:]))
                    self.data += str(act[4:])
                    
                    # Case 1a: last data packet
                    if len(act[4:]) < BLOCKSIZE:
                        self.sendACK()
                        break
                #Case 2: at least one packet has lost   
                else:
                    error = 1
            elif opinfo[0] == 5: # Error
                if opinfo[1] == 1:
                    print("ERROR! File not found or not accessible.")
                else:
                    print("ERROR! <unknown type>")
                break
            else:
                break

            # Send ACK when necessary
            if self.accepted%WSIZE == 0 or error == 1:
                self.sendACK()

            # Recv next packet from server
            self.lastPacket = str(struct.pack('!HH', ACK, self.accepted))
            act = self.recv()
            
            if self.terminate is True:
                print("FATAL ERROR! PROBABLY CONNECTION IS DEAD")
                break

        
# Main func
if __name__ == '__main__':

    # Create and run TFTP Client
    client = FileClient(HOST, PORT, FILE)
    client.download()
    print("FILE CHECKSUM: {}".format(client.getMD5()))
    print("---ALL DONE---")

