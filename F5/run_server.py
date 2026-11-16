import uvicorn
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("=" * 60)
    print("  LAUNCHING F5 WARDROBE MULTI-USER SERVER (PORT 8000)")
    print("=" * 60)
    print("Access locally: http://localhost:8000")
    print("Access across devices on LAN: http://0.0.0.0:8000\n")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, log_level="info")
