import requests
from web3 import Web3
from solcx import compile_standard, install_solc
import os
from flask import *
import logging
import sqlite3
from werkzeug.utils import secure_filename
import schedule
import time
import threading
from tensorflow.keras.preprocessing.image import load_img, img_to_array
import numpy as np
import tensorflow as tf

app = Flask(__name__)
app.secret_key = "secret key"

from nacl.utils import random
import nacl.bindings
import os




# Define the folder for uploaded images
UPLOAD_FOLDER = "static/uploads/"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}

# Load the pre-trained models
model_elbow_frac = tf.keras.models.load_model("../weights/ResNet50_Elbow_frac.h5")
model_hand_frac = tf.keras.models.load_model("../weights/ResNet50_Hand_frac.h5")
model_shoulder_frac = tf.keras.models.load_model("../weights/ResNet50_Shoulder_frac.h5")
model_parts = tf.keras.models.load_model("../weights/ResNet50_BodyParts.h5")

# Define categories
categories_parts = ["Elbow", "Hand", "Shoulder"]
categories_fracture = ["Fractured", "Normal"]


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def predict_bone_type(image_path):
    """Predict the body part of the uploaded image (Elbow, Hand, Shoulder)."""
    size = 224
    temp_img = load_img(image_path, target_size=(size, size))
    x = img_to_array(temp_img)
    x = np.expand_dims(x, axis=0)

    prediction = np.argmax(model_parts.predict(x), axis=1)
    return categories_parts[prediction.item()]


def predict_fracture(image_path, bone_type):
    """Predict whether the detected bone has a fracture or not."""
    size = 224
    temp_img = load_img(image_path, target_size=(size, size))
    x = img_to_array(temp_img)
    x = np.expand_dims(x, axis=0)

    if bone_type == "Elbow":
        model = model_elbow_frac
    elif bone_type == "Hand":
        model = model_hand_frac
    elif bone_type == "Shoulder":
        model = model_shoulder_frac
    else:
        return "Unknown"

    prediction = np.argmax(model.predict(x), axis=1)
    return categories_fracture[prediction.item()]


