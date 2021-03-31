import socket
import time
import threading
import math
import serial


# Read i bytes from array as int
def int_read_from_array(array, array_index, i):
    var_bytes = array[array_index:array_index + i]
    var = hex(int.from_bytes(var_bytes, 'little'))
    return var, array_index + i


# Read i bytes from array as i chars
def char_read_from_array(array, array_index, i):
    var_bytes = array[array_index:array_index + i]
    # native to unicode???
    var = str(var_bytes, 'utf-8')
    return var, array_index + i


class SlideWindow():
    def __init__(self, min_value, max_value):
        self.min_value = min_value
        self.max_value = max_value
        self.num_time_stamp = 0
        self.num_last_time_stamp = 0
        self.time_stamp_list = []
        self.sound_fre = 10
        self.slide_window = max_value * 20
        self.potential_threshold = [i for i in range(1, 50)]
        self.trigger_times = len(self.potential_threshold) * [0]
        self.trigger_marker = len(self.potential_threshold) * [0]
        self.time_above_threshold = len(self.potential_threshold) * [0.0]

    def add_time_stamp(self, time_stamp):
        if self.min_value < time_stamp < self.max_value:
            self.num_time_stamp += 1
            self.time_stamp_list.append(time_stamp)

    def remove_time_stamp(self):
        self.num_last_time_stamp = self.num_time_stamp
        if len(self.time_stamp_list) != 0 and self.time_stamp_list[0] < self.min_value:
            self.time_stamp_list.remove(self.time_stamp_list[0])
            self.num_time_stamp -= 1

    def sync(self, new_right_hand):
        if new_right_hand > self.slide_window:
            self.max_value = new_right_hand
            self.min_value = new_right_hand - self.slide_window
            self.storage = [1] * len(self.potential_threshold)

    def return_time_stamp(self):
        return self.num_time_stamp


class FindThresholdThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        global slide_window
        global program_start_time
        global calibrate_time
        global calibrate_period

        calibrate_start_time = time.time()
        while True:
            time.sleep(0.001)
            if time.time() - program_start_time < calibrate_time:

                if time.time() - calibrate_start_time <= calibrate_period:
                    for i in range(len(slide_window.potential_threshold)):
                        if slide_window.return_time_stamp() > slide_window.potential_threshold[i]:
                            if slide_window.trigger_marker[i] == 0:
                                print('threshold {} triggered'.format(slide_window.potential_threshold[i]))
                                slide_window.trigger_times[i] += 1
                                slide_window.trigger_marker[i] += 1

                else:
                    print(slide_window.trigger_times)
                    slide_window.trigger_marker = [0] * len(slide_window.potential_threshold)
                    calibrate_start_time = time.time()

            else:

                # Finishing
                print('Calibration is over...')
                print(slide_window.potential_threshold)
                print(slide_window.trigger_times)
                num_period = calibrate_time / calibrate_period
                abs_difference = [0.0] * len(slide_window.potential_threshold)
                trigger_rate = [0.0] * len(slide_window.potential_threshold)
                for i in range(len(slide_window.potential_threshold)):
                    trigger_rate[i] = slide_window.trigger_times[i] / num_period
                    abs_difference[i] = abs(trigger_rate[i] - baseline)
                print(trigger_rate)
                recommended_index = abs_difference.index(min(abs_difference))
                print('Recommended threshold is {}, average trigger rate in {} seconds is {}'.format(
                    slide_window.potential_threshold[recommended_index], calibrate_period,
                    trigger_rate[recommended_index]))
                break


class ParseNeuralSignalThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        global slide_window
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
            b'set ' + channel_name.encode() + b'.TCPDataOutputEnabled true;set ' + channel_name.encode() + b'.TCPDataOutputEnabledSpike true;set runmode run;')
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
                    slide_window.add_time_stamp(int(single_timestamp, 16))


class SlideWindowSyncThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        global program_start_time
        global slide_window
        while True:
            time.sleep(0.004)
            program_cur_time = int((time.time() - program_start_time) * 20 * 1000)
            slide_window.sync(program_cur_time)


class SlideWindowRemoveTimeStampThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        global program_start_time
        global slide_window
        while True:
            time.sleep(0.002)
            slide_window.remove_time_stamp()


###############Initial Settings##########
channel_name = 'd-024'

calibrate_time = 300
calibrate_period = 10

baseline = 0.2
#############End of Initial Settings#######

#############Execute the Program###########
program_start_time = time.time()
slide_window = SlideWindow(0, 200)

find_threshold_thread = FindThresholdThread()
slide_window_sync_thread = SlideWindowSyncThread()
slide_window_remove_time_stamp_thread = SlideWindowRemoveTimeStampThread()
parse_neural_signal_thread = ParseNeuralSignalThread()

find_threshold_thread.start()
slide_window_sync_thread.start()
slide_window_remove_time_stamp_thread.start()
parse_neural_signal_thread.start()
