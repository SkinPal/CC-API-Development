from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from ..schemas.user_schema import UserCreate
from ..services.storage_service import StorageService
from ..services.firestore_service import FirestoreService
from ..services.skincare_service import SkincareService
from ..services.ai_service import AIService
from google.cloud import firestore
from app.schemas.user_schema import UserLogin
import pandas as pd
import io
import traceback
import sys
import os
from typing import Dict, Any
import bcrypt
from ..services.auth_service import AuthService
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()
storage_service = StorageService()
firestore_service = FirestoreService()
skincare_service = SkincareService()
ai_service = AIService()
auth_service = AuthService()

@router.post("/users/")
async def register(user: UserCreate):
    try:
        # Create Storage folders
        storage_service.register_folders(user.user_id)
        
        # Create Firestore document
        firestore_service.register_document(
            user.user_id,
            user.nama,
            user.email,
            user.password,
        )
        
        return {"message": "User structure created successfully"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/users/login")
async def login(user: UserLogin):
    try:
        # Verifikasi credentials
        user_ref = firestore_service.collection.document(user.user_id)
        user_doc = user_ref.get()

        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="Username tidak ditemukan!")

        user_data = user_doc.to_dict()
        stored_password = user_data['password'].encode('utf-8')

        # Cek password
        is_valid = bcrypt.checkpw(user.password.encode('utf-8'), stored_password)
        if not is_valid:
            raise HTTPException(status_code=401, detail="Password salah!")

        # Generate token
        access_token = auth_service.create_access_token(user.user_id)

        return {
            "message": "Login berhasil",
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "user_id": user.user_id,
                "nama": user_data.get('nama'),
                "email": user_data.get('email'),
                "createdAt": user_data.get('createdAt')
            }
        }

    except HTTPException as he:
        # Re-raise HTTP exceptions
        raise he
    except Exception as e:
        # Log error untuk debugging
        print(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Terjadi kesalahan pada server: {str(e)}"
        )
    
@router.post("/users/analyze")
async def analyze_image(
    user_id: str,
    week: str,
    file: UploadFile = File(...),
    current_user: str = Depends(auth_service.verify_token)
):
    # Verifikasi bahwa user yang request sama dengan token
    if current_user != user_id:
        raise HTTPException(status_code=403, detail="Tidak memiliki akses")
    
    try:
        # Validate week format
        if week not in ['pekan0', 'pekan1', 'pekan2', 'pekan3', 'pekan4', 'test']:
            raise HTTPException(
                status_code=400,
                detail="Week must be one of: pekan0, pekan1, pekan2, pekan3, pekan4, test"
            )

        # Validate file type
        if not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=400,
                detail="File must be an image"
            )

        # Read file
        contents = await file.read()
        
        # Reset the file stream to the beginning
        await file.seek(0)
        
        # Upload to Cloud Storage first
        public_url = storage_service.upload_image(user_id, week, file)
        
        # Process image with AI
        analysis_result = ai_service.process_image(contents)
        
        # Update Firestore with analysis results and image URL
        firestore_service.update_analysis_data(user_id, week, analysis_result, public_url)
        
        # Generate recommendations based on analysis
        recommendations = skincare_service.get_recommendations(analysis_result['result_your_skinhealth'])
        
        # Save recommendations to Firestore
        firestore_service.update_skin_analysis_with_recommendations(user_id, week, recommendations)
        
        # Calculate progress only for week 4 compared to week 0
        progress_data = {}
        if week == 'pekan4':
            week_zero_data = firestore_service.get_week_zero_data(user_id)
            print(f"Week zero data: {week_zero_data}")
            if week_zero_data:
                progress_percentage, progress_message = firestore_service.calculate_final_progress(
                    analysis_result, 
                    week_zero_data
                )
                print(f"Final progress calculation: {progress_percentage}%")
                if progress_percentage is not None:
                    # Update score in Firestore
                    firestore_service.update_final_progress_score(user_id, week, progress_percentage)
                    
                    progress_data = {
                        "progress": {
                            "percentage": progress_percentage,
                            "message": progress_message
                        }
                    }
        
        # Sederhanakan response
        simplified_analysis = {
            "public_url": public_url,
            "result_your_skinhealth": {
                "skin_type": analysis_result['result_your_skinhealth']['skin_type'],
                "skin_conditions": {
                    "acne": analysis_result['result_your_skinhealth']['skin_conditions']['acne'],
                    "normal": analysis_result['result_your_skinhealth']['skin_conditions']['normal'],
                    "redness": analysis_result['result_your_skinhealth']['skin_conditions']['redness'],
                    "wrinkles": analysis_result['result_your_skinhealth']['skin_conditions']['wrinkles']
                }
            },
            "progress": progress_data.get('progress', {}),
            "recommendations": {
                "facial_wash": [],
                "toner": [],
                "serum": [],
                "moisturizer": [],
                "sunscreen": [],
                "treatment": []
            },
            "notes": recommendations['notes']  # Pindahkan notes ke luar recommendations
        }

        # Ambil rekomendasi produk dan format sesuai permintaan
        for product_type in ['facial_wash', 'toner', 'serum', 'moisturizer', 'sunscreen']:
            for product in recommendations['basic_routine'][product_type]:
                simplified_analysis['recommendations'][product_type].append({
                    "product_id": product['product_id'],
                    "name": product['name'],
                    "type": product['type'],
                    "image_url": product['image_url'],
                    "description": product['description'],
                    "ingredients": product['ingredients']
                })

        # Gabungkan additional care products
        for product_type in ['eye_cream', 'mask', 'acne_spot']:
            for product in recommendations['additional_care'][product_type]:
                simplified_analysis['recommendations']['treatment'].append({
                    "product_id": product['product_id'],
                    "name": product['name'],
                    "type": product['type'],
                    "image_url": product['image_url'],
                    "description": product['description'],
                    "ingredients": product['ingredients']
                })

        return simplified_analysis  # Kembalikan langsung response tanpa status
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/users/analysis")
async def get_skin_analysis(
    user_id: str, 
    week: str,
    current_user: str = Depends(auth_service.verify_token)
):
    if current_user != user_id:
        raise HTTPException(status_code=403, detail="Tidak memiliki akses")
    
    try:
        result = firestore_service.get_skin_analysis_data(user_id, week)
        if result is None:
            raise HTTPException(status_code=404, detail="Data not found")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/skincare")
