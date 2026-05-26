from fastapi import FastAPI

app = FastAPI(
    title="FraudShield API",
    description="Real-time credit card fraud detection system API",
    version="0.1.0"
)

@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint to verify the API is running.
    """
    return {"status": "healthy"}
