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

# Real time process core class
class SlideWindow():
    def __init__(self, min_value, max_value):
        self.min_value = min_value
        self.max_value = max_value

        self.num_time_stamp = [0, 0]
        self.num_last_time_stamp = [0, 0]
        self.time_stamp_list = [[], []]
        self.slide_window = max_value * 20

        # Very important: threshold must start from 0
        # Ensure the value of threshold is equal to its index
        self.potential_threshold = [i for i in range(0, 51)]
        self.pos = [[] for _ in range(len(self.potential_threshold))]
        self.trigger_times = [[] for _ in range(len(self.potential_threshold))]
        self.trigger_marker = [[] for _ in range(len(self.potential_threshold))]
        self.time_above_threshold = len(self.potential_threshold) * [0.0]

        for i in range(len(self.potential_threshold)):
            #self.pos[i] = [[0,0] for _ in range(len(self.potential_threshold))]
            self.pos[i] = [[0,300] for _ in range(len(self.potential_threshold))]
            self.trigger_times[i] = [0.0 for _ in range(len(self.potential_threshold))]
            self.trigger_marker[i] = [0.0 for _ in range(len(self.potential_threshold))]

    # Add time stamp to slide window
    def add_time_stamp(self, channel_idx, time_stamp):
        if self.min_value <= time_stamp <= self.max_value:
            self.num_time_stamp[channel_idx] += 1
            self.time_stamp_list[channel_idx].append(time_stamp)

    # Return the number of time stamps in slide window
    def return_time_stamp(self):
        return self.num_time_stamp

    def tcp_sync(self,new_max_value):
        self.max_value = new_max_value
        self.min_value = new_max_value - self.slide_window

        for i in range(len(self.time_stamp_list)):
            self.num_last_time_stamp[i] = self.num_time_stamp[i]
            while len(self.time_stamp_list[i]) != 0 and self.time_stamp_list[i][0] < self.min_value:
                self.time_stamp_list[i].remove(self.time_stamp_list[i][0])
                self.num_time_stamp[i] -= 1


class FindThresholdThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):

        global slide_window
        global program_start_time
        global calibrate_time
        global calibrate_period
        global stride
        calibrate_count = 0

        calibrate_start_time = time.time()
        while True:
            time.sleep(0.001)

            if time.time() - program_start_time < calibrate_time:

                if time.time() - calibrate_start_time <= calibrate_period:
                    for i in range(len(slide_window.potential_threshold)):
                        for j in range(len(slide_window.potential_threshold)):
                            if slide_window.num_time_stamp[0] >= slide_window.potential_threshold[i]:
                                #print(slide_window.pos)
                                slide_window.pos[i][j][0] += stride
                                if slide_window.pos[i][j][0] > 300:
                                    slide_window.pos[i][j][0] -= stride

                            if slide_window.num_time_stamp[1] >= slide_window.potential_threshold[j]:
                                slide_window.pos[i][j][1] += stride
                                if slide_window.pos[i][j][1] > 300:
                                    slide_window.pos[i][j][1] -= stride

                            #if slide_window.pos[i][j][0] >= 300 and slide_window.pos[i][j][1] >= 300:
                            if slide_window.pos[i][j][0] >= 300:
                                if slide_window.trigger_marker[i][j] == 0.0:
                                    print('threshold combination {} and {} get reward'
                                          .format(slide_window.potential_threshold[i],slide_window.potential_threshold[j]))
                                    slide_window.trigger_times[i][j] += 1
                                    slide_window.trigger_marker[i][j] += 1
                else:
                    print('calibration finished')
                    calibrate_count += 1
                    slide_window.trigger_marker = [[] for _ in range(len(slide_window.potential_threshold))]
                    slide_window.pos = [[] for _ in range(len(slide_window.potential_threshold))]

                    for i in range(len(slide_window.potential_threshold)):
                        slide_window.pos[i] = [[0, 300] for _ in range(len(slide_window.potential_threshold))]
                        slide_window.trigger_marker[i] = [0.0 for _ in range(len(slide_window.potential_threshold))]
                    calibrate_start_time = time.time()

            else:
                print('calibrate_count :', calibrate_count)
                trigger_rate = [[] for _ in range(len(slide_window.potential_threshold))]
                abs_difference_times_ten = [[] for _ in range(len(slide_window.potential_threshold))]
                for i in range(len(slide_window.potential_threshold)):
                    trigger_rate[i] = [0.0 for _ in range(len(slide_window.potential_threshold))]
                    abs_difference_times_ten[i] = [0.0 for _ in range(len(slide_window.potential_threshold))]

                print('Calibration is over...')
                for i in range(len(slide_window.potential_threshold)):
                    for j in range(len(slide_window.potential_threshold)):
                        trigger_rate[i][j] = slide_window.trigger_times[i][j] / calibrate_count
                        abs_difference_times_ten[i][j] = int(abs(trigger_rate[i][j] - baseline) * 10)
                print(trigger_rate)
                tempi = []
                tempj = []
                for i in range(len(slide_window.potential_threshold)):
                    for j in range(len(slide_window.potential_threshold)):
                        if abs_difference_times_ten[i][j] <= 1:
                            tempi.append(i)
                            tempj.append(j)
                            #print('i,j,trigger_rate = {},{},{}'.format(i,j,trigger_rate[i][j]))
                            print('i,trigger_rate = {},{}'.format(i,trigger_rate[i][j]))

                tempmax = 0
                tempmaxi = 0
                tempmaxj = 0
                for k in range(len(tempi)):
                    if tempi[k] > tempmax:
                        tempmax = tempi[k]
                        tempmaxi = tempi[k]
                        tempmaxj = tempj[k]

                # print('Recommended threshold combination are {} and {}, average trigger rate is {}'.format(
                #     tempmaxi, tempmaxj,trigger_rate[tempmaxi][tempmaxj]
                # ))

                print(tempi)
                print(tempj)
                print('Recommended threshold is {}, average trigger rate is {}'.format(
                    tempmaxi,trigger_rate[tempmaxi][tempmaxj]
                ))
                break


# Parse neural signals sent from Intan Recorder
class ParseNeuralSignalThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        global slide_window
        global channel_name
        global program_start_time
        global P1
        # Set localhost
        HOST = '127.0.0.1'

        # Connect to spike server
        spike_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        spike_socket.connect((HOST, 5002))

        # Connect to command server
        cmd_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cmd_socket.connect((HOST, 5000))

        # Send TCP commands to set up TCP data output
        cmd_socket.sendall(
            b'set ' + channel_name[0].encode() + b'.TCPDataOutputEnabled true;set ' + channel_name[0].encode() + b'.TCPDataOutputEnabledSpike true;'+
            b'set ' + channel_name[1].encode() + b'.TCPDataOutputEnabled true;set ' + channel_name[1].encode() + b'.TCPDataOutputEnabledSpike true;'+
            b'set runmode run;')
        # cmd_socket.sendall(
        #     b'set ' + channel_name_1.encode() + b'.TCPDataOutputEnabled true;set ' + channel_name_1.encode() + b'.TCPDataOutputEnabledSpike true;'+
        #     b'set runmode run;')
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
                #program_cur_time = int((time.time() - program_start_time) *20 * 1000)

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
                    slide_window.tcp_sync(int(single_timestamp, 16))

                    if native_channel_name[-3:] == channel_name[0][-3:]:
                        slide_window.add_time_stamp(0,int(single_timestamp, 16))

                    if native_channel_name[-3:] == channel_name[1][-3:]:
                        slide_window.add_time_stamp(1,int(single_timestamp, 16))



###############Initial Settings##########
channel_name = ['c-069','c-114']

calibrate_time = 60
calibrate_period = 10
stride = 10
baseline = 0.3
#############End of Initial Settings#######

#############Execute the Program###########
program_start_time = time.time()
slide_window = SlideWindow(0, 200)

find_threshold_thread = FindThresholdThread()
parse_neural_signal_thread = ParseNeuralSignalThread()

find_threshold_thread.start()
parse_neural_signal_thread.start()
