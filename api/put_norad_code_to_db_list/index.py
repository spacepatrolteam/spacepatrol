from Flask import request, jsonify

def handler(event, context):
    # Controlla che la richiesta sia JSON
    if not request.is_json:
        return jsonify({"error": "Unsupported Media Type. Content-Type must be application/json"}), 415

    input_data = request.json
    return jsonify({"status": "success", "message": "NORAD codes saved to database", "data": input_data})
