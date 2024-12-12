from fastapi import FastAPI
from .routes.user_routes import router as user_router
import os

app = FastAPI(title="SkinPal API")

app.include_router(user_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": "Welcome to SkinPal API"}

if __name__ == "__main__":
    import uvicorn
    # Get port from environment variable with fallback to 8080
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)