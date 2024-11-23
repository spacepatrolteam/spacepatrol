from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/", methods=["GET"])
def handler():
    # Simula il recupero di TLE per un NORAD code
    data = {
        "status": "success",
        "norad_tle": {
            "satellite_name": "ISS (ZARYA)",
            "tle_line1": "1 25544U 98067A   23269.63541667  .00016717  00000-0  10270-3 0  9992",
            "tle_line2": "2 25544  51.6457 200.5350 0007913  32.3308  50.0150 15.50048536396073"
        },
        "related_tles": [
            {
                "satellite_name": "NOAA 19",
                "tle_line1": "1 33591U 09005A   23269.63541667  .00000117  00000-0  68273-4 0  9993",
                "tle_line2": "2 33591  99.1948 334.4665 0014078 203.2253 156.7524 14.12505315653279"
            },
            {
                "satellite_name": "Hubble Space Telescope",
                "tle_line1": "1 20580U 90037B   23269.63541667  .00000473  00000-0  36089-4 0  9995",
                "tle_line2": "2 20580  28.4706 239.2971 0002845  79.5727 280.5947 15.09107505686102"
            }
        ]
    }
    return jsonify(data)
