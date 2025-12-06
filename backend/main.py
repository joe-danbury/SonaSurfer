from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import yaml

load_dotenv()

# Load config
with open('config.yaml') as f:
    config = yaml.safe_load(f)

app = FastAPI(title=config['app']['name'])

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=config['app']['cors_origins'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "SonaSurfer API"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

