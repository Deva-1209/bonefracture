import numpy as np
import os
import tensorflow as tf
# from keras.preprocessing import image
from tensorflow.keras.preprocessing.image import load_img, img_to_array


# load the models when import "predictions.py"
model_elbow_frac = tf.keras.models.load_model("weights/ResNet50_Elbow_frac.h5")
model_hand_frac = tf.keras.models.load_model("weights/ResNet50_Hand_frac.h5")
model_shoulder_frac = tf.keras.models.load_model("weights/ResNet50_Shoulder_frac.h5")
model_parts = tf.keras.models.load_model("weights/ResNet50_BodyParts.h5")

# categories for each result by index

#   0-Elbow     1-Hand      2-Shoulder
categories_parts = ["Elbow", "Hand", "Shoulder"]

#   0-fractured     1-normal
categories_fracture = ['fractured', 'normal']


# get image and model name, the default model is "Parts"
# Parts - bone type predict model of 3 classes
# otherwise - fracture predict for each part
def predict(img, model="Parts"):
    size = 224
    supported_models = ['Parts', 'Elbow', 'Hand', 'Shoulder']
    if model not in supported_models:
        raise ValueError(f"Invalid model '{model}'. Choose from {supported_models}")

    if not os.path.exists(img):
        raise FileNotFoundError(f"Image file not found: {img}")

    if model == 'Parts':
        chosen_model = model_parts
    else:
        if model == 'Elbow':
            chosen_model = model_elbow_frac
        elif model == 'Hand':
            chosen_model = model_hand_frac
        elif model == 'Shoulder':
            chosen_model = model_shoulder_frac

    temp_img = load_img(img, target_size=(size, size))
    x = img_to_array(temp_img)
    x = np.expand_dims(x, axis=0)
    images = np.vstack([x])

    probabilities = chosen_model.predict(images)[0]
    prediction_index = np.argmax(probabilities)
    confidence = float(np.max(probabilities))

    if model == 'Parts':
        prediction_str = categories_parts[prediction_index]
    else:
        prediction_str = categories_fracture[prediction_index]

    print(f"[Prediction] Model: {model} | Result: {prediction_str} | Confidence: {confidence:.2%}")
    return prediction_str
