import uvicorn
import os
import sys

# Ensure f6 is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("=" * 60)
    print("  LAUNCHING AURA FASHION AI WEB SERVER (PORT 8080)")
    print("=" * 60)
    print("Access locally at: http://127.0.0.1:8080\n")
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8080, log_level="info")
