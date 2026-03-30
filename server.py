#!/usr/bin/env python3
import argparse
import http.server
import json
import socketserver
from functools import partial
from math import atan2, cos, sin, sqrt
from pathlib import Path
from urllib.parse import parse_qs, urlparse


PROJECT_ROOT = Path(__file__).resolve().parent
VENUES_PATH = PROJECT_ROOT / "data" / "venues.json"


class ReusableTcpServer(socketserver.TCPServer):
    allow_reuse_address = True


class AppRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, directory=None, **kwargs):
        self.projectDirectory = Path(directory or ".").resolve()
        super().__init__(*args, directory=str(self.projectDirectory), **kwargs)

    def do_GET(self):
        parsedUrl = urlparse(self.path)

        if parsedUrl.path == "/api/venues":
            self.serveVenues(parsedUrl.query)
            return

        super().do_GET()

    def serveVenues(self, queryString):
        try:
            payload = VENUES_PATH.read_text(encoding="utf-8")
            venues = json.loads(payload)
        except FileNotFoundError:
            self.send_error(500, "venues.json not found")
            return
        except json.JSONDecodeError:
            self.send_error(500, "venues.json is invalid")
            return

        filters = parseFilters(queryString)
        filteredVenues = filterVenues(venues, filters)
        responseBody = json.dumps(
            {
                "venues": filteredVenues[:3],
                "count": len(filteredVenues),
                "filters": filters,
            },
            ensure_ascii=False,
        ).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(responseBody)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(responseBody)


def parseFilters(queryString):
    params = parse_qs(queryString)

    return {
        "partySize": parseInt(params.get("partySize", ["4"])[0], 4),
        "maxBudget": params.get("budget", ["low"])[0],
        "cuisine": params.get("cuisine", ["any"])[0],
        "maxDistanceMeters": parseInt(params.get("distance", ["2500"])[0], 2500),
        "requireOpenAfter21": params.get("openAfter21", ["true"])[0] != "false",
        "latitude": parseFloat(params.get("latitude", ["35.6895"])[0], 35.6895),
        "longitude": parseFloat(params.get("longitude", ["139.6917"])[0], 139.6917),
    }


def parseInt(rawValue, defaultValue):
    try:
        return int(rawValue)
    except (TypeError, ValueError):
        return defaultValue


def parseFloat(rawValue, defaultValue):
    try:
        return float(rawValue)
    except (TypeError, ValueError):
        return defaultValue


def toRadians(value):
    return (value * 3.141592653589793) / 180


def getDistanceMeters(fromLatitude, fromLongitude, toLatitude, toLongitude):
    earthRadius = 6371000
    latitudeDiff = toRadians(toLatitude - fromLatitude)
    longitudeDiff = toRadians(toLongitude - fromLongitude)
    aValue = (
        (sin(latitudeDiff / 2) ** 2)
        + cos(toRadians(fromLatitude))
        * cos(toRadians(toLatitude))
        * (sin(longitudeDiff / 2) ** 2)
    )

    return 2 * earthRadius * atan2(sqrt(aValue), sqrt(1 - aValue))


def fitsBudget(venuePrice, selectedBudget):
    budgetOrder = ["low", "mid", "high"]
    return budgetOrder.index(venuePrice) <= budgetOrder.index(selectedBudget)


def buildScore(venue, distanceMeters):
    distanceScore = max(0, 5000 - distanceMeters) / 100

    if venue["openUntilHour"] >= 26:
        lateNightScore = 25
    elif venue["openUntilHour"] >= 24:
        lateNightScore = 16
    else:
        lateNightScore = 8

    if venue["priceRange"] == "low":
        priceScore = 18
    elif venue["priceRange"] == "mid":
        priceScore = 12
    else:
        priceScore = 6

    return distanceScore + lateNightScore + priceScore


def filterVenues(venues, filters):
    rankedVenues = []

    for venue in venues:
        distanceMeters = getDistanceMeters(
            filters["latitude"],
            filters["longitude"],
            venue["latitude"],
            venue["longitude"],
        )

        if distanceMeters > filters["maxDistanceMeters"]:
            continue

        if not fitsBudget(venue["priceRange"], filters["maxBudget"]):
            continue

        if not (venue["minPartySize"] <= filters["partySize"] <= venue["maxPartySize"]):
            continue

        if filters["cuisine"] != "any" and filters["cuisine"] not in venue["cuisines"]:
            continue

        if filters["requireOpenAfter21"] and venue["openUntilHour"] < 21:
            continue

        rankedVenues.append(
            {
                **venue,
                "distanceMeters": distanceMeters,
                "score": buildScore(venue, distanceMeters),
            }
        )

    rankedVenues.sort(key=lambda venue: venue["score"], reverse=True)
    return rankedVenues


def main():
    parser = argparse.ArgumentParser(description="Serve the afterparty izakaya finder.")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind")
    parser.add_argument("--port", type=int, default=8123, help="Port to bind")
    parser.add_argument("--directory", default=".", help="Directory to serve")
    args = parser.parse_args()

    handlerClass = partial(AppRequestHandler, directory=args.directory)

    with ReusableTcpServer((args.host, args.port), handlerClass) as httpd:
        print(f"Serving {args.directory} at http://{args.host}:{args.port}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
