# Charlottesville Weather Tracker — DS5220 Data Project 3

## What I Built

For this project I decided to track hourly weather conditions in Charlottesville, VA. The idea was pretty simple. Weather changes constantly and in interesting ways, and a time series of temperature readings over days or weeks tells a much betterstory than any single snapshot. I used the Open-Meteo API because it's free, requires no API key, and returns clean, consistent JSON which made it easy to get the pipeline running without any authentication headaches.

Every hour, a Lambda function wakes up, asks Open-Meteo what the weather is like in Charlottesville right now, and stores that reading in DynamoDB. After each write, it also creates a temperature chart and uploads it to S3 so the plot is always fresh.

## How Often It Samples

The ingestion Lambda runs **every hour** via an EventBridge scheduled rule. Each run captures one weather sample and adds it to the DynamoDB table.

## Storage Schema

Data is stored in a DynamoDB table called `weather-data` with the following structure:

| Field | Type | Description |
|-------|------|-------------|
| `location` | String | Partition key — always `"charlottesville"` |
| `timestamp` | Number | Sort key — Unix epoch timestamp of the reading |
| `temperature` | String | Temperature in degrees Celsius |
| `windspeed` | String | Wind speed in km/h |
| `weathercode` | Number | WMO weather condition code (0 = clear sky, 61 = rain, etc.) |

The partition key and sort key design makes it easy to query a time range for any location — exactly what the trend and plot resources need.

## API

**Base URL:** `https://ucpymhly5h.execute-api.us-east-1.amazonaws.com/api`

**Discord project ID:** `tiyeh21_weatherdata`

The API is built with Chalice and shows three resources:

### GET /current

Returns the most recent weather reading from DynamoDB. The response includes the current temperature, a human-readable weather condition (translated from the WMO code), and wind speed.

Example:
```json
{"response": "Charlottesville weather: 8.6°C, Clear sky, wind 8.2 km/h (as of Unix time 1746300000)"}
```

### GET /trend

Looks at all readings from the last 24 hours and computes a simple trend — the average temperature across all samples, and whether the temperature went up or down over the window and by how much.

Example:
```json
{"response": "Over the last 24 hours (12 samples): avg temp 9.1°C, temp trended down by 1.3°C (from 10.2°C to 8.9°C)"}
```

### GET /plot

Returns a public S3 URL pointing to a PNG chart of Charlottesville's temperature over the last 24 hours. The chart is regenerated automatically after every hourly ingest, so it's always up to date (refer to below link).

Example:
```json
{"response": "https://dp3-weather-plots-ty.s3.us-east-1.amazonaws.com/latest.png"}
```

## Architecture Overview

- **EventBridge** fires every hour and triggers the `weather_ingest` Lambda
- **weather_ingest Lambda** fetches from Open-Meteo, writes to DynamoDB, and uploads a fresh plot to S3
- **Chalice API** (`weather-api-dev`) reads from DynamoDB to serve the three resources
- **S3 bucket** `dp3-weather-plots-ty` stores the publicly readable plot image

## Stretch Goals

One thing I would add given more time is parameterized time windows for the trend and plot resources. This would allow users to request something like `GET /plot/7d` or `GET /trend/48h` so users can request data over different periods rather than being fixed to the last 24 hours. Right now the window is hardcoded, but since all the data is stored in DynamoDB with a Unix timestamp sort key, adding that flexibility would just be a matter of parsing the window parameter and adjusting the query range.
