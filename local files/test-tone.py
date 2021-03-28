import time
with open('./'+str(time.strftime("%m-%d", time.localtime()))+'.txt','w') as f:
    f.writelines('111\n')
    f.writelines('222')
