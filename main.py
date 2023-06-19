import multiprocessing
import subprocess
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import schedule
import time
import batch
from batch import get_today_food
from batch import get_batchID
import feeder
from feeder import feedOp

# Initialize Firebase Admin SDK and Firestore database
cred = credentials.Certificate("./fish-feeder-firebase.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

def batch_listener():
    batch.listener(db)

def feeder_listener():  #manual feed
    feeder.listener(db, get_batchID(), get_today_food(), True)

def run_feedOp():   #auto feed
    target_food = feeder.get_target_food(db, get_today_food())
    feedOp(db, get_batchID(), get_today_food(), target_food, False)

# Create and start the listener process
b_listener = multiprocessing.Process(target=batch_listener)
b_listener.start()

m_listener = multiprocessing.Process(target=feeder_listener)
m_listener.start()

# Schedule the feeder to run every day at 8AM and 4PM
schedule.every().day.at("09:00").do(run_feedOp)
schedule.every().day.at("15:00").do(run_feedOp)


# Main loop to keep the program running
while True:
    schedule.run_pending()
    time.sleep(60)
    
