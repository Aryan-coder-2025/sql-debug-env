from fastapi import FastAPI

app = FastAPI(title="OpenEnv - AI Intelligence Benchmark")

@app.get("/")
def root():
    return {"status": "OpenEnv is running", "version": "0.1.0"}

@app.get("/health")
def health():
    return {"healthy": True}