from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/getNoradToElaborate', methods=['GET'])
def get_norad_to_elaborate():
    # Simulazione di recupero di codici NORAD
    data = {"status": "success", "norad_codes": [12345, 67890]}
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True)
