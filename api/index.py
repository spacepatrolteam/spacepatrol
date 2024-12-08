import logging
import requests
import psycopg2
import numpy as np
import os
import json
from flask import Flask, jsonify, request
from sgp4.api import Satrec, jday
from psycopg2 import sql
from datetime import datetime, timedelta
from dotenv import load_dotenv, find_dotenv

# Impostazione del logging
logging.basicConfig(
    level=logging.DEBUG if os.getenv("FLASK_ENV", "production") == "development" else logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Rilevare l'ambiente di esecuzione
is_vercel_env = os.getenv("VERCEL_ENV") is not None
logger.info(f"Running in {'Vercel' if is_vercel_env else 'Local'} environment.")

# Caricare le variabili di ambiente
if not is_vercel_env:
    # Ambiente locale: carica il file .env
    dotenv_path = find_dotenv()
    if dotenv_path:
        logger.info(f"Loading .env file from: {dotenv_path}")
        load_dotenv(dotenv_path)
    else:
        logger.warning("No .env file found. Ensure environment variables are set.")

# Recuperare le variabili di ambiente
ENV = os.getenv("FLASK_ENV", "production")
URL_DB = os.getenv("URL_DB")
USR_DB = os.getenv("USR_DB")
SCRT_DB = os.getenv("SCRT_DB")
USR_SPACETRACK = os.getenv("USR_SPACETRACK")
SCRT_SPACETRACK = os.getenv("SCRT_SPACETRACK")

# Configurazione dell'app Flask
app = Flask(__name__)
app.config["ENV"] = ENV
app.config["DEBUG"] = ENV == "development"
app.config["URL_DB"] = URL_DB
app.config["USR_DB"] = USR_DB
app.config["SCRT_DB"] = SCRT_DB

# Debug delle configurazioni solo in modalità debug
if app.config["DEBUG"]:
    logger.debug("Flask App Configurations:")
    logger.debug(f"URL_DB: {app.config['URL_DB']}")


# Endpoint di sistema da CANCELLARE
@app.route("/config", methods=["GET"])
def config():
    """
    Endpoint per visualizzare le configurazioni attive del sistema.
    Determina automaticamente se ci si trova in ambiente di sviluppo (locale) o produzione.
    """
    try:
        # Determina l'ambiente
        is_local = app.config["ENV"] == "development"

        # Configura i dati da restituire
        config_data = {
            "Environment": "Local" if is_local else "Production",
            "Database Config": {
                "User": os.getenv("DB_USER", "Not Configured") if is_local else "*****",
                "Host": os.getenv("DB_HOST", "Not Configured") if is_local else "*****",
                "Port": os.getenv("DB_PORT", "Not Configured") if is_local else "*****",
                "Name": os.getenv("DB_NAME", "Not Configured") if is_local else "*****"
            },
            "Logging Level": "DEBUG" if is_local else "INFO"
        }

        logger.info("Configuration endpoint accessed successfully.")
        return jsonify(config_data), 200
    except Exception as e:
        logger.error(f"Error retrieving configuration: {e}")
        return jsonify({"status": "error", "message": "Unable to retrieve configuration"}), 500


# ****************************************************************************************
# Sezione 1: Funzioni di servizio filtraggio TLE
# ****************************************************************************************


def filter_by_altitude(spacetrack_data, apoapsis, periapsis, tolerance_km=100):
    filtered = [
        obj for obj in spacetrack_data
        if abs(float(obj["APOAPSIS"]) - apoapsis) <= tolerance_km and
           abs(float(obj["PERIAPSIS"]) - periapsis) <= tolerance_km
    ]
    return filtered

def filter_by_inclination(data, inclination, tolerance_deg=2):
    filtered = [
        obj for obj in data
        if abs(float(obj["INCLINATION"]) - inclination) <= tolerance_deg
    ]
    return filtered

def filter_by_ra_of_asc_node(data, ra_of_asc_node, tolerance_deg=15):
    filtered = [
        obj for obj in data
        if abs(float(obj["RA_OF_ASC_NODE"]) - ra_of_asc_node) <= tolerance_deg
    ]
    return filtered

def filter_potential_colliders(spacetrack_data, target):
    # Step 1: Filtra per altezza
    filtered = filter_by_altitude(
        spacetrack_data,
        apoapsis=target["APOAPSIS"],
        periapsis=target["PERIAPSIS"]
    )
    # Step 2: Filtra per inclinazione
    filtered = filter_by_inclination(
        filtered,
        inclination=target["INCLINATION"]
    )
    # Step 3: Filtra per nodo ascendente
    filtered = filter_by_ra_of_asc_node(
        filtered,
        ra_of_asc_node=target["RA_OF_ASC_NODE"]
    )
    return filtered

def get_main_object(space_track_data, norad_cat_id):
    """
    Trova il main object nel TLE_DATA_ARRAY in base al NORAD_CAT_ID ottenuto dal database.
    """
    try:
        # Cerca il record corrispondente nel TLE_DATA_ARRAY
        for obj in space_track_data:
            # Cambia l'accesso da chiave stringa a posizione
            if str(obj[1]) == norad_cat_id:  # 4 è la posizione che contiene NORAD_CAT_ID
                logger.info(f"Main object found for NORAD_CAT_ID {norad_cat_id}")
                tl1 = obj[23]["tle_line1"]
                tl2 = obj[23]["tle_line2"]
                return {
                    "TLE_LINE1": tl1,  # Modifica in base alla posizione corretta di TLE_LINE1
                    "TLE_LINE2": tl2,  # Modifica in base alla posizione corretta di TLE_LINE2
                }

        # Solleva errore se il main object non viene trovato
        raise ValueError(f"Main object con NORAD_CAT_ID {norad_cat_id} non trovato!")
    except Exception as e:
        logger.error(f"Errore in get_main_object: {e}")
        raise

def get_potential_colliders(space_track_data, norad_cat_id, min_or_equal_apoapsis_km_value, min_or_equal_periapsis_km_value, min_or_equal_inclination_degrees_value):
    """
    Calcola i potenziali collider basandosi sui dati del database e dei TLE.
    """
    try:
        # Cerca i dati del TLE corrispondenti al NORAD_CAT_ID
        tle_record = next(
            (item for item in space_track_data if item[1] == int(norad_cat_id)),
            None
        )
        if not tle_record:
            raise ValueError(f"Nessun TLE trovato per il NORAD_CAT_ID {norad_cat_id}")

        logger.info(f"TLE record for NORAD_CAT_ID {norad_cat_id} found: {tle_record}")

        # Estrai i parametri dal record del TLE
        try:
            target = {
                "APOAPSIS": float(tle_record[-3]),  # Posizione specifica per APOAPSIS
                "PERIAPSIS": float(tle_record[-2]),  # Posizione specifica per PERIAPSIS
                "INCLINATION": float(tle_record[-1])  # Posizione specifica per INCLINATION
            }
        except (KeyError, ValueError, IndexError) as e:
            raise ValueError(f"Errore nell'estrazione dei parametri dal TLE record: {e}")

        logger.debug(f"Target TLE parameters: {target}")

        # Filtra i potenziali collider basandoti sui parametri
        colliders = []
        for obj in space_track_data:
            try:
                # Controlla che l'oggetto abbia i parametri necessari
                apoapsis = float(obj[-3])  # Indice per APOAPSIS
                periapsis = float(obj[-2])  # Indice per PERIAPSIS
                inclination = float(obj[-1])  # Indice per INCLINATION

                # Salta il target stesso
                if obj[1] == int(norad_cat_id):
                    continue

                # Controlla le condizioni per il potenziale collider
                if (
                    abs(target["APOAPSIS"] - apoapsis) <= min_or_equal_apoapsis_km_value
                    and abs(target["PERIAPSIS"] - periapsis) <= min_or_equal_periapsis_km_value
                    and abs(target["INCLINATION"] - inclination) <= min_or_equal_inclination_degrees_value
                ):
                    colliders.append(obj)
            except (ValueError, IndexError) as e:
                logger.warning(f"Errore durante la lettura dei dati dell'oggetto: {obj}, errore: {e}")
                continue

        logger.info(f"Potential colliders for NORAD_CAT_ID {norad_cat_id}: {len(colliders)} found")
        return colliders

    except ValueError as e:
        logger.error(f"Errore di valore: {e}")
        raise
    except Exception as e:
        logger.error(f"Errore inatteso: {e}")
        raise


# ****************************************************************************************
# Sezione 1: Funzioni di servizio
# ****************************************************************************************

def get_db_connection():
    try:
        # Controlla l'ambiente
        if ENV == "development":  # Locale
            logger.info("Connecting to the local database.")
            db_user = os.getenv("DB_USER", "postgres")
            db_password = os.getenv("DB_PASS", "password")
            db_host = os.getenv("DB_HOST", "localhost")
            db_name = os.getenv("DB_NAME", "spacepatrol")
            db_port = os.getenv("DB_PORT", 5432)
            
            conn = psycopg2.connect(
                user=db_user,
                password=db_password,
                host=db_host,
                port=db_port,
                database=db_name
            )
        else:  # Su Vercel
            logger.info("Connecting to the remote database using URL_DB.")
            conn = psycopg2.connect(URL_DB)
        
        return conn
    except Exception as e:
        logger.error("Database connection error: %s", e)
        return None

def retrieve_tle_engaged(min_or_equal_apoapsis_km_value, min_or_equal_periapsis_km_value, min_or_equal_inclination_degrees_value, norad_cat_id_to_check):
    try:
        logger.info("Retrieving TLE and parameters...")

        # Connessione al database
        conn = get_db_connection()
        if conn is None:
            raise Exception("Connessione al database non riuscita.")

        # Recupera il TLE_DATA_ARRAY dal database
        tle_data_query = "SELECT * FROM tle_list"  # Adatta alla struttura della tabella
        cursor = conn.cursor()
        cursor.execute(tle_data_query)
        space_track_data = cursor.fetchall()
        logger.info(f"{len(space_track_data)} lines in own space track data database found")
        cursor.close()

        try:
            main_object = get_main_object(space_track_data, norad_cat_id_to_check)
            logger.debug(f"Main object trovato: {main_object}")
        except ValueError as e:
            logger.error(f"Errore nella ricerca del main object: {e}")
            raise

        try:
            potential_colliders = get_potential_colliders(space_track_data, norad_cat_id_to_check, min_or_equal_apoapsis_km_value, min_or_equal_periapsis_km_value, min_or_equal_inclination_degrees_value)
            logger.debug(f"TLE - Potential Colliders: {len(potential_colliders)}")
        except ValueError as e:
            logger.error(f"Errore nella ricerca dei colliders: {e}")
            raise

        logger.debug(f"Main object structure: {main_object}")
        # logger.debug(f"Potential collider structure: {potential_colliders}")

        tle_set = {
            "main_object": [main_object.get("TLE_LINE1", ""), main_object.get("TLE_LINE2", "")]
        }

        for i, obj in enumerate(potential_colliders):
            tle_line1 = obj[23]["tle_line1"]
            tle_line2 = obj[23]["tle_line2"]
            
            if tle_line1 and tle_line2:  # Aggiungi solo se entrambi esistono
                tle_set[f"object_{i + 1}"] = [tle_line1, tle_line2]


        logger.debug(f"Generated TLE Set: {len(tle_set)}")
        conn.close()  # Chiude la connessione
        return tle_set
    except Exception as e:
        logger.error("Error retrieving TLE and parameters: %s", e)
        raise

# def calculate_positions(tle, start_time, duration_minutes, step_seconds=60):
#     satellite = Satrec.twoline2rv(tle[0], tle[1])
#     positions = []
#     current_time = start_time

#     for _ in range(0, duration_minutes * 60, step_seconds):
#         jd, fr = jday(
#             current_time.year,
#             current_time.month,
#             current_time.day,
#             current_time.hour,
#             current_time.minute,
#             current_time.second,
#         )
#         e, r, _ = satellite.sgp4(jd, fr)
#         if e == 0:
#             offset_seconds = (current_time - start_time).total_seconds()
#             positions.append((offset_seconds, r))
#         else:
#             logger.warning(f"SGP4 Error at {current_time}: e={e}, jd={jd}, fr={fr}")
#         current_time += timedelta(seconds=step_seconds)

#     # logger.debug(f"Calculated Positions for TLE: {tle}")
#     return positions
def calculate_positions(tle, start_time, duration_minutes, step_seconds=60):
    """
    Calcola le posizioni di un satellite in un determinato intervallo di tempo.

    Args:
        tle (list): Due linee del TLE.
        start_time (datetime): Tempo di inizio.
        duration_minutes (int): Durata in minuti.
        step_seconds (int): Intervallo di tempo tra i passi in secondi.

    Returns:
        list: Posizioni del satellite [(offset_seconds, [x, y, z]), ...].
    """
    try:
        # Inizializza il satellite usando il TLE
        satellite = Satrec.twoline2rv(tle[0], tle[1])

        # Genera i tempi richiesti
        time_steps = [
            start_time + timedelta(seconds=i)
            for i in range(0, duration_minutes * 60, step_seconds)
        ]

        # Pre-calcolo jd e fr per tutti i passi temporali
        jd_fr_list = [
            jday(
                current_time.year,
                current_time.month,
                current_time.day,
                current_time.hour,
                current_time.minute,
                current_time.second,
            )
            for current_time in time_steps
        ]

        # Calcolo delle posizioni in batch
        results = [satellite.sgp4(jd, fr) for jd, fr in jd_fr_list]

        # Creazione della lista di posizioni
        positions = []
        for offset_seconds, (e, r, _) in zip(
            range(0, duration_minutes * 60, step_seconds), results
        ):
            if e == 0:  # Solo se il calcolo è valido
                positions.append((offset_seconds, r))
            else:
                logger.warning(f"SGP4 Error at offset {offset_seconds}: e={e}")

        return positions

    except Exception as e:
        logger.error(f"Error calculating positions: {e}")
        return []


def from_tle_to_positions(tle_set, start_time, duration_minutes, step_seconds=60):
    tle_positions = {}
    for satellite_id, tle in tle_set.items():
        # logger.info(f"Processing TLE for Satellite: {satellite_id}")
        positions = calculate_positions(tle, start_time, duration_minutes, step_seconds)
        if not positions:
            logger.warning(f"No positions calculated for {satellite_id}. Skipping.")
        else:
            tle_positions[satellite_id] = positions
    logger.debug(f"Processed Positions Dict: {tle_positions}")
    return tle_positions

def calculate_intersections(tle_positions, threshold_km=5000.0):
    main_object_id = "main_object"
    intersections = []

    main_positions = tle_positions.get(main_object_id, [])
    for satellite_id, related_positions in tle_positions.items():
        if satellite_id == main_object_id:
            continue
        for pos_main, pos_related in zip(main_positions, related_positions):
            _, coord_main = pos_main
            _, coord_related = pos_related
            distance = np.linalg.norm(np.array(coord_main) - np.array(coord_related))
            if distance <= threshold_km:
                intersections.append({
                    "time": pos_main[0],
                    "sat1": main_object_id,
                    "sat2": satellite_id,
                    "coord1": coord_main,
                    "coord2": coord_related,
                    "distance": distance
                })
        print(f"Intersections for {satellite_id}:")  # Log delle intersezioni trovate

    print("Total Intersections:", len(intersections))  # Log del totale delle intersezioni
    return intersections

def create_czml(tle_positions, epoch, intersections=None):
    czml = [
        {
            "id": "document",
            "name": "Satellite Orbits",
            "version": "1.0",
            "clock": {
                "interval": f"{epoch.isoformat()}Z/{(epoch + timedelta(hours=2)).isoformat()}Z",
                "currentTime": epoch.isoformat() + "Z",
                "multiplier": 1,
                "range": "CLAMPED"
            }
        }
    ]

    for idx, (satellite_id, positions) in enumerate(tle_positions.items(), start=1):
        if len(positions) < 2:
            logger.warning(f"Satellite {satellite_id} has insufficient data: {positions}")
            continue

        cartesian_data = []
        for time, (x, y, z) in positions:
            cartesian_data.extend([time, x, y, z])

        logger.debug(f"Cartesian Data for {satellite_id}: {cartesian_data}")

        czml.append({
            "id": f"line{idx}",
            "name": f"Satellite {satellite_id}",
            "availability": f"{epoch.isoformat()}Z/{(epoch + timedelta(hours=2)).isoformat()}Z",
            "path": {
                "material": {"solidColor": {"color": {"rgba": [255, 0, 0, 255]}}},
                "width": 5
            },
            "position": {
                "epoch": epoch.isoformat() + "Z",
                "cartesian": cartesian_data
            }
        })

    if intersections:
        logger.debug(f"Intersections added to CZML: {intersections}")

    return czml

def update_match_actual(intersections):
    """
    Aggiorna la tabella match_actual: elimina tutti i record esistenti
    e inserisce i nuovi dati.
    """
    conn = get_db_connection()
    if conn is None:
        raise Exception("Database connection failed")

    try:
        cursor = conn.cursor()
        # Elimina tutti i record esistenti
        cursor.execute("DELETE FROM match_actual")

        # Inserisci i nuovi match
        insert_query = """
            INSERT INTO match_actual (sat1, sat2, distance, time, coord1, coord2)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        for intersect in intersections:
            cursor.execute(insert_query, (
                intersect["sat1"],
                intersect["sat2"],
                intersect["distance"],
                intersect["time"],
                json.dumps(intersect["coord1"]),  # Serializza le coordinate in JSON
                json.dumps(intersect["coord2"])   # Serializza le coordinate in JSON
            ))

        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        conn.rollback()
        conn.close()
        raise Exception(f"Failed to update match_actual: {str(e)}")

def update_match_history(intersections):
    """
    Aggiunge nuovi dati alla tabella match_history senza eliminare i record esistenti.
    """
    conn = get_db_connection()
    if conn is None:
        raise Exception("Database connection failed")

    try:
        cursor = conn.cursor()

        # Inserisci i nuovi match
        insert_query = """
            INSERT INTO match_history (sat1, sat2, distance, time, coord1, coord2)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        for intersect in intersections:
            cursor.execute(insert_query, (
                intersect["sat1"],
                intersect["sat2"],
                intersect["distance"],
                intersect["time"],
                json.dumps(intersect["coord1"]),  # Serializza le coordinate in JSON
                json.dumps(intersect["coord2"])   # Serializza le coordinate in JSON
            ))

        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        conn.rollback()
        conn.close()
        raise Exception(f"Failed to append to match_history: {str(e)}")

@app.route("/register_new_norad", methods=["PUT"])
def register_new_norad():
    """
    Aggiunge un nuovo record alla tabella norad_list.
    """
    conn = get_db_connection()
    if conn is None:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    # Recupera i dati dal corpo della richiesta
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400

    norad_code = data.get("norad_code")
    subscription_level = data.get("subscription_level")
    priority_level = data.get("priority_level")

    # Verifica che tutti i campi richiesti siano presenti
    if norad_code is None or subscription_level is None or priority_level is None:
        return jsonify({"status": "error", "message": "Missing required fields"}), 400

    try:
        cursor = conn.cursor()

        # Query per inserire un nuovo record in norad_list
        insert_query = """
            INSERT INTO norad_list (norad_code, subscription_level, priority_level)
            VALUES (%s, %s, %s)
        """
        cursor.execute(insert_query, (norad_code, subscription_level, priority_level))

        # Commit delle modifiche e chiusura connessione
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"status": "success", "message": "Record added to norad_list"}), 201

    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"status": "error", "message": f"Database error: {str(e)}"}), 500