def get_skincare_items():
    try:
        products = skincare_service.get_skincare_products()
        return products
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/users/upload-profile")
async def upload_profile(
    user_id: str,
    file: UploadFile = File(...),
    current_user: str = Depends(auth_service.verify_token)
):
    # Verifikasi bahwa user yang request sama dengan token
    if current_user != user_id:
        raise HTTPException(status_code=403, detail="Tidak memiliki akses")
        
    try:
        # Validate file type
        if not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=400,
                detail="File must be an image"
            )

        # Upload to Cloud Storage under profile directory
        public_url = storage_service.upload_profile(user_id, file)

        # Update Firestore with the profile image URL
        firestore_service.update_profile_image(user_id, public_url)

        return {
            "message": "Profile image uploaded successfully",
            "public_url": public_url
        }

    except Exception as e:
        print(f"Error in upload_profile: {str(e)}")
        print("Full error:", traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/users/profile")
async def get_user_profile(
    user_id: str,
    current_user: str = Depends(auth_service.verify_token)
):
    try:
        # Get user data from Firestore
        user_data = firestore_service.get_user_profile(user_id)
        
        if not user_data:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )
            
        return {
            "status": "success",
            "data": {
                "nama": user_data.get('nama'),
                "email": user_data.get('email'),
                "username": user_id,
                "profile_image": user_data.get('profile_image_url') 
            }
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching profile: {str(e)}"
        )

@router.delete("/users/delete")
async def delete_image(user_id: str, week: str):
    try:
        # Hapus dari Cloud Storage
        if not storage_service.delete_image(user_id, week):
            raise HTTPException(status_code=404, detail="Image not found in Cloud Storage")

        # Hapus dari Firestore
        if not firestore_service.delete_image_data(user_id, week):
            raise HTTPException(status_code=404, detail="Image data not found in Firestore")

        return {"message": "Image deleted successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/skincare/count")
