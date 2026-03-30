#!/usr/bin/env python3
import argparse
import http.server
import json
import ssl
import socketserver
from functools import partial
from math import atan2, cos, sin, sqrt
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlencode, urlparse
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parent
VENUES_PATH = PROJECT_ROOT / "data" / "venues.json"
STATIONS_PATH = PROJECT_ROOT / "data" / "stations.json"
STATION_COORDINATES_PATH = PROJECT_ROOT / "data" / "station_coordinates.json"
OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"
NOMINATIM_API_URL = "https://nominatim.openstreetmap.org/search"
APP_USER_AGENT = "afterparty-izakaya-finder/0.1"
stationCoordinateCache = None


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
        if parsedUrl.path == "/api/stations":
            self.serveStations()
            return

        super().do_GET()

    def serveVenues(self, queryString):
        filters = parseFilters(queryString)
        fallbackPayload = loadSampleVenues(filters)

        try:
            liveVenues, resolvedFilters = fetchLiveVenues(filters)
            responsePayload = {
                "venues": liveVenues[:3],
                "count": len(liveVenues),
                "filters": resolvedFilters,
                "source": "live",
                "sourceLabel": "OpenStreetMap / Overpass",
                "attribution": "Map data from OpenStreetMap contributors",
            }
        except (FileNotFoundError, json.JSONDecodeError):
            self.send_error(500, "venues data is invalid")
            return
        except (HTTPError, URLError, TimeoutError, ValueError):
            responsePayload = {
                **fallbackPayload,
                "source": "sample",
                "sourceLabel": "内蔵サンプルデータ",
                "attribution": "",
            }

        responseBody = json.dumps(responsePayload, ensure_ascii=False).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(responseBody)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(responseBody)

    def serveStations(self):
        try:
            payload = STATIONS_PATH.read_text(encoding="utf-8")
            stations = json.loads(payload)
        except FileNotFoundError:
            self.send_error(500, "stations.json not found")
            return
        except json.JSONDecodeError:
            self.send_error(500, "stations.json is invalid")
            return

        responseBody = json.dumps({"lines": stations}, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(responseBody)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(responseBody)


def parseFilters(queryString):
    params = parse_qs(queryString)

    return {
        "searchMode": params.get("searchMode", ["gps"])[0],
        "line": params.get("line", [""])[0],
        "station": params.get("station", [""])[0],
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


def loadSampleVenues(filters):
    resolvedFilters = resolveSearchOrigin(filters)
    payload = VENUES_PATH.read_text(encoding="utf-8")
    venues = json.loads(payload)
    filteredVenues = filterVenues(venues, resolvedFilters)
    return {
        "venues": filteredVenues[:3],
        "count": len(filteredVenues),
        "filters": resolvedFilters,
    }


def resolveSearchOrigin(filters):
    if filters["searchMode"] != "station" or not filters["station"]:
        return filters

    global stationCoordinateCache
    if stationCoordinateCache is None:
        stationCoordinateCache = loadStationCoordinateCache()

    stationKey = f'{filters["line"]}:{filters["station"]}'
    if stationKey in stationCoordinateCache:
        latitude, longitude = stationCoordinateCache[stationKey]
    else:
        latitude, longitude = geocodeStation(filters["line"], filters["station"])
        stationCoordinateCache[stationKey] = (latitude, longitude)
        saveStationCoordinateCache(stationCoordinateCache)

    return {
        **filters,
        "latitude": latitude,
        "longitude": longitude,
    }


def fetchLiveVenues(filters):
    resolvedFilters = resolveSearchOrigin(filters)
    overpassQuery = buildOverpassQuery(resolvedFilters)
    requestUrl = f"{OVERPASS_API_URL}?data={quote(overpassQuery)}"
    request = Request(
        requestUrl,
        headers={
            "User-Agent": APP_USER_AGENT,
            "Accept": "application/json",
        },
    )

    with urlopen(request, timeout=12) as response:
        payload = json.loads(response.read().decode("utf-8"))

    liveVenues = []
    for element in payload.get("elements", []):
        normalizedVenue = normalizeOsmVenue(element, resolvedFilters)
        if normalizedVenue is None:
            continue

        liveVenues.append(normalizedVenue)

    liveVenues.sort(key=lambda venue: venue["score"], reverse=True)
    return liveVenues, resolvedFilters


def geocodeStation(lineKey, stationName):
    queryParts = [stationName, "駅", "東京都"]
    if lineKey == "denentoshi":
        queryParts.append("東急田園都市線")
    elif lineKey == "yamanote":
        queryParts.append("JR山手線")
    elif lineKey == "ginza":
        queryParts.append("東京メトロ銀座線")
    elif lineKey == "marunouchi":
        queryParts.append("東京メトロ丸ノ内線")

    requestQuery = urlencode(
        {
            "q": " ".join(queryParts),
            "format": "jsonv2",
            "limit": "1",
            "countrycodes": "jp",
        }
    )
    request = Request(
        f"{NOMINATIM_API_URL}?{requestQuery}",
        headers={
            "User-Agent": APP_USER_AGENT,
            "Accept": "application/json",
        },
    )

    with urlopen(request, timeout=12) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if not payload:
        raise ValueError("station geocoding failed")

    firstMatch = payload[0]
    return float(firstMatch["lat"]), float(firstMatch["lon"])


def loadStationCoordinateCache():
    try:
        rawPayload = STATION_COORDINATES_PATH.read_text(encoding="utf-8")
        payload = json.loads(rawPayload)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}

    normalizedCache = {}
    for stationKey, coordinatePair in payload.items():
        if not isinstance(coordinatePair, list) or len(coordinatePair) != 2:
            continue
        normalizedCache[stationKey] = (float(coordinatePair[0]), float(coordinatePair[1]))

    return normalizedCache


def saveStationCoordinateCache(cachePayload):
    serializablePayload = {
        stationKey: [coordinates[0], coordinates[1]]
        for stationKey, coordinates in cachePayload.items()
    }
    STATION_COORDINATES_PATH.write_text(
        json.dumps(serializablePayload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def buildOverpassQuery(filters):
    radius = min(max(filters["maxDistanceMeters"], 1000), 5000)

    return f"""
[out:json][timeout:10];
(
  nwr(around:{radius},{filters["latitude"]},{filters["longitude"]})["amenity"~"restaurant|bar|pub|biergarten"];
);
out center tags 40;
"""


def normalizeOsmVenue(element, filters):
    tags = element.get("tags", {})
    venueName = tags.get("name")
    if not venueName:
        return None

    latitude = element.get("lat")
    longitude = element.get("lon")
    center = element.get("center", {})
    if latitude is None:
        latitude = center.get("lat")
    if longitude is None:
        longitude = center.get("lon")

    if latitude is None or longitude is None:
        return None

    cuisineKeys = normalizeCuisines(tags.get("cuisine", ""))
    priceRange = normalizePriceRange(tags)
    openUntilHour = normalizeOpenUntilHour(tags.get("opening_hours", ""))
    nearestStation = buildAreaLabel(tags)
    walkMinutes = max(1, round(getDistanceMeters(filters["latitude"], filters["longitude"], latitude, longitude) / 80))

    normalizedVenue = {
        "id": f'osm-{element.get("type", "node")}-{element.get("id", "unknown")}',
        "name": venueName,
        "latitude": latitude,
        "longitude": longitude,
        "walkMinutes": walkMinutes,
        "nearestStation": nearestStation,
        "openUntilHour": openUntilHour,
        "priceRange": priceRange,
        "minPartySize": 1,
        "maxPartySize": 12,
        "cuisines": cuisineKeys,
        "features": buildFeatures(tags),
    }

    filteredVenues = filterVenues([normalizedVenue], filters)
    if not filteredVenues:
        return None

    return filteredVenues[0]


def normalizeCuisines(rawCuisine):
    cuisineMapping = {
        "japanese": "japanese",
        "izakaya": "japanese",
        "yakitori": "yakitori",
        "chicken": "yakitori",
        "seafood": "seafood",
        "fish": "seafood",
        "korean": "korean",
        "bbq": "meat",
        "steak_house": "meat",
        "burger": "meat",
    }
    normalizedKeys = []

    for rawItem in rawCuisine.split(";"):
        key = cuisineMapping.get(rawItem.strip())
        if key and key not in normalizedKeys:
            normalizedKeys.append(key)

    if not normalizedKeys:
        normalizedKeys.append("japanese")

    return normalizedKeys


def normalizePriceRange(tags):
    fee = tags.get("fee", "")
    if fee == "yes":
        return "mid"

    return "mid"


def normalizeOpenUntilHour(openingHours):
    if "24/7" in openingHours:
        return 29
    if "02:00" in openingHours or "03:00" in openingHours or "04:00" in openingHours:
        return 26
    if "00:00" in openingHours or "01:00" in openingHours:
        return 24
    if "23:00" in openingHours:
        return 23
    if "22:00" in openingHours:
        return 22
    return 24


def buildAreaLabel(tags):
    areaCandidates = [
        tags.get("addr:suburb", ""),
        tags.get("addr:quarter", ""),
        tags.get("addr:city", ""),
    ]

    for candidate in areaCandidates:
        if candidate:
            return candidate

    return "周辺"


def buildFeatures(tags):
    features = []

    if tags.get("outdoor_seating") == "yes":
        features.append("テラス席あり")
    if tags.get("smoking") == "yes":
        features.append("喫煙可")
    if tags.get("takeaway") == "yes":
        features.append("テイクアウト可")
    if tags.get("internet_access") in {"wlan", "yes"}:
        features.append("Wi-Fiあり")

    if tags.get("opening_hours"):
        features.append("営業時間データあり")
    else:
        features.append("営業時間は要確認")

    return features[:3]


def main():
    parser = argparse.ArgumentParser(description="Serve the afterparty izakaya finder.")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind")
    parser.add_argument("--port", type=int, default=8123, help="Port to bind")
    parser.add_argument("--directory", default=".", help="Directory to serve")
    parser.add_argument("--certfile", default="", help="TLS certificate file")
    parser.add_argument("--keyfile", default="", help="TLS private key file")
    args = parser.parse_args()

    handlerClass = partial(AppRequestHandler, directory=args.directory)

    with ReusableTcpServer((args.host, args.port), handlerClass) as httpd:
        if args.certfile and args.keyfile:
            sslContext = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            sslContext.load_cert_chain(certfile=args.certfile, keyfile=args.keyfile)
            httpd.socket = sslContext.wrap_socket(httpd.socket, server_side=True)
        print(f"Serving {args.directory} at http://{args.host}:{args.port}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
