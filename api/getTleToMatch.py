from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/getTleToMatch', methods=['GET'])
def get_tle_to_match():
    # Logica per recuperare TLE da associare (simulata)
    data = {"status": "success", "tle_list": ["TLE1", "TLE2"]}
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True)