@app.route("/delete_norad", methods=["DELETE"])
def delete_norad():
    """
    Elimina un record dalla tabella norad_list in base al norad_code.
    """
    conn = get_db_connection()
    if conn is None:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    # Recupera il norad_code dal corpo della richiesta
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400

    norad_code = data.get("norad_code")

    # Verifica che il norad_code sia stato fornito
    if norad_code is None:
        return jsonify({"status": "error", "message": "Missing required field: norad_code"}), 400

    try:
        cursor = conn.cursor()

        # Query per eliminare il record in base al norad_code
        delete_query = """
            DELETE FROM norad_list WHERE norad_code = %s
        """
        cursor.execute(delete_query, (norad_code,))

        # Controlla se un record è stato effettivamente eliminato
        if cursor.rowcount == 0:
            return jsonify({"status": "error", "message": f"No record found with norad_code: {norad_code}"}), 404

        # Commit delle modifiche e chiusura connessione
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"status": "success", "message": f"Record with norad_code {norad_code} deleted"}), 200

    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"status": "error", "message": f"Database error: {str(e)}"}), 500

# ****************************************************************************************
# Sezione 2: API Endpoint
# ****************************************************************************************


@app.route("/create_czml", methods=["GET"])
def create_czml_api():
    # {
    #     "start_time": "2024-11-25T00:00:00Z",
    #     "duration_minutes": 120,
    #     "step_seconds": 1800,
    #     "min_or_equal_apoapsis_km_value": 100,
    #     "min_or_equal_periapsis_km_value": 100,
    #     "min_or_equal_inclination_degrees_value": 1,
    #     "threshold": 5000
    # }
    try:

        conn = get_db_connection()
        if conn is None:
            raise Exception("Connessione al database non riuscita.")
    
        data = request.get_json()
        start_time = data.get("start_time", None)
        duration_minutes = data.get("duration_minutes", 120)
        logger.info(f"duration_minutes: {duration_minutes}")
        step_seconds = data.get("step_seconds", 1800)
        logger.info(f"step_seconds: {step_seconds}")
        min_or_equal_apoapsis_km_value = data.get("min_or_equal_apoapsis_km_value", 100)
        logger.info(f"min_or_equal_apoapsis_km_value: {min_or_equal_apoapsis_km_value}")
        min_or_equal_periapsis_km_value = data.get("min_or_equal_periapsis_km_value", 100)
        logger.info(f"min_or_equal_periapsis_km_value: {min_or_equal_periapsis_km_value}")
        min_or_equal_inclination_degrees_value = data.get("min_or_equal_inclination_degrees_value", 1)
        logger.info(f"min_or_equal_inclination_degrees_value: {min_or_equal_inclination_degrees_value}")
        threshold_km = data.get("threshold", 5000.0)
        logger.info(f"threshold_km: {threshold_km}")
    
        if not start_time:
            return jsonify({"status": "error", "message": "Missing required parameter: start_time"}), 400
        
        try:
            start_time = datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError as e:
            logger.error(f"Invalid start_time format: {start_time}. Error: {e}")
            return jsonify({"status": "error", "message": "Invalid start_time format. Expected ISO 8601."}), 400
        
        logger.debug(f"Parameters received - Threshold: {threshold_km}, Start Time: {start_time}")

        norad_cat_id_to_check = get_norad_code_from_db(conn, record_id=0)

        tle_engaged = retrieve_tle_engaged(min_or_equal_apoapsis_km_value, min_or_equal_periapsis_km_value, min_or_equal_inclination_degrees_value, norad_cat_id_to_check)
        tle_positions = from_tle_to_positions(tle_engaged, start_time, duration_minutes, step_seconds)
        logger.debug(f"Positions Dict for CZML: {tle_positions}")
        czml_data = create_czml(tle_positions, start_time)
        logger.info("CZML data generated successfully")
        return jsonify(czml_data)
    except Exception as e:
        logger.error("Error in /create_czml API: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/calculate_matches", methods=["GET"])
