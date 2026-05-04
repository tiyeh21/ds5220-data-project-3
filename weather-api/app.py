import logging
import time
import boto3
from boto3.dynamodb.conditions import Key
from chalice import Chalice

logger = logging.getLogger()
logger.setLevel(logging.INFO)

app = Chalice(app_name='weather-api')

DYNAMODB_TABLE = "weather-data"
LOCATION = "charlottesville"
S3_BUCKET = "dp3-weather-plots-ty"
S3_KEY = "latest.png"
REGION = "us-east-1"

dynamodb = boto3.resource("dynamodb", region_name=REGION)
table = dynamodb.Table(DYNAMODB_TABLE)

WEATHER_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Icy fog", 51: "Light drizzle", 53: "Drizzle",
    55: "Heavy drizzle", 61: "Light rain", 63: "Rain", 65: "Heavy rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 80: "Rain showers",
    85: "Snow showers", 95: "Thunderstorm",
}


def query_recent(hours=24):
    since = int(time.time()) - (hours * 3600)
    logger.info(f"Querying DynamoDB for records since {since}")
    try:
        response = table.query(
            KeyConditionExpression=Key("location").eq(LOCATION) & Key("timestamp").gte(since)
        )
        items = response.get("Items", [])
        logger.info(f"Retrieved {len(items)} items")
        return items
    except Exception as e:
        logger.error(f"DynamoDB query failed: {e}")
        raise


@app.route('/')
def index():
    logger.info("GET / called")
    return {
        "about": "Tracks hourly weather in Charlottesville, VA using Open-Meteo. Collects temperature, wind speed, and weather condition over time.",
        "resources": ["current", "trend", "plot"],
    }


@app.route('/current')
def current():
    logger.info("GET /current called")
    try:
        items = query_recent(hours=24)
        if not items:
            logger.warning("No items found in DynamoDB")
            return {"response": "No data available yet."}

        latest = max(items, key=lambda x: int(x["timestamp"]))
        temp = float(latest["temperature"])
        wind = float(latest["windspeed"])
        code = int(latest["weathercode"])
        condition = WEATHER_CODES.get(code, f"Code {code}")
        ts = int(latest["timestamp"])

        response = (
            f"Charlottesville weather: {temp}°C, {condition}, "
            f"wind {wind} km/h (as of Unix time {ts})"
        )
        logger.info(f"Current response: {response}")
        return {"response": response}
    except Exception as e:
        logger.error(f"/current failed: {e}")
        return {"response": f"Error retrieving current weather: {str(e)}"}


@app.route('/trend')
def trend():
    logger.info("GET /trend called")
    try:
        items = query_recent(hours=24)
        if len(items) < 2:
            return {"response": "Not enough data yet for a trend (need at least 2 samples)."}

        sorted_items = sorted(items, key=lambda x: int(x["timestamp"]))
        temps = [float(i["temperature"]) for i in sorted_items]
        avg = sum(temps) / len(temps)
        delta = temps[-1] - temps[0]
        direction = "up" if delta > 0 else "down" if delta < 0 else "unchanged"

        response = (
            f"Over the last 24 hours ({len(temps)} samples): "
            f"avg temp {avg:.1f}°C, "
            f"temp trended {direction} by {abs(delta):.1f}°C "
            f"(from {temps[0]}°C to {temps[-1]}°C)"
        )
        logger.info(f"Trend response: {response}")
        return {"response": response}
    except Exception as e:
        logger.error(f"/trend failed: {e}")
        return {"response": f"Error computing trend: {str(e)}"}


@app.route('/plot')
def plot():
    logger.info("GET /plot called")
    url = f"https://{S3_BUCKET}.s3.{REGION}.amazonaws.com/{S3_KEY}"
    logger.info(f"Returning plot URL: {url}")
    return {"response": url}
