const cuisineLabels = {
  chinese: "中華",
  western: "洋食",
  yakitori: "焼き鳥",
  japanese: "和食",
  yakiniku: "焼肉",
  korean: "韓国料理",
  creative: "創作",
};

const fallbackVenues = [
  {
    id: "yoyogi-yakitori-lamp",
    name: "炭火やきとり 灯",
    latitude: 35.6837,
    longitude: 139.7028,
    walkMinutes: 4,
    nearestStation: "代々木",
    openUntilHour: 24,
    priceRange: "low",
    minPartySize: 2,
    maxPartySize: 8,
    cuisines: ["yakitori", "japanese"],
    features: ["喫煙ブースあり", "2軒目向け小皿", "カウンターあり"],
  },
  {
    id: "shinjuku-sakana-nami",
    name: "魚と酒 波音",
    latitude: 35.6912,
    longitude: 139.7004,
    walkMinutes: 6,
    nearestStation: "新宿",
    openUntilHour: 27,
    priceRange: "mid",
    minPartySize: 2,
    maxPartySize: 16,
    cuisines: ["japanese"],
    features: ["刺身盛り", "半個室", "終電前後でも入りやすい"],
  },
  {
    id: "ebisu-korean-sora",
    name: "ソウル酒場 ソラ",
    latitude: 35.6479,
    longitude: 139.7102,
    walkMinutes: 5,
    nearestStation: "恵比寿",
    openUntilHour: 25,
    priceRange: "mid",
    minPartySize: 3,
    maxPartySize: 12,
    cuisines: ["korean"],
    features: ["サムギョプサル", "遅い時間の注文に強い", "テーブル席中心"],
  },
  {
    id: "shibuya-creative-kumo",
    name: "創作酒場 雲海",
    latitude: 35.6598,
    longitude: 139.6996,
    walkMinutes: 7,
    nearestStation: "渋谷",
    openUntilHour: 26,
    priceRange: "high",
    minPartySize: 2,
    maxPartySize: 10,
    cuisines: ["creative"],
    features: ["クラフトサワー", "落ち着いた照明", "デート利用向け"],
  },
  {
    id: "shinbashi-meat-garage",
    name: "肉酒場 Garage",
    latitude: 35.6661,
    longitude: 139.7589,
    walkMinutes: 3,
    nearestStation: "新橋",
    openUntilHour: 28,
    priceRange: "low",
    minPartySize: 2,
    maxPartySize: 20,
    cuisines: ["yakiniku"],
    features: ["大人数OK", "飲み放題あり", "深夜2時以降も営業"],
  },
  {
    id: "ueno-sakaba-matsuri",
    name: "大衆酒場 まつり",
    latitude: 35.7111,
    longitude: 139.7774,
    walkMinutes: 4,
    nearestStation: "上野",
    openUntilHour: 23,
    priceRange: "low",
    minPartySize: 2,
    maxPartySize: 14,
    cuisines: ["japanese"],
    features: ["コスパ重視", "串揚げあり", "にぎやか"],
  },
  {
    id: "ikebukuro-yakitori-zen",
    name: "やきとり 善",
    latitude: 35.7305,
    longitude: 139.7111,
    walkMinutes: 5,
    nearestStation: "池袋",
    openUntilHour: 26,
    priceRange: "mid",
    minPartySize: 2,
    maxPartySize: 10,
    cuisines: ["yakitori"],
    features: ["炭火焼", "半地下の隠れ家感", "二次会セットあり"],
  },
  {
    id: "nakameguro-aji-tokyo",
    name: "味東京 中目黒",
    latitude: 35.6438,
    longitude: 139.6984,
    walkMinutes: 8,
    nearestStation: "中目黒",
    openUntilHour: 24,
    priceRange: "high",
    minPartySize: 2,
    maxPartySize: 6,
    cuisines: ["creative"],
    features: ["日本酒が豊富", "静かめ", "少人数向け"],
  },
];

