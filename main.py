from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {"greeting": "Hello from Compose-to-Zerops!", "status": "running"}