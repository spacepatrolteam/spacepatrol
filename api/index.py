from flask import Flask, jsonify, request
import requests
import psycopg2
import os
from sgp4.api import Satrec, jday
from datetime import datetime, timedelta
import numpy as np

app = Flask(__name__)

# load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
USR = os.getenv("USR")
SCRT = os.getenv("SCRT")

API_URL_GET_NORAD = os.getenv("API_URL_GET_NORAD")
API_URL_GET_TLE_TO_MATCH = os.getenv("API_URL_GET_TLE_TO_MATCH")
API_URL_PUT_TLE_IN_DB = os.getenv("API_URL_PUT_TLE_IN_DB")
API_URL_PUT_NORAD_IN_DB = os.getenv("API_URL_PUT_NORAD_IN_DB")

API_URL_GET_REAL_SPACETRACK_DATA = os.getenv("API_URL_GET_REAL_SPACETRACK_DATA")

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

# Funzione per calcolare le posizioni a partire da un TLE
def calculate_positions(tle, start_time, duration_minutes, step_seconds=60):
    satellite = Satrec.twoline2rv(tle[0], tle[1])
    positions = []
    current_time = start_time

    for i in range(0, duration_minutes * 60, step_seconds):
        jd, fr = jday(
            current_time.year,
            current_time.month,
            current_time.day,
            current_time.hour,
            current_time.minute,
            current_time.second,
        )
        e, r, _ = satellite.sgp4(jd, fr)
        if e == 0:  # Solo posizione valida
            offset_seconds = (current_time - start_time).total_seconds()
            positions.append((offset_seconds, r))
        current_time += timedelta(seconds=step_seconds)
    
    return positions

# Funzione per gestire più TLE
def process_tle_set(tle_set, start_time, duration_minutes, step_seconds=60):
    positions_dict = {}
    for satellite_id, tle in tle_set.items():
        positions_dict[satellite_id] = calculate_positions(tle, start_time, duration_minutes, step_seconds)
    return positions_dict

# Funzione per calcolare le intersezioni
def calculate_intersections_from_dict(positions_dict, threshold_km=1.0):
    """
    Calcola le intersezioni tra il NORAD principale (main_object) e i related TLE.
    Non confronta gli oggetti related tra loro.
    """
    main_object_id = "main_object"
    intersections = []

    # Ottieni la traiettoria del NORAD principale
    main_positions = positions_dict.get(main_object_id, [])

    # Controlla ogni related TLE rispetto al NORAD principale
    for satellite_id, related_positions in positions_dict.items():
        if satellite_id == main_object_id:
            continue  # Salta il NORAD principale stesso

        for pos_main, pos_related in zip(main_positions, related_positions):
            time_main, coord_main = pos_main
            time_related, coord_related = pos_related

            # Calcola la distanza tra il NORAD principale e l'oggetto related
            distance = np.linalg.norm(np.array(coord_main) - np.array(coord_related))
            if distance <= threshold_km:
                intersections.append({
                    "time": time_main,
                    "sat1": main_object_id,
                    "sat2": satellite_id,
                    "coord1": coord_main,
                    "coord2": coord_related,
                    "distance": distance
                })

    return intersections

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

        norad_tle_resp = tle_data.get("norad_tle")
        related_tles_resp = tle_data.get("related_tles")

        # Step 3: Costruisci il dizionario TLE per il calcolo
        tle_set = {
            "main_object": [
                norad_tle_resp["tle_line1"],
                norad_tle_resp["tle_line2"]
            ]
        }
        for related_tle in related_tles_resp:
            tle_set[related_tle["related_tle"]] = [
                related_tle["tle_line1"],
                related_tle["tle_line2"]
            ]

        # Step 4: Parametri della simulazione
        start_time = "2024-11-25T00:00:00Z"  # Start time statico per ora
        duration_minutes = 120
        step_seconds = 60
        threshold_km = 1.0  # Distanza di intersezione in km

        # Step 5: Calcolo delle traiettorie
        positions_dict = process_tle_set(tle_set, datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%SZ"), duration_minutes, step_seconds)

        # Step 6: Calcolo delle intersezioni
        intersections = calculate_intersections_from_dict(positions_dict, threshold_km)

        # Optional: Inserisci i risultati nel database (attualmente commentato)
        # conn = get_db_connection()
        # if conn is None:
        #     return jsonify({"error": "Database connection failed"}), 500

        # try:
        #     cursor = conn.cursor()
        #     # Elimina tutti i record esistenti
        #     cursor.execute("DELETE FROM neon_match_actual")
        #     # Inserisci i nuovi match
        #     insert_query = """
        #         INSERT INTO neon_match_actual (norad_code, tle_line1, tle_line2)
        #         VALUES (%s, %s, %s)
        #     """
        #     for intersect in intersections:
        #         cursor.execute(insert_query, (
        #             intersect["sat1"],  # Satellite 1
        #             intersect["coord1"],  # Posizione 1
        #             intersect["coord2"]  # Posizione 2
        #         ))
        #     conn.commit()
        #     cursor.close()
        #     conn.close()
        # except Exception as e:
        #     conn.rollback()
        #     conn.close()
        #     return jsonify({"error": f"Failed to save match history: {str(e)}"}), 500

        # Step 7: Restituisce i risultati
        return jsonify(intersections)

    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500
    
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

@app.route("/real_space_track_data_wip")
def real_space_track_data_wip():

    BASE_URL = "https://www.space-track.org"
    SESSION = requests.Session()
    query = "/basicspacedata/query/class/gp/decay_date/null-val/epoch/>now-30/orderby/norad_cat_id/format/json/object_type/debris"

    def login(email, password):
        """Effettua il login a SpaceTrack."""
        login_url = f"{BASE_URL}/ajaxauth/login"
        payload = {
            "identity": email,
            "password": password
        }
        response = SESSION.post(login_url, data=payload)
        if response.status_code == 200:
            print("Login effettuato con successo.")
        else:
            print("Errore durante il login.")
            response.raise_for_status()

    def get_data(query):
        """Estrae dati dalla query fornita."""
        request_url = f"{BASE_URL}{query}"
        response = SESSION.get(request_url)
        if response.status_code == 200:
            print("Dati estratti con successo.")
            return response.json()  
        else:
            print("Errore durante l'estrazione dei dati.")
            response.raise_for_status()

    def logout():
        """Effettua il logout da SpaceTrack."""
        logout_url = f"{BASE_URL}/ajaxauth/logout"
        response = SESSION.get(logout_url)
        if response.status_code == 200:
            print("Logout effettuato.")
        else:
            print("Errore durante il logout.")
            response.raise_for_status()
        
    try:
        login(USR, SCRT)
        data = get_data(query)
        return {
            "status": "success",
            "data": data
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "details": repr(e),
            "USR": repr(USR),
            "SCRT": repr(SCRT),
        }
    finally:
        try:
            logout()
        except Exception as logout_error:
            # Includi il fallimento del logout nel messaggio di errore, se necessario
            print(f"Failed to logout: {logout_error}")


