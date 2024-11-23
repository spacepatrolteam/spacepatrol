from Flask import jsonify

def handler(event, context):
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
