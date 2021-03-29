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
    var = str(var_bytes, 'utf-8')
    return var, array_index + i


# Sound frequency transformation
def spike2sound(theSlideWindow, theArduino, theLowerLimit, theHigherLimit, theThreshold):
    numTimeStamp = theSlideWindow.return_time_stamp()

    theBase = theHigherLimit / theLowerLimit
    if numTimeStamp < theThreshold:
        soundFrequency = theLowerLimit * (theBase ** (numTimeStamp / theThreshold))
    else:
        soundFrequency = theHigherLimit

    gap = 500000 / soundFrequency
    theArduino.write((str(gap) + ',').encode())
    return numTimeStamp


# Reward function
def giveReward(theArduino):
    theArduino.write(b'314159265354,')


# Real time process core class
class SlideWindow():
    def __init__(self, min_value, max_value):
        self.min_value = min_value
        self.max_value = max_value
        self.num_time_stamp = 0
        self.num_last_time_stamp = 0
        self.time_stamp_list = []
        self.sound_fre = 10
        self.slide_window = max_value * 20
        self.potential_threshold = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
        self.time_above_threshold = len(self.potential_threshold) * [0.0]

    # Add time stamp to slide window
    def add_time_stamp(self, time_stamp):
        if self.min_value < time_stamp < self.max_value:
            self.num_time_stamp += 1
            self.time_stamp_list.append(time_stamp)

    # Remove time stamp that exceeds slide window range
    def remove_time_stamp(self):
        self.num_last_time_stamp = self.num_time_stamp
        if len(self.time_stamp_list) != 0 and self.time_stamp_list[0] < self.min_value:
            self.time_stamp_list.remove(self.time_stamp_list[0])
            self.num_time_stamp -= 1

    # Return the number of time stamps in slide window
    def return_time_stamp(self):
        return self.num_time_stamp

    # Sync the slide window, make sure it is in real time
    def sync(self, new_max_value):
        if new_max_value > self.slide_window:
            self.max_value = new_max_value
            self.min_value = new_max_value - self.slide_window


# Parse neural signals sent from Intan Recorder
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


# Main thread to execute the rewarding system
class MainTrialThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        global reward_threshold
        global serial_port
        global slide_window
        global arduino
        global total_trial_time
        global trial_period
        global trial_start_time
        global reward_condition_lock

        fail_count = 0
        reward_count = 0
        trial_count = 0

        # Open a file to prepare for writing results
        f = open('./reward_count' + str(time.strftime("%m-%d", time.localtime())) + '.txt', 'w')

        # Initialize the first trial start time
        trial_start_time = time.time()

        # Loop
        while True:
            time.sleep(0.01)

            # If current time dose not exceed  total trial time
            if time.time() - program_start_time < total_trial_time:

                # In every trial, detect the animal's current spikes within 200 ms
                if time.time() - trial_start_time <= trial_period:

                    # Play sound according to the animal's firing rate
                    current_num_time_stamp = spike2sound(slide_window, arduino, low_frequency, high_frequency,
                                                         reward_threshold)

                    # If the animal dose not get a reward in the previous time of the trial period
                    if reward_condition_lock == 0:
                        if current_num_time_stamp >= reward_threshold:
                            reward_condition_lock = 1
                            f.writelines('invoke times + 1 ' + str(time.time() - program_start_time) + '\n')
                            giveReward(arduino)
                            reward_count += 1
                            trial_count += 1
                            print('{} Success : {} Time Out (Success in Last Trial)'.format(reward_count, fail_count))

                # If the animal dose not get a reward in a total trial period
                elif trial_period < time.time() - trial_start_time < trial_period + 5:

                    # Punish it for 5 seconds
                    if reward_condition_lock == 0:
                        fail_count += 1
                        print('{} Success : {} Time Out (Time Out in Last Trial)'.format(reward_count, fail_count))
                        time.sleep(5)

                # Trial failed
                else:
                    trial_count += 1
                    trial_start_time = time.time()
                    reward_condition_lock = 0

            # Write all trial results to file
            else:
                print('Total {} seconds task finished, waiting for release'.format(total_trial_time))
                f.writelines('threshold: ' + str(reward_threshold) + '\n')
                f.writelines('trial_period: ' + str(trial_period) + '\n')
                f.writelines('total_trial_time: ' + str(total_trial_time) + '\n')
                f.writelines('reward_count: ' + str(reward_count) + '\n')
                f.close()
                break

# Slide window sync thread
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


# Slide window will remove its old time stamp
class SlideWindowRemoveTimeStampThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        global program_start_time
        global slide_window
        while True:
            time.sleep(0.002)
            slide_window.remove_time_stamp()


# Receive signals from Arduino
class Listen2ArduinoThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        global reward_condition_lock
        global arduino
        global trial_start_time
        while True:
            time.sleep(0.002)

            # If the is ready for next trial
            if arduino.read_until(b','):
                reward_condition_lock = 0
                trial_start_time = time.time()


# Initialize trial time
trial_start_time = time.time()

# A lock to avoid conflict
reward_condition_lock = 0

###############Initial Settings##########
# Arduino serial port, you can know this from Arduino->Tools->Port
# It is usually 'COM3' in Windows and '/dev/cu.usbXXXX' in MacOS
serial_port = '/dev/cu.usbmodem1401'

# Baud rate between Arduino and PC
baud_rate = 115200
arduino = serial.Serial(serial_port, baud_rate)

# You can always choose a proper channel name by editing the following line
channel_name = 'c-069'

# Set a threshold
reward_threshold = 11

# Time for a trial
trial_period = 10

# Total training time
total_trial_time = 300

# Define the lowest and highest sound frequency for the mouse
low_frequency = 8000
high_frequency = 24000
#############End of Initial Settings#######

#############Execute the Program###########
program_start_time = time.time()
slide_window = SlideWindow(0, 200)

# Instantiate
main_trial_thread = MainTrialThread()
slide_window_sync_thread = SlideWindowSyncThread()
slide_window_remove_time_stamp_thread = SlideWindowRemoveTimeStampThread()
parse_neural_signal_thread = ParseNeuralSignalThread()
listen2arduino_thread = Listen2ArduinoThread()

# Start the program
slide_window_sync_thread.start()
slide_window_remove_time_stamp_thread.start()
parse_neural_signal_thread.start()
main_trial_thread.start()
listen2arduino_thread.start()
