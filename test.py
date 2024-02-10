import yt_dlp
import os

if os.path.exists("./audio/*"):
    os.remove("./audio/*")
    print("file removeed.")
else:
    print("no file existed")