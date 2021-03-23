import socket
import time
import threading
import math
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

# Buzzer frequency transformation
def spike2sound(slideWindowBear):
    numTimeStamp = slideWindowBear.talk()
    soundFrequency = A1 * exp(numTimeStamp) - A2 * exp(numTimeStamp-1) + A3
    buzzerGapTime = 1 / (soundFrequency * 2)
    if soundFrequency > 1500 and soundFrequency < 4000:
        digital[7].write(1)
        time.sleep(buzzerGapTime)
        digital[7].write(0)
        time.sleep(buzzerGapTime)
    else:
        digital[8].write(1)
        time.sleep(buzzerGapTime)
        digital[8].write(0)
        time.sleep(buzzerGapTime)

# Reward function
def giveReward(outputChannel, gapTime):
    digital[outputChannel].write(1)
    time.sleep(gapTime)
    digital[outputChannel].write(0)
    time.sleep(gapTime)



class SlideWindowBear():
    def __init__(self, left_hand, right_hand):
        self.left_hand = left_hand
        self.right_hand = right_hand
        self.num_time_stamp = 0
        self.num_last_time_stamp = 0
        self.time_stamp_list = []
        self.sound_fre = 10
        self.slide_window = right_hand * 20
        self.potential_threshold = [0,1,2,3,4,5,6,7,8,9,10]
        self.margin_points = [[] for _ in range(len(self.potential_threshold))]
        self.num_margin_point = len(self.potential_threshold) * [0]
        self.time_above_threshold = len(self.potential_threshold) * [0]

    def eat(self, time_stamp):
        if time_stamp > self.left_hand and time_stamp < self.right_hand:
            self.num_time_stamp += 1
            self.time_stamp_list.append(time_stamp)

    def clean(self):
        self.num_last_time_stamp = self.num_time_stamp
        if len(self.time_stamp_list) != 0 and self.time_stamp_list[0] < self.left_hand:
            self.time_stamp_list.remove(self.time_stamp_list[0])
            self.num_time_stamp -= 1
        

    def move(self, new_right_hand):
        if new_right_hand > self.slide_window:
            self.right_hand = new_right_hand
            self.left_hand = new_right_hand - self.slide_window

    def talk(self):
        return self.num_time_stamp 


class FindThresholdThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
    def run(self):
        global slide_window_bear
        global program_start_time
        global calibrate_time
        while True:
            time.sleep(0.00001)
            print(slide_window_bear.num_margin_point)
            for i in range(len(slide_window_bear.potential_threshold)):

                # Record critical point higher than threshold
                if slide_window_bear.talk() == slide_window_bear.potential_threshold[i] and \
                        slide_window_bear.num_last_time_stamp < slide_window_bear.potential_threshold[i]:
                    program_cur_time = time.time() - program_start_time
                    slide_window_bear.num_margin_point[i] += 1
                    slide_window_bear.margin_points[i].append(program_cur_time)

                # Record critical point lower than threshold
                if slide_window_bear.num_margin_point[i] > 0 and \
                        slide_window_bear.talk() == slide_window_bear.potential_threshold[i] and \
                        slide_window_bear.num_last_time_stamp > slide_window_bear.potential_threshold[i]:
                    program_cur_time = time.time() - program_start_time
                    slide_window_bear.num_margin_point[i] += 1
                    slide_window_bear.margin_points[i].append(program_cur_time)

            # 1 mins for threshold setting
            if time.time() - program_start_time > calibrate_time:
                for i in range(len(slide_window_bear.potential_threshold)):
                    for j in range(len(slide_window_bear.margin_points[i])-1):
                        if j % 2 == 1:
                            slide_window_bear.time_above_threshold[i] += slide_window_bear.margin_points[i][j] - \
                                                                     slide_window_bear.margin_points[i][j-1]

                    if slide_window_bear.time_above_threshold[i] / calibrate_time >= baseline:
                        print("*****",i, slide_window_bear.time_above_threshold[i],slide_window_bear.time_above_threshold[i] / calibrate_time)
                print(slide_window_bear.time_above_threshold)
                break


class FoodCollectThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
    def run(self):
        global slide_window_bear
        global channel_name
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
            b'set '+channel_name.encode()+b'.TCPDataOutputEnabled true;set '+channel_name.encode()+b'.TCPDataOutputEnabledSpike true;set runmode run;')
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
                    #print(int(single_timestamp, 16))

                    #update_time(int(single_timestamp, 16))

                    # Next 1 byte is int id
                    single_ID, spike_index = int_read_from_array(spike_array, spike_index, 1)

                    # Calculate the firing rate
                    # TODO
                    slide_window_bear.eat(int(single_timestamp, 16))

class SoundPlayingThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
    def run(self):
        global serial_port
        global slide_window_bear
        board = Arduino(serial_port)
        while True:
            spike2sound()

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
serial_port = '/dev/cu.usbmodem1401'
channel_name = 'd-103'
calibrate_time = 10
baseline = 0.3
program_start_time = time.time()
slide_window_bear = SlideWindowBear(0, 200)

#sound_playing_thread = SoundPlayingThread()
bear_move_thread = BearMoveThread()
bear_clean_thread = BearCleanThread()
food_collect_thread = FoodCollectThread()
find_threshold_thread = FindThresholdThread()

find_threshold_thread.start()
bear_move_thread.start()
bear_clean_thread.start()
food_collect_thread.start()
#sound_playing_thread.start()