def calculate_matches_api():
    # {
    #     "start_time": "2024-11-25T00:00:00Z",
    #     "duration_minutes": 120,
    #     "step_seconds": 1800,
    #     "min_or_equal_apoapsis_km_value": 100,
    #     "min_or_equal_periapsis_km_value": 100,
    #     "min_or_equal_inclination_degrees_value": 1,
    #     "threshold": 5000
    # }
    """Calcola le intersezioni tra il NORAD principale e altri satelliti."""
    try:        

        conn = get_db_connection()
        if conn is None:
            raise Exception("Connessione al database non riuscita.")
        
        data = request.get_json()
        start_time = data.get("start_time", None)
        duration_minutes = data.get("duration_minutes", 120)
        step_seconds = data.get("step_seconds", 1800)
        min_or_equal_apoapsis_km_value = data.get("min_or_equal_apoapsis_km_value", 100)
        min_or_equal_periapsis_km_value = data.get("min_or_equal_periapsis_km_value", 100)
        min_or_equal_inclination_degrees_value = data.get("min_or_equal_inclination_degrees_value", 1)
        threshold_km = data.get("threshold", 5000.0)
    
        if not start_time:
            return jsonify({"status": "error", "message": "Missing required parameter: start_time"}), 400
        
        try:
            start_time = datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError as e:
            logger.error(f"Invalid start_time format: {start_time}. Error: {e}")
            return jsonify({"status": "error", "message": "Invalid start_time format. Expected ISO 8601."}), 400
                
        norad_cat_id_to_check = get_norad_code_from_db(conn, record_id=0)

        tle_engaged = retrieve_tle_engaged(min_or_equal_apoapsis_km_value, min_or_equal_periapsis_km_value, min_or_equal_inclination_degrees_value, norad_cat_id_to_check)
        tle_positions = from_tle_to_positions(tle_engaged, start_time, duration_minutes, step_seconds)

        intersections = calculate_intersections(tle_positions, threshold_km)

        # Aggiorna i database solo in produzione
        if app.config["ENV"] == "production":
            update_match_actual(intersections)
            update_match_history(intersections)
        else:
            logger.info("Bypass database update in debug mode")

        return jsonify({"status": "success", "intersections_numbers": len(intersections), "intersections": intersections})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ****************************************************************************************
