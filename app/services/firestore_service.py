from google.cloud import firestore
from datetime import datetime
import os
from dotenv import load_dotenv
import bcrypt

load_dotenv()

class FirestoreService:
    def __init__(self):
        key_path = os.getenv('GCP_FIRESTORE_KEY_PATH')
        self.collection_name = os.getenv('COLLECTION_NAME')
        
        if not key_path:
            # For Cloud Run, use default credentials
            self.db = firestore.Client()
        else:
            # For local development
            self.db = firestore.Client.from_service_account_json(key_path)
            
        self.collection = self.db.collection(self.collection_name)

    def register_document(self, user_id: str, nama: str, email: str, password: str):
        try:
            user_ref = self.collection.document(user_id)
            
            # Check if user already exists first
            if user_ref.get().exists:
                raise ValueError("Error, user_id sudah terdaftar")
            
            # Then validate password
            if len(password) < 8:
                raise ValueError("Password harus minimal 8 karakter")
            
            # Hash the password
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

            # Create base user data
            user_data = {
                "user_id": user_id,
                'nama': nama,
                'email': email,
                'password': hashed_password.decode('utf-8'), 
                'profile_url': None,
                'createdAt': datetime.now()
            }
            user_ref.set(user_data)

            # Create image structure
            image_ref = user_ref.collection('image')
            weeks = ['pekan0', 'pekan1', 'pekan2', 'pekan3', 'pekan4']
            
            for week in weeks:
                week_ref = image_ref.document(week)
                week_data = {
                    'tipe_kulit': None,
                    'acne': None,
                    'redness': None,
                    'wrinkles': None,
                    'score': None,
                    'createdAt': None,
                    'public_url': None
                }
                week_ref.set(week_data)
        except Exception as e:
            print(f"Error registering user: {str(e)}")
            raise

    def update_image_data(self, user_id: str, week: str, public_url: str):
        user_ref = self.collection.document(user_id)
        week_ref = user_ref.collection('image').document(week)
        
        week_ref.update({
            'createdAt': datetime.now(),
            'public_url': public_url
        })

    # tambahkan update hasil data model pada firestore disini seperti fungsi update image
    def delete_image_data(self, user_id: str, week: str):
        user_ref = self.collection.document(user_id)
        week_ref = user_ref.collection('image').document(week)
        
        if week_ref.get().exists:
        # Reset semua field ke None
            reset_data = {
                'tipe_kulit': None,
                'acne': None,
                'redness': None,
                'wrinkles': None,
                'normal': None,
                'darkspots': None,
                'score': None,
                'createdAt': None,
                'public_url': None
            }
            week_ref.update(reset_data)
            return True
        else:
            return False
        
    def get_skin_analysis_data(self, user_id: str, week: str):
        try:
            user_ref = self.collection.document(user_id)
            week_ref = user_ref.collection('image').document(week)
            
            doc = week_ref.get()
            if not doc.exists:
                return None
            
            data = doc.to_dict()
            
            # Siapkan progress data jika ini pekan4
            progress_data = {}
            if week == 'pekan4':
                score = data.get('score')
                if score is not None:
                    progress_data = {
                        "percentage": score,
                        "message": self.get_progress_message(score)
                    }

            # Format response
            response = {
                "public_url": data.get('public_url'),
                "result_your_skinhealth": {
                    "skin_type": data.get('tipe_kulit'),
                    "skin_conditions": {
                        "acne": data.get('acne'),
                        "normal": data.get('normal'),
                        "redness": data.get('redness'),
                        "wrinkles": data.get('wrinkles')
                    }
                },
                "progress": progress_data if week == 'pekan4' else {},
                "recommendations": {
                    "facial_wash": [],
                    "toner": [],
                    "serum": [],
                    "moisturizer": [],
                    "sunscreen": [],
                    "treatment": []
                },
                "notes": []
            }

            # Tambahkan recommendations jika ada
            if data.get('recommendations'):
                recs = data.get('recommendations')
                
                # Format basic routine products
                for product_type in ['facial_wash', 'toner', 'serum', 'moisturizer', 'sunscreen']:
                    if product_type in recs.get('basic_routine', {}):
                        response['recommendations'][product_type] = [
                            {
                                "product_id": p.get('product_id'),
                                "name": p.get('name'),
                                "type": p.get('type'),
                                "image_url": p.get('image_url'),
                                "description": p.get('description'),
                                "ingredients": p.get('ingredients')
                            }
                            for p in recs['basic_routine'][product_type]
                        ]

                # Format treatment products (additional care)
                treatment_products = []
                for product_type in ['eye_cream', 'mask', 'acne_spot']:
                    if product_type in recs.get('additional_care', {}):
                        treatment_products.extend([
                            {
                                "product_id": p.get('product_id'),
                                "name": p.get('name'),
                                "type": p.get('type'),
                                "image_url": p.get('image_url'),
                                "description": p.get('description'),
                                "ingredients": p.get('ingredients')
                            }
                            for p in recs['additional_care'][product_type]
                        ])
                response['recommendations']['treatment'] = treatment_products

                # Tambahkan notes
                response['notes'] = recs.get('notes', [])

            return response
            
        except Exception as e:
            print(f"Error getting skin analysis data: {str(e)}")
            raise

    def update_skin_analysis_with_recommendations(self, user_id: str, week: str, recommendations: dict):
        try:
            user_ref = self.collection.document(user_id)
            week_ref = user_ref.collection('image').document(week)
            
            # Update existing document with recommendations
            week_ref.update({
                'recommendations': recommendations,
                'updatedAt': datetime.now()
            })
            
            return True
        except Exception as e:
            print(f"Error updating recommendations: {e}")
            raise Exception(f"Failed to update recommendations: {str(e)}")

    def update_analysis_data(self, user_id: str, week: str, analysis_result: dict, public_url: str):
        user_ref = self.collection.document(user_id)
        week_ref = user_ref.collection('image').document(week)
        
        skin_conditions = analysis_result['result_your_skinhealth']['skin_conditions']
        
        week_ref.set({
            'tipe_kulit': analysis_result['result_your_skinhealth']['skin_type'],
            'acne': skin_conditions['acne'],
            'redness': skin_conditions['redness'],
            # 'eyebags': skin_conditions['eyebags'],
            'wrinkles': skin_conditions['wrinkles'],
            # 'darkspots': skin_conditions['darkspots'],
            'normal': skin_conditions['normal'],
            'createdAt': datetime.now(),
            'public_url': public_url
        })

    def update_profile_image(self, user_id: str, public_url: str):
        try:
            user_ref = self.collection.document(user_id)
            
            # Update with server timestamp
            user_ref.update({
                'profile_image_url': public_url,
                'profile_updated_at': firestore.SERVER_TIMESTAMP
            })
            
            # Verify update
            updated_doc = user_ref.get()
            if updated_doc.exists:
                data = updated_doc.to_dict()
                if data.get('profile_image_url') != public_url:
                    raise Exception("Profile URL update failed")
                
        except Exception as e:
            print(f"Error updating profile image: {str(e)}")
            raise

    def get_user_profile(self, user_id: str) -> dict:
        try:
            user_ref = self.collection.document(user_id)
            user_doc = user_ref.get()
            
            if not user_doc.exists:
                return None
            
            return user_doc.to_dict()
            
        except Exception as e:
            print(f"Error getting user profile: {str(e)}")
            raise

    def get_previous_week_data(self, user_id: str, current_week: str) -> dict:
        try:
            # Get week number
            current_week_num = int(current_week[-1])
            if current_week_num == 0:
                return None
            
            previous_week = f"pekan{current_week_num - 1}"
            
            # Get previous week data
            user_ref = self.collection.document(user_id)
            prev_week_ref = user_ref.collection('image').document(previous_week)
            prev_week_doc = prev_week_ref.get()
            
            if not prev_week_doc.exists:
                return None
            
            return prev_week_doc.to_dict()
        except Exception as e:
            print(f"Error getting previous week data: {str(e)}")
            return None

    def get_week_zero_data(self, user_id: str) -> dict:
        try:
            # Get week 0 data
            user_ref = self.collection.document(user_id)
            week_zero_ref = user_ref.collection('image').document('pekan0')
            week_zero_doc = week_zero_ref.get()
            
            if not week_zero_doc.exists:
                return None
            
            return week_zero_doc.to_dict()
        except Exception as e:
            print(f"Error getting week zero data: {str(e)}")
            return None

    def calculate_final_progress(self, current_data: dict, week_zero_data: dict) -> tuple:
        try:
            if not week_zero_data:
                return None, None
            
            # Get current conditions from analysis result
            current_conditions = current_data['skin_conditions_details']
            
            # Calculate total difference percentage
            total_improvement = 0
            total_conditions = 0
            
            for condition in ['acne', 'normal', 'redness', 'wrinkles']:
                current_val = float(current_conditions[condition])
                initial_val = float(week_zero_data.get(condition, 0) or 0)
                
                # For 'normal' condition, higher is better
                if condition == 'normal':
                    diff = current_val - initial_val
                # For other conditions (acne, redness, wrinkles), lower is better
                else:
                    diff = -(current_val - initial_val)  # Negative because lower is better
                    
                total_improvement += diff
                total_conditions += 1
            
            # Calculate average improvement
            progress_percentage = total_improvement / total_conditions
            
            # Determine progress message
            if -5 <= progress_percentage <= 5:
                message = "Your skin condition is stable and well-maintained! 🌟"
            elif 5 < progress_percentage <= 10:
                message = "Yay! There has been an improvement in your skin condition! 🎉"
            elif progress_percentage > 10:
                message = "Wow! Your skin has shown a significant improvement! 🌟✨"
            else:
                message = "It seems your skin needs more attention. Keep it up! 💪"
            
            return round(progress_percentage, 2), message
            
        except Exception as e:
            print(f"Error calculating progress: {str(e)}")
            return None, None

    def update_final_progress_score(self, user_id: str, week: str, progress_percentage: float):
        try:
            user_ref = self.collection.document(user_id)
            week_ref = user_ref.collection('image').document(week)
            
            week_ref.update({
                'score': progress_percentage,
                'updatedAt': datetime.now()
            })
            
        except Exception as e:
            print(f"Error updating progress score: {str(e)}")
            raise

    def get_progress_message(self, progress_percentage: float) -> str:
        if -5 <= progress_percentage <= 5:
            message = "Your skin condition is stable and well-maintained! 🌟"
        elif 5 < progress_percentage <= 10:
            message = "Yay! There has been an improvement in your skin condition! 🎉"
        elif progress_percentage > 10:
            message = "Wow! Your skin has shown a significant improvement! 🌟✨"
        else:
            message = "It seems your skin needs more attention. Keep it up! 💪"