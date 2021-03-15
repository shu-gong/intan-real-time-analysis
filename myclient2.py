import socket
import threading

class Thread(threading.Thread):
    def __init__(self, threadID, name, counter):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.counter = counter
    def run(self):
        print('start threading: ' + self.name)
        print('exit threading: ' + self.name)



# Read 4 bytes from array as int
def int_read_from_array(array, array_index):
    var_bytes = array[array_index:array_index+4]
    var = int(var_bytes)
    return var, array_index + 4

# Read 5 bytes from array as 5 chars
def char_read_from_array(array, array_index):
    var_bytes = array[array_index:array_index+5]
    # native to unicode???
    var = ord(var_bytes)
    return var, array_index + 5

# Connect to intan server
HOST = '127.0.0.1'
PORT = 5002
c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
c.connect((HOST, 5000))
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((HOST, PORT))

c.sendall(b'set a-000.tcpdataoutputenabled true;set a-000.TCPDataOutputEnabledSpike true;set runmode run;')
while True:
    k = s.recv(14)

    if k:
        print('received something')