# Sezione 3: Update TLE
# ****************************************************************************************


def clean_value(value):
    try:
        if isinstance(value, str):
            # Rimuove spazi extra e tenta di convertire
            return float(value.replace(" ", "").replace("-", "e-"))
        return float(value)
    except ValueError:
        # Restituisce 0.0 come valore di fallback
        return 0.0

def process_tle_batch(conn, batch_data):
    try:
        cursor = conn.cursor()
        cursor.executemany("""
            INSERT INTO tle_list (
                codnorad_riga1, classificazione, anno, nrlancio_anno,
                pezzo_lancio, annoepoca_astro, epoca_astro, derivata_prima, derivata_seconda,
                termine_trascinamento, tipo_effemeridi, nrset, chksum_riga1, codnorad_riga2,
                inclinazione, ascensione_retta, eccentricita, arg_perigeo, anomalia_media,
                moto_medio, nr_rivoluzioni, chksum_riga2, json, dt, extra_info,
                apoapsis, periapsis, inclination
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, NOW(), %s,
                %s, %s, %s
            )
        """, batch_data)  # Inserisci il batch di tuple
        conn.commit()
        cursor.close()
        print(f"Inseriti {len(batch_data)} TLE nel database.")
    except Exception as e:
        logging.error(f"Errore durante l'inserimento batch: {e}")
        conn.rollback()

