import pandas as pd
from google.cloud import firestore
import os
from app.services.storage_service import StorageService
from dotenv import load_dotenv

load_dotenv()

def import_skincare_database():
    # Inisialisasi services
    storage_service = StorageService()
    key_path = os.getenv('GCP_FIRESTORE_KEY_PATH')
    
    if not key_path:
        db = firestore.Client()
    else:
        db = firestore.Client.from_service_account_json(key_path)
    
    # Baca CSV
    df = pd.read_csv('database_skincare.csv')
    
    # Batch write untuk Firestore
    batch = db.batch()
    products_ref = db.collection('products')
    
    imported_count = 0
    errors = []
    
    for index, row in df.iterrows():
        try:
            # Upload gambar ke Cloud Storage
            image_path = os.path.join('temp_images', row['image_filename'])
            if not os.path.exists(image_path):
                raise Exception(f"File tidak ditemukan: {image_path}")
                
            # Upload dan dapatkan public URL
            public_url = storage_service.upload_skincare_image(
                row['image_filename'], 
                image_path
            )
            
            # Persiapkan data produk
            doc_ref = products_ref.document(str(row['product_id']))
            product_data = {
                'name': str(row['product_name']),
                'type': str(row['product_type']),
                'ingredients': str(row['ingredients']),
                'description': str(row['description']),
                'image_url': public_url,
                'skin_types': {
                    'oily': bool(float(row['oily_check']) >= 0.01),
                    'dry': bool(float(row['dry_check']) >= 0.01),
                    'normal': bool(float(row['normal_check']) >= 0.01)
                },
                'skin_conditions': {
                    'acne': bool(float(row['acne_check']) >= 0.01),
                    'redness': bool(float(row['redness_check']) >= 0.01),
                    'wrinkles': bool(float(row['wrinkles_check']) >= 0.01)
                }
            }
            
            # Tambahkan ke batch
            batch.set(doc_ref, product_data)
            imported_count += 1
            
            # Commit setiap 400 dokumen
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
    
    print(f"\nImport selesai!")
    print(f"Total produk diimport: {imported_count}")
    if errors:
        print("\nError yang terjadi:")
        for error in errors:
            print(f"- {error}")

if __name__ == "__main__":
    import_skincare_database()