const state = {
  searchMode: "station",
  lines: {},
  selectedLine: "ginza",
  selectedStation: "",
  venues: [],
  venueSource: "loading",
  lastQueryString: "",
  autoLocateAttempted: false,
  currentPage: 0,
};
let activeSearchController = null;

const searchButtonBottom = document.getElementById("searchButtonBottom");
const gpsSearchButton = document.getElementById("gpsSearchButton");
const stationTab = document.getElementById("stationTab");
const gpsTab = document.getElementById("gpsTab");
const stationSearchPanel = document.getElementById("stationSearchPanel");
const gpsSearchPanel = document.getElementById("gpsSearchPanel");
const gpsDistanceFilter = document.getElementById("gpsDistanceFilter");
const lineSelect = document.getElementById("lineSelect");
const stationSelect = document.getElementById("stationSelect");
const cuisineSelect = document.getElementById("cuisine");
const smokingSelect = document.getElementById("smoking");
const openAfter21Checkbox = document.getElementById("openAfter21");
const openAfter22Checkbox = document.getElementById("openAfter22");
const resultsHeader = document.getElementById("resultsHeader");
const resultsPager = document.getElementById("resultsPager");
const resultsMeta = document.getElementById("resultsMeta");
const resultsList = document.getElementById("resultsList");
const prevResultsButton = document.getElementById("prevResultsButton");
const nextResultsButton = document.getElementById("nextResultsButton");
const loadingIndicator = document.getElementById("loadingIndicator");
const stationFields = document.getElementById("stationFields");
const statusMessage = document.getElementById("statusMessage");
const sourceNote = document.getElementById("sourceNote");

function normalizeCuisineKey(cuisineKey) {
  const cuisineAliases = {
    seafood: "japanese",
    meat: "yakiniku",
  };

  if (cuisineLabels[cuisineKey]) {
    return cuisineKey;
  }

  return cuisineAliases[cuisineKey] || "japanese";
}

function formatHour(hour) {
  if (hour === 24) return "24:00";
  if (hour > 24) return `${String(hour - 24).padStart(2, "0")}:00`;
  return `${String(hour).padStart(2, "0")}:00`;
}