def insert_tle_data(conn, tle_line1, tle_line2, tle_apoapsis, tle_periapsis, tle_inclination):
    try:
        # Estrai i dati dai TLE (linea 1 e linea 2)
        norad_cat_id = tle_line1[2:7]
        classification = tle_line1[7:8]
        launch_year = 1900 + int(tle_line1[9:11]) if int(tle_line1[9:11]) >= 57 else 2000 + int(tle_line1[9:11])
        launch_number = int(tle_line1[11:14])
        launch_piece = tle_line1[14:17].strip()
        epoch_year = 2000 + int(tle_line1[18:20]) if int(tle_line1[18:20]) < 50 else 1900 + int(tle_line1[18:20])
        epoch_day = clean_value(tle_line1[20:32])
        first_derivative = clean_value(tle_line1[33:43])
        second_derivative = clean_value(tle_line1[44:52])
        bstar = clean_value(tle_line1[53:61])
        ephemeris_type = int(tle_line1[62:63])
        element_set = int(tle_line1[64:68])
        checksum1 = int(tle_line1[68:69])

        inclination = clean_value(tle_line2[8:16])
        right_ascension = clean_value(tle_line2[17:25])
        eccentricity = clean_value("0." + tle_line2[26:33])
        argument_of_perigee = clean_value(tle_line2[34:42])
        mean_anomaly = clean_value(tle_line2[43:51])
        mean_motion = clean_value(tle_line2[52:63])
        revolution_number = int(tle_line2[63:68])
        checksum2 = int(tle_line2[68:69])
        
        # Query SQL aggiornata per includere APOAPSIS, PERIAPSIS e INCLINATION
        query = sql.SQL("""
            INSERT INTO tle_list (
                codnorad_riga1, classificazione, anno, nrlancio_anno,
                pezzo_lancio, annoepoca_astro, epoca_astro, derivata_prima, derivata_seconda,
                termine_trascinamento, tipo_effemeridi, nrset, chksum_riga1, codnorad_riga2,
                inclinazione, ascensione_retta, eccentricita, arg_perigeo, anomalia_media,
                moto_medio, nr_rivoluzioni, chksum_riga2, json, dt, extra_info,
                apoapsis, periapsis, inclination
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, NOW(), %s,
                %s, %s, %s
            )
        """)

        cursor = conn.cursor()
        cursor.execute(query, (
            norad_cat_id, classification, launch_year, launch_number,
            launch_piece, epoch_year, epoch_day, first_derivative, second_derivative,
            bstar, ephemeris_type, element_set, checksum1, norad_cat_id,
            inclination, right_ascension, eccentricity, argument_of_perigee,
            mean_anomaly, mean_motion, revolution_number, checksum2,
            json.dumps({"tle_line1": tle_line1, "tle_line2": tle_line2}), "{}",
            tle_apoapsis, tle_periapsis, tle_inclination
        ))
        conn.commit()
        print(f"TLE {norad_cat_id} inserito correttamente.")
        cursor.close()
    except Exception as e:
        print(f"Errore durante l'inserimento del TLE: {e}")
        conn.rollback()

