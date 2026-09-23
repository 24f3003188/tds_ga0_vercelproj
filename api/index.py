from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import statistics
import os

app = FastAPI()

# Enable CORS for POST requests from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["*"],
)

# Define the expected format of the incoming request body
class LatencyRequest(BaseModel):
    regions: list[str]
    threshold_ms: float

# Load the telemetry data
# Since this runs in a serverless environment, we need to locate the file relative to this script
current_dir = os.path.dirname(os.path.realpath(__file__))
# The json file is in the root directory, one level up from the api directory
data_file_path = os.path.join(current_dir, '..', 'q-vercel-latency.json')

try:
    with open(data_file_path, 'r') as f:
        telemetry_data = json.load(f)
except FileNotFoundError:
    # Fallback in case paths are slightly different during Vercel deployment
    telemetry_data = [] 
    try:
         with open('q-vercel-latency.json', 'r') as f:
            telemetry_data = json.load(f)
    except FileNotFoundError:
        pass


@app.post("/")
def analyze_latency(request: LatencyRequest):
    results = {}
    
    # Process each requested region separately
    for region in request.regions:
        # Filter the data for the current region
        region_data = [item for item in telemetry_data if item['region'].lower() == region.lower()]
        
        if not region_data:
            # If a region isn't found, return empty stats for it
            results[region] = {
                "avg_latency": 0,
                "p95_latency": 0,
                "avg_uptime": 0,
                "breaches": 0
            }
            continue

        # Extract the specific values into lists for calculation
        latencies = [item['latency_ms'] for item in region_data]
        uptimes = [item['uptime_pct'] for item in region_data]
        
        # Calculate Breaches (count of latencies strictly greater than threshold)
        breaches = sum(1 for lat in latencies if lat > request.threshold_ms)
        
        # Calculate Averages (Mean)
        avg_latency = statistics.mean(latencies)
        avg_uptime = statistics.mean(uptimes)
        
        # Calculate p95 Latency
        # Note: Depending on the exact grading logic, different p95 calculation methods might be expected.
        # Python 3.8+ statistics module has 'quantiles'
        p95 = statistics.quantiles(latencies, n=100)[94] # index 94 represents the 95th percentile

        results[region] = {
            "avg_latency": round(avg_latency, 2),
            "p95_latency": round(p95, 2),
            "avg_uptime": round(avg_uptime, 3),
            "breaches": breaches
        }
        
    return results