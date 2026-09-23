from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import os
import math

app = FastAPI()

# Catch-all CORS handling
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyticsRequest(BaseModel):
    regions: list[str]
    threshold_ms: float

def calculate_p95(data):
    """Calculates the 95th percentile using linear interpolation (matches standard numpy behavior)"""
    if not data:
        return 0
    sorted_data = sorted(data)
    idx = (len(sorted_data) - 1) * 0.95
    lower = math.floor(idx)
    upper = math.ceil(idx)
    if lower == upper:
        return sorted_data[int(idx)]
    weight = idx - lower
    return (sorted_data[lower] * (1 - weight)) + (sorted_data[upper] * weight)

@app.post("/")
def process_analytics(req: AnalyticsRequest):
    # Locate the JSON file reliably in the Vercel serverless environment
    # First, try the parent directory (root of the repo)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    file_path = os.path.join(base_dir, "q-vercel-latency.json")
    
    # Fallback to current directory just in case
    if not os.path.exists(file_path):
        file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "q-vercel-latency.json")

    try:
        with open(file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        # Prevent hidden 500 crash if file goes missing
        return {"error": "q-vercel-latency.json not found on server"}

    response = {}
    for region in req.regions:
        region_name = region.lower()
        
        # Filter data for the specific region
        region_data = [item for item in data if item.get("region", "").lower() == region_name]
        
        if not region_data:
            response[region] = {
                "avg_latency": 0,
                "p95_latency": 0,
                "avg_uptime": 0,
                "breaches": 0
            }
            continue
        
        latencies = [item["latency_ms"] for item in region_data]
        uptimes = [item["uptime_pct"] for item in region_data]
        
        # Calculations
        avg_latency = sum(latencies) / len(latencies)
        avg_uptime = sum(uptimes) / len(uptimes)
        breaches = sum(1 for lat in latencies if lat > req.threshold_ms)
        p95_latency = calculate_p95(latencies)
        
        response[region] = {
            "avg_latency": round(avg_latency, 2),
            "p95_latency": round(p95_latency, 2),
            "avg_uptime": round(avg_uptime, 3),
            "breaches": breaches
        }
        
    return response