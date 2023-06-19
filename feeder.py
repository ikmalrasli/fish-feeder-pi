from hx711 import HX711
import RPi.GPIO as GPIO
from firebase_admin import firestore
import time
import csv
from collections import deque
from datetime import time as datetime_time
from datetime import datetime, timedelta

def regEq(slope, t, firstdata):
    return slope * t + firstdata

def massEq(y_diff, CF):
    V_diff = (y_diff * 5) / (128 * 16777216)
    return V_diff / CF

def getrawdata(arr):
    arr.sort()  # Sort the array in ascending order
    min_diff = float('inf')  # Set initial minimum difference to infinity
    min_index = 0  # Initialize index of the minimum difference
    
    # Iterate through the array and find the minimum difference
    for i in range(len(arr) - 1):
        diff = arr[i+1] - arr[i]
        if diff < min_diff:
            min_diff = diff
            min_index = i
    
    # Calculate the average of the two closest numbers
    avg = (arr[min_index] + arr[min_index+1]) / 2
    return avg

def find_nearest_number(arr, number):
    nearestNumber = arr[0]
    minDifference = abs(arr[0] - number)

    for element in arr[1:]:
        difference = abs(element - number)
        if difference < minDifference:
            minDifference = difference
            nearestNumber = element

    return nearestNumber

def addtoOp(db, batch_ID, today_food, target_food, given_food, runtime, manual):
    feedrate = given_food/runtime
    percent_error = abs((given_food-target_food)/target_food)
    try:
        operation_ref = db.collection('operation').document()
        print('set')
        operation_ref.set({
            'batch_ID': batch_ID,
            'timestamp': firestore.SERVER_TIMESTAMP,
            'today_food': today_food,
            'target_food': target_food,
            'given_food': given_food,
            'runtime': runtime,
            'percent_error' : percent_error,
            'feedrate' : feedrate,
            'manual' : manual
        })
        print('set2')
    except:
        print('error set')
    print(f'feedOp: given {given_food}g of food within {runtime}s')

def get_target_food(db, today_food):
    todays_food = today_food
    given_food_array = []
    
    today = datetime.today()
    midnight = datetime.combine(today, datetime_time.min) - timedelta(hours=8)
    query = db.collection('operation').where('timestamp', '>=', midnight)
    results = query.get()
    for doc in results:
        given_food = doc.to_dict()['given_food']
        given_food_array.append(given_food)
        
    total_given_food = sum(given_food_array)
    print(f'total given : {total_given_food}')
    if total_given_food == 0:
        target_food = todays_food/2
    elif total_given_food >= todays_food:
        target_food = 0
        print("total given food exceed today's required food, no food given")
    else:
        target_food = todays_food - total_given_food
    
    return target_food

def feedOp(db, batch_ID, today_food, target_food, manual):
    if target_food > 0:
        cf = 0.00000134
        slope = -0.1556166666667
        m_desired = target_food
        feedrate = 0.8
        t_desired = m_desired / feedrate
        
        print(f"todays food= {today_food}g, feedOp mass = {m_desired}g")
        
        if not manual:
            status_ref = db.collection('status').document('feeder')
            status_ref.update({'active': True})

        # Initialize GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        in2 = 23
        in1 = 24
        en = 25
        GPIO.setup(in2, GPIO.OUT)
        GPIO.setup(in1, GPIO.OUT)
        GPIO.setup(en, GPIO.OUT)
        motor_pwm = GPIO.PWM(en, 500)
        hx = HX711(dout_pin=17, pd_sck_pin=27, gain=128, channel='A')
            
        # Tare load cell
        offset_valid = False
        
        while not offset_valid:
            print("Reset loadcell")
            result = hx.reset()
            if result:
                print('Loadcell ready')
                print('Finding offset value')
            
            correct_i_count = 0
            elapsed_time = 0
            v = hx.get_raw_data(3)
            firstdata = getrawdata(v)
            start_time = time.time()
            y_reg_i = regEq(slope, 0, firstdata)
            y_diff_i = y_reg_i - firstdata
            m_i = massEq(y_diff_i, cf)

            print(f't = 0, m_i = {m_i}g, firstdata = {firstdata}')

            # Testing firstdata
            i = 0
            while i <= 10:
                val = hx.get_raw_data()
                raw_value = getrawdata(val)
                elapsed_time = time.time() - start_time
                y_reg = regEq(slope, elapsed_time, firstdata)
                y_diff = y_reg - raw_value
                m = massEq(y_diff, cf)
                print(f't = {elapsed_time}, m_i = {m}g, y = {y_diff}')

                if -2 <= m <= 2:
                    correct_i_count += 1
                i += 1

            if correct_i_count >= 7:
                print('Offset value confirmed, start motor')
                offset_valid = True
            else:
                print("Invalid offset value. Retrying...")

        # Start motor
        GPIO.output(in2, GPIO.HIGH)
        GPIO.output(in1, GPIO.LOW)
        motor_pwm.start(50)
        print(f'time required: {t_desired} s')
        
        time.sleep(t_desired)

        # Stop motor
        GPIO.output(in2, GPIO.LOW)
        GPIO.output(in1, GPIO.LOW)
        motor_pwm.ChangeDutyCycle(0)
        status_ref = db.collection('status').document('feeder')
        status_ref.update({'active': False, 'm_desired':0})
        
        # Wait for 2s to stabilize the feeder
        time.sleep(2)

        # Get weight measurements
        m_array = []
        t = 0
        target_count=0
        while t <= 60:
            elapsed_time = time.time() - start_time
            val = hx.get_raw_data(3)
            raw_value = getrawdata(val)
            y_reg = regEq(slope, elapsed_time, firstdata)
            y_diff = y_reg - raw_value
            m = massEq(y_diff, cf)
            print(f't= {elapsed_time}, m= {m}g')
            m_array.append(m)                    
            time.sleep(1)
            t += 1
        
        m_avg = sum(m_array)/len(m_array)
        if m_avg > 0 and m_desired-15<=m_avg<= m_desired +15:
            m_final = m_avg
        else:
            m_final = find_nearest_number(m_array, m_desired)
        
        if m_final:
            addtoOp(db, batch_ID, today_food, m_desired, m_final, t_desired, manual)
            
        GPIO.cleanup()

def on_change(doc_snapshot, changes, read_time, db, batch_ID, today_food, manual):
    for change in changes:
        if change.type.name == 'ADDED' or change.type.name == 'MODIFIED':
            data = change.document.to_dict()
            active = data['active']
            m_d = data['m_desired']
            
            if active and m_d>0:
                feedOp(db, batch_ID, today_food, m_d, manual)
    
def listener(firebase_db, batch_ID, today_food, manual):
    global db
    db = firebase_db
    
    batch_collection_ref = db.collection('status').document('feeder')
    listener = batch_collection_ref.on_snapshot(lambda doc_snapshot, changes, read_time: on_change(doc_snapshot, changes, read_time, db, batch_ID, today_food, manual))

    # Keep the program running to continue receiving updates
    while True:
        pass