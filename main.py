from fastapi import FastAPI
from routers.judge import router as judge_router

app = FastAPI(
    title="MTG Judge API",
    description="AI-powered Magic: The Gathering judge using Claude",
    version="1.0.0",
)

app.include_router(judge_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