function haversineDistance(lat1, lng1, lat2, lng2) {
  const earthRadius = 6371000;
  const toRad = (degree) => (degree * Math.PI) / 180;
  const deltaLat = toRad(lat2 - lat1);
  const deltaLng = toRad(lng2 - lng1);
  const aValue =
    Math.sin(deltaLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(deltaLng / 2) ** 2;
  return earthRadius * 2 * Math.asin(Math.sqrt(aValue));
}

function formatBusinessHours(venue) {
  const closeLabel = venue.closeLabel || formatHour(venue.openUntilHour);
  const lastOrderLabel = venue.lastOrderLabel || "要確認";
  return `営業 ${closeLabel}まで / LO ${lastOrderLabel}`;
}

function buildMapLink(venue) {
  const params = new URLSearchParams({
    api: "1",
    query: `${venue.name} ${venue.nearestStation}`,
  });

  return `https://www.google.com/maps/search/?${params.toString()}`;
}

function setStatusMessage(message) {
  if (!message) {
    statusMessage.hidden = true;
    statusMessage.textContent = "";
    return;
  }

  statusMessage.hidden = false;
  statusMessage.textContent = message;
}

function setSourceNote(message) {
  if (!message) {
    sourceNote.hidden = true;
    sourceNote.textContent = "";
    return;
  }

  sourceNote.hidden = false;
  sourceNote.textContent = message;
}

function setLoadingState(isLoading) {
  loadingIndicator.hidden = !isLoading;
  searchButtonBottom.disabled = isLoading;
  if (gpsSearchButton) {
    gpsSearchButton.disabled = isLoading;
  }
}

function getFilters() {
  if (state.searchMode === "gps") {
    return {
      searchMode: "gps",
      cuisine: cuisineSelect.value,
      smoking: smokingSelect.value,
      requireOpenAfter21: openAfter21Checkbox.checked,
      requireOpenAfter22: openAfter22Checkbox.checked,
      distance: parseInt(gpsDistanceFilter.value, 10),
    };
  }

  return {
    searchMode: "station",
    line: state.selectedLine,
    station: state.selectedStation,
    maxBudget: "mid",
    cuisine: cuisineSelect.value,
    smoking: smokingSelect.value,
    requireOpenAfter21: openAfter21Checkbox.checked,
    requireOpenAfter22: openAfter22Checkbox.checked,
  };
}

function buildSearchParams() {
  const filters = getFilters();
  const params = new URLSearchParams();

  params.set("searchMode", filters.searchMode);
  if (filters.line) {
    params.set("line", filters.line);
  }
  if (filters.station) {
    params.set("station", filters.station);
  }
  params.set("cuisine", filters.cuisine);
  params.set("smoking", filters.smoking);
  params.set("openAfter21", String(filters.requireOpenAfter21));
  params.set("openAfter22", String(filters.requireOpenAfter22));

  return params;
}

function renderEmpty() {
  resultsHeader.hidden = false;
  resultsPager.hidden = true;
  resultsMeta.textContent = "0件ヒット";
  const emptyMessage =
    state.searchMode === "gps"
      ? "現在地の近くで条件に合う店が見つかりませんでした。距離条件を広げるか、もう一度お試しください。"
      : "指定駅から徒歩10分以内とホットペッパーで確認できる店が見つかりませんでした。路線や駅、料理ジャンルを変えると候補が見つかりやすくなります。";
  resultsList.innerHTML = `
    <article class="empty">
      <h3>条件に合う店がありません</h3>
      <p>${emptyMessage}</p>
    </article>
  `;
}

function renderRecommendations() {
  if (state.venues.length === 0) {
    renderEmpty();
    return;
  }

  resultsHeader.hidden = false;
  const searchOriginLabel = state.searchMode === "gps" ? "現在地" : `${state.selectedStation}駅`;
  const pageSize = 3;
  const resultPages = buildResultPages(pageSize);
  resultsPager.hidden = resultPages.length <= 1;
  resultsMeta.textContent = buildResultsMetaText(0, resultPages);
  resultsList.innerHTML = resultPages.map((page, pageIndex) => {
    const startIndex = page.startIndex;
    const visibleVenues = page.venues;
    return `
      <section class="results-page" aria-label="${startIndex + 1}件目から${Math.min(startIndex + visibleVenues.length, state.venues.length)}件目">
        ${visibleVenues
          .map(
            (venue, index) => {
              if (state.searchMode === "gps") {
                return buildGpsResultCard(venue);
              }

              const genreChips = (venue.cuisines || [])
                .map((item) => cuisineLabels[item])
                .filter(Boolean)
                .map((label) => `<span class="genre-chip">${label}</span>`)
                .join("");
              const featureText = venue.features.slice(0, 1).join(" • ");

              return `
      <article class="result-card">
        <div class="result-top">
          <div class="rank">${startIndex + index + 1}</div>
          <div class="result-headline">
            <h3>${venue.name}</h3>
            <p class="station">${searchOriginLabel}から徒歩${venue.walkMinutes}分</p>
          </div>
        </div>
        <div class="meta">
          <span class="pill">徒歩${venue.walkMinutes}分</span>
          <span class="pill business-hours-pill">${formatBusinessHours(venue)}</span>
          <span class="pill">${venue.smokingLabel || "要確認"}</span>
        </div>
        ${genreChips ? `<div class="genres">${genreChips}</div>` : ""}
        ${featureText ? `<p class="features">${featureText}</p>` : ""}
        <div class="result-actions">
          <a class="action-link primary" href="${buildMapLink(venue)}" target="_blank" rel="noreferrer">地図で開く</a>
          <a class="action-link secondary" href="${
            venue.hotpepperUrl ||
            `https://www.google.com/search?q=${encodeURIComponent(`${venue.name} ${venue.nearestStation}`)}`
          }" target="_blank" rel="noreferrer">ホットペッパーでみる</a>
        </div>
      </article>
    `;
            }
          )
          .join("")}
      </section>
    `;
  }).join("");
  resultsList.scrollTo({ left: 0, behavior: "auto" });
  prevResultsButton.disabled = true;
  nextResultsButton.disabled = resultPages.length <= 1;
}