@app.route("/from_spacetrack_to_our_db")
def from_spacetrack_to_our_db():

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
        login(USR_SPACETRACK, SCRT_SPACETRACK)
        data = get_data(query)

        # Connessione al database
        conn = get_db_connection()
        if conn is None:
            return {
                "status": "error",
                "message": "Connessione al database fallita"
            }
        
        # Connessione al database
        conn = get_db_connection()
        if conn is None:
            return {
                "status": "error",
                "message": "Connessione al database fallita"
            }

        # Elimina tutti i record esistenti
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tle_list")
        conn.commit()
        cursor.close()

        # Lista per raccogliere i dati
        batch_data = []

        for tle in data:
            tle_line1 = tle.get("TLE_LINE1")
            tle_line2 = tle.get("TLE_LINE2")
            tle_apoapsis = tle.get("APOAPSIS")
            tle_periapsis = tle.get("PERIAPSIS")
            tle_inclination = tle.get("INCLINATION")

            if not tle_line1 or not tle_line2 or not tle_apoapsis or not tle_periapsis or not tle_inclination:
                logging.warning("Qualche dato del TLE mancante, salto questo TLE.")
                continue

            try:
                # Aggiungi i dati al batch (in formato tuple)
                norad_cat_id = tle_line1[2:7]
                classification = tle_line1[7:8]
                launch_year = 1900 + int(tle_line1[9:11]) if int(tle_line1[9:11]) >= 57 else 2000 + int(tle_line1[9:11])
                launch_number = int(tle_line1[11:14])
                launch_piece = tle_line1[14:17].strip()
                epoch_year = 2000 + int(tle_line1[18:20]) if int(tle_line1[18:20]) < 50 else 1900 + int(tle_line1[18:20])
                epoch_day = clean_value(tle_line1[20:32])
                first_derivative = clean_value(tle_line1[33:43])
                second_derivative = clean_value(tle_line1[44:52])
                bstar = clean_value(tle_line1[53:61])
                ephemeris_type = int(tle_line1[62:63])
                element_set = int(tle_line1[64:68])
                checksum1 = int(tle_line1[68:69])

                inclination = clean_value(tle_line2[8:16])
                right_ascension = clean_value(tle_line2[17:25])
                eccentricity = clean_value("0." + tle_line2[26:33])
                argument_of_perigee = clean_value(tle_line2[34:42])
                mean_anomaly = clean_value(tle_line2[43:51])
                mean_motion = clean_value(tle_line2[52:63])
                revolution_number = int(tle_line2[63:68])
                checksum2 = int(tle_line2[68:69])

                # Aggiungi tuple al batch
                batch_data.append((
                    norad_cat_id, classification, launch_year, launch_number,
                    launch_piece, epoch_year, epoch_day, first_derivative, second_derivative,
                    bstar, ephemeris_type, element_set, checksum1, norad_cat_id,
                    inclination, right_ascension, eccentricity, argument_of_perigee,
                    mean_anomaly, mean_motion, revolution_number, checksum2,
                    json.dumps({"tle_line1": tle_line1, "tle_line2": tle_line2}), "{}",
                    tle_apoapsis, tle_periapsis, tle_inclination
                ))
            except Exception as e:
                logging.error(f"Errore durante la preparazione del TLE: {e}")
                continue

        # Chiamata a process_tle_batch
        if batch_data:
            process_tle_batch(conn, batch_data)


        # Chiudi la connessione al database
        conn.close()

        return {
            "status": "success",
            "message": "Dati inseriti correttamente nel database."
        }
    except Exception as e:
        logging.error(f"Errore durante l'inserimento dei dati nel database: {e}")
        return {
            "status": "error",
            "message": str(e),
            "details": repr(e)
        }
    finally:
        try:
            logout()
        except Exception as logout_error:
            logging.error(f"Failed to logout: {logout_error}")


