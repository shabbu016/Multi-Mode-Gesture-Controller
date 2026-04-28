import cv2
import mediapipe as mp
import numpy as np
import time
import pyautogui
import screen_brightness_control as sbc
from ctypes import cast , POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

#------------------Gesture Functions----------------------
def get_fingers(handLms):
    fingers=[]

    #thumb
    fingers.append(handLms.landmark[4].x> handLms.landmark[3].x)

    #other finger
    tips = [8,12,16,20]
    bases = [6,10,14,18]

    for tip, base in zip(tips,bases):
        fingers.append(handLms.landmark[tip].y < handLms.landmark[base].y)
    return  fingers

def handle_gestures(fingers, last_action_time):
    action = "None"

    if time.time() - last_action_time > 1 :

        if not any(fingers):
            pyautogui.press('m')
            action="Mute"
            
        elif fingers == [False,True,False,False,False]:
            pyautogui.press('space')
            action = "Play/Pause"

        elif fingers ==  [False,True,True,False,False]:
            pyautogui.press('right')
            action = "Next"
        
        elif fingers == [False,False,True,False,False]:
            pyautogui.press('left')
            action = "Previous"
        
        elif all(fingers):
            pyautogui.press('f')
            action = "Fullscreen"

        last_action_time = time.time()
    return action, last_action_time

#------------------Volume Setup---------------------------#

devices = AudioUtilities.GetSpeakers()
interface = devices.Activate(
    IAudioEndpointVolume._iid_,
    CLSCTX_ALL,
    None
)
volume = cast(interface, POINTER(IAudioEndpointVolume))

#------------------Mediapipe setup------------------------

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    min_detection_confidence = 0.7,
    min_tracking_confidence = 0.7,
    max_num_hands = 1
)
mp_draw = mp.solutions.drawing_utils

#------------------Camera setup----------------------------

cap = cv2.VideoCapture(0,cv2.CAP_DSHOW)
cap.set(3,640)
cap.set(4,480)

for _ in range (10):
    cap.read()
if not cap.isOpened():
    print('Camera is not detected')
    exit()  

#---------------------Variables-------------------------------

prev_scalar = 0
last_update_time = 0

#gesture controlls

last_action_time = 0    
action_text = "None"

mode = "volume"
mode_candidate = None
mode_start_time = time.time()

#-------------------Main Loop-----------------------------

while True: 
    ret , frame = cap.read()
    if not ret:
        break
    frame = cv2.flip(frame,1)
    rgb = cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
    result = hands.process(rgb)

    current_scalar = volume.GetMasterVolumeLevelScalar()
    volume_percent = int (current_scalar * 100)

    if result.multi_hand_landmarks:
        for handLms in result.multi_hand_landmarks:
            mp_draw.draw_landmarks(frame,handLms, mp_hands.HAND_CONNECTIONS)

            fingers = get_fingers(handLms)

            #--------Mode Switching--------------------

            new_mode = mode

            if fingers[0] and fingers[4]: #thumb + pinky
                new_mode = "mouse"

            elif all(fingers):  #open hand
                new_mode = "volume"

            elif not any(fingers):  # fist
                new_mode = "media"

            #apply with delay
            if new_mode == mode_candidate:
                if time.time() -  mode_start_time>1:
                    mode = new_mode
            
            else:
                mode_candidate=new_mode
                mode_start_time=time.time()

            #-----------BLock while Switching--------------

            if new_mode != mode:
                cv2.putText(frame,"Switching....",(200,60),cv2.FONT_HERSHEY_SIMPLEX,0.8,(0,255,255),2)
                continue

            h,w, _ = frame.shape
            thumb = handLms.landmark[4]
            index = handLms.landmark[8]
            middle = handLms.landmark[12]

            # # -------- Mode Switching -------- #
            # if fingers[0] and fingers[4]:
            #   mode = "mouse"

            # elif all(fingers):
            #  mode = "volume"

            # elif not any(fingers):
            #  mode = "media"

            x1, y1 = int(thumb.x * w), int(thumb.y * h)
            # x2, y2 = int(thumb.x * w), int(thumb.y * h)
            x2, y2 = int(index.x * w), int(index.y * h)
            x3, y3 = int(middle.x * w), int(middle.y * h)


    #-----------------Mode Logic------------------------
            #volume + Brightness

            if mode ==  "volume":
                #volume
                distance = np.hypot(x2 - x1, y2 - y1)
                new_scalar = np.interp(distance,[20,200],[0.0,1.0])

                smoothed_scalar=0.85 * prev_scalar + 0.15 * new_scalar
                prev_scalar = smoothed_scalar

                volume.SetMasterVolumeLevelScalar(smoothed_scalar,None)

                #brightness
                brightness_distance = np.hypot(x3 - x1 , y3 - y1)
                brightness_level = np.interp(brightness_distance, [20,200],[0,100])
                sbc.set_brightness(int(brightness_level))

            # media mode
            elif mode == "media":
                action_text,last_action_time = handle_gestures(
                    fingers,last_action_time
                )
            
            #Mouse mode
            elif mode == "mouse":
                screen_w,screen_h = pyautogui.size()

                cursor_x = np.interp(index.x, [0,1],[0,screen_w])
                cursor_y = np.interp(index.y, [0,1],[0,screen_h])

                pyautogui.moveTo(cursor_x,cursor_y)

                #click
                click_distance = np.hypot(x2 - x1, y2 - y1)

                if click_distance < 30:
                    pyautogui.click()
                    time.sleep(0.3)
                
                #scroll
                if fingers[1] and fingers[2]:
                    pyautogui.scroll(20)

            cv2.circle(frame, (x1,y1), 10, (255,0,255),-1)
            cv2.circle(frame, (x2,y2), 10, (255,0,255),-1)
            cv2.line(frame, (x1,y1),(x2,y2), (255,0,255),2)

            distance = np.hypot(x2 - x1 , y2 - y1)
            new_scalar = np.interp(distance,[20,200],[0.0,1.0])

            smoothed_scalar = 0.85 * prev_scalar + 0.15 * new_scalar
            prev_scalar = smoothed_scalar

            current_time = time.time()
            if current_time - last_update_time>0.15:
                volume.SetMasterVolumeLevelScalar(smoothed_scalar, None)
                last_update_time = current_time

    #----------------------UI Bar-------------------------------------
    bar_x , bar_y = 50,100
    bar_height , bar_width = 300,30

    cv2.rectangle(frame, (bar_x,bar_y),(bar_x + bar_width, bar_y + bar_height), (60,60,60),2)

    fill_height = int(np.interp(volume_percent,[0,100],[0,bar_height]))
    cv2.rectangle(frame,(bar_x,bar_y + bar_height - fill_height),
                (bar_x + bar_width, bar_y + bar_height),(0,255,0),-1)
    cv2.putText(frame,f'{volume_percent}%', (40,450),cv2.FONT_HERSHEY_SIMPLEX,1, (0,255,0),2)
    cv2.putText(frame, f'Action: {action_text}',(40,420), cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255),2)
    cv2.putText(frame,f'Mode:{mode}',(10,30),cv2.FONT_HERSHEY_SIMPLEX,0.8,(0,255,255),2)
    cv2.putText(frame,'AI  Volume control',(150,40), cv2.FONT_HERSHEY_SIMPLEX,1, (255,255,255),2)
    cv2.imshow('Levlox Volume Control', frame)

    if cv2.waitKey(1) & 0xFF == 27:
        break

#-------------------CleanUp-----------------------------------------
cap.release()
cv2.destroyAllWindows()
