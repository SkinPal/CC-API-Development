from google.cloud import storage
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

class StorageService:
    def __init__(self):
        key_path = os.getenv('GCP_STORAGE_KEY_PATH')
        self.bucket_name = os.getenv('BUCKET_NAME')
        
        if not key_path:
            # For Cloud Run, use default credentials
            self.client = storage.Client()
        else:
            # For local development
            self.client = storage.Client.from_service_account_json(key_path)
            
        self.bucket = self.client.bucket(self.bucket_name)

    def _ensure_public_access(self, blob):
        """Helper method to ensure blob is publicly accessible"""
        try:
            # Reset ACL
            blob.acl.save()
            
            # Set public access
            blob.acl.all().grant_read()
            blob.acl.save()
            
            # Make blob public
            blob.make_public()
            
            # Set cache control
            blob.cache_control = 'no-cache, no-store, must-revalidate'
            
            # Force metadata update
            blob.metadata = {'updated': datetime.now().isoformat()}
            blob.patch()
            
            # Get the public URL
            public_url = f"https://storage.googleapis.com/{self.bucket_name}/{blob.name}"
            return public_url
            
        except Exception as e:
            print(f"Error ensuring public access: {str(e)}")
            raise

    def register_folders(self, user_id: str):
        folders = [
            f"{user_id}/pekan0/",
            f"{user_id}/pekan1/",
            f"{user_id}/pekan2/",
            f"{user_id}/pekan3/",
            f"{user_id}/pekan4/",
            f"{user_id}/profile/",
            f"{user_id}/test/"
        ]
        
        for folder in folders:
            blob = self.bucket.blob(folder)
            if not blob.exists():
                blob.upload_from_string('')
    
    def upload_image(self, user_id: str, week: str, file) -> str:
        try:
            blob_name = f"{user_id}/{week}/{user_id}_{week}"
            
            # Delete existing blob if it exists
            existing_blob = self.bucket.blob(blob_name)
            if existing_blob.exists():
                existing_blob.delete()
            
            # Create new blob
            new_blob = self.bucket.blob(blob_name)
            
            # Upload file
            new_blob.upload_from_file(file.file, content_type=file.content_type)
            
            # Ensure public access and return URL
            return self._ensure_public_access(new_blob)
            
        except Exception as e:
            print(f"Error uploading image: {str(e)}")
            raise
    
    def upload_profile(self, user_id: str, file) -> str:
        try:
            # Generate timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            blob_name = f"{user_id}/profile/{user_id}_profile_{timestamp}"
            
            # Delete all existing profile images
            prefix = f"{user_id}/profile/"
            blobs = self.bucket.list_blobs(prefix=prefix)
            for blob in blobs:
                blob.delete()
            
            # Create new blob with cache control
            new_blob = self.bucket.blob(blob_name)
            new_blob.cache_control = 'no-cache, no-store, must-revalidate'
            
            # Upload file
            new_blob.upload_from_file(file.file, content_type=file.content_type)
            
            # Ensure public access and return URL
            public_url = self._ensure_public_access(new_blob)
            
            # Print debug info
            print(f"Upload complete. Blob name: {blob_name}")
            print(f"Public URL: {public_url}")
            
            return public_url
            
        except Exception as e:
            print(f"Error uploading profile: {str(e)}")
            raise
    
    def delete_image(self, user_id: str, week: str):
        blob_name = f"{user_id}/{week}/{user_id}_{week}"  # Sesuaikan dengan format nama file yang diupload
        blob = self.bucket.blob(blob_name)
        
        if blob.exists():
            blob.delete()
            return True
        else:
            return False
    
    def upload_skincare_image(self, image_filename: str, file_path: str) -> str:
        # Gunakan bucket khusus untuk skincare
        skincare_bucket_name = "skinpal-bucket-skincare"
        skincare_bucket = self.client.bucket(skincare_bucket_name)
        
        # Buat bucket baru jika belum ada
        if not skincare_bucket.exists():
            skincare_bucket.create()
            
        blob_name = f"products/{image_filename}"
        blob = skincare_bucket.blob(blob_name)
        
        # Upload file
        blob.upload_from_filename(file_path)
        
        # Make public
        blob.make_public()
        
        return blob.public_url
    