function buildGpsResultCard(venue) {
  const distanceMeters = Number.isFinite(venue.distance_m) ? venue.distance_m : 0;
  const walkMinutes = Math.max(1, Math.round(distanceMeters / 80));
  const googleMapsUrl = `https://maps.google.com/?q=${encodeURIComponent(venue.name)}`;

  return `
      <article class="result-card">
        <div class="result-top">
          <div class="result-headline">
            <h3>${venue.name}</h3>
            <p class="station">徒歩約${walkMinutes}分（${distanceMeters}m）</p>
          </div>
        </div>
        <div class="meta">
          <span class="pill">${venue.genre || "ジャンル不明"}</span>
          <span class="pill business-hours-pill">${venue.open || "営業時間不明"}</span>
          <span class="pill">${venue.budget || "予算要確認"}</span>
        </div>
        <p class="features">${venue.access || "アクセス情報はホットペッパーでご確認ください。"}</p>
        <div class="result-actions">
          <a class="action-link secondary" href="${venue.urls || googleMapsUrl}" target="_blank" rel="noreferrer">ホットペッパーで見る</a>
          <a class="action-link primary" href="${googleMapsUrl}" target="_blank" rel="noreferrer">Google Mapsで開く</a>
        </div>
      </article>
    `;
}

function buildResultsMetaText(pageIndex, resultPages) {
  if (state.venues.length === 0) {
    return "0件ヒット";
  }

  const currentPage = resultPages[Math.min(pageIndex, resultPages.length - 1)];
  const startIndex = currentPage.startIndex + 1;
  const endIndex = currentPage.startIndex + currentPage.venues.length;
  return `${startIndex}-${endIndex}件目 / 全${state.venues.length}件`;
}

function buildResultPages(pageSize) {
  const resultPages = [];
  for (let index = 0; index < state.venues.length; index += pageSize) {
    resultPages.push({
      startIndex: index,
      venues: state.venues.slice(index, index + pageSize),
    });
  }

  return resultPages;
}

function updateSearchModeUi() {
  stationFields.hidden = false;
}

function setSearchTab(mode) {
  const isStationMode = mode === "station";
  state.searchMode = isStationMode ? "station" : "gps";
  stationTab.classList.toggle("active", isStationMode);
  gpsTab.classList.toggle("active", !isStationMode);
  stationTab.setAttribute("aria-selected", String(isStationMode));
  gpsTab.setAttribute("aria-selected", String(!isStationMode));
  stationSearchPanel.hidden = !isStationMode;
  gpsSearchPanel.hidden = isStationMode;
  stationSearchPanel.classList.toggle("active", isStationMode);
  gpsSearchPanel.classList.toggle("active", !isStationMode);
}

function renderLineOptions() {
  const entries = Object.entries(state.lines);
  lineSelect.innerHTML = entries
    .map(([lineKey, lineValue]) => `<option value="${lineKey}">${lineValue.label}</option>`)
    .join("");

  if (!state.lines[state.selectedLine] && entries.length > 0) {
    state.selectedLine = entries[0][0];
  }

  lineSelect.value = state.selectedLine;
}

function renderStationOptions() {
  const line = state.lines[state.selectedLine];
  const stations = line ? line.stations : [];

  stationSelect.innerHTML = stations
    .map((stationName) => `<option value="${stationName}">${stationName}</option>`)
    .join("");

  if (!stations.includes(state.selectedStation)) {
    state.selectedStation = stations[0] || "";
  }

  stationSelect.value = state.selectedStation;
}

