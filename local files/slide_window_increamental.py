import socket
import time
import threading
from pyfirmata import Arduino

# Read i bytes from array as int
def int_read_from_array(array, array_index, i):
    var_bytes = array[array_index:array_index+i]
    var = hex(int.from_bytes(var_bytes, 'little'))
    return var, array_index + i

# Read i bytes from array as i chars
def char_read_from_array(array, array_index, i):
    var_bytes = array[array_index:array_index+i]
    # native to unicode???
    var = str(var_bytes,'utf-8')
    return var, array_index + i


class SlideWindowBear():
    def __init__(self, left_hand, right_hand):
        self.left_hand = left_hand
        self.right_hand = right_hand
        self.num_time_stamp = 0
        self.time_stamp_list = []
        self.sound_fre = 100
        self.slide_window = right_hand * 20

    def eat(self, time_stamp):
        if time_stamp > self.left_hand and time_stamp < self.right_hand:
            self.num_time_stamp += 1
            self.time_stamp_list.append(time_stamp)

    def clean(self):
        if len(self.time_stamp_list) != 0 and self.time_stamp_list[0] < self.left_hand:
            self.time_stamp_list.remove(self.time_stamp_list[0])
            self.num_time_stamp -= 1

    def move(self, new_right_hand):
        if new_right_hand > self.slide_window:
            self.right_hand = new_right_hand
            self.left_hand = new_right_hand - self.slide_window

    def talk(self):
        # Calculate sound frequency
        time.sleep(0.5)
        if self.num_time_stamp > 3:
            self.sound_fre = 2*(self.sound_fre)
            return self.sound_fre
        else: return self.sound_fre

class FoodCollectThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
    def run(self):
        global slide_window_bear
        # Set localhost
        HOST = '127.0.0.1'

        # Connect to spike server
        spike_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        spike_socket.connect((HOST, 5002))

        # Connect to command server
        cmd_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cmd_socket.connect((HOST, 5000))

        # Clear TCP data output to ensure no TCP channels are enabled at
        # the begining of this script

        # Send TCP commands to set up TCP data output
        cmd_socket.sendall(
            b'set d-103.TCPDataOutputEnabled true;set d-103.TCPDataOutputEnabledSpike true;set runmode run;')
        print('Connection set up...')

        # Wait 1 second to make sure data sockets are ready to begin
        time.sleep(1)

        # Each spike chunk contains 4 bytes for magic number, 5 bytes for natice
        # channel name, 4 bytes for timestamp, and 1 byte for id. Total: 14 bytes
        bytes_per_spike_chunk = 14

        # Loop
        while True:
            print('Start to receive data from stream...')

            spike_array = spike_socket.recv(1024)
            if spike_array == b'':
                raise RuntimeError("socket connection broken")

            if spike_array:
                print(spike_array)

            if len(spike_array) > 0 and len(spike_array) % bytes_per_spike_chunk == 0:
                print('Successfully received the 1st chunk')
                chunks_to_read = len(spike_array) / bytes_per_spike_chunk
                spike_index = 0

                for chunk in range(int(chunks_to_read)):

                    print('Start to process the {} chunk'.format(chunk + 1))

                    # Make sure we get the correct magic number for this chunk
                    magic_number, spike_index = int_read_from_array(spike_array, spike_index, 4)
                    if magic_number != '0x3ae2710f':
                        print('incorrect spike magic number', magic_number)
                    if magic_number == '0x3ae2710f':
                        print('magic number is right', magic_number)

                    # Next 5 bytes are chars of native channel name
                    native_channel_name, spike_index = char_read_from_array(spike_array, spike_index, 5)
                    print(native_channel_name)

                    # Next 4 bytes are int timestamp
                    single_timestamp, spike_index = int_read_from_array(spike_array, spike_index, 4)

                    # Next 1 byte is int id
                    single_ID, spike_index = int_read_from_array(spike_array, spike_index, 1)

                    # Calculate the firing rate
                    slide_window_bear.eat(int(single_timestamp, 16))

class SoundPlayingThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
    def run(self):
        board = Arduino('/dev/cu.usbmodem11401')
        global slide_window_bear
        while True:
            board.digital[7].write(1)
            buz_gap = 0.5/slide_window_bear.talk()
            time.sleep(buz_gap)
            board.digital[7].write(0)
            time.sleep(buz_gap)

class BearMoveThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        global program_start_time
        global slide_window_bear
        while True:
            time.sleep(0.00001)
            program_cur_time = int((time.time() - program_start_time) * 20* 1000)
            slide_window_bear.move(program_cur_time)

class BearCleanThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        global program_start_time
        global slide_window_bear
        while True:
            time.sleep(0.00001)
            slide_window_bear.clean()

# Global Variable
program_start_time = time.time()
slide_window_bear = SlideWindowBear(0, 500)

sound_playing_thread = SoundPlayingThread()
bear_move_thread = BearMoveThread()
bear_clean_thread = BearCleanThread()
food_collect_thread = FoodCollectThread()


bear_move_thread.start()
bear_clean_thread.start()
food_collect_thread.start()
sound_playing_thread.start()
