from __future__ import print_function # WalabotAPI works on both Python 2 and 3.
from sys import platform, exit
from os import system, name
from imp import load_source
from math import sin, cos, radians, sqrt # used to calculate MAX_Y_VALUE fixmewhatfor?
import time
import pika

R_MIN, R_MAX, R_RES = 30, 300, 8 # walabot SetArenaR parameters
THETA_MIN, THETA_MAX, THETA_RES = -20, 0, 5 # walabot SetArenaTheta parameters
PHI_MIN, PHI_MAX, PHI_RES = -60, 60, 5 # walabot SetArenaPhi parametes
MAX_Y_VALUE = R_MAX * cos(radians(THETA_MAX)) * sin(radians(PHI_MAX))

THRESHOLD = 15 # walabot SetThreshold parameter
TARGET_THRESHOLD = 0.002 # min amplitude for detected target to be valid

TRIGGER_INTERVAL = 1 # seconds
HYSTERESIS = 25 # num intervals with same result before changing state

credentials = pika.PlainCredentials('pi', 'raspberry')
connection = pika.BlockingConnection(pika.ConnectionParameters('raspberrypi.local',
                                                                5672,
                                                                '/',
                                                                credentials))
channel = connection.channel()
channel.queue_declare(queue='hello')

def distance(target):
  return sqrt(target.xPosCm**2 + target.yPosCm**2 + target.zPosCm**2)

def init():
  global wlbt
  if (name=='nt'): # os is windows
    wlbt = load_source('WalabotAPI','C:/Program Files/Walabot/WalabotSDK/python/WalabotAPI.py')
  elif (name=='posix'): #os is linux
    wlbt = load_source('WalabotAPI','/usr/share/walabot/python/WalabotAPI.py')

  wlbt.Init()
  wlbt.SetSettingsFolder()

  while True:
    try:
      print("- Looking for Walabot Device")
      wlbt.ConnectAny()
      break
    except wlbt.WalabotError as err:
      if err.message == 'WALABOT_INSTRUMENT_NOT_FOUND':
        raw_input("-- Connect Walabot and press 'Enter'.")
      else:
        print('error message: ' + err.message)
        return False

  wlbt.SetProfile(wlbt.PROF_SENSOR)
  wlbt.SetArenaR(R_MIN, R_MAX, R_RES)
  wlbt.SetArenaTheta(THETA_MIN, THETA_MAX, THETA_RES)
  wlbt.SetArenaPhi(PHI_MIN, PHI_MAX, PHI_RES)
  wlbt.SetThreshold(THRESHOLD)
  wlbt.SetDynamicImageFilter(wlbt.FILTER_TYPE_NONE)
  print('- Walabot Configurated.')
  return True

def calibrate():
  wlbt.Start()
  wlbt.StartCalibration()
  print('- Calibrating...')
  while wlbt.GetStatus()[0] == wlbt.STATUS_CALIBRATING:
    wlbt.Trigger()
  print('- Calibration ended.\n- Ready!')

if(not init()):
  exit()

calibrate()

valid_targets = 0
no_target_count = 0

awake = True
prevState = 'awake'
currState = 'awake'
currStateCount = 0

while True:
  try:
    wlbt.Trigger()
    ener = wlbt.GetImageEnergy()
    #print("energy: ", ener)
    targets = wlbt.GetSensorTargets()
  except wlbt.WalabotError as err:
    print("error ", err.message)

  if targets:
    for target in targets:
      if (target.amplitude > TARGET_THRESHOLD):
        #print("target amplitude ", target.amplitude)
        valid_targets += 1

    if (valid_targets > 0):
      currState = 'asleep'
      nearest_target = min(targets, key=lambda t: distance(t))
      #print("num valid targets: ", valid_targets, "nearest target distance ", distance(nearest_target))
      valid_targets = 0
      # Trigger once without checking the results: This avoids double-triggering
      # as a shadow-signal appears behind a signal that has just vanished.
      wlbt.Trigger()
    else:
      #print('no valid targets')
      currState = 'awake'
  else:
    print('no targets')
    currState = 'awake'
    no_target_count += 1
    # if (no_target_count > 10):
    #   break

  if (currState == prevState):
    currStateCount = currStateCount + 1
    #print("currStateCount = " + str(currStateCount))
  else:
    prevState = currState
    currStateCount = 0
    #print("currStateCount = " + str(currStateCount))

  if (currStateCount > HYSTERESIS):
    currStateCount = 0
    #print("currStateCount = " + str(currStateCount))
    if (currState == 'awake'):
      awake = True
    else:
      awake = False

  if (awake == True):
    print("State: AWAKE, currState: " + currState )
  else:
    print("State: ASLEEP, currState: " + currState)

  channel.basic_publish(exchange='',
                      routing_key='hello',
                      body=str(awake))


  time.sleep(TRIGGER_INTERVAL)