function bindSearchMode() {
  stationTab.addEventListener("click", () => {
    setSearchTab("station");
  });

  gpsTab.addEventListener("click", () => {
    setSearchTab("gps");
  });

  lineSelect.addEventListener("change", () => {
    state.selectedLine = lineSelect.value;
    renderStationOptions();
  });

  stationSelect.addEventListener("change", () => {
    state.selectedStation = stationSelect.value;
  });
}

function bindForm() {
  return;
}

function applyFiltersFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const searchMode = params.get("searchMode");
  const line = params.get("line");
  const station = params.get("station");
  const cuisine = params.get("cuisine");
  const smoking = params.get("smoking");
  const openAfter21 = params.get("openAfter21");
  const openAfter22 = params.get("openAfter22");

  if (searchMode === "gps") {
    state.searchMode = "gps";
  } else {
    state.searchMode = "station";
  }

  if (line) {
    state.selectedLine = line;
  }

  if (station) {
    state.selectedStation = station;
  }

  if (cuisine && cuisineSelect.querySelector(`option[value="${cuisine}"]`)) {
    cuisineSelect.value = cuisine;
  }

  if (smoking && smokingSelect.querySelector(`option[value="${smoking}"]`)) {
    smokingSelect.value = smoking;
  }

  if (openAfter21 === "true" || openAfter21 === "false") {
    openAfter21Checkbox.checked = openAfter21 === "true";
  }
  if (openAfter22 === "true" || openAfter22 === "false") {
    openAfter22Checkbox.checked = openAfter22 === "true";
  }

  updateSearchModeUi();
  setSearchTab(state.searchMode);
}

function bindSearchButton() {
  searchButtonBottom.addEventListener("click", () => {
    state.searchMode = "station";
    setSearchTab("station");
    loadVenues();
  });

  if (gpsSearchButton) {
    gpsSearchButton.addEventListener("click", () => {
      state.searchMode = "gps";
      setSearchTab("gps");
      loadCurrentLocationVenues();
    });
  }
}

function bindResultsPager() {
  prevResultsButton.addEventListener("click", () => {
    scrollResultsPage(-1);
  });

  nextResultsButton.addEventListener("click", () => {
    scrollResultsPage(1);
  });

  resultsList.addEventListener("scroll", updateResultsPagerState, { passive: true });
}

function scrollResultsPage(direction) {
  const pageWidth = resultsList.clientWidth;
  if (!pageWidth) {
    return;
  }

  resultsList.scrollBy({
    left: pageWidth * direction,
    behavior: "smooth",
  });
}

function updateResultsPagerState() {
  const pageWidth = resultsList.clientWidth;
  if (!pageWidth) {
    return;
  }

  const maxScrollLeft = Math.max(0, resultsList.scrollWidth - pageWidth);
  const currentPage = Math.round(resultsList.scrollLeft / pageWidth);
  resultsMeta.textContent = buildResultsMetaText(currentPage, buildResultPages(3));
  prevResultsButton.disabled = resultsList.scrollLeft < 20;
  nextResultsButton.disabled = resultsList.scrollLeft >= maxScrollLeft - 20;
}

