import tensorflow as tf
import numpy as np
from PIL import Image
import io

class AIService:
    def __init__(self):
        # Load models
        self.skin_type_model = tf.keras.models.load_model('./app/model/skinstype1.h5')
        self.skin_condition_model = tf.keras.models.load_model('./app/model/skinscondition.h5')
        
    def preprocess_image(self, image_bytes):
        # Membuka gambar
        img = Image.open(io.BytesIO(image_bytes))
        
        # Mengonversi gambar ke RGB jika dalam format RGBA
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Resize gambar sesuai input model
        img = img.resize((224, 224))
        
        # Mengubah gambar menjadi array numpy
        img = np.array(img)
        
        # Normalisasi gambar
        img = img / 255.0
        
        # Menambah dimensi batch
        img = np.expand_dims(img, axis=0)
        
        return img
        
    def process_image(self, image_bytes):
        try:
            processed_image = self.preprocess_image(image_bytes)
            
            # Get predictions
            skin_type_pred = self.skin_type_model.predict(processed_image)
            skin_condition_pred = self.skin_condition_model.predict(processed_image)
            
            # Process detailed results
            skin_types = ['dry', 'normal', 'oily']
            skin_conditions = ['acne', 'normal', 'redness', 'wrinkles']
            
            # Convert predictions to percentages
            skin_type_details = {
                skin_type: float(pred * 100) 
                for skin_type, pred in zip(skin_types, skin_type_pred[0])
            }
            
            skin_conditions_details = {
                condition: float(pred * 100)
                for condition, pred in zip(skin_conditions, skin_condition_pred[0])
            }
            
            # Get best skin type
            best_skin_type = max(skin_type_details.items(), key=lambda x: x[1])[0]
            
            return {
                'skin_type_details': skin_type_details,
                'skin_conditions_details': skin_conditions_details,
                'result_your_skinhealth': {
                    'skin_type': best_skin_type,
                    'skin_conditions': skin_conditions_details
                }
            }
            
        except Exception as e:
            raise Exception(f"Error processing image: {str(e)}")