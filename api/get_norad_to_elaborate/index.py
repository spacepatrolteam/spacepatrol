from Flask import jsonify

def handler(event, context):
    # Simulazione di recupero di NORAD code
    data = {
        "status": "success",
        "norad_code": "25544",
        "subscription_level": "Gold",
        "priority_level": "High",
        "timestamp": "2024-11-22 12:00:00"
    }
    return jsonify(data)
