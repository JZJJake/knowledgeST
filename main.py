import uvicorn
import socket
import webbrowser
import threading
import time
import os

def check_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """
    Check if a specific port is currently occupied by another process.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # returns 0 if connection succeeds, meaning the port is in use
        result = s.connect_ex((host, port))
        return result == 0

def open_browser(url: str):
    """
    Wait a moment for the server to spin up, then open the browser to the 3D viewer.
    """
    time.sleep(2)
    print(f"Opening browser at: {url}")
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"Failed to automatically open browser: {e}")
        print(f"Please manually navigate to {url}")

if __name__ == "__main__":
    PORT = 8000
    HOST = "127.0.0.1"

    # Force HuggingFace to use a domestic mirror to prevent connection timeouts
    # when downloading the sentence-transformers embedding model for the first time.
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

    print("Checking system ports...")
    if check_port_in_use(PORT, HOST):
        print(f"\n[ERROR] Port {PORT} is already in use by another service on this system.")
        print(f"Please check your Server 2012 R2 processes (e.g., using 'netstat -ano | findstr {PORT}')")
        print("and terminate the conflicting service before starting the Academic Knowledge Graph.")

        # We don't want to just crash silently, so we exit with code 1 which the bat file will catch
        exit(1)

    print(f"Port {PORT} is available. Preparing to start Uvicorn server...")

    # We construct a local file path or server endpoint URL for the browser
    # Since we are using an API-only FastAPI implementation and static HTML:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    frontend_path = os.path.join(current_dir, "frontend", "index.html")
    file_url = f"file:///{frontend_path.replace(os.sep, '/').lstrip('/')}"

    # Start a background thread to open the browser automatically
    browser_thread = threading.Thread(target=open_browser, args=(file_url,))
    browser_thread.start()

    # Start the backend API Service
    print("\nStarting Backend Uvicorn Application Server...")
    try:
        uvicorn.run("backend.app:app", host=HOST, port=PORT, log_level="info", reload=False)
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Failed to start backend service: {e}")
        exit(1)
