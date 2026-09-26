"""Local dev entrypoint: `python3 -m periop_api.main`."""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("periop_api.app:app", host="0.0.0.0", port=8000, reload=True)
