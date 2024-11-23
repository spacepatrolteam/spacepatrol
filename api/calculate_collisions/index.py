from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/", methods=["GET"])
def handler():
    # Simula il calcolo delle collisioni
    data = {
        "status": "success",
        "norad_code": "25544",
        "matches": [
            "Intersection calculated between ISS (ZARYA) and NOAA 19",
            "Intersection calculated between ISS (ZARYA) and Hubble Space Telescope"
        ]
    }
    return jsonify(data)
