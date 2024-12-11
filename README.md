# SkinPal API with Python

## Deskripsi
API ini dibangun menggunakan FastAPI untuk mengelola penyimpanan pengguna dan analisis kulit menggunakan Google Cloud Storage dan Firestore.

## Prerequisites
Sebelum memulai, pastikan Anda memiliki:
- **Python 3.7** atau **lebih baru**
- Pip (package installer untuk Python), rekomendasi version **pip 24.3.1** 

## Instalasi

1. **Clone Repositori**
   ```bash
   git clone https://github.com/daffaverse/Skinpal-API-py.git <repo-name>
   ```
1. **Check Version Python ( harus > 3.7) dan Pip**
   ```bash
   python --version
   pip --version
   ```
   Jika masih belum sesuai dengan prerequisites, harap sesuaikan dahulu.

3. **Instal Dependensi**
   ```bash
   pip install -r requirements.txt
   ```
4. **Run Program**
   ```bash
   uvicorn app.main:app --host localhost --reload
   ```

## Aplikasi akan berjalan di `http://localhost:8000`. Anda dapat mengakses dokumentasi API di `http://localhost:8000/docs`.

## Penggunaan
- Untuk mengupload gambar, gunakan endpoint `/api/v1/users/upload`.
- Untuk menghapus gambar, gunakan endpoint `/api/v1/users/delete-image`.
- Untuk mendapatkan data analisis kulit, gunakan endpoint `/api/v1/users/analysis`.

## Kontribusi
Jika Anda ingin berkontribusi, silakan buat pull request atau buka issue.

## Lisensi
[MIT License](LICENSE)


user register :
=======
## User Register ##
```
{
    "user_id": "user1",
    "nama": "Ahmad Cristian",
    "email": "ahmadcristian@email.com"
}
```

## Cloud Storage Bucket Architecture ##
```bash
storage-bucket-01/
├── [user1_id]/
│   ├── pekan1/
|   |   ├── user1_pekan1.jpg  
│   ├── pekan2/
│   ├── pekan3/
│   └── pekan4/
└── [user2_id]/
    ├── pekan1/
    ├── pekan2/
    ├── pekan3/
    └── pekan4/
```

## Firestore Architecture ##
```bash
skinpal-firestore(default)/
└── pengguna/
    ├── [user1_id]/
    │   ├── nama: "Ahmad Cristian"
    │   ├── email: "ahmadcristian@email.com"
    │   ├── createdAt: timestamp
    │   └── image/
    │       ├── pekan0/
    │       │   ├── tipe_kulit: null
    │       │   ├── acne: null
    │       │   ├── redness: null
    │       │   ├── eyebags: null
    │       │   ├── wrinkles: null
    │       │   ├── darkspot: null
    │       │   ├── score: null
    │       │   ├── createdAt: null
    │       │   ├── public_url: null
    │       ├── pekan1/
    │       ├── pekan2/
    │       ├── pekan3/
    │       └── pekan4/
    └── [user2_id]/
        ├── nama: "User 2 Name"
        ├── email: "user2@email.com"
        ├── createdAt: timestamp
        └── image/
            ├── pekan0/
            ├── pekan1/
            ├── pekan2/
            ├── pekan3/
            └── pekan4/
