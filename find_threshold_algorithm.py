import socket
import time
import threading
import math
import serial

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
        self.num_last_time_stamp = 0
        self.time_stamp_list = []
        self.sound_fre = 10
        self.slide_window = right_hand * 20
        self.potential_threshold = [i for i in range(1, 50)]
        self.trigger_times = len(self.potential_threshold) * [0]
        self.trigger_marker = len(self.potential_threshold) * [0]
        self.time_above_threshold = len(self.potential_threshold) * [0.0]

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
            self.storage = [1] * len(self.potential_threshold)

    def talk(self):
        return self.num_time_stamp 


class FindThresholdThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
    def run(self):
        global slide_window_bear
        global program_start_time
        global calibrate_time
        global calibrate_period

        calibrate_start_time = time.time()
        while True:
            time.sleep(0.001)
            if time.time() - program_start_time < calibrate_time:

                if time.time() - calibrate_start_time <= calibrate_period:
                    for i in range(len(slide_window_bear.potential_threshold)):
                        if slide_window_bear.talk() > slide_window_bear.potential_threshold[i]:
                            if slide_window_bear.trigger_marker[i] == 0:
                                print('threshold {} triggered'.format(slide_window_bear.potential_threshold[i]))
                                slide_window_bear.trigger_times[i] += 1
                                slide_window_bear.trigger_marker[i] += 1

                else:
                    print(slide_window_bear.trigger_times)
                    slide_window_bear.trigger_marker = [0] * len(slide_window_bear.potential_threshold)
                    calibrate_start_time = time.time()

            else:

                # Finishing
                print('Calibration is over...')
                print(slide_window_bear.potential_threshold)
                print(slide_window_bear.trigger_times)
                num_period = calibrate_time / calibrate_period
                abs_difference = [0.0] * len(slide_window_bear.potential_threshold)
                trigger_rate = [0.0] * len(slide_window_bear.potential_threshold)
                for i in range(len(slide_window_bear.potential_threshold)):
                    trigger_rate[i] = slide_window_bear.trigger_times[i] / num_period
                    abs_difference[i] = abs(trigger_rate[i] - baseline)
                print(trigger_rate)
                recommended_index = abs_difference.index(min(abs_difference))
                print('Recommended threshold is {}, average trigger rate in {} seconds is {}'.format(slide_window_bear.potential_threshold[recommended_index], calibrate_period,trigger_rate[recommended_index]))
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

            spike_array = spike_socket.recv(1024)
            if spike_array == b'':
                raise RuntimeError("socket connection broken")

            if len(spike_array) > 0 and len(spike_array) % bytes_per_spike_chunk == 0:
                chunks_to_read = len(spike_array) / bytes_per_spike_chunk
                spike_index = 0

                for chunk in range(int(chunks_to_read)):

                    # Make sure we get the correct magic number for this chunk
                    magic_number, spike_index = int_read_from_array(spike_array, spike_index, 4)
                    if magic_number != '0x3ae2710f':
                        print('incorrect spike magic number', magic_number)

                    # Next 5 bytes are chars of native channel name
                    native_channel_name, spike_index = char_read_from_array(spike_array, spike_index, 5)

                    # Next 4 bytes are int timestamp
                    single_timestamp, spike_index = int_read_from_array(spike_array, spike_index, 4)

                    # Next 1 byte is int id
                    single_ID, spike_index = int_read_from_array(spike_array, spike_index, 1)

                    # Calculate the firing rate
                    # TODO
                    slide_window_bear.eat(int(single_timestamp, 16))

class BearMoveThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        global program_start_time
        global slide_window_bear
        while True:
            time.sleep(0.004)
            program_cur_time = int((time.time() - program_start_time) * 20* 1000)
            slide_window_bear.move(program_cur_time)

class BearCleanThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        global program_start_time
        global slide_window_bear
        while True:
            time.sleep(0.002)
            slide_window_bear.clean()

###############Initial Settings##########
channel_name = 'd-024'

calibrate_time = 300
calibrate_period = 10

baseline = 0.2
#############End of Initial Settings#######

#############Execute the Program###########
program_start_time = time.time()
slide_window_bear = SlideWindowBear(0, 200)


find_threshold_thread = FindThresholdThread()
bear_move_thread = BearMoveThread()
bear_clean_thread = BearCleanThread()
food_collect_thread = FoodCollectThread()

find_threshold_thread.start()
bear_move_thread.start()
bear_clean_thread.start()
food_collect_thread.start()