@app.route("/predict", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        if "file" not in request.files:
            return redirect(request.url)

        file = request.files["file"]
        if file.filename == "" or not allowed_file(file.filename):
            return redirect(request.url)

        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(file_path)

        # Predict bone type
        bone_type = predict_bone_type(file_path)
        # Predict fracture status
        fracture_status = predict_fracture(file_path, bone_type)

        return render_template("predict.html", filename=filename, bone_type=bone_type, result=fracture_status)

    return render_template("predict.html")

# Encrypt a single file using XChaCha20 (with Poly1305 for authentication)
def encrypt_file(filepath, key):
    nonce = random(24)  # 24-byte nonce for XChaCha20
    with open(filepath, 'rb') as f:
        plaintext = f.read()

    # Encrypt using XChaCha20 and Poly1305 (authenticated encryption)
    ciphertext = nacl.bindings.crypto_aead_xchacha20poly1305_ietf_encrypt(
        plaintext, b"", nonce, key
    )

    encrypted_filepath = filepath + '.enc'
    
    # Write nonce + ciphertext to the encrypted file
    with open(encrypted_filepath, 'wb') as f:
        f.write(nonce + ciphertext)  # Store nonce and ciphertext together
    
    print(f"Encrypted file saved to: {encrypted_filepath}")
    return encrypted_filepath

# Decrypt a single file using XChaCha20 (with Poly1305 for authentication)
def decrypt_file(encrypted_filename, key):
    with open(encrypted_filename, 'rb') as f:
        # Read the nonce (first 24 bytes) and the ciphertext
        nonce = f.read(24)  # The first 24 bytes are the nonce
        ciphertext = f.read()  # The rest is the ciphertext

    # Decrypt using XChaCha20 and Poly1305 (authenticated decryption)
    try:
        plaintext = nacl.bindings.crypto_aead_xchacha20poly1305_ietf_decrypt(
            ciphertext, b"", nonce, key
        )
    except Exception as e:
        print(f"Decryption failed: {str(e)}")
        return None

    decrypted_filename = encrypted_filename[:-4]  # Remove '.enc'
    
    with open("check"+decrypted_filename, 'wb') as f:
        f.write(plaintext)
    
    print(f"Decrypted file saved to: {decrypted_filename}")
    return decrypted_filename

logging.basicConfig(
    filename="app.log",  # Log file location
    level=logging.INFO,  # Log level (INFO, DEBUG, ERROR, etc.)
    format="%(asctime)s - %(levelname)s - %(message)s",  # Log format
    filemode='w'  # Overwrite log file on each start
)

def connect():
    return sqlite3.connect("user.db")
def get_log_content(log_file="app.log"):
    if not os.path.exists(log_file):
        logging.error(f"{log_file} does not exist.")
        return []

    # Read log file
    with open(log_file, "r") as file:
        log_lines = file.readlines()

    return log_lines
import os  # Required for path handling
import requests  # Required for making HTTP requests to the IPFS API

ipfs_api_url = "http://127.0.0.1:5001/api/v0"  # Your IPFS node API endpoint

def cloudupload(file_path):
    try:
        # Send a POST request to add the file to IPFS
        response = requests.post(
            f"{ipfs_api_url}/add", files={"file": open("static/upload/"+file_path, "rb")})
        if response.status_code == 200:
            json_response = response.json()
            print(json_response)
            # The file has been successfully uploaded to IPFS
            ipfs_hash = json_response["Hash"]
            print(ipfs_hash)
            return ipfs_hash
        else:
            print(
                f"Failed to upload file to IPFS. Status code: {response.status_code}")
            return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None
def upload_log_file():
    """Scheduled function to upload log file every 24 hours."""
    log_file = "app.log"  # Path to your log file
    ipfs_hash = cloudupload(log_file)
    contract("0xb433A3c33A3B67675c14D2ac1F495BEE3D576ff2", "0xbd8475490c560d9fdee4d511d36e83bf4fb3729f3eba0b8402c095c5c7afdd99", 0, 0, ipfs_hash)
    if ipfs_hash:
        print(f"Successfully uploaded and received IPFS hash: {ipfs_hash}")
    else:
        print("Failed to upload log file.")


def run_schedule():
    """Function to run the scheduler in a background thread."""
    while True:
        schedule.run_pending()
        time.sleep(60)  # Wait for 1 minute before checking again

def download_file(f, fileid):
    print(f, fileid)
 # The URL of the file you want to download
    # Replace with the actual API URL of your IPFS server
    url = "http://127.0.0.1:8080/ipfs/%s?filename=%s" % (fileid, fileid)
    # The local file path where you want to save the downloaded file
    response = requests.get(url)
    if response.status_code == 200:
        with open("static/download/download"+f, "wb") as file:
            file.write(response.content)
        print(f"File downloaded and saved to {f}")

def contract(address, key, fromid, toid, pid):

    import json

    install_solc("0.6.0")
    with open("./SimpleStorage.sol", "r") as file:
        simple_storage_file = file.read()

    compiled_sol = compile_standard(
        {
            "language": "Solidity",
            "sources": {"SimpleStorage.sol": {"content": simple_storage_file}},
            "settings": {
                "outputSelection": {
                    "*": {
                        "*": ["abi", "metadata", "evm.bytecode", "evm.bytecode.sourceMap"]
                    }
                }
            },
        },
        solc_version="0.6.0",
    )

    with open("compiled_code.json", "w") as file:
        json.dump(compiled_sol, file)

    bytecode = compiled_sol["contracts"]["SimpleStorage.sol"]["SimpleStorage"]["evm"][
        "bytecode"
    ]["object"]
    # get abi
    abi = json.loads(
        compiled_sol["contracts"]["SimpleStorage.sol"]["SimpleStorage"]["metadata"]
    )["output"]["abi"]

    import json

    w3 = Web3(Web3.HTTPProvider('HTTP://127.0.0.1:7545'))
    chain_id = 1337
    print(w3.is_connected())
    my_address = address
    private_key = key
    # initialize contract
    SimpleStorage = w3.eth.contract(abi=abi, bytecode=bytecode)
    nonce = w3.eth.get_transaction_count(my_address)
    # set up transaction from constructor which executes when firstly
    transaction = SimpleStorage.constructor().build_transaction(
        {"chainId": chain_id, "from": my_address, "nonce": nonce}
    )
    signed_tx = w3.eth.account.sign_transaction(
        transaction, private_key=private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print("Transacation completed")
    import datetime

    transaction_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tx_hash = "".join(["{:02X}".format(b)
                      for b in tx_receipt["transactionHash"]])
    c = connect()
    cursor = c.cursor()
    cursor.execute("select count(*) from transactions")
    d = cursor.fetchone()[0]+1
    c = connect()
    cursor = c.cursor()
    tx = "INSERT INTO transactions (id,hash, cdate,fromid,toid,fdid) VALUES ('%s','%s', '%s','%s','%s','%s')" % (
        d, str(tx_hash), transaction_date, fromid, toid, pid)

    cursor.execute(tx)
    c.commit()

    return tx_hash
# Define a route to view logs
@app.route('/loggfile')
def view_logs():
    log_lines = get_log_content()  # Read log lines
    html_content = """
    <html>
    <head>
        <title>Log Viewer</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f4f4f4; }
            h1 { color: #333; }
            pre { background-color: #fff; padding: 15px; border: 1px solid #ccc; white-space: pre-wrap; word-wrap: break-word; }
            .log-line { color: #555; }
            .error { color: red; }
            .info { color: blue; }
        </style>
    </head>
    <body>
      {%include "adminnav.html"%}
        <h1>Log Viewer</h1>
        <pre>
    """

    # Add log lines to the HTML content
    for line in log_lines:
        if "ERROR" in line:
            html_content += f'<span class="log-line error">{line}</span>'
        elif "INFO" in line:
            html_content += f'<span class="log-line info">{line}</span>'
        else:
            html_content += f'<span class="log-line">{line}</span>'
    
    html_content += """
        </pre>
    </body>
    </html>
    """
    
    return render_template_string(html_content)

@app.route('/')
def first():
    return render_template('first.html')


@app.route('/user')
def login():
    return render_template('index.html')


@app.route('/hospital')
def hospital():
    return render_template('hospitallogin.html')


@app.route('/admin')
def admin():
    return render_template('adminlogin.html')

@app.route("/adminlogin", methods=["POST"])
def adminlogin():
    mail1 = request.form['user']
    password1 = request.form['password']
    
    # Log the admin login attempt
    logging.info(f"Admin login attempt with email: {mail1}")
    
    if mail1 == "admin@gmail.com" and password1 == "1212":
        session['username'] = "admin"
        logging.info("Admin login successful")
        return redirect("viewuser")
    else:
        logging.warning(f"Failed admin login attempt with email: {mail1}")
        return render_template("adminlogin.html", error="Wrong username or password")


@app.route("/signin", methods=["POST"])
def signin():
    mail1 = request.form['user']
    password1 = request.form['password']
    
    # Log the user login attempt
    logging.info(f"User login attempt with email: {mail1}")
    
    con = connect()
    data = con.execute("SELECT usid, email, password, approve FROM user WHERE email=? AND password=?", 
                       (mail1, password1,)).fetchone()
    
    try:
        if data:  # Check if a record is returned
            if mail1 == str(data[1]) and password1 == str(data[2]):
                if data[3] == 0:
                    logging.warning(f"User login failed: {mail1} (User not approved)")
                    return render_template("index.html", error="User not approved")
                else:
                    session['username'] = data[0]
                    logging.info(f"User login successful: {mail1}")
                    return redirect("viewfile")
            else:
                logging.warning(f"Failed login attempt (incorrect password) for email: {mail1}")
                return render_template("index.html", error="Wrong username or password")
        else:
            logging.warning(f"Failed login attempt (no user found) for email: {mail1}")
            return render_template("index.html", error="Wrong username or password")
    except Exception as e:
        logging.exception(f"An error occurred during user login: {e}")
        return render_template("index.html", error="An error occurred, please try again later")


@app.route("/hospitallogin", methods=["POST"])
def hospitallogin():
    mail1 = request.form['user']
    password1 = request.form['password']
    
    # Log the hospital login attempt
    logging.info(f"Hospital login attempt with email: {mail1}")
    
    con = connect()
    data = con.execute("SELECT hid, email, password, approve FROM hospital WHERE email=? AND password=?", 
                       (mail1, password1,)).fetchone()
    
    try:
        if data:  # Check if a record is returned
            if mail1 == str(data[1]) and password1 == str(data[2]):
                if data[3] == 0:  # If the hospital is not approved
                    logging.warning(f"Hospital login failed: {mail1} (User not approved)")
                    return render_template("hospitallogin.html", error="User not approved")
                else:
                    session['username'] = data[0]
                    logging.info(f"Hospital login successful: {mail1}")
                    return redirect("viewfilehospital")
            else:
                logging.warning(f"Failed login attempt (incorrect password) for hospital: {mail1}")
                return render_template("hospitallogin.html", error="Wrong username or password")
        else:
            logging.warning(f"Failed login attempt (no hospital found) for email: {mail1}")
            return render_template("hospitallogin.html", error="Wrong username or password")
    except Exception as e:
        logging.exception(f"An error occurred during hospital login: {e}")
        return render_template("hospitallogin.html", error="An error occurred, please try again later")

@app.route('/insertuser1')
def insertuser1():
    return render_template('insertuser.html')


@app.route('/insertuser', methods=['POST'])
def insertuser():
    # Extract data from the form
    name = request.form['name']
    password = request.form['password']
    email = request.form['email']
    addresss = request.form['addresss']
    privatekey = request.form['privatekey']

    # Log the incoming data (except sensitive data like password and private key)
    logging.info(f"Insert user attempt with email: {email} and name: {name}")
    
    # Connect to SQLite database (or create it if it doesn't exist)
    conn = connect()
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT usid FROM user ORDER BY usid DESC LIMIT 1')
        usid = cursor.fetchone()[0] + 1
        logging.info(f"Generated new user ID: {usid}")
    except Exception as e:
        # If no users exist, start with usid = 1
        usid = 1
        logging.info("No users found, starting with user ID 1")

    # Insert data into the users table
    try:
        cursor.execute('''INSERT INTO user (usid, name, password, email, addresss, privatekey) 
                          VALUES (?, ?, ?, ?, ?, ?)''',
                       (usid, name, password, email, addresss, privatekey))
        # Commit the transaction
        conn.commit()
        logging.info(f"User {name} ({email}) inserted successfully with usid {usid}")

        cursor.close()
        conn.close()

        return redirect("insertuser1")
    except Exception as e:
        logging.error(f"Error inserting user {name} ({email}): {str(e)}")
        cursor.close()
        conn.close()
        return jsonify({'error': str(e)}), 400
@app.route('/viewuser')
def viewuser():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user")
    users = cursor.fetchall()
    logging.info(f"Fetched {len(users)} users from the database")
    conn.close()
    return render_template('viewuser.html', data=users, column=['usid', 'name', 'password', 'email', 'addresss', 'privatekey'])


@app.route('/deleteuser', methods=['POST', "GET"])
def deleteuser():
    a = request.args.get('a')
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user WHERE usid=?", [a])
    conn.commit()
    logging.info(f"User with usid {a} has been deleted from the database")
    conn.close()
    return redirect("viewuser")


@app.route('/updateuser1')
def updateuser1():
    usid = request.args.get('usid')
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user WHERE usid=?", [usid])
    n = cursor.fetchone()
    
    if n:
        logging.info(f"Fetching details for user with usid {usid}")
    else:
        logging.warning(f"User with usid {usid} not found")
    
    conn.close()
    return render_template('updateuser.html', n=n)


@app.route('/approveuser')
def approveuser():
    # Extract data from the form
    usid = request.args.get("a")
    
    # Connect to SQLite database (or create it if it doesn't exist)
    conn = connect()
    cursor = conn.cursor()

    try:
        cursor.execute('''UPDATE user SET approve=? WHERE usid=?''', (1, usid))
        conn.commit()
        logging.info(f"User with usid {usid} has been approved")

        cursor.execute('''SELECT * FROM user WHERE usid=?''', [usid])
        v = cursor.fetchone()
        # Assuming contract() is defined somewhere else
        contract(v[4], v[5], 0, usid, "")  # Example contract call
        logging.info(f"Contract function called for user with usid {usid}")
        
        cursor.close()
        conn.close()
        return redirect("viewuser")
    
    except Exception as e:
        logging.error(f"Error while approving user with usid {usid}: {str(e)}")
        return jsonify({'error': str(e)}), 400


@app.route('/approvehospital')
def approvehospital():
    # Extract data from the form
    usid = request.args.get("a")
    
    # Log the hospital approval attempt
    logging.info(f"Approving hospital with hid {usid}")
    
    # Connect to SQLite database (or create it if it doesn't exist)
    conn = connect()
    cursor = conn.cursor()

    # Insert data into the users table
    try:
        cursor.execute('''UPDATE hospital SET approve=? WHERE hid=?''', (1, usid))
        conn.commit()
        logging.info(f"Hospital with hid {usid} has been approved")

        cursor.execute('''SELECT * FROM hospital WHERE hid=?''', [usid])
        v = cursor.fetchone()
        
        # Assuming contract() is defined somewhere else
        contract(v[4], v[5], 0, usid, "")  # Example contract call
        logging.info(f"Contract function called for hospital with hid {usid}")
        
        cursor.close()
        conn.close()
        return redirect("viewhospital")
    
    except Exception as e:
        logging.error(f"Error while approving hospital with hid {usid}: {str(e)}")
        return jsonify({'error': str(e)}), 400


@app.route('/updateuser', methods=['POST'])
def updateuser():
    # Extract data from the form
    usid = request.form['usid']
    name = request.form['name']
    password = request.form['password']
    email = request.form['email']
    addresss = request.form['addresss']
    privatekey = request.form['privatekey']
    
    # Log the update attempt
    logging.info(f"Updating user with usid {usid}, name: {name}, email: {email}")

    # Connect to SQLite database (or create it if it doesn't exist)
    conn = connect()
    cursor = conn.cursor()

    try:
        cursor.execute('''UPDATE users SET name=?, password=?, email=?, addresss=?, privatekey=? WHERE usid=?''',
                       (name, password, email, addresss, privatekey, usid))
        conn.commit()
        logging.info(f"User with usid {usid} has been updated successfully")
        
        cursor.close()
        conn.close()
        return redirect("viewuser")
    except Exception as e:
        logging.error(f"Error while updating user with usid {usid}: {str(e)}")
        return jsonify({'error': str(e)}), 400


@app.route('/inserthospital1')
def inserthospital1():
    return render_template('inserthospital.html')


@app.route('/inserthospital', methods=['POST'])
def inserthospital():
    # Extract data from the form
    name = request.form['name']
    password = request.form['password']
    email = request.form['email']
    addresss = request.form['addresss']
    privatekey = request.form['privatekey']
    
    # Log the hospital insertion attempt
    logging.info(f"Inserting hospital with name {name}, email: {email}")

    # Connect to SQLite database (or create it if it doesn't exist)
    conn = connect()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT hid FROM hospital ORDER BY hid DESC LIMIT 1')
        hid = cursor.fetchone()[0] + 1
    except:
        hid = 1

    # Insert data into the hospital table
    try:
        cursor.execute('''INSERT INTO hospital (hid, name, password, email, addresss, privatekey) 
                          VALUES (?, ?, ?, ?, ?, ?)''',
                       (hid, name, password, email, addresss, privatekey))
        conn.commit()
        logging.info(f"Hospital with hid {hid} has been inserted successfully")
        cursor.close()
        conn.close()
        return redirect("inserthospital1")
    except Exception as e:
        logging.error(f"Error while inserting hospital: {str(e)}")
        return jsonify({'error': str(e)}), 400


@app.route('/viewhospital')
def viewhospital():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hospital")
    hospitals = cursor.fetchall()
    logging.info(f"Fetched {len(hospitals)} hospitals from the database")
    conn.close()
    return render_template('viewhospital.html', data=hospitals, column=['hid', 'name', 'password', 'email', 'addresss', 'privatekey'])


@app.route('/deletehospital', methods=['POST', "GET"])
def deletehospital():
    a = request.args.get('a')
    
    # Log the deletion attempt
    logging.info(f"Attempting to delete hospital with hid {a}")

    conn = connect()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM hospital WHERE hid=?", [a])
        conn.commit()
        logging.info(f"Hospital with hid {a} has been deleted from the database")
        conn.close()
        return redirect("viewhospital")
    except Exception as e:
        logging.error(f"Error while deleting hospital with hid {a}: {str(e)}")
        conn.close()
        return jsonify({'error': str(e)}), 400
@app.route('/updatehospital1')
def updatehospital1():
    hid = request.form.get('hid')
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hospital WHERE hid=?", [hid])
    n = cursor.fetchone()

    logging.info(f"Attempting to fetch hospital details for hid {hid}")
    return render_template('updatehospital.html', n=n)


@app.route('/updatehospital', methods=['POST'])
def updatehospital():
    # Extract data from the form
    hid = request.form['hid']
    name = request.form['name']
    password = request.form['password']
    email = request.form['email']
    addresss = request.form['addresss']
    privatekey = request.form['privatekey']

    # Log the update attempt
    logging.info(f"Attempting to update hospital with hid {hid}. New details: Name={name}, Email={email}")

    # Connect to SQLite database (or create it if it doesn't exist)
    conn = connect()
    cursor = conn.cursor()

    try:
        cursor.execute('''UPDATE hospital SET name=?, password=?, email=?, addresss=?, privatekey=? WHERE hid=?''',
                       (name, password, email, addresss, privatekey, hid))
        conn.commit()
        logging.info(f"Hospital with hid {hid} updated successfully")
        cursor.close()
        conn.close()
        return redirect("viewhospital")
    except Exception as e:
        logging.error(f"Error while updating hospital with hid {hid}: {str(e)}")
        return jsonify({'error': str(e)}), 400


@app.route('/insertfile1')
def insertfile1():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hospital")
    hospitals = cursor.fetchall()
    logging.info(f"Fetched {len(hospitals)} hospitals for file insertion")
    return render_template('insertfile.html', user=hospitals)


@app.route('/insertfile1hospital')
def insertfile1hospital():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user")
    users = cursor.fetchall()
    logging.info(f"Fetched {len(users)} users for hospital file insertion")
    return render_template('insertfilehospital.html', user=users)


@app.route('/insertfilehospital', methods=['POST'])
def insertfilehospital():
    # Extract data from the form
    usid = request.form['usid'].split("-")[0]
    hid = request.form['hid']
    fileshare = request.form['fileshare']

    logging.info(f"Inserting file for usid {usid}, hid {hid}, with fileshare {fileshare}")

    # Connect to SQLite database (or create it if it doesn't exist)
    conn = connect()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT fid FROM file ORDER BY fid DESC LIMIT 1')
        fid = cursor.fetchone()[0] + 1
    except:
        fid = 1

    # Insert data into the file table
    try:
        cursor.execute('''INSERT INTO file (fid, usid, hid, fileshare) VALUES (?, ?, ?, ?)''',
                       (fid, usid, hid, fileshare))
        conn.commit()
        logging.info(f"File with fid {fid} inserted successfully into the database")

        # Deleting files from the static/upload folder
        folder_path = "static/upload/"
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
                logging.info(f"Deleted file {filename} from upload folder")

        files = request.files.getlist('files')
        for file in files:
            if file.filename == '':
                logging.warning("No selected file")
                return 'No selected file'
            file.save('static/upload/' + file.filename)
            try:
                encrypt_file(file.filename)
            except:
                pass
            logging.info(f"File {file.filename} saved successfully")

            try:
                keys=cloudupload(file.filename)
                logging.info(f"Uploaded {file.filename} to cloud storage")
            except Exception as e:
                logging.error(f"Error uploading file {file.filename} to cloud storage: {str(e)}")

            cursor.execute('''SELECT * FROM user WHERE usid=?''', ([usid]))
            v = cursor.fetchone()
            print(keys)
            try:
                cursor.execute('SELECT fdid FROM filedetails ORDER BY fdid DESC LIMIT 1')
                fdid = cursor.fetchone()[0] + 1
            except:
                fdid = 1
            cursor.execute('''INSERT INTO filedetails (fdid, fid, filename,key) VALUES (?, ?, ?,?)''',
                           (fdid, fid, file.filename,keys))
            conn.commit()
            print(v[4], v[5], usid, hid, fdid)
            # Assuming the contract function works as expected
            contract(v[4], v[5], usid, hid, fdid)
            logging.info(f"Contract executed for file {file.filename} with fdid {fdid}")

        cursor.close()
        conn.close()
        return redirect("insertfile1hospital")
    except Exception as e:
        logging.error(f"Error while inserting file hospital: {str(e)}")
        return jsonify({'error': str(e)}), 400
@app.route('/insertfile', methods=['POST'])
def insertfile():
    # Extract data from the form
    usid = request.form['usid']
    hid = request.form['hid'].split("-")[0]
    fileshare = request.form['fileshare']

    logging.info(f"Attempting to insert file for usid {usid}, hid {hid}, fileshare {fileshare}")

    # Connect to SQLite database (or create it if it doesn't exist)
    conn = connect()
    cursor = conn.cursor()
    try:
        cursor.execute('select fid from file order by fid desc limit 1')
        fid = cursor.fetchone()[0]+1
    except:
        fid = 1

    try:
        # Insert data into the file table
        cursor.execute('''INSERT INTO file (fid, usid, hid, fileshare) VALUES (?, ?, ?, ?)''',
                       (fid, usid, hid, fileshare))
        conn.commit()

        logging.info(f"File with fid {fid} inserted successfully into the database")

        # Delete existing files from the upload folder
        folder_path = "static/upload/"
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
                logging.info(f"Deleted file {filename} from upload folder")

        # Process the uploaded files
        files = request.files.getlist('files')
        for file in files:
            if file.filename == '':
                logging.warning("No selected file")
                return 'No selected file'
            file.save('static/upload/' + file.filename)
            logging.info(f"File {file.filename} saved to the server")

            try:
                # Upload file to cloud storage
                keys=cloudupload(file.filename)
                logging.info(f"File {file.filename} uploaded to cloud storage successfully")
            except Exception as e:
                logging.error(f"Error uploading file {file.filename} to cloud storage: {str(e)}")

            cursor.execute('''SELECT * FROM user WHERE usid=?''', ([usid]))
            v = cursor.fetchone()

            try:
                cursor.execute('SELECT fdid FROM filedetails ORDER BY fdid DESC LIMIT 1')
                fdid = cursor.fetchone()[0]+1
            except:
                fdid = 1

            cursor.execute('''INSERT INTO filedetails (fdid, fid, filename,key) VALUES (?, ?, ?,?)''',
                           (fdid, fid, file.filename,keys))
            conn.commit()

            # Execute contract function (assumed to be defined elsewhere)
            contract(v[4], v[5], usid, hid, fdid)
            logging.info(f"Contract executed for file {file.filename} with fdid {fdid}")

        cursor.close()
        conn.close()
        return redirect("insertfile1")

    except Exception as e:
        logging.error(f"Error while inserting file for usid {usid}: {str(e)}")
        return jsonify({'error': str(e)}), 400


@app.route('/viewfile')
def viewfile():
    try:
        conn = connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM file WHERE usid='%s'" % (session["username"]))
        users = cursor.fetchall()

        logging.info(f"Fetched {len(users)} files for user {session['username']}")

        return render_template('viewfile.html', data=users, column=['fid', 'usid', 'hid', 'fileshare', 'trandate'])

    except Exception as e:
        logging.error(f"Error while fetching files for user {session['username']}: {str(e)}")
        return jsonify({'error': str(e)}), 400


@app.route('/viewfilehospital')
def viewfilehospital():
    try:
        conn = connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM file WHERE hid='%s'" % (session["username"]))
        users = cursor.fetchall()

        logging.info(f"Fetched {len(users)} files for hospital {session['username']}")

        return render_template('viewfilehospital.html', data=users, column=['fid', 'usid', 'hid', 'fileshare', 'trandate'])

    except Exception as e:
        logging.error(f"Error while fetching files for hospital {session['username']}: {str(e)}")
        return jsonify({'error': str(e)}), 400


@app.route('/deletefile', methods=['POST', "GET"])
def deletefile():
    try:
        a = request.args.get('a')
        conn = connect()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM file WHERE fid=?", [a])
        conn.commit()
        logging.info(f"File with fid {a} deleted successfully from database")
        return redirect("viewfile")

    except Exception as e:
        logging.error(f"Error while deleting file with fid {a}: {str(e)}")
        return jsonify({'error': str(e)}), 400


@app.route('/updatefile1')
def updatefile1():
    fid = request.form.get('fid')
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM fid WHERE fid=?", [fid])
    n = cursor.fetchone()

    logging.info(f"Fetching details for file with fid {fid}")

    return render_template('updatefile.html', n=n)


@app.route('/updatefile', methods=['POST'])
def updatefile():
    # Extract data from the form
    fid = request.form['fid']
    usid = request.form['usid']
    hid = request.form['hid']
    fileshare = request.form['fileshare']
    trandate = request.form['trandate']

    logging.info(f"Attempting to update file with fid {fid}, usid {usid}, hid {hid}, fileshare {fileshare}, trandate {trandate}")

    # Connect to SQLite database (or create it if it doesn't exist)
    conn = connect()
    cursor = conn.cursor()

    try:
        cursor.execute('''UPDATE users SET usid=?, hid=?, fileshare=?, trandate=? WHERE fid=?''',
                       (usid, hid, fileshare, trandate, fid))
        conn.commit()

        logging.info(f"File with fid {fid} updated successfully")

        cursor.close()
        conn.close()

        return redirect("viewfile")
    except Exception as e:
        logging.error(f"Error while updating file with fid {fid}: {str(e)}")
        return jsonify({'error': str(e)}), 400


@app.route('/insertfiledetails1')
def insertfiledetails1():
    logging.info("Rendering insertfiledetails form")

    return render_template('insertfiledetails.html')

@app.route('/insertfiledetails', methods=['POST'])
def insertfiledetails():
    # Extract data from the form
    fid = request.form['fid']
    filename = request.form['filename']

    logging.info(f"Attempting to insert file details for fid {fid}, filename {filename}")

    # Connect to SQLite database (or create it if it doesn't exist)
    conn = connect()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT fdid FROM filedetails ORDER BY fdid DESC LIMIT 1')
        fdid = cursor.fetchone()[0] + 1
    except:
        fdid = 1

    try:
        cursor.execute('''INSERT INTO filedetails (fdid, fid, filename) VALUES (?, ?, ?)''', (fdid, fid, filename))
        conn.commit()
        logging.info(f"File details inserted successfully for fid {fid}, filename {filename}")
        cursor.close()
        conn.close()

        return redirect("insertfiledetails1")
    except Exception as e:
        logging.error(f"Error inserting file details for fid {fid}, filename {filename}: {str(e)}")
        return jsonify({'error': str(e)}), 400


@app.route('/viewfiledetails')
def viewfiledetails():
    a = request.args.get("a")
    logging.info(f"Fetching file details for fid {a}")
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM filedetails WHERE fid='%s'" % (a))
    users = cursor.fetchall()
    return render_template('viewfiledetails.html', data=users, column=['fdid', 'fid', 'filename'])


@app.route('/viewfiledetailshospital')
def viewfiledetailsshospital():
    a = request.args.get("a")
    logging.info(f"Fetching file details for fid {a} for hospital view")
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM filedetails WHERE fid='%s'" % (a))
    users = cursor.fetchall()
    return render_template('viewfiledetailsshospital.html', data=users, column=['fdid', 'fid', 'filename'])


def download(b,a):
    logging.info(f"Attempting to download file with keyword {a}")
    download_file(b,a)
    logging.info(f"File {a} downloaded successfully")


@app.route('/downloadfilehospital')
def downloadfilehospital():
    a = request.args.get("a")
    b=request.args.get("b")
    download(b,a)
    x = "static/download/" + "download"+b
    try:
        decrypt_file(x)
    except:
        pass
    logging.info(f"File downloaded to {x} for hospital")
    return render_template('downloadfilehospital.html', file=x)


@app.route('/downloadfile')
def downloadfile():
    a = request.args.get("a")
    b=request.args.get("b")
    download(b,a)
    x = "static/download/" + "download"+b
    logging.info(f"File downloaded to {x}")
    return render_template('downloadfile.html', file=x)


@app.route('/deletefiledetails', methods=['POST', "GET"])
def deletefiledetails():
    a = request.args.get('a')
    logging.info(f"Attempting to delete file details for fdid {a}")
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM filedetails WHERE fdid=?", [a])
    conn.commit()
    conn.close()
    logging.info(f"File details with fdid {a} deleted successfully")
    return redirect("viewfiledetails")


@app.route('/updatefiledetails1')
def updatefiledetails1():
    fdid = request.form.get('fdid')
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM fdid WHERE fdid=?", [fdid])
    n = cursor.fetchone()
    logging.info(f"Rendering update form for file details with fdid {fdid}")
    return render_template('updatefiledetails.html', n=n)


@app.route('/updatefiledetails', methods=['POST'])
def updatefiledetails():
    # Extract data from the form
    fdid = request.form['fdid']
    fid = request.form['fid']
    filename = request.form['filename']

    logging.info(f"Attempting to update file details for fdid {fdid}, fid {fid}, filename {filename}")

    # Connect to SQLite database (or create it if it doesn't exist)
    conn = connect()
    cursor = conn.cursor()

    try:
        cursor.execute('''UPDATE users SET fid=?, filename=? WHERE fdid=?''', (fid, filename, fdid))
        conn.commit()
        logging.info(f"File details with fdid {fdid} updated successfully")
        cursor.close()
        conn.close()

        return redirect("viewfiledetails")
    except Exception as e:
        logging.error(f"Error updating file details for fdid {fdid}: {str(e)}")
        return jsonify({'error': str(e)}), 400


@app.route('/inserttransactions1')
def inserttransactions1():
    logging.info("Rendering insert transactions form")
    return render_template('inserttransactions.html')


@app.route('/inserttransactions', methods=['POST'])
def inserttransactions():
    # Extract data from the form
    hash = request.form['hash']
    cdate = request.form['cdate']
    fromid = request.form['fromid']
    toid = request.form['toid']
    fdid = request.form['fdid']

    logging.info(f"Attempting to insert transaction: hash={hash}, fromid={fromid}, toid={toid}, fdid={fdid}")

    # Connect to SQLite database (or create it if it doesn't exist)
    conn = connect()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id FROM transactions ORDER BY id DESC LIMIT 1')
        id = cursor.fetchone()[0] + 1
    except:
        id = 1

    # Insert data into the transactions table
    try:
        cursor.execute('''INSERT INTO transactions (id, hash, cdate, fromid, toid, fdid) VALUES (?, ?, ?, ?, ?, ?)''',
                       (id, hash, cdate, fromid, toid, fdid))
        conn.commit()
        logging.info(f"Transaction inserted successfully with ID {id}")
        cursor.close()
        conn.close()

        return redirect("inserttransactions1")
    except Exception as e:
        logging.error(f"Error inserting transaction: {str(e)}")
        return jsonify({'error': str(e)}), 400


@app.route('/viewtransactions')
def viewtransactions():
    logging.info("Fetching transactions to display")
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions")
    users = cursor.fetchall()
    return render_template('viewtransactions.html', data=users, column=['id', 'hash', 'cdate', 'fromid', 'toid', 'fdid'])


@app.route('/deletetransactions', methods=['POST', "GET"])
def deletetransactions():
    a = request.args.get('a')
    logging.info(f"Attempting to delete transaction with ID {a}")
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transactions WHERE id=?", [a])
    conn.commit()
    conn.close()
    logging.info(f"Transaction with ID {a} deleted successfully")
    return redirect("viewtransactions")


@app.route('/updatetransactions1')
def updatetransactions1():
    id = request.form.get('id')
    logging.info(f"Rendering update form for transaction with ID {id}")
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions WHERE id=?", [id])
    n = cursor.fetchone()

    return render_template('updatetransactions.html', n=n)


@app.route('/updatetransactions', methods=['POST'])
def updatetransactions():
    # Extract data from the form
    id = request.form['id']
    hash = request.form['hash']
    cdate = request.form['cdate']
    fromid = request.form['fromid']
    toid = request.form['toid']
    fdid = request.form['fdid']

    logging.info(f"Attempting to update transaction with ID {id}, new data: hash={hash}, cdate={cdate}, fromid={fromid}, toid={toid}, fdid={fdid}")

    # Connect to SQLite database (or create it if it doesn't exist)
    conn = connect()
    cursor = conn.cursor()

    try:
        cursor.execute('''UPDATE transactions SET hash=?, cdate=?, fromid=?, toid=?, fdid=? WHERE id=?''',
                       (hash, cdate, fromid, toid, fdid, id))
        conn.commit()
        logging.info(f"Transaction with ID {id} updated successfully")
        cursor.close()
        conn.close()

        return redirect("viewtransactions")
    except Exception as e:
        logging.error(f"Error updating transaction with ID {id}: {str(e)}")
        return jsonify({'error': str(e)}), 400


@app.route('/insertfileshare1')
def insertfileshare1():
    logging.info("Rendering insert file share form")
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM file WHERE usid='%s'" % (session["username"]))
    users = cursor.fetchall()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hospital")
    hospital = cursor.fetchall()
    return render_template('insertfileshare.html', user=users, hospital=hospital)


@app.route('/insertfileshare', methods=['POST'])
def insertfileshare():
    # Extract data from the form
    fid = request.form['fid'].split("-")[0]
    passwords = request.form['passwords']
    hid = request.form['hid'].split("-")[0]

    logging.info(f"Attempting to share file with fid {fid} to hospital with hid {hid}, passwords={passwords}")

    # Connect to SQLite database (or create it if it doesn't exist)
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM file WHERE fid='%s' AND hid='%s'" % (fid, hid))
    users = cursor.fetchone()
    if (users[0] == 0):
        cursor.execute("SELECT count(*) FROM fileshare WHERE fid='%s' AND hid='%s'" % (fid, hid))
        users = cursor.fetchone()
        if (users[0] == 0):
            cursor = conn.cursor()
            try:
                cursor.execute('SELECT fsid FROM fileshare ORDER BY fsid DESC LIMIT 1')
                fsid = cursor.fetchone()[0] + 1
            except:
                fsid = 1

            # Insert data into the fileshare table
            try:
                cursor.execute('''INSERT INTO fileshare (fsid, fid, passwords, hid) VALUES (?, ?, ?, ?)''',
                               (fsid, fid, passwords, hid))
                conn.commit()
                logging.info(f"File {fid} successfully shared with hospital {hid} using passwords {passwords}")

                cursor.execute('SELECT * FROM user WHERE usid=?', [session["username"]])
                v = cursor.fetchone()
                contract(v[4], v[5], session["username"], hid, fid)

                cursor.close()
                conn.close()
                return redirect("insertfileshare1")
            except Exception as e:
                logging.error(f"Error sharing file {fid} with hospital {hid}: {str(e)}")
                return jsonify({'error': str(e)}), 400
        else:
            logging.warning(f"File {fid} already shared with hospital {hid}")
            return render_template('insertfileshare.html', error="File already shared")
    else:
        logging.warning(f"File {fid} belongs to hospital {hid}, cannot share")
        return render_template('insertfileshare.html', error="File belongs to hospital")

@app.route('/viewfileshare')
def viewfileshare():
    logging.info(f"User {session['username']} is viewing file shares.")
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM fileshare WHERE fid IN (SELECT fid FROM file WHERE usid='%s')" % (session["username"]))
    users = cursor.fetchall()
    return render_template('viewfileshare.html', data=users, column=['fsid', 'fid', 'passwords', 'sharedate', 'hid'])


@app.route('/viewfilesharehospital')
def viewfilesharehospital():
    logging.info(f"User {session['username']} is viewing file shares in their hospital.")
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT fs.fsid, fs.fid, fs.sharedate, f.usid, fs.passwords FROM fileshare fs JOIN file f ON f.fid=fs.fid JOIN user u ON u.usid=f.usid WHERE fs.hid='%s'" % (session["username"]))
    users = cursor.fetchall()
    return render_template('viewfilesharehospital.html', data=users, column=['fsid', 'fid', 'sharedate', 'usid'])


@app.route('/deletefileshare', methods=['POST', "GET"])
def deletefileshare():
    fsid = request.args.get('a')
    logging.info(f"User {session['username']} is attempting to delete file share with fsid {fsid}.")
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM fileshare WHERE fsid=?", [fsid])
    conn.commit()
    conn.close()
    logging.info(f"File share with fsid {fsid} deleted successfully.")
    return redirect("viewfileshare")


@app.route('/updatefileshare1')
def updatefileshare1():
    fsid = request.form.get('fsid')
    logging.info(f"User {session['username']} is attempting to update file share with fsid {fsid}.")
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM fileshare WHERE fsid=?", [fsid])
    n = cursor.fetchone()
    return render_template('updatefileshare.html', n=n)


@app.route('/updatefileshare', methods=['POST'])
def updatefileshare():
    # Extract data from the form
    fsid = request.form['fsid']
    fid = request.form['fid']
    passwords = request.form['passwords']
    sharedate = request.form['sharedate']

    logging.info(f"User {session['username']} is updating file share with fsid {fsid}: fid={fid}, passwords={passwords}, sharedate={sharedate}")

    # Connect to SQLite database (or create it if it doesn't exist)
    conn = connect()
    cursor = conn.cursor()

    try:
        cursor.execute('''UPDATE fileshare SET fid=?, passwords=?, sharedate=? WHERE fsid=?''',
                       (fid, passwords, sharedate, fsid))
        conn.commit()
        logging.info(f"File share with fsid {fsid} updated successfully.")
        cursor.close()
        conn.close()

        return redirect("viewfileshare")
    except Exception as e:
        logging.error(f"Error updating file share with fsid {fsid}: {str(e)}")
        return jsonify({'error': str(e)}), 400


@app.route('/logout')
def logout():
    logging.info(f"User {session['username']} is logging out.")
    session.pop('username', None)
    return redirect("/")

if __name__ == '__main__':
    # Schedule the upload every 24 hours
    schedule.every(24).hours.do(upload_log_file)

    # Start the scheduling in a separate thread
    threading.Thread(target=run_schedule, daemon=True).start()
    app.run("0.0.0.0",debug=True)
