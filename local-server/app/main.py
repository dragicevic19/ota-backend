import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
import os

LATEST_VERSION = "0.0.2"
FIRMWARE_DIR = "firmware"
HOST_IP = "0.0.0.0"
PORT = 8000

IP_ADDR = "192.168.0.28"

app = FastAPI()


@app.get("/check-for-update")
async def check_for_update(current_version: str = Query()):
    print(f"Device triggered API with current version: {current_version}")

    if current_version != LATEST_VERSION:
        print(f"Newer version <{LATEST_VERSION}> is available! Sending URLs...")
        base_url = f"http://{IP_ADDR}:{PORT}"

        response_data = {
            "update": True,
            "version": LATEST_VERSION,
            "url": f"{base_url}/firmware/{LATEST_VERSION}",
            "signature_url": f"{base_url}/signature/{LATEST_VERSION}"
        }
        return JSONResponse(content=response_data)
    else:
        print("Device has the latest version.")
        return JSONResponse(content={"update": False})


@app.get("/firmware/{version}")
async def get_firmware(version: str):
    file_path = os.path.join(FIRMWARE_DIR, version, "BasicOTA.ino.bin")
    print(f"Requested firmware: {file_path}")

    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="application/octet-stream", filename="firmware.bin")
    else:
        print(f"ERROR: Firmware file not found: {file_path}")
        raise HTTPException(status_code=404, detail="Firmware file not found")


@app.get("/signature/{version}")
async def get_signature(version: str):
    file_path = os.path.join(FIRMWARE_DIR, version, "firmware.sig")
    print(f"Requested signature: {file_path}")

    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="application/octet-stream", filename="firmware.sig")
    else:
        print(f"ERROR: Signature file not found: {file_path}")
        raise HTTPException(status_code=404, detail="Signature file not found")


if __name__ == "__main__":
    uvicorn.run(app, host=HOST_IP, port=PORT)