async def count_skincare_products():
    try:
        key_path = os.getenv('GCP_FIRESTORE_KEY_PATH')
        
        if not key_path:
            db = firestore.Client()
        else:
            db = firestore.Client.from_service_account_json(key_path)
        
        # Get collection reference
        products_ref = db.collection('products')
        
        # Hitung dokumen
        docs = products_ref.stream()
        count = len(list(docs))
        
        # Tambahan info per kategori (opsional)
        categories = {}
        docs = products_ref.stream()  # stream ulang karena iterator sudah habis
        for doc in docs:
            product = doc.to_dict()
            product_type = product.get('type', 'Unknown')
            if product_type in categories:
                categories[product_type] += 1
            else:
                categories[product_type] = 1
        
        return {
            "total_products": count,
            "per_category": categories
        }
        
    except Exception as e:
        print(f"Error counting products: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error menghitung produk: {str(e)}"
        )

@router.post("/skincare/import-with-images")
async def import_skincare_data_with_images():
    try:
        # Inisialisasi services
        storage_service = StorageService()
        
        # Baca CSV
        df = pd.read_csv('./database.csv')
        
        key_path = os.getenv('GCP_FIRESTORE_KEY_PATH')
        
        if not key_path:
            db = firestore.Client()
        else:
            db = firestore.Client.from_service_account_json(key_path)
        
        batch = db.batch()
        products_ref = db.collection('products')
        
        imported_count = 0
        errors = []
        
        for index, row in df.iterrows():
            try:
                # Upload gambar ke Cloud Storage
                image_path = f"./temp_images/{row['image_filename']}"
                if os.path.exists(image_path):
                    public_url = storage_service.upload_skincare_image(
                        row['image_filename'],
                        image_path
                    )
                else:
                    raise Exception(f"Image file not found: {image_path}")
                
                # Persiapkan data produk
                doc_ref = products_ref.document(str(row['product_id']))
                product_data = {
                    'name': str(row['product_name']),
                    'type': str(row['product_type']),
                    'ingredients': str(row['ingredients']),
                    'description': str(row['description']),
                    'image_url': public_url,
                    'skin_types': {
                        'oily': bool(row['oily_check']),
                        'dry': bool(row['dry_check']),
                        'normal': bool(row['normal_check'])
                    },
                    'skin_conditions': {
                        'acne': bool(row['acne_check']),
                        'wrinkles': bool(row['wrinkles_check']),
                        'redness': bool(row['redness_check'])
                    }
                }
                
                # Tambahkan ke batch
                batch.set(doc_ref, product_data)
                imported_count += 1
                
                # Commit batch setiap 400 dokumen
                if imported_count % 400 == 0:
                    batch.commit()
                    batch = db.batch()
                    print(f"Committed batch of {imported_count} documents")
                    
            except Exception as e:
                error_msg = f"Error pada produk ID {row['product_id']}: {str(e)}"
                print(error_msg)
                errors.append(error_msg)
        
        # Commit sisa dokumen
        if imported_count % 400 != 0:
            batch.commit()
        
        result = {
            "status": "success",
            "message": "Import berhasil",
            "total_imported": imported_count
        }
        
        if errors:
            result["errors"] = errors
            
        return result
        
    except Exception as e:
        print(f"Error during import: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error during import: {str(e)}"
        )