# ****************************************************************************************
# Sezione 3: NORAD Rotation
# ****************************************************************************************


def get_norad_code_from_db(conn, record_id):
    """
    Recupera il valore del campo 'norad_code' dal record con id specificato nella tabella 'norad_list'.
    Gestisce sia ambiente locale che produzione.
    """
    try:
        # Log dell'ambiente in cui si sta operando
        logger.info("Retrieving 'norad_code' from database (Record ID: %s)...", record_id)
        
        query = sql.SQL(f"SELECT norad_code FROM norad_list WHERE id = {record_id}")
        cursor = conn.cursor()

        # Esecuzione della query
        cursor.execute(query, (record_id,))
        result = cursor.fetchone()
        
        # Chiusura del cursore
        cursor.close()

        if result:
            logger.info(f"Retrieved 'norad_code': {result[0]}")
            return result[0]
        else:
            logger.warning(f"No record found with id {record_id} in 'norad_list'")
            raise ValueError(f"Nessun record trovato con id {record_id}")
    except psycopg2.Error as db_error:
        logger.error("Database error while retrieving 'norad_code': %s", db_error)
        raise Exception(f"Errore durante il recupero del NORAD_CAT_ID: {db_error}")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        raise Exception(f"Errore inatteso durante il recupero del NORAD_CAT_ID: {e}")


# ****************************************************************************************
# Sezione 5: Main Application
# ****************************************************************************************

if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"])