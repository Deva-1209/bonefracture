import os
from flask import Flask, request, render_template, redirect, url_for
from werkzeug.utils import secure_filename
from tensorflow.keras.preprocessing.image import load_img, img_to_array
import numpy as np
import tensorflow as tf

app = Flask(__name__)

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


@app.route("/", methods=["GET", "POST"])
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

        return render_template("index.html", filename=filename, bone_type=bone_type, result=fracture_status)

    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)
