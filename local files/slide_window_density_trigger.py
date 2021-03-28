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
    print('current frequency', soundFrequency)
    theArduino.write((str(gap)+',').encode())
    return numTimeStamp


# Reward function
def giveReward(theArduino):
    global reward_count
    theArduino.write(b'314159265354,')
    reward_count += 1


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


class FindThresholdThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
    def run(self):
        global slide_window_bear
        global program_start_time
        global calibrate_time
        global reward_threshold
        temp_percent = [0.0] * len(slide_window_bear.potential_threshold)
        temp_abs = [0.0] * len(slide_window_bear.potential_threshold)
        if calibrate_time != 0:
            condition_lock.acquire()
            while True:
                time.sleep(0.001)
                print('Calibration time left: ',int(calibrate_time - (time.time()-program_start_time)))
                if time.time() - program_start_time < calibrate_time:
                    for i in range(len(slide_window_bear.potential_threshold)):
                        if slide_window_bear.talk() > slide_window_bear.potential_threshold[i]:
                            slide_window_bear.sample_points[i].append(time.time() - program_start_time)
                else:

                    for i in range(len(slide_window_bear.potential_threshold)):
                        for j in range(len(slide_window_bear.sample_points[i])):
                            slide_window_bear.time_above_threshold[i] = 0.001 * len(slide_window_bear.sample_points[i])

                    # Calculate percentage
                    for i in range(len(slide_window_bear.potential_threshold)):
                            temp_percent[i] = slide_window_bear.time_above_threshold[i] / calibrate_time

                    print('*'*89)
                    print('Calibration is over')
                    print(slide_window_bear.time_above_threshold)
                    print(temp_percent)
                    for i in range(len(slide_window_bear.potential_threshold)):
                        temp_abs[i] = abs(float(temp_percent[i]) - baseline)
                    threshold_index = temp_abs.index(min(temp_abs))
                    reward_threshold = slide_window_bear.potential_threshold[threshold_index]

                    print('Threshold set to {}, account for {}'.format(reward_threshold, temp_percent[threshold_index]))
                    condition_lock.release()
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
        global reward_threshold
        global serial_port
        global slide_window_bear
        global total_test_time
        global reward_count
        global arduino
        global reward_condition_lock

        if condition_lock.acquire():
            f = open('./reward_count' + str(time.strftime("%m-%d", time.localtime())) + '.txt', 'w')
            while True:
                time.sleep(0.01)
                if time.time() - program_start_time < total_test_time:
                    current_num_time_stamp = spike2sound(slide_window_bear, arduino, low_frequency, high_frequency, reward_threshold)
                    if current_num_time_stamp >= reward_threshold:
                        if reward_condition_lock == 0:
                            reward_condition_lock = 1
                            f.writelines('invoke times + 1 ' + str(time.time()- program_start_time) +'\n')
                            giveReward(arduino)

                else:
                    f.writelines('threshold: '+str(reward_threshold)+'\n')
                    f.writelines('total_test_time: '+str(total_test_time)+'\n')
                    f.writelines('reward_count: '+str(reward_count)+'\n')
                    f.close()
                    break
            condition_lock.release()


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
        while True:
            time.sleep(0.002)
            if arduino.read_until(b','):
                reward_condition_lock = 0


# The following variables should never be changed
reward_count = 0

###############Initial Settings##########
serial_port = '/dev/cu.usbmodem11401'
baud_rate = 115200
channel_name = 'd-024'
arduino = serial.Serial(serial_port, baud_rate)
# Automatic mode: set calibrate_time to !0, reward_threshold to 9999
# Manual mode: set calibrate_time to 0, reward_threshold to 'threshold you want'
calibrate_time = 0
reward_threshold = 4
total_test_time = 30
# Define the lowest and highest sound frequency for the mouse
low_frequency = 8000
high_frequency = 24000
baseline = 0.2
#############End of Initial Settings#######

#############Execute the Program###########
program_start_time = time.time()
slide_window_bear = SlideWindowBear(0, 200)

condition_lock = threading.Condition()
reward_condition_lock = 0

find_threshold_thread = FindThresholdThread()
sound_playing_thread = SoundPlayingThread()
bear_move_thread = BearMoveThread()
bear_clean_thread = BearCleanThread()
food_collect_thread = FoodCollectThread()
listen2arduino_thread = Listen2ArduinoThread()

find_threshold_thread.start()
bear_move_thread.start()
bear_clean_thread.start()
food_collect_thread.start()
sound_playing_thread.start()
listen2arduino_thread.start()