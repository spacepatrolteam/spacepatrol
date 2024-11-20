from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/putAllTleInDbList', methods=['POST'])
def put_all_tle_in_db_list():
    # Logica per salvare TLE nel database (simulata)
    input_data = request.json
    response = {"status": "success", "message": "TLE data saved to database"}
    return jsonify(response)

if __name__ == '__main__':
    app.run(debug=True)
