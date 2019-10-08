#!/bin/python3
from app import app

# Following code is executed when running the server directly, for development
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9000)