@router.post("/skincare/import")
async def import_skincare_data(file: UploadFile = File(...)):
    if not file:
        raise HTTPException(status_code=400, detail="File tidak ditemukan")
        
    try:
        # Debug info
        print(f"File received: {file.filename}")
        print(f"Content type: {file.content_type}")
        
        # Validasi file type
        if file.content_type not in ['text/csv', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']:
            raise HTTPException(
                status_code=400,
                detail=f"Format file tidak didukung. Gunakan CSV atau Excel. Content type: {file.content_type}"
            )
        
        # Dapatkan thresholds
        try:
            thresholds = skincare_service.get_thresholds()
        except Exception as e:
            print(f"Error getting thresholds: {str(e)}")
            # Gunakan default thresholds jika gagal mendapatkan dari database
            thresholds = {
                'skin_types': {
                    'oily': 0.01,
                    'dry': 0.01,
                    'normal': 0.01
                },
                'skin_conditions': {
                    'acne': 0.01,
                    'redness': 0.01,
                    'wrinkles': 0.01
                }
            }
        
        # Baca file
        try:
            contents = await file.read()
            if not contents:
                raise HTTPException(status_code=400, detail="File kosong")
                
            print(f"File size: {len(contents)} bytes")
            
            # Parse file
            if file.filename.endswith('.csv'):
                df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
            else:
                df = pd.read_excel(io.BytesIO(contents))
            
            print(f"Data loaded. Shape: {df.shape}")
            
        except Exception as e:
            print(f"Error reading file: {str(e)}")
            print(traceback.format_exc())
            raise HTTPException(status_code=400, detail=f"Gagal membaca file: {str(e)}")
        
        # Validasi kolom
        required_columns = [
            'product_id', 'product_name', 'product_type', 'ingredients', 
            'description', 'image_url', 'oily_check', 'dry_check', 
            'normal_check', 'acne_check', 'wrinkles_check', 
            'redness_check'
        ]
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise HTTPException(
                status_code=400,
                detail=f"Kolom yang diperlukan tidak ada: {', '.join(missing_columns)}"
            )
        
        # Validasi product_type
        valid_product_types = [
            'Facial Wash', 'Toner', 'Serum', 'Moisturizer', 
            'Sunscreen', 'Eye Cream', 'Mask', 'Acne Spot'
        ]
        invalid_types = df[~df['product_type'].isin(valid_product_types)]['product_type'].unique()
        if len(invalid_types) > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid product types found: {', '.join(invalid_types)}. Valid types are: {', '.join(valid_product_types)}"
            )
        
        # Import ke Firestore
        try:
            key_path = os.getenv('GCP_FIRESTORE_KEY_PATH')
            
            if not key_path:
                db = firestore.Client()
            else:
                db = firestore.Client.from_service_account_json(key_path)
            
            batch = db.batch()
            products_ref = db.collection('products')
            
            imported_count = 0
            errors = []
            
            for index, row in df.iterrows():
                try:
                    doc_ref = products_ref.document(str(int(row['product_id'])))
                    product_data = {
                        'name': str(row['product_name']),
                        'type': str(row['product_type']),
                        'ingredients': str(row['ingredients']),
                        'description': str(row['description']),
                        'image_url': str(row['image_url']),
                        'skin_types': {
                            'oily': bool(float(row['oily_check']) >= thresholds['skin_types']['oily']),
                            'dry': bool(float(row['dry_check']) >= thresholds['skin_types']['dry']),
                            'normal': bool(float(row['normal_check']) >= thresholds['skin_types']['normal'])
                        },
                        'skin_conditions': {
                            'acne': bool(float(row['acne_check']) >= thresholds['skin_conditions']['acne']),
                            'redness': bool(float(row['redness_check']) >= thresholds['skin_conditions']['redness']),
                            'wrinkles': bool(float(row['wrinkles_check']) >= thresholds['skin_conditions']['wrinkles'])
                        }
                    }
                    
                    batch.set(doc_ref, product_data)
                    imported_count += 1
                    
                    if imported_count % 400 == 0:
                        batch.commit()
                        batch = db.batch()
                        print(f"Committed batch of {imported_count} documents")
                        
                except Exception as e:
                    error_msg = f"Error pada produk ID {row['product_id']}: {str(e)}"
                    print(error_msg)
                    errors.append(error_msg)
            
            # Commit sisa dokumen
            if imported_count % 400 != 0:
                batch.commit()
            
            result = {
                "status": "success",
                "message": "Import berhasil",
                "total_imported": imported_count
            }
            
            if errors:
                result["errors"] = errors
                
            return result
            
        except Exception as e:
            print(f"Firestore error: {str(e)}")
            print(traceback.format_exc())
            raise HTTPException(
                status_code=500,
                detail=f"Error saat import ke Firestore: {str(e)}"
            )
            
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )

@router.post("/users/upload")
async def upload_image(
    user_id: str,
    week: str,
    file: UploadFile = File(...),
    current_user: str = Depends(auth_service.verify_token)
):
    if current_user != user_id:
        raise HTTPException(status_code=403, detail="Tidak memiliki akses")
    
    try:
        # Validate week format
        if week not in ['pekan0','pekan1', 'pekan2', 'pekan3', 'pekan4', 'test']:
            raise HTTPException(
                status_code=400,
                detail="Week must be one of: pekan 0, pekan1, pekan2, pekan3, pekan4, test"
            )

        # Validate file type
        if not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=400,
                detail="File must be an image"
            )

        # Upload to Cloud Storage
        public_url = storage_service.upload_image(user_id, week, file)
        
        # Update Firestore
        firestore_service.update_image_data(user_id, week, public_url)
        
        return {
            "message": "Image uploaded successfully",
            "public_url": public_url
        }
        
    except Exception as e:
        print(f"Error in upload_image: {str(e)}")
        print("Full error:", traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))