#!/usr/bin/env python3
import argparse
import http.server
import html
import json
import os
import re
import ssl
import socketserver
from functools import partial
from math import atan2, cos, sin, sqrt
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlencode, urlparse, unquote_plus
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parent
VENUES_PATH = PROJECT_ROOT / "data" / "venues.json"
STATIONS_PATH = PROJECT_ROOT / "data" / "stations.json"
STATION_COORDINATES_PATH = PROJECT_ROOT / "data" / "station_coordinates.json"
OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"
HOTPEPPER_GOURMET_API_URL = "https://webservice.recruit.co.jp/hotpepper/gourmet/v1/"
NOMINATIM_SEARCH_API_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE_API_URL = "https://nominatim.openstreetmap.org/reverse"
OSRM_TABLE_API_URL = "https://router.project-osrm.org/table/v1/foot/"
APP_USER_AGENT = "afterparty-izakaya-finder/0.1"
HOTPEPPER_API_KEY = os.environ.get("HOTPEPPER_API_KEY", "").strip()
stationCoordinateCache = None
stationLinesIndex = None
hotpepperGuideCache = {}
stationAccessAliases = {
    "新宿": ["新宿", "新宿三丁目", "新宿西口", "西新宿", "南新宿", "代々木"],
    "渋谷": ["渋谷", "神泉", "表参道"],
    "飯田橋": ["飯田橋", "水道橋", "九段下", "神楽坂", "後楽園"],
    "下北沢": ["下北沢", "東北沢", "池ノ上"],
}


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
        if parsedUrl.path == "/api/location-label":
            self.serveLocationLabel(parsedUrl.query)
            return

        super().do_GET()

    def serveVenues(self, queryString):
        filters = parseFilters(queryString)
        try:
            hotpepperVenues, resolvedFilters = fetchHotpepperVenues(filters)
            responsePayload = {
                "venues": hotpepperVenues[:12],
                "count": len(hotpepperVenues),
                "filters": resolvedFilters,
                "source": "hotpepper",
                "sourceLabel": "ホットペッパーグルメ",
                "attribution": "Powered by ホットペッパーグルメ Webサービス",
            }
        except (HTTPError, URLError, TimeoutError, ValueError):
            try:
                liveVenues, resolvedFilters = fetchLiveVenues(filters)
                responsePayload = {
                    "venues": liveVenues[:12],
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
                try:
                    fallbackPayload = loadSampleVenues(filters)
                    responsePayload = {
                        **fallbackPayload,
                        "source": "sample",
                        "sourceLabel": "内蔵サンプルデータ",
                        "attribution": "",
                    }
                except (FileNotFoundError, json.JSONDecodeError):
                    self.send_error(500, "venues data is invalid")
                    return
                except (HTTPError, URLError, TimeoutError, ValueError):
                    responsePayload = {
                        "venues": [],
                        "count": 0,
                        "filters": filters,
                        "source": "empty",
                        "sourceLabel": "検索結果なし",
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

    def serveLocationLabel(self, queryString):
        params = parse_qs(queryString)
        latitude = parseFloat(params.get("latitude", ["35.6895"])[0], 35.6895)
        longitude = parseFloat(params.get("longitude", ["139.6917"])[0], 139.6917)

        try:
            locationLabel = reverseGeocodeLocation(latitude, longitude)
        except (HTTPError, URLError, TimeoutError, ValueError):
            locationLabel = f"{latitude:.5f}, {longitude:.5f}"

        responseBody = json.dumps({"label": locationLabel}, ensure_ascii=False).encode("utf-8")
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
        "station": unquote_plus(params.get("station", [""])[0]),
        "partySize": parseInt(params.get("partySize", ["4"])[0], 4),
        "maxBudget": "mid",
        "cuisine": params.get("cuisine", ["any"])[0],
        "smoking": params.get("smoking", ["any"])[0],
        "maxDistanceMeters": parseInt(params.get("distance", ["2000"])[0], 2000),
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

    return distanceScore + lateNightScore + priceScore + buildGenrePriorityScore(venue)


def buildGenrePriorityScore(venue):
    genreText = " ".join(
        [
            venue.get("genreLabel", ""),
            venue.get("subGenreLabel", ""),
            venue.get("name", ""),
        ]
    )

    if any(keyword in genreText for keyword in ["和風", "居酒屋", "酒場", "大衆酒場"]):
        return 28

    if any(
        keyword in genreText
        for keyword in [
            "魚民",
            "笑笑",
            "白木屋",
            "山内農場",
            "鳥貴族",
            "磯丸",
            "ミライザカ",
            "さかなや道場",
            "庄や",
            "天狗",
            "金の蔵",
            "一軒め酒場",
            "さくら水産",
            "養老乃瀧",
            "つぼ八",
        ]
    ):
        return 24

    if any(keyword in genreText for keyword in ["バー", "BAR", "バル", "ダイニングバー", "カラオケ"]):
        return 20

    if any(keyword in genreText for keyword in ["焼き鳥", "鶏料理"]):
        return 16

    return 0


def filterVenues(venues, filters):
    rankedVenues = []

    for venue in venues:
        distanceMeters = 0
        if filters["searchMode"] != "station":
            distanceMeters = getDistanceMeters(
                filters["latitude"],
                filters["longitude"],
                venue["latitude"],
                venue["longitude"],
            )
        elif venue.get("distanceMeters") is not None:
            distanceMeters = float(venue["distanceMeters"])
        elif venue.get("stationWalkMinutes") is not None:
            distanceMeters = float(venue["stationWalkMinutes"] * 80)

        if filters["searchMode"] != "station" and distanceMeters > filters["maxDistanceMeters"]:
            continue

        if not fitsBudget(venue["priceRange"], filters["maxBudget"]):
            continue

        if filters["cuisine"] != "any" and filters["cuisine"] not in venue["cuisines"]:
            continue

        if filters["smoking"] == "non-smoking" and venue.get("smokingLabel") not in {"禁煙", "分煙"}:
            continue

        if filters["smoking"] == "smoking" and venue.get("smokingLabel") not in {"喫煙可", "分煙"}:
            continue

        if filters["requireOpenAfter21"] and venue["openUntilHour"] < 21:
            continue

        walkMinutes = max(1, round(distanceMeters / 80))
        if filters["searchMode"] == "station":
            hotpepperWalkMinutes = venue.get("stationWalkMinutes")
            if hotpepperWalkMinutes is None or hotpepperWalkMinutes > 10:
                continue
            walkMinutes = hotpepperWalkMinutes
        rankedVenues.append(
            {
                **venue,
                "distanceMeters": distanceMeters,
                "walkMinutes": walkMinutes,
                "score": buildScore(venue, distanceMeters),
            }
        )

    rankedVenues.sort(
        key=lambda venue: (
            round(venue["distanceMeters"]),
            venue["walkMinutes"],
            -venue["openUntilHour"],
            venue["name"],
        )
    )
    return rankedVenues


def limitStationWalkTime(venues, filters):
    if filters["searchMode"] != "station":
        return venues

    return [venue for venue in venues if venue.get("stationWalkMinutes") and venue["stationWalkMinutes"] <= 10]


def loadSampleVenues(filters):
    resolvedFilters = resolveSearchOrigin(filters)
    payload = VENUES_PATH.read_text(encoding="utf-8")
    venues = json.loads(payload)
    filteredVenues = filterVenues(venues, resolvedFilters)
    return {
        "venues": filteredVenues[:12],
        "count": len(filteredVenues),
        "filters": resolvedFilters,
    }


def resolveSearchOrigin(filters):
    if filters["searchMode"] != "station" or not filters["station"]:
        return filters

    global stationCoordinateCache
    if stationCoordinateCache is None:
        stationCoordinateCache = loadStationCoordinateCache()

    canonicalLineKey = resolveStationLine(filters["line"], filters["station"])
    stationKey = f"{canonicalLineKey}:{filters['station']}"
    if stationKey in stationCoordinateCache:
        latitude, longitude = stationCoordinateCache[stationKey]
    else:
        latitude, longitude = geocodeStation(canonicalLineKey, filters["station"])
        stationCoordinateCache[stationKey] = (latitude, longitude)
        saveStationCoordinateCache(stationCoordinateCache)

    return {
        **filters,
        "line": canonicalLineKey,
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

    liveVenues = enrichWalkingMetrics(liveVenues, resolvedFilters)
    liveVenues = limitStationWalkTime(liveVenues, resolvedFilters)
    liveVenues.sort(
        key=lambda venue: (
            round(venue["distanceMeters"]),
            venue["walkMinutes"],
            -venue["openUntilHour"],
            venue["name"],
        )
    )
    return liveVenues, resolvedFilters


def fetchHotpepperVenues(filters):
    if not HOTPEPPER_API_KEY:
        raise ValueError("hotpepper api key is missing")

    if filters["searchMode"] == "station" and filters["station"]:
        return fetchHotpepperStationVenues(filters)

    resolvedFilters = resolveSearchOrigin(filters)
    filteredVenues = loadHotpepperCandidates(
        resolvedFilters,
        filters["maxBudget"],
        mapHotpepperRange(filters["maxDistanceMeters"]),
        "30",
        True,
    )
    if not filteredVenues and resolvedFilters["searchMode"] == "station":
        filteredVenues = loadHotpepperCandidates(
            resolvedFilters,
            filters["maxBudget"],
            "5",
            "100",
            False,
        )
    filteredVenues = enrichWalkingMetrics(filteredVenues, resolvedFilters)
    filteredVenues = limitStationWalkTime(filteredVenues, resolvedFilters)
    filteredVenues.sort(
        key=lambda venue: (
            round(venue["distanceMeters"]),
            venue["walkMinutes"],
            -venue["openUntilHour"],
            venue["name"],
        )
    )
    return filteredVenues, resolvedFilters


def fetchHotpepperStationVenues(filters):
    stationFilters = {
        **filters,
        "latitude": 0,
        "longitude": 0,
    }
    stationCandidates = loadHotpepperStationCandidates(
        stationFilters,
        filters["maxBudget"],
        True,
    )
    if not stationCandidates:
        stationCandidates = loadHotpepperStationCandidates(
            stationFilters,
            filters["maxBudget"],
            False,
        )

    stationCandidates.sort(
        key=lambda venue: (
            venue["walkMinutes"],
            -buildGenrePriorityScore(venue),
            -venue["openUntilHour"],
            venue["name"],
        )
    )
    return stationCandidates, stationFilters


def loadHotpepperStationCandidates(filters, maxBudget, includeBudget):
    requestParams = [
        ("key", HOTPEPPER_API_KEY),
        ("format", "json"),
        ("keyword", filters["station"]),
        ("service_area", "SA11"),
        ("genre", "G001"),
        ("genre", "G012"),
        ("genre", "G014"),
        ("count", "100"),
        ("order", "4"),
    ]

    if includeBudget:
        for budgetCode in mapHotpepperBudgetCodes(maxBudget):
            requestParams.append(("budget", budgetCode))

    request = Request(
        f"{HOTPEPPER_GOURMET_API_URL}?{urlencode(requestParams)}",
        headers={
            "User-Agent": APP_USER_AGENT,
            "Accept": "application/json",
        },
    )

    with urlopen(request, timeout=12) as response:
        payload = json.loads(response.read().decode("utf-8"))

    shops = payload.get("results", {}).get("shop", [])
    normalizedVenues = []
    for shop in shops:
        normalizedVenue = normalizeHotpepperVenue(shop)
        if normalizedVenue is None:
            continue
        normalizedVenues.append(normalizedVenue)

    normalizedVenues = applyHotpepperStationGuides(normalizedVenues, filters["station"])
    return filterVenues(normalizedVenues, filters)


def loadHotpepperCandidates(resolvedFilters, maxBudget, rangeCode, count, includeBudget):
    requestParams = [
        ("key", HOTPEPPER_API_KEY),
        ("format", "json"),
        ("lat", f'{resolvedFilters["latitude"]:.6f}'),
        ("lng", f'{resolvedFilters["longitude"]:.6f}'),
        ("range", rangeCode),
        ("count", count),
        ("order", "4"),
    ]

    if includeBudget:
        for budgetCode in mapHotpepperBudgetCodes(maxBudget):
            requestParams.append(("budget", budgetCode))

    request = Request(
        f"{HOTPEPPER_GOURMET_API_URL}?{urlencode(requestParams)}",
        headers={
            "User-Agent": APP_USER_AGENT,
            "Accept": "application/json",
        },
    )

    with urlopen(request, timeout=12) as response:
        payload = json.loads(response.read().decode("utf-8"))

    shops = payload.get("results", {}).get("shop", [])
    normalizedVenues = []
    for shop in shops:
        normalizedVenue = normalizeHotpepperVenue(shop)
        if normalizedVenue is None:
            continue
        normalizedVenues.append(normalizedVenue)

    if resolvedFilters["searchMode"] == "station":
        normalizedVenues = applyHotpepperStationGuides(normalizedVenues, resolvedFilters["station"])

    return filterVenues(normalizedVenues, resolvedFilters)


def geocodeStation(lineKey, stationName):
    payload = searchStationCoordinates(buildStationQueryParts(lineKey, stationName))
    if payload:
        firstMatch = payload[0]
        return float(firstMatch["lat"]), float(firstMatch["lon"])

    fallbackPayload = searchStationCoordinates([stationName, "駅", "東京都"])
    if fallbackPayload:
        firstMatch = fallbackPayload[0]
        return float(firstMatch["lat"]), float(firstMatch["lon"])

    raise ValueError("station geocoding failed")


def buildStationQueryParts(lineKey, stationName):
    queryParts = [stationName, "駅", "東京都"]
    if lineKey == "denentoshi":
        queryParts.append("東急田園都市線")
    elif lineKey == "yamanote":
        queryParts.append("JR山手線")
    elif lineKey == "ginza":
        queryParts.append("東京メトロ銀座線")
    elif lineKey == "marunouchi":
        queryParts.append("東京メトロ丸ノ内線")
    elif lineKey == "tozai":
        queryParts.append("東京メトロ東西線")
    elif lineKey == "namboku":
        queryParts.append("東京メトロ南北線")
    elif lineKey == "yurakucho":
        queryParts.append("東京メトロ有楽町線")
    elif lineKey == "oedo":
        queryParts.append("都営大江戸線")
    elif lineKey == "odakyu":
        queryParts.append("小田急小田原線")

    return queryParts


def searchStationCoordinates(queryParts):
    requestQuery = urlencode(
        {
            "q": " ".join(queryParts),
            "format": "jsonv2",
            "limit": "1",
            "countrycodes": "jp",
        }
    )
    request = Request(
        f"{NOMINATIM_SEARCH_API_URL}?{requestQuery}",
        headers={
            "User-Agent": APP_USER_AGENT,
            "Accept": "application/json",
        },
    )

    with urlopen(request, timeout=12) as response:
        return json.loads(response.read().decode("utf-8"))


def resolveStationLine(lineKey, stationName):
    stationLines = loadStationLinesIndex().get(stationName, [])
    if not stationLines:
        return lineKey
    if lineKey in stationLines:
        return lineKey
    return stationLines[0]


def loadStationLinesIndex():
    global stationLinesIndex
    if stationLinesIndex is not None:
        return stationLinesIndex

    try:
        rawPayload = STATIONS_PATH.read_text(encoding="utf-8")
        payload = json.loads(rawPayload)
    except (FileNotFoundError, json.JSONDecodeError):
        stationLinesIndex = {}
        return stationLinesIndex

    indexedLines = {}
    for lineKey, lineValue in payload.items():
        for stationName in lineValue.get("stations", []):
            indexedLines.setdefault(stationName, []).append(lineKey)

    stationLinesIndex = indexedLines
    return stationLinesIndex


def reverseGeocodeLocation(latitude, longitude):
    requestQuery = urlencode(
        {
            "lat": str(latitude),
            "lon": str(longitude),
            "format": "jsonv2",
            "addressdetails": "1",
            "zoom": "18",
        }
    )
    request = Request(
        f"{NOMINATIM_REVERSE_API_URL}?{requestQuery}",
        headers={
            "User-Agent": APP_USER_AGENT,
            "Accept": "application/json",
        },
    )

    with urlopen(request, timeout=12) as response:
        payload = json.loads(response.read().decode("utf-8"))

    address = payload.get("address", {})
    detailedParts = [
        address.get("postcode"),
        address.get("state"),
        address.get("city"),
        address.get("city_district"),
        address.get("suburb"),
        address.get("quarter"),
        address.get("neighbourhood"),
        address.get("road"),
        address.get("block"),
        address.get("house_number"),
    ]
    normalizedParts = []
    for detailedPart in detailedParts:
        if detailedPart and detailedPart not in normalizedParts:
            normalizedParts.append(detailedPart)

    if normalizedParts:
        return " ".join(normalizedParts)

    displayName = payload.get("display_name")
    if displayName:
        displayParts = [part.strip() for part in displayName.split(",") if part.strip()]
        return ", ".join(displayParts[:4])

    raise ValueError("reverse geocoding failed")


def mapHotpepperRange(maxDistanceMeters):
    if maxDistanceMeters <= 300:
        return "1"
    if maxDistanceMeters <= 500:
        return "2"
    if maxDistanceMeters <= 1000:
        return "3"
    if maxDistanceMeters <= 2000:
        return "4"
    return "5"


def mapHotpepperBudgetCodes(maxBudget):
    if maxBudget == "mid":
        return ["B009", "B010", "B011", "B001", "B002", "B003", "B008", "B004"]
    return ["B005", "B006", "B012", "B013", "B014"]


def normalizeHotpepperVenue(shop):
    try:
        latitude = float(shop["lat"])
        longitude = float(shop["lng"])
    except (KeyError, TypeError, ValueError):
        return None

    budgetCode = shop.get("budget", {}).get("code", "")
    if budgetCode in {"B005", "B006", "B012", "B013", "B014"}:
        priceRange = "high"
    elif budgetCode in {"B003", "B008", "B004"}:
        priceRange = "mid"
    else:
        priceRange = "low"

    genreNames = [shop.get("genre", {}).get("name", ""), shop.get("sub_genre", {}).get("name", "")]
    joinedGenres = " ".join(genreNames)
    if any(
        keyword in joinedGenres
        for keyword in [
            "フレンチ",
            "イタリアン",
            "ビストロ",
            "スペイン",
            "各国料理",
            "カフェ",
            "カレー",
            "ラーメン",
            "定食",
            "喫茶",
            "アジア・エスニック料理",
            "その他グルメ",
            "お好み焼き・もんじゃ",
            "韓国料理",
            "中華",
            "焼肉・ホルモン",
            "洋食",
        ]
    ):
        return None
    if not any(
        keyword in joinedGenres or keyword in shop.get("name", "")
        for keyword in [
            "居酒屋",
            "和風",
            "焼き鳥",
            "鶏料理",
            "酒場",
            "バー",
            "BAR",
            "バル",
            "ダイニングバー",
            "魚民",
            "笑笑",
            "白木屋",
            "山内農場",
            "鳥貴族",
            "磯丸",
            "ミライザカ",
            "さかなや道場",
            "庄や",
            "天狗",
            "金の蔵",
            "一軒め酒場",
            "さくら水産",
            "養老乃瀧",
            "つぼ八",
            "カラオケ",
        ]
    ):
        return None
    cuisineKeys = normalizeHotpepperCuisines(genreNames)
    openInfo = normalizeHotpepperOpenInfo(shop.get("open", ""), shop.get("midnight", ""))
    features = buildHotpepperFeatures(shop)

    return {
        "id": shop.get("id", ""),
        "name": shop.get("name", "店名不明"),
        "latitude": latitude,
        "longitude": longitude,
        "walkMinutes": 0,
        "stationWalkMinutes": None,
        "nearestStation": shop.get("station_name", "現在地周辺"),
        "accessText": shop.get("access", ""),
        "openUntilHour": openInfo["closeHour"],
        "closeLabel": openInfo["closeLabel"],
        "lastOrderLabel": openInfo["lastOrderLabel"],
        "priceRange": priceRange,
        "smokingLabel": normalizeHotpepperSmokingLabel(shop.get("non_smoking", "")),
        "genreLabel": shop.get("genre", {}).get("name", ""),
        "subGenreLabel": shop.get("sub_genre", {}).get("name", ""),
        "minPartySize": 1,
        "maxPartySize": parseInt(shop.get("party_capacity"), 12),
        "cuisines": cuisineKeys,
        "features": features,
        "address": shop.get("address", ""),
        "hotpepperUrl": shop.get("urls", {}).get("pc", ""),
        "photoUrl": shop.get("photo", {}).get("pc", {}).get("m", ""),
        "budgetText": shop.get("budget", {}).get("average", "") or shop.get("budget", {}).get("name", ""),
    }


def enrichWalkingMetrics(venues, filters):
    if not venues:
        return venues

    coordinates = [f'{filters["longitude"]},{filters["latitude"]}']
    for venue in venues:
        coordinates.append(f'{venue["longitude"]},{venue["latitude"]}')

    requestQuery = urlencode(
        {
            "sources": "0",
            "annotations": "duration,distance",
        }
    )
    request = Request(
        f'{OSRM_TABLE_API_URL}{";".join(coordinates)}?{requestQuery}',
        headers={
            "User-Agent": APP_USER_AGENT,
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, ValueError):
        return venues

    durations = payload.get("durations", [])
    distances = payload.get("distances", [])
    if not durations or not distances:
        return venues

    sourceDurations = durations[0]
    sourceDistances = distances[0]
    for index, venue in enumerate(venues, start=1):
        routeDuration = sourceDurations[index] if index < len(sourceDurations) else None
        routeDistance = sourceDistances[index] if index < len(sourceDistances) else None
        if routeDuration is None or routeDistance is None:
            continue

        venue["distanceMeters"] = float(routeDistance)
        if filters["searchMode"] != "station":
            venue["walkMinutes"] = max(1, round(float(routeDuration) / 60))
        venue["score"] = buildScore(venue, venue["distanceMeters"])

    return venues


def applyHotpepperStationGuides(venues, targetStationName):
    for venue in venues:
        guideText = fetchHotpepperGuideText(venue["id"]) or venue.get("accessText", "")
        venue["stationGuideText"] = guideText
        venue["stationWalkMinutes"] = extractStationWalkMinutes(
            targetStationName,
            guideText,
            venue.get("nearestStation", ""),
        )

    return venues


def normalizeHotpepperCuisines(genreNames):
    joinedNames = " ".join(genreNames)
    cuisineKeys = []
    if "焼き鳥" in joinedNames:
        cuisineKeys.append("yakitori")
    if "海鮮" in joinedNames or "魚" in joinedNames:
        cuisineKeys.append("seafood")
    if "韓国" in joinedNames:
        cuisineKeys.append("korean")
    if "肉" in joinedNames or "焼肉" in joinedNames or "ステーキ" in joinedNames:
        cuisineKeys.append("meat")
    if "創作" in joinedNames or "ダイニング" in joinedNames or "イタリアン" in joinedNames:
        cuisineKeys.append("creative")
    if not cuisineKeys:
        cuisineKeys.append("japanese")
    return cuisineKeys


def normalizeHotpepperSmokingLabel(nonSmokingText):
    normalizedText = str(nonSmokingText).strip()
    if not normalizedText or normalizedText == "未確認":
        return "要確認"
    if any(keyword in normalizedText for keyword in ["全面禁煙", "禁煙席のみ", "禁煙"]):
        return "禁煙"
    if any(keyword in normalizedText for keyword in ["一部禁煙", "分煙"]):
        return "分煙"
    if any(keyword in normalizedText for keyword in ["禁煙席なし", "喫煙"]):
        return "喫煙可"
    return "要確認"


def extractStationWalkMinutes(stationName, accessText, listedStationName=""):
    if not accessText or accessText == "＿":
        return None

    candidateNames = buildStationAccessCandidates(stationName, listedStationName)
    normalizedAccessText = normalizeAccessText(accessText)

    for candidateName in candidateNames:
        stationPattern = buildStationMentionPattern(candidateName)
        matched = re.search(rf"{stationPattern}[^。]*?徒歩(?:約)?(\d+)分", normalizedAccessText)
        if matched:
            return int(matched.group(1))

    for candidateName in candidateNames:
        stationPattern = buildStationMentionPattern(candidateName)
        matched = re.search(rf"徒歩(?:約)?(\d+)分[^。]*?{stationPattern}", normalizedAccessText)
        if matched:
            return int(matched.group(1))

    genericMatch = re.search(r"徒歩(?:約)?(\d+)分", normalizedAccessText)
    if genericMatch and any(
        re.search(buildStationMentionPattern(candidateName), normalizedAccessText)
        for candidateName in candidateNames
    ):
        return int(genericMatch.group(1))

    if any(
        re.search(buildStationMentionPattern(candidateName), normalizedAccessText)
        and "直通" in normalizedAccessText
        for candidateName in candidateNames
    ):
        return 1

    if any(
        re.search(buildStationMentionPattern(candidateName), normalizedAccessText)
        and keyword in normalizedAccessText
        for candidateName in candidateNames
        for keyword in ["駅近", "駅ちか", "駅スグ", "駅すぐ", "すぐ", "目の前"]
    ):
        return 3

    if "/" in normalizedAccessText or "・" in normalizedAccessText:
        if any(
            re.search(buildStationMentionPattern(candidateName), normalizedAccessText)
            for candidateName in candidateNames
        ):
            return 10

    return None


def buildStationAccessCandidates(stationName, listedStationName):
    candidateNames = []
    for name in [stationName]:
        if name and name not in candidateNames:
            candidateNames.append(name)

    for aliasName in stationAccessAliases.get(stationName, []):
        if aliasName not in candidateNames:
            candidateNames.append(aliasName)

    normalizedListedStation = normalizeStationName(listedStationName)
    if normalizedListedStation and normalizedListedStation in candidateNames:
        candidateNames.append(normalizedListedStation)

    return candidateNames


def normalizeAccessText(accessText):
    return str(accessText).replace("　", " ").replace("／", "/")


def normalizeStationName(stationName):
    normalizedName = str(stationName).strip()
    if normalizedName.endswith("駅"):
        normalizedName = normalizedName[:-1]
    return normalizedName


def buildStationMentionPattern(candidateName):
    return rf"{re.escape(candidateName)}駅"


def fetchHotpepperGuideText(shopId):
    if not shopId:
        return ""

    if shopId in hotpepperGuideCache:
        return hotpepperGuideCache[shopId]

    request = Request(
        f"https://www.hotpepper.jp/str{shopId}/map/",
        headers={
            "User-Agent": APP_USER_AGENT,
            "Accept": "text/html",
        },
    )

    try:
        with urlopen(request, timeout=12) as response:
            htmlBody = response.read().decode("utf-8", errors="ignore")
    except (HTTPError, URLError, TimeoutError, ValueError):
        hotpepperGuideCache[shopId] = ""
        return ""

    matched = re.search(r"道案内</th><td>([^<]+)", htmlBody)
    guideText = html.unescape(matched.group(1).strip()) if matched else ""
    hotpepperGuideCache[shopId] = guideText
    return guideText


def normalizeHotpepperOpenInfo(openText, midnightText):
    closeMatches = re.findall(r"(\d{1,2}:\d{2}|翌\d{1,2}:\d{2})", openText)
    loMatches = re.findall(r"L\.O\.\s*(翌?\d{1,2}:\d{2})", openText)

    closeLabel = closeMatches[-1] if closeMatches else "要確認"
    lastOrderLabel = loMatches[-1] if loMatches else "要確認"

    closeHour = 24 if midnightText == "営業している" else convertHourLabelToValue(closeLabel)
    if closeHour is None:
        closeHour = 24

    return {
        "closeHour": closeHour,
        "closeLabel": closeLabel,
        "lastOrderLabel": lastOrderLabel,
    }


def convertHourLabelToValue(hourLabel):
    matched = re.search(r"(翌)?(\d{1,2}):(\d{2})", hourLabel)
    if not matched:
        return None

    isNextDay = matched.group(1)
    hourValue = int(matched.group(2))
    if isNextDay:
        hourValue += 24
    return hourValue


def buildHotpepperFeatures(shop):
    featureKeys = []
    for key in ["catch", "private_room", "free_drink", "free_food", "wifi", "non_smoking"]:
        value = shop.get(key)
        if value and value != "なし":
            featureKeys.append(str(value))

    if not featureKeys and shop.get("access"):
        featureKeys.append(shop["access"])

    return featureKeys[:3] if featureKeys else ["ホットペッパー掲載店"]


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
    radius = min(max(filters["maxDistanceMeters"], 100), 5000)

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
    normalizedVenue = {
        "id": f'osm-{element.get("type", "node")}-{element.get("id", "unknown")}',
        "name": venueName,
        "latitude": latitude,
        "longitude": longitude,
        "walkMinutes": 0,
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
