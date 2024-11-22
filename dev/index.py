
from flask import Flask, jsonify, request
import requests
import psycopg2

# Configurazione dei dati di connessione
DB_CONFIG = {
    "dbname": "spacepatrol",
    "user": "postgres",
    "password": "1458",
    "host": "localhost",
    "port": 5432
}

# Funzione per connettersi al database
def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print("Errore nella connessione al database:", e)
        return None
    
app = Flask(__name__)

@app.route('/match', methods=['GET'])
def match():
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
        if not tle_data.get("norad_tle"):
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

@app.route('/fakeWebTle', methods=['GET'])
def fakeWebTle():
    # Logica di estrazione TLE dal web (simulata qui)
    data = [
        {
            "satellite_name": "Satellite-1",
            "tle_line1": "1 16749U 2216Q   23094.84432363  .99430934 67072-0  22659-3 0  9278",
            "tle_line2": "2 22227  95.8910 299.5581 0.3805685 341.1076 45.0676 13.639897775478"
        },
        {
            "satellite_name": "Satellite-2",
            "tle_line1": "1 26460U 2424G   23273.52675787  .24200172 79167-0  21964-3 0  2315",
            "tle_line2": "2 46421  13.8920 15.4769 0.5121698 191.2023 239.0087 13.18838295071"
        },
        {
            "satellite_name": "Satellite-3",
            "tle_line1": "1 22688U 3356W   23257.79868370  .38480760 73184-0  78518-3 0  5207",
            "tle_line2": "2 96815  97.5603 307.8366 0.3824456 70.3647 306.5547 12.308876571255"
        },
        {
            "satellite_name": "Satellite-4",
            "tle_line1": "1 46025U 1117X   23336.29337137  .49315293 27366-0  88317-3 0  5402",
            "tle_line2": "2 18204  29.2691 182.2753 0.2163541 305.3757 183.0335 14.490545850654"
        },
        {
            "satellite_name": "Satellite-5",
            "tle_line1": "1 18035U 1079P   23255.36699218  .43636234 53986-0  95456-3 0  1177",
            "tle_line2": "2 31898  51.7970 300.4197 0.9320130 163.9918 144.4677 14.414231583085"
        }
    ]

    return jsonify(data)

@app.route('/getAllTleFromWeb', methods=['GET'])
def get_all_tle_from_web():
    # Logica di estrazione TLE dal web (simulata qui)
    data = {"status": "success", "message": "TLE data extracted from web"}
    return jsonify(data)

@app.route('/getNoradToElaborate', methods=['GET'])
def get_norad_to_elaborate():
    # Per ora recupero sempre il record con ID 0 dal database
    conn = get_db_connection()
    if conn is None:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor()
        query = "SELECT id, norad_code, subscription_level, priority_level, timestamp FROM NORAD_List WHERE id = 0;"
        cursor.execute(query)
        record = cursor.fetchone()

        if record:
            data = {
                "status": "success",
                "norad_code": record[1],
                "subscription_level": record[2],
                "priority_level": record[3],
                "timestamp": str(record[4])  # Convertiamo il timestamp in stringa
            }
        else:
            data = {"status": "error", "message": "No record found with ID 0"}

        cursor.close()
        conn.close()
        return jsonify(data)
    except Exception as e:
        conn.close()
        return jsonify({"status": "error", "message": f"An error occurred: {str(e)}"}), 500

@app.route('/getTleToMatch', methods=['GET'])
def get_tle_to_match():
    # Simulazione della logica per recuperare i dati TLE
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

@app.route('/putAllTleInDbList', methods=['POST'])
def put_all_tle_in_db_list():
    if not request.is_json:
        return jsonify({"error": "Unsupported Media Type. Content-Type must be application/json"}), 415

    input_data = request.json
    response = {"status": "success", "message": "TLE data saved to database"}
    return jsonify(response)

@app.route('/putNoradCodeToDbList', methods=['POST'])
def put_norad_code_to_db_list():
    # Controlla che la richiesta abbia un Content-Type JSON
    if not request.is_json:
        return jsonify({"error": "Unsupported Media Type. Content-Type must be application/json"}), 415

    input_data = request.json
    response = {"status": "success", "message": "NORAD codes saved to database"}
    return jsonify(response)

if __name__ == '__main__':
    app.run(debug=True)
