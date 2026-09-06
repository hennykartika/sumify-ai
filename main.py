from fastapi import FastAPI

from src.router import pdf_generator, pdf_templates, summary, transcribe, upload

app = FastAPI(title="Sumify AI")

app.include_router(upload.router)
app.include_router(transcribe.router)
app.include_router(summary.router)
app.include_router(pdf_templates.router)
app.include_router(pdf_generator.router)


@app.get("/")
async def root():
    return {"message": "Hello Iam Sumify AI"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)