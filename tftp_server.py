#!/usr/bin/env python3

import socket
import sys
import threading
import struct
import select

# Init vars
HOST = 'localhost'
PORT = int(sys.argv[1])
DIR = sys.argv[2]

# Other vars
BLOCKSIZE = 512
ATTEMPTS = 5
SOCK_TIMEOUT = 1
ACK = 4

# Manage connection with client 
class FileTransferHandler(threading.Thread):

    def __init__(self, addr, port, initMsg):
        # Create base daemon thread
        threading.Thread.__init__(self, daemon = True)
        
        # Set client info
        self.addr = addr
        self.port = port
        
        # Create socket to transfer
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(SOCK_TIMEOUT)
        
        # Num of successfully sent packets
        self.accepted = 0
        self.attempts = ATTEMPTS
        
        # Chcek if request is valid and can be accepted
        self.valid = True
        self.parseInitMsg(initMsg)
        
        # Open requested file
        self.loadFile()
      
        #print("---INIT FINISHED---")
        
        
    def parseInitMsg(self, initMsg):
        
        #print(initMsg)
        initMsg = initMsg.split(b'\x00')
        initMsg = list( filter(None, initMsg) )
        #print(initMsg)
        
        if len(initMsg) < 4:
            self.valid = False
            return
        
        opcode = int(initMsg[0][0])
        self.fileName = initMsg[0][1:].decode("utf-8")
        mode = initMsg[1].decode("utf-8")
        windowsize = initMsg[2].decode("utf-8")
        self.windowsize = int(initMsg[3])
            
        if opcode != 1 or mode != "octet" or windowsize != "windowsize":
            self.valid = False
        
        #print("OPINFO :")
        #print(opcode, self.fileName, mode, windowsize, self.windowsize, self.valid)
        
        
    def loadFile(self):
        # Open requested file
        try:
            self.file = open(DIR + self.fileName, "rb")
        except Exception as e:
            #print(e)
            data = struct.pack('!HHsH', 5, 1, str.encode("FOpen error"), 0)
            self.sock.sendto(data, (self.addr, self.port))
            self.valid = False
            return
        
        # Parse file data
        self.data = []
         
        blkID = 1
        tmp = self.file.read(BLOCKSIZE)
        
        while len(tmp) > 0:
            self.data.append( (blkID, tmp) )
            blkID += 1
            tmp = self.file.read(BLOCKSIZE)
            
        self.data.insert(0, (0, 0))
        #print(len(self.data))
        self.file.close()

    
    def sendWindow(self):
        # Select interval of blocks to send
        begin = self.accepted + 1
        end = begin + self.windowsize
        
        # Send every block to client
        for i in range(begin, min(end, len(self.data))):
            data = struct.pack("!HH%ds" % len(self.data[i][1]), 3, i, self.data[i][1])
            self.sock.sendto(data, (self.addr, self.port))
        
    def run(self):
        
        # Check if we should do sonething...
        if self.valid is False:
            print("Invalid REQ data! Cancelling transfer...")
            return
        
        print("Start sending file...")
        # Send zero-packet
        self.sendWindow()
        
        # Send file
        while True:
            # Receive data
            while True:
                try:
                    recvData, client = self.sock.recvfrom(1024)
                    self.attempts = ATTEMPTS
                    break
                    
                except socket.timeout:
                    # We are counting consecutive timeouts
                    self.attempts -= 1
                    
                    if self.attempts <= 0:
                        break
                    else:
                        # Try to send last window
                        self.sendWindow()
                        continue
            
            # We probably lost connection - time to surrender
            if self.attempts <= 0:
                break    
                    
            # Ignoring msg from unknown source
            if client[0] != self.addr or client[1] != self.port:
                continue
            
            # Extract received data
            opcode = struct.unpack("!H", recvData[0:2])[0]
            
            # Got ACK from client, uff
            if opcode == ACK:
                
                blkNum = struct.unpack("!H", recvData[2:4])[0]
                
                if blkNum > 0:
                    self.accepted = blkNum
                    print("Accepted {} blocks".format(blkNum))
                    
                    if len(self.data[blkNum][1]) < 512:
                        break
                
                self.sendWindow()
                
            # We finished
            if self.accepted + 1 == len(self.data):
                break
                
        if self.attempts > 0:
            print("TRANSFER {} DONE SUCCESSFUL".format(self.fileName))
        else:
            print("TRANSFER {} FAILED".format(self.fileName))
        # Time to clean
        self.data = []
        self.sock.close()


# Main server class
class FileServer:

    def __init__(self, host, port):
        self.clients = {}
        self.open_socket(host, port)
    
    def open_socket(self, host, port):
        
        # Create server on host:port
        self.server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server.bind( (host, port) ) 
        
    def run(self):
        
        print("Waiting for clients...")
        
        while True:
            
            # Block until server socket has input on it...
            print("Select()...")
            sInput, sOut, sSpec = select.select([self.server], [], [])

            # Remove dead threads
            self.clients = {key:val for key, val in self.clients.items() if val.isAlive() is True}

            # Handle message if available
            if len(sInput) > 0:
            
                # Traffic on the main server socket
                buffer, (raddress, rport) = self.server.recvfrom(1024)

                print("---> NEW CLIENT <---\nMSG: {}\n---".format(buffer))

                key = "%s:%s" % (raddress, rport)

                # Connect with client if new
                if key not in self.clients.keys():
                    print("Creating new handler for {}".format(key))
                        
                    self.clients[key] = FileTransferHandler(raddress, rport, buffer)
                    self.clients[key].start()
                    
                    print("Now handling:")
                    for x in self.clients:
                        print(x)

        print("After main server loop")
            
# Main func
if __name__ == '__main__':

    # Create and run TFTP Server
    server = FileServer(HOST, PORT)
    server.run()
    print("---ALL DONE---")
    

        
