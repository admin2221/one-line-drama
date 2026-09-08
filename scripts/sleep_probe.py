import time
with open(r'D:/Comfyui/comfyui-drama/scripts/watchdog_heartbeat.txt','w') as f:
    f.write('alive '+str(int(time.time())))
time.sleep(120)
