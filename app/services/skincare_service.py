from google.cloud import firestore
import traceback
import os
from dotenv import load_dotenv

load_dotenv()

class SkincareService:
    def __init__(self):
        key_path = os.getenv('GCP_FIRESTORE_KEY_PATH')
        
        if not key_path:
            self.db = firestore.Client()
        else:
            self.db = firestore.Client.from_service_account_json(key_path)
        
    def get_skincare_products(self):
        products_ref = self.db.collection('products')
        docs = products_ref.stream()
        return [doc.to_dict() for doc in docs]
    
    def get_thresholds(self):
        threshold_ref = self.db.collection('thresholds')
        skin_types = threshold_ref.document('skin_types').get()
        skin_conditions = threshold_ref.document('skin_conditions').get()
        
        return {
            'skin_types': skin_types.to_dict(),
            'skin_conditions': skin_conditions.to_dict()
        }
    
    def get_recommendations(self, skin_analysis):
        try:
            products_ref = self.db.collection('products')
            skincare_routine = {
                'facial_wash': [],
                'toner': [],
                'serum': [],
                'moisturizer': [],
                'sunscreen': [],
                'eye_cream': [],
                'mask': [],
                'acne_spot': []
            }

            if skin_analysis.get('skin_type'):
                skin_type = skin_analysis['skin_type'].lower()
                print(f"Processing skin type: {skin_type}")
                
                # A. Basic Routine
                basic_products = ['facial_wash', 'toner', 'serum', 'moisturizer', 'sunscreen']
                for product_type in basic_products:
                    print(f"\nSearching for basic product: {product_type}")
                    
                    query = products_ref.where("type", "==", product_type)\
                                       .where(f"skin_types.{skin_type}", "==", True)
                    
                    products = list(query.get())
                    print(f"Found {len(products)} products for {product_type}")
                    
                    if not products:
                        print(f"No specific products found for {skin_type} skin, trying normal skin products")
                        query = products_ref.where("type", "==", product_type)\
                                           .where("skin_types.normal", "==", True)
                        products = list(query.get())
                        print(f"Found {len(products)} normal skin products for {product_type}")
                    
                    for product in products:
                        product_data = product.to_dict()
                        product_data['product_id'] = product.id
                        skincare_routine[product_type].append(product_data)

                # B. Additional Care
                additional_products = ['eye_cream', 'mask', 'acne_spot']
                skin_conditions = {
                    'acne': skin_analysis.get('skin_conditions', {}).get('acne', 0),
                    'redness': skin_analysis.get('skin_conditions', {}).get('redness', 0),
                    'wrinkles': skin_analysis.get('skin_conditions', {}).get('wrinkles', 0)
                }

                thresholds = self.get_thresholds()

                for product_type in additional_products:
                    print(f"\nSearching for additional product: {product_type}")
                    
                    conditions_over_threshold = []
                    for condition, value in skin_conditions.items():
                        if value is not None and condition in thresholds['skin_conditions']:
                            threshold = thresholds['skin_conditions'][condition]
                            if float(value) >= threshold:
                                conditions_over_threshold.append(condition)

                    if conditions_over_threshold:
                        query = products_ref.where("type", "==", product_type)
                        products = list(query.get())
                        
                        for product in products:
                            product_data = product.to_dict()
                            product_data['product_id'] = product.id
                            if any(product_data.get('skin_conditions', {}).get(condition, False) 
                                  for condition in conditions_over_threshold):
                                skincare_routine[product_type].append(product_data)

                # Format hasil rekomendasi
                routine_result = {
                    'basic_routine': {
                        'facial_wash': skincare_routine['facial_wash'],
                        'toner': skincare_routine['toner'],
                        'serum': skincare_routine['serum'],
                        'moisturizer': skincare_routine['moisturizer'],
                        'sunscreen': skincare_routine['sunscreen']
                    },
                    'additional_care': {
                        'eye_cream': skincare_routine['eye_cream'],
                        'mask': skincare_routine['mask'],
                        'acne_spot': skincare_routine['acne_spot']
                    },
                    'notes': []
                }

                # C. Tambahkan catatan berdasarkan kondisi
                for condition, value in skin_conditions.items():
                    if value is not None and float(value) >= thresholds['skin_conditions'].get(condition, 0):
                        routine_result['notes'].append(f"Disarankan menggunakan produk khusus untuk mengatasi {condition}")

                return routine_result

        except Exception as e:
            print(f"Error getting recommendations: {e}")
            print("Full error:", traceback.format_exc())
            raise Exception(f"Failed to get recommendations: {str(e)}")