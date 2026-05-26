from flask import Flask
import threading
import os

app = Flask('')

@app.route('/')
def home():
    return "I am alive!"

def keep_alive():
    port = int(os.environ.get("PORT", 8080))
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port)).start()
