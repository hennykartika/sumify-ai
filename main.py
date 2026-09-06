from fastapi import FastAPI

from src.router import summary, upload

app = FastAPI(title="Sumify AI")

app.include_router(upload.router)
app.include_router(summary.router)


@app.get("/")
async def root():
    return {"message": "Hello Iam Sumify AI"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)