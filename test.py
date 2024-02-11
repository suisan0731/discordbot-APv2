import yt_dlp
import os

if os.path.existes("./audio/*"):
    os.remove("./audio/*")
    print("file removeed.")
else:
    print("no file")