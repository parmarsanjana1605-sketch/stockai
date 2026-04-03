import numpy as np
from tensorflow.keras.models import load_model
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

lstm_path = os.path.join(BASE_DIR, "model_ml", "lstm_model.h5")

model = load_model(lstm_path)

def predict(data):
    data = np.array(data)
    data = data.reshape(1, -1, 1)
    
    result = model.predict(data)
    return result[0][0]