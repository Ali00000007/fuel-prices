from flask import Flask, render_template, request
from db import get_latest_prices, get_station_history

app = Flask(__name__)

@app.route("/")
def home():
    rows = get_latest_prices()
    return render_template("prices.html", prices=rows)

@app.route("/history")
def history():
    station = request.args.get("station")
    rows = get_station_history(station)
    return render_template("history.html", prices=rows, station=station)

if __name__ == "__main__":
    app.run(debug=True)