async function loadVenues() {
  const queryString = buildSearchParams().toString();
  const previousVenues = [...state.venues];
  const previousVenueSource = state.venueSource;
  if (activeSearchController) {
    activeSearchController.abort();
  }
  activeSearchController = new AbortController();
  state.lastQueryString = queryString;
  setLoadingState(true);
  setStatusMessage("条件に合う店舗データを検索しています。");

  try {
    const response = await fetch(`./api/venues?${queryString}`, {
      headers: {
        Accept: "application/json",
      },
      signal: activeSearchController.signal,
    });

    if (!response.ok) {
      throw new Error(`Failed to load venues: ${response.status}`);
    }

    const payload = await response.json();
    if (state.lastQueryString !== queryString) {
      return;
    }

    state.venues = Array.isArray(payload.venues) ? payload.venues : [];
    state.currentPage = 0;
    state.venueSource = "api";
    history.replaceState(null, "", `?${queryString}`);
    setStatusMessage("条件に合う候補を表示しています。3件ずつ確認できます。");
    setSourceNote(
      payload.source === "live"
        ? `${payload.sourceLabel} を利用しています。${payload.attribution ?? ""}`.trim()
        : `${payload.sourceLabel} を表示しています。`
    );
  } catch (error) {
    if (state.lastQueryString !== queryString) {
      return;
    }
    if (error.name === "AbortError") {
      return;
    }

    state.venueSource = previousVenueSource;
    state.venues = previousVenues;
    state.currentPage = 0;
    setStatusMessage("検索に失敗しました。通信状況を確認して、もう一度お試しください。");
    setSourceNote("");
  }

  if (state.lastQueryString === queryString) {
    renderRecommendations();
  }

  if (state.lastQueryString === queryString) {
    setLoadingState(false);
  }
  if (activeSearchController && activeSearchController.signal.aborted === false) {
    activeSearchController = null;
  }
}

async function loadCurrentLocationVenues() {
  const previousVenues = [...state.venues];
  const previousVenueSource = state.venueSource;
  if (activeSearchController) {
    activeSearchController.abort();
  }
  activeSearchController = new AbortController();
  setLoadingState(true);
  setStatusMessage("現在地から候補を検索しています。");
  setSourceNote("");

  try {
    const position = await getCurrentPosition();
    const userLat = position.coords.latitude;
    const userLng = position.coords.longitude;
    const response = await fetch(`./api/venues?lat=${userLat}&lng=${userLng}&range=3&count=10`, {
      headers: {
        Accept: "application/json",
      },
      signal: activeSearchController.signal,
    });

    if (!response.ok) {
      throw new Error(`Failed to load venues: ${response.status}`);
    }

    const payload = await response.json();
    const distanceLimit = parseInt(gpsDistanceFilter.value, 10);
    const venues = (Array.isArray(payload.venues) ? payload.venues : [])
      .map((venue) => {
        const distanceMeters = Math.round(
          haversineDistance(userLat, userLng, Number(venue.lat), Number(venue.lng))
        );
        return {
          ...venue,
          distance_m: distanceMeters,
        };
      })
      .sort((leftVenue, rightVenue) => leftVenue.distance_m - rightVenue.distance_m)
      .filter((venue) => venue.distance_m <= distanceLimit)
      .slice(0, 3);

    state.venues = venues;
    state.currentPage = 0;
    state.venueSource = "api";
    setStatusMessage("現在地から近い候補を表示しています。");
    setSourceNote(payload.sourceLabel ? `${payload.sourceLabel} を表示しています。` : "");
    renderRecommendations();
  } catch (error) {
    state.venueSource = previousVenueSource;
    state.venues = previousVenues;
    state.currentPage = 0;
    if (error.name === "AbortError") {
      return;
    }
    setStatusMessage("現在地を取得できませんでした。HTTPSで接続しているか確認してください。");
    setSourceNote("");
    renderRecommendations();
  } finally {
    setLoadingState(false);
    if (activeSearchController && activeSearchController.signal.aborted === false) {
      activeSearchController = null;
    }
  }
}

function getCurrentPosition() {
  return new Promise((resolve, reject) => {
    navigator.geolocation.getCurrentPosition(resolve, reject, {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 0,
    });
  });
}

bindForm();
bindSearchMode();
bindSearchButton();
bindResultsPager();

async function loadStations() {
  const response = await fetch("./api/stations", {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to load stations: ${response.status}`);
  }

  const payload = await response.json();
  state.lines = payload.lines ?? {};
  renderLineOptions();
  renderStationOptions();
}

async function bootstrap() {
  setLoadingState(false);
  try {
    await loadStations();
  } catch (error) {
    setStatusMessage("駅一覧の読み込みに失敗しました。時間をおいて再度お試しください。");
  }

  applyFiltersFromUrl();
  renderLineOptions();
  renderStationOptions();
  updateSearchModeUi();
}

bootstrap();
