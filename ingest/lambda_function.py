import json
import logging
import time
import io
import boto3
import urllib.request
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from boto3.dynamodb.conditions import Key
from datetime import datetime, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DYNAMODB_TABLE = "weather-data"
LOCATION = "charlottesville"
S3_BUCKET = "dp3-weather-plots-ty"
S3_KEY = "latest.png"
REGION = "us-east-1"
API_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude=38.03&longitude=-78.48&current_weather=true"
)

dynamodb = boto3.resource("dynamodb", region_name=REGION)
table = dynamodb.Table(DYNAMODB_TABLE)
s3 = boto3.client("s3", region_name=REGION)


def lambda_handler(event, context):
    logger.info("Ingest Lambda started")

    try:
        weather = fetch_weather()
    except Exception as e:
        logger.error(f"Failed to fetch weather data: {e}")
        return {"statusCode": 500, "body": "Fetch failed"}

    try:
        write_to_dynamodb(weather)
    except Exception as e:
        logger.error(f"Failed to write to DynamoDB: {e}")
        return {"statusCode": 500, "body": "Write failed"}

    try:
        generate_and_upload_plot()
    except Exception as e:
        logger.error(f"Failed to generate/upload plot: {e}")

    logger.info("Ingest Lambda completed successfully")
    return {"statusCode": 200, "body": "OK"}


def fetch_weather():
    logger.info(f"Fetching weather from {API_URL}")
    try:
        with urllib.request.urlopen(API_URL, timeout=10) as response:
            raw = response.read()
            data = json.loads(raw)
            logger.info(f"Raw API response: {data}")
            current = data["current_weather"]
            result = {
                "temperature": current["temperature"],
                "windspeed": current["windspeed"],
                "weathercode": current["weathercode"],
            }
            logger.info(f"Parsed weather: {result}")
            return result
    except urllib.error.URLError as e:
        logger.error(f"Network error fetching weather: {e}")
        raise
    except (KeyError, json.JSONDecodeError) as e:
        logger.error(f"Unexpected API response shape: {e}")
        raise


def write_to_dynamodb(weather):
    timestamp = int(time.time())
    item = {
        "location": LOCATION,
        "timestamp": timestamp,
        "temperature": str(weather["temperature"]),
        "windspeed": str(weather["windspeed"]),
        "weathercode": int(weather["weathercode"]),
    }
    logger.info(f"Writing item to DynamoDB: {item}")
    try:
        table.put_item(Item=item)
        logger.info(f"Successfully wrote record with timestamp {timestamp}")
    except Exception as e:
        logger.error(f"DynamoDB put_item failed: {e}")
        raise


def generate_and_upload_plot():
    since = int(time.time()) - (24 * 3600)
    logger.info("Querying last 24 hours of data for plot")
    try:
        response = table.query(
            KeyConditionExpression=Key("location").eq(LOCATION) & Key("timestamp").gte(since)
        )
        items = response.get("Items", [])
        logger.info(f"Retrieved {len(items)} items for plot")

        if len(items) < 2:
            logger.warning("Not enough data to generate plot yet")
            return

        sorted_items = sorted(items, key=lambda x: int(x["timestamp"]))
        timestamps = [int(i["timestamp"]) for i in sorted_items]
        temps = [float(i["temperature"]) for i in sorted_items]
        labels = [datetime.fromtimestamp(t, tz=timezone.utc).strftime("%H:%M") for t in timestamps]

        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(labels, temps, marker="o", linewidth=2, color="steelblue")
        ax.set_title("Charlottesville Temperature (Last 24 Hours)")
        ax.set_xlabel("Time (UTC)")
        ax.set_ylabel("Temperature (°C)")
        ax.tick_params(axis="x", rotation=45)
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)

        logger.info(f"Uploading plot to s3://{S3_BUCKET}/{S3_KEY}")
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=S3_KEY,
            Body=buf.getvalue(),
            ContentType="image/png",
        )
        logger.info("Plot uploaded successfully")
    except Exception as e:
        logger.error(f"Plot generation failed: {e}")
        raise
