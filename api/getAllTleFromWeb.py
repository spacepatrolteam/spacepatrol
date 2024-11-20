from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/getAllTleFromWeb', methods=['GET'])
def get_all_tle_from_web():
    # Logica di estrazione TLE dal web (simulata qui)
    data = {"status": "success", "message": "TLE data extracted from web"}
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True)
