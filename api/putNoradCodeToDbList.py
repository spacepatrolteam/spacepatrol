from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/putNoradCodeToDbList', methods=['POST'])
def put_norad_code_to_db_list():
    # Logica per salvare codici NORAD nel database (simulata)
    input_data = request.json
    response = {"status": "success", "message": "NORAD codes saved to database"}
    return jsonify(response)

if __name__ == '__main__':
    app.run(debug=True)
