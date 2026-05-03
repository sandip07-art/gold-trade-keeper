from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "GoldTrade Gatekeeper running"}

@app.get("/docs-test")
def test():
    return {"status": "ok"}
