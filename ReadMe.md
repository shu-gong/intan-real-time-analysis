###### This program can be used to train your mouse. 

**mouse_reward.py:** It consists of demo codes of parsing neural signals from Intan Recorder and transform these signals into sound frequency. This program can also sent signals to an Arduino to control a water pump or any other rewarding system. To run it, you need to activate the Intan network port. Go to Intan->Network and click all bottons  'connect'. Then go to the folder where the program is and type 'python mouse_reward.py' in a Terminal or Command Line of a computer.

For example:

```shell
cd C://user/zhao/Desktop/mouse_reward_system/
python mouse_reward.py
```

**find_threshold_algorithm.py:** It can be used to find the best threshold (i.e., the threshold that is triggered in a particular percentage in animal's spontanuous activities). To run it, you also need to activate Intan network port first as mentioned in mouse_reward.py.

**sound_and_reward.ino:** Upload this program to an Arduino board so it can be used to control the water pump or other rewarding devices.