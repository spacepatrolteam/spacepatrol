
from flask import Flask, jsonify, request
import requests

app = Flask(__name__)

# Endpoint per il calcolo del match
@app.route('/match', methods=['GET'])
def match_tle():
    try:
        # Step 1: Recupera il codice NORAD da elaborare
        norad_response = requests.get('http://localhost:5000/getNoradToElaborate')
        if norad_response.status_code != 200:
            return jsonify({"status": "error", "message": "Error retrieving NORAD code"}), 500
        
        norad_code = norad_response.json().get("norad_code")
        if not norad_code:
            return jsonify({"status": "error", "message": "No NORAD code received"}), 500

        # Step 2: Recupera i TLE per il NORAD e per altri oggetti correlati
        tle_response = requests.get('http://localhost:5000/getTleToMatch', params={"norad_code": norad_code})
        if tle_response.status_code != 200:
            return jsonify({"status": "error", "message": "Error retrieving TLE data"}), 500
        
        tle_data = tle_response.json()
        if not tle_data.get("tle_list"):
            return jsonify({"status": "error", "message": "No TLE data received"}), 500

        norad_tle = tle_data.get("norad_tle")
        related_tles = tle_data.get("related_tles")

        # Step 3: Calcola il match
        # Simulazione del calcolo del match (intersezioni entro 10 ore)
        matches = []
        for tle in related_tles:
            matches.append(f"Intersection calculated between {norad_tle} and {tle}")

        # Step 4: Restituisce i risultati del calcolo
        return jsonify({
            "status": "success",
            "norad_code": norad_code,
            "norad_tle": norad_tle,
            "matches": matches
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
