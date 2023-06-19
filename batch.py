import firebase_admin
from firebase_admin import firestore
import json
from datetime import datetime, timezone

db = None

def get_today_food():
    with open('./current_batch_info.json', 'r') as json_file:
        doc = json.load(json_file)
        
        batch_ID = doc['ID']
        num_fish = doc['num_fish']
        start_age = doc['start_age']
        start_date = datetime.fromisoformat(doc['start_date']).replace(tzinfo=timezone.utc)
        k_constant = doc['k_constant']
        
        now = datetime.now(timezone.utc)
        
        time_diff = now - start_date
        
        current_age = start_age + time_diff.days
        today_food= (0.0232902*current_age*num_fish + 2.912*num_fish)*k_constant;
        
    return today_food

def get_batchID():
    with open('./current_batch_info.json', 'r') as json_file:
        doc = json.load(json_file)
        
        batch_ID = doc['ID']
        
    return batch_ID

# Define a callback function to handle document changes
def on_snapshot(doc_snapshot, changes, read_time):
    for change in changes:
        if change.type.name == 'ADDED' or change.type.name == 'MODIFIED' or change.type.name == 'REMOVED':
            # Perform the Firestore query
            query = db.collection('batch').where('current', '==', True)
            results = query.get()
            
            # Check if there is exactly one result
            if len(results) == 1:
                # Extract the desired fields from the document
                doc = results[0]
                name = doc.to_dict()['name']
                sd=doc.to_dict()['start_date'].isoformat()
                
                data = {
                    'current' : doc.to_dict()['current'],
                    'ID': doc.id,
                    'name' : doc.to_dict()['name'],
                    'num_fish' : doc.to_dict()['num_fish'],
                    'start_age' : doc.to_dict()['start_age'],
                    'start_date' : doc.to_dict()['start_date'].isoformat(),
                    'k_constant' : doc.to_dict()['k_constant']
                }
                json_data = json.dumps(data)
                with open("current_batch_info.json", "w") as json_file:
                    json_file.write(json_data)

                print(f"batch info saved, batch name: {name}.")
            else:
                print("batch info not found")

def listener(firebase_db):
    global db
    db = firebase_db
    
    # Create a listener for the 'batch' collection
    batch_collection_ref = db.collection('batch')
    listener = batch_collection_ref.on_snapshot(on_snapshot)

    # Keep the program running to continue receiving updates
    while True:
        pass


