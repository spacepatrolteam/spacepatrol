from flask import Flask, jsonify, request
import requests
import psycopg2
import os

app = Flask(__name__)

# load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
API_URL_GET_NORAD = os.getenv("API_URL_GET_NORAD")
API_URL_GET_TLE_TO_MATCH = os.getenv("API_URL_GET_TLE_TO_MATCH")
API_URL_PUT_TLE_IN_DB = os.getenv("API_URL_PUT_TLE_IN_DB")
API_URL_PUT_NORAD_IN_DB = os.getenv("API_URL_PUT_NORAD_IN_DB")

# API_URL_GET_NORAD = "https://spacepatrol.vercel.app/get_norad_to_elaborate"
# API_URL_GET_TLE_TO_MATCH = "https://spacepatrol.vercel.app/get_tle_to_match"
# API_URL_PUT_TLE_IN_DB = "https://spacepatrol.vercel.app/put_all_tle_in_db_list"
# API_URL_PUT_NORAD_IN_DB = "https://spacepatrol.vercel.app/put_norad_code_to_db_list"

def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print("Errore nella connessione al database:", e)
        return None
    
# CRON
@app.route("/calc_match")
def calc_match():
    try:
        # Step 1: Recupera il codice NORAD da elaborare
        norad_response = requests.get(API_URL_GET_NORAD)
        if norad_response.status_code != 200:
            return jsonify({"status": "error", "message": "Error retrieving NORAD code"}), 500

        norad_code = norad_response.json().get("norad_code")
        if not norad_code:
            return jsonify({"status": "error", "message": "No NORAD code received"}), 500

        # Step 2: Recupera i TLE per il NORAD e per altri oggetti correlati
        tle_response = requests.get(API_URL_GET_TLE_TO_MATCH, params={"norad_code": norad_code})
        if tle_response.status_code != 200:
            return jsonify({"status": "error", "message": "Error retrieving TLE data"}), 500

        tle_data = tle_response.json()
        if not tle_data.get("norad_tle"):
            return jsonify({"status": "error", "message": "No TLE data received"}), 500

        norad_tle = tle_data.get("norad_tle")
        related_tles = tle_data.get("related_tles")

        # Step 3: Calcola il match
        # matches = []
        # for tle in related_tles:
        #     matches.append(f"{norad_tle} and {tle}")

        # Step 4: Inserisce i risultati del calcolo nella tabella neon_match_history
        conn = get_db_connection()
        if conn is None:
            return jsonify({"error": "Database connection failed"}), 500

        try:
            cursor = conn.cursor()

            # Elimina tutti i record dalla tabella neon_match_actual
            delete_query = "DELETE FROM neon_match_actual"
            cursor.execute(delete_query)

            # Inserisci i dati nella tabella neon_match_actual
            insert_query_actual = """
                INSERT INTO neon_match_actual (norad_code, tle_line1, tle_line2)
                VALUES (%s, %s, %s)
            """
            cursor.execute(insert_query_actual, ("2334255334", "1 20580U 90037B   23269.63541667  .00000473  00000-0  36089-4 0  9995", "2 25544  51.6457 200.5350 0007913  32.3308  50.0150 15.50048536396073"))

            # Inserisci i dati nella tabella neon_match_history
            insert_query_history = """
                INSERT INTO neon_match_history (norad_code, tle_line1, tle_line2)
                VALUES (%s, %s, %s)
            """
            cursor.execute(insert_query_history, ("2334255334", "1 20580U 90037B   23269.63541667  .00000473  00000-0  36089-4 0  9995", "2 25544  51.6457 200.5350 0007913  32.3308  50.0150 15.50048536396073"))

            # Commit dei cambiamenti
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            conn.rollback()
            conn.close()
            return jsonify({"error": f"Failed to save match history: {str(e)}"}), 500

        # Restituisce una risposta di successo
        return jsonify({"status": "success", "message": "Match data saved to database"})


    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
@app.route("/get_norad_to_elaborate")
def get_norad_to_elaborate():
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

@app.route("/get_tle_to_match")
def get_tle_to_match():
        # Simula il recupero di TLE per un NORAD code
    data = {
        "norad_tle": {
            "norad_tle": "21544",
            "tle_line1": "1 25544U 98067A   23269.63541667  .00016717  00000-0  10270-3 0  9992",
            "tle_line2": "2 25544  51.6457 200.5350 0007913  32.3308  50.0150 15.50048536396073"
        },
        "related_tles": [
            {
                "related_tle": "NOAA 19",
                "tle_line1": "1 33591U 09005A   23269.63541667  .00000117  00000-0  68273-4 0  9993",
                "tle_line2": "2 33591  99.1948 334.4665 0014078 203.2253 156.7524 14.12505315653279"
            },
            {
                "related_tle": "Hubble Space Telescope",
                "tle_line1": "1 20580U 90037B   23269.63541667  .00000473  00000-0  36089-4 0  9995",
                "tle_line2": "2 20580  28.4706 239.2971 0002845  79.5727 280.5947 15.09107505686102"
            }
        ]
    }
    return jsonify(data)

# CRON
@app.route("/update_web_tle_in_db")
def update_web_tle_in_db():
    # Chiamata interna all'API fake_web_tle_source_api
    with app.test_client() as client:
        response = client.get("/fake_web_tle_source_api")
        if response.status_code != 200:
            return jsonify({"error": "Failed to fetch TLE data"}), 500
        
        tle_data = response.json

    # Connessione al database Neon
    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        cursor = conn.cursor()
        for tle in tle_data:
            query = """
                INSERT INTO neon_tle_list (norad_code, tle_line1, tle_line2, timestamp)
                VALUES (%s, %s, %s, NOW())
            """
            cursor.execute(query, (tle["norad_code"], tle["tle_line1"], tle["tle_line2"]))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"status": "success", "message": "TLE data saved to database", "data": tle_data})

    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"error": f"Failed to save data: {str(e)}"}), 500

@app.route("/fake_web_tle_source_api", methods=["GET"])
def fake_web_tle_source_api():
    data = [
        {
            "norad_code": "Satellite-FAKE_1",
            "tle_line1": "1 16749U 2216Q   23094.84432363  .99430934 67072-0  22659-3 0  9278",
            "tle_line2": "2 22227  95.8910 299.5581 0.3805685 341.1076 45.0676 13.639897775478"
        },
        {
            "norad_code": "Satellite-FAKE_2",
            "tle_line1": "1 16749U 2216Q   23094.84432363  .99430934 67072-0  22659-3 0  9278",
            "tle_line2": "2 22227  95.8910 299.5581 0.3805685 341.1076 45.0676 13.639897775478"
        }
    ]
    return jsonify(data)

@app.route("/put_norad_code_to_db_list", methods=["PUT"])
def put_norad_code_to_db_list():
        # Controlla che la richiesta abbia un Content-Type JSON
    if not request.is_json:
        return jsonify({"error": "Unsupported Media Type. Content-Type must be application/json"}), 415

    input_data = request.json
    response = {"status": "success", "message": "NORAD codes saved to database"}
    return jsonify(response)

