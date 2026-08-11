from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request
import arrow
import json
import os
import redis
import requests

load_dotenv()
APPID = os.environ["appid"]

app = Flask(__name__)
r = redis.Redis(host='redis',port=6379, decode_responses=True)

LIMIT = 600 # how many seconds before we need to fetch new data
@app.route("/")
def hello_world():
    return render_template('index.html')

# provides datetimeformat for use in Jinja tekmplates
@app.template_filter('datetimeformat')
def datetimeformat(value, format='%Y-%m-%d %H:%M:%S'):
    if value is None:
        return ""
    # if timestamp is a numeric string
    if isinstance(value, (int, float, str)):
        value = datetime.fromtimestamp(float(value))
    return value.strftime(format)
@app.route("/location")
def get_location_weather():
    q = request.args.get('q','')
    # from here we need to talk to the geocode service
    url = f"http://geolocate/geolocate?q={q}"
    response = requests.get(url)

    resp_json = response.json()

    # geolocate service returns an empty (or missing) places list when it
    # can't match the zip code / location the user searched for
    if not resp_json.get('places'):
        return render_template('index.html', error=f"No results found for '{q}'. Please try a different zip code or location.")

    # create some vars we will use later
    place_name = resp_json['places'][0]['place name']
    place_state = resp_json['places'][0]['state']
    place_abbr = resp_json['places'][0]['state abbreviation']
    place_lat = resp_json['places'][0]['latitude']
    place_long = resp_json['places'][0]['longitude']
    place_zip = resp_json['post code']

    try:
        cached_hit = r.get(f"location:{place_zip}")
        cached_data = json.loads(cached_hit)
        #print(cached_data['dt'])

    except:
        print(f"did not find location:{place_zip} in cached results")

    # check cached data age 
    ts = arrow.now().int_timestamp
    try:
        diff = ts - cached_data['dt']
    except:
        print("no cached data can be found")
        diff = 9999 # set limit to ensure new data is fetched
    if diff > LIMIT:
        print("LOG: diff has exceeded LIMIT value")
        r.delete(f"location:{place_zip}")
        weather_url = f"https://api.openweathermap.org/data/2.5/weather?lat={place_lat}&lon={place_long}&exclude=%7Bpart%7D&appid={APPID}&units=imperial"
        
        weather_resp = requests.get(weather_url)
        # commented out API call, provided static object for testing purposes

        #weather_resp = {'coord': {'lon': -78.0941, 'lat': 39.1973}, 'weather': [{'id': 800, 'main': 'Clear', 'description': 'clear sky', 'icon': '01d'}], 'base': 'stations', 'main': {'temp': 83.37, 'feels_like': 84.74, 'temp_min': 81.41, 'temp_max': 85.17, 'pressure': 1012, 'humidity': 52, 'sea_level': 1012, 'grnd_level': 986}, 'visibility': 10000, 'wind': {'speed': 12.06, 'deg': 331, 'gust': 15.61}, 'clouds': {'all': 2}, 'dt': 1785438465, 'sys': {'type': 2, 'id': 2009416, 'country': 'US', 'sunrise': 1785406245, 'sunset': 1785457600}, 'timezone': -14400, 'id': 4794120, 'name': 'Winchester', 'cod': 200}

        # lets store this information in Reids now
        r.set(f"location:{place_zip}",json.dumps(weather_resp.json()))
        #print(weather_resp)
        #print("RESPONSE: ", resp_json['places'][0]['place name'])
        return render_template('weather.html',data=weather_resp.json(), geo=resp_json['places'][0])
    elif diff < LIMIT:
        # diff is less than 10 minutes, we can reliably display it
        print(f"Rendering cached data to save API calls")
        return render_template('weather.html',data=cached_data, geo=resp_json['places'][0])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port="5000")
