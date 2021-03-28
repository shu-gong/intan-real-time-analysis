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

# Buzzer frequency transformation
def spike2sound(theSlideWindowBear,theArduino,theLowerLimit,theHigherLimit,theThreshold):

    numTimeStamp = theSlideWindowBear.talk()
    #theDifference = theHigherLimit - theLowerLimit
    #theDiffGap = theDifference / theThreshold
    #soundFrequency = numTimeStamp * theDiffGap

    theBase = theHigherLimit / theLowerLimit
    if numTimeStamp < theThreshold:
        soundFrequency = theLowerLimit * (theBase**(numTimeStamp/theThreshold))
    else:
        soundFrequency = theHigherLimit

    gap = 500000 / soundFrequency
    theArduino.write((str(gap)+',').encode())
    return numTimeStamp


# Reward function
def giveReward(theArduino):
    theArduino.write(b'314159265354,')


class SlideWindowBear():
    def __init__(self, left_hand, right_hand):
        self.left_hand = left_hand
        self.right_hand = right_hand
        self.num_time_stamp = 0
        self.num_last_time_stamp = 0
        self.time_stamp_list = []
        self.sound_fre = 10
        self.slide_window = right_hand * 20
        self.potential_threshold = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15]
        self.sample_points = [[] for _ in range(len(self.potential_threshold))]
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

class MainTrialThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
    def run(self):
        global reward_threshold
        global serial_port
        global slide_window_bear
        global arduino
        global total_trial_time
        global trial_period
        global trial_start_time
        global reward_condition_lock

        fail_count = 0
        reward_count = 0
        trial_count = 0
        f = open('./reward_count' + str(time.strftime("%m-%d", time.localtime())) + '.txt', 'w')
        trial_start_time = time.time()
        while True:
            time.sleep(0.01)
            if time.time() - program_start_time < total_trial_time:

                if time.time() - trial_start_time <= trial_period:
                    current_num_time_stamp = spike2sound(slide_window_bear, arduino, low_frequency, high_frequency, reward_threshold)
                    if reward_condition_lock == 0:
                        if current_num_time_stamp >= reward_threshold:
                            reward_condition_lock = 1
                            f.writelines('invoke times + 1 ' + str(time.time()- program_start_time) +'\n')
                            giveReward(arduino)
                            reward_count += 1
                            trial_count += 1
                            print('{} Success : {} Time Out (Success in Last Trial)'.format(reward_count, fail_count))


                elif time.time() - trial_start_time > trial_period and \
                        time.time() - trial_start_time < trial_period + 5:
                    if reward_condition_lock == 0:
                        fail_count += 1
                        print('{} Success : {} Time Out (Time Out in Last Trial)'.format(reward_count,fail_count))
                        time.sleep(5)


                # Trial failed
                else:
                    trial_count += 1
                    trial_start_time = time.time()
                    reward_condition_lock = 0

            else:
                print('Total {} seconds task finished, waiting for release'.format(total_trial_time))
                f.writelines('threshold: '+str(reward_threshold)+'\n')
                f.writelines('trial_period: '+str(trial_period)+'\n')
                f.writelines('total_trial_time: '+str(total_trial_time)+'\n')
                f.writelines('reward_count: '+str(reward_count)+'\n')
                f.close()
                break

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

class Listen2ArduinoThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        global reward_condition_lock
        global arduino
        global trial_start_time
        while True:
            time.sleep(0.002)
            if arduino.read_until(b','):
                reward_condition_lock = 0
                trial_start_time = time.time()

trial_start_time = time.time()
reward_condition_lock = 0

###############Initial Settings##########
serial_port = '/dev/cu.usbmodem1401'
baud_rate = 115200
channel_name = 'c-069'
arduino = serial.Serial(serial_port, baud_rate)

reward_threshold = 10
trial_period = 10
total_trial_time = 300

# Define the lowest and highest sound frequency for the mouse
low_frequency = 8000
high_frequency = 24000
#############End of Initial Settings#######

#############Execute the Program###########
program_start_time = time.time()
slide_window_bear = SlideWindowBear(0, 200)


main_trial_thread = MainTrialThread()
bear_move_thread = BearMoveThread()
bear_clean_thread = BearCleanThread()
food_collect_thread = FoodCollectThread()
listen2arduino_thread = Listen2ArduinoThread()

bear_move_thread.start()
bear_clean_thread.start()
food_collect_thread.start()
main_trial_thread.start()
listen2arduino_thread.start()