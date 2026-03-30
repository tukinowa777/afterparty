const cuisineLabels = {
  yakitori: "焼き鳥",
  seafood: "海鮮",
  japanese: "和食",
  korean: "韓国料理",
  creative: "創作系",
  meat: "肉系",
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
    cuisines: ["seafood", "japanese"],
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
    cuisines: ["korean", "meat"],
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
    cuisines: ["creative", "japanese"],
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
    cuisines: ["meat", "creative"],
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
    cuisines: ["japanese", "seafood"],
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
    cuisines: ["yakitori", "meat"],
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
    cuisines: ["creative", "seafood"],
    features: ["日本酒が豊富", "静かめ", "少人数向け"],
  },
];

const state = {
  location: {
    latitude: 35.6895,
    longitude: 139.6917,
    label: "新宿駅周辺",
  },
  searchMode: "gps",
  lines: {},
  selectedLine: "ginza",
  selectedStation: "",
  budget: "low",
  venues: [],
  venueSource: "loading",
  lastQueryString: "",
  autoLocateAttempted: false,
};

const locationLabel = document.getElementById("locationLabel");
const locationNote = document.getElementById("locationNote");
const locateButton = document.getElementById("locateButton");
const searchButton = document.getElementById("searchButton");
const searchButtonBottom = document.getElementById("searchButtonBottom");
const partySizeInput = document.getElementById("partySize");
const lineSelect = document.getElementById("lineSelect");
const stationSelect = document.getElementById("stationSelect");
const cuisineSelect = document.getElementById("cuisine");
const distanceSelect = document.getElementById("distance");
const openAfter21Checkbox = document.getElementById("openAfter21");
const resultsMeta = document.getElementById("resultsMeta");
const resultsList = document.getElementById("resultsList");
const budgetGroup = document.getElementById("budgetGroup");
const searchModeGroup = document.getElementById("searchModeGroup");
const stationFields = document.getElementById("stationFields");
const statusMessage = document.getElementById("statusMessage");
const shareButton = document.getElementById("shareButton");
const sourceNote = document.getElementById("sourceNote");

function formatBudget(priceRange) {
  if (priceRange === "low") return "¥";
  if (priceRange === "mid") return "¥¥";
  return "¥¥¥";
}

function formatHour(hour) {
  if (hour === 24) return "24:00";
  if (hour > 24) return `${String(hour - 24).padStart(2, "0")}:00`;
  return `${String(hour).padStart(2, "0")}:00`;
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

function getFilters() {
  const parsedPartySize = Number.parseInt(partySizeInput.value, 10);

  return {
    searchMode: state.searchMode,
    line: state.selectedLine,
    station: state.selectedStation,
    partySize: Number.isFinite(parsedPartySize) && parsedPartySize > 0 ? parsedPartySize : 4,
    maxBudget: state.budget,
    cuisine: cuisineSelect.value,
    maxDistanceMeters: Number.parseInt(distanceSelect.value, 10),
    requireOpenAfter21: openAfter21Checkbox.checked,
  };
}

function buildSearchParams() {
  const filters = getFilters();
  const params = new URLSearchParams();

  params.set("partySize", String(filters.partySize));
  params.set("searchMode", filters.searchMode);
  params.set("line", filters.line);
  params.set("station", filters.station);
  params.set("cuisine", filters.cuisine);
  params.set("distance", String(filters.maxDistanceMeters));
  params.set("budget", filters.maxBudget);
  params.set("openAfter21", String(filters.requireOpenAfter21));
  params.set("latitude", String(state.location.latitude));
  params.set("longitude", String(state.location.longitude));

  return params;
}

function renderEmpty() {
  resultsMeta.textContent = "0件ヒット";
  resultsList.innerHTML = `
    <article class="empty">
      <h3>条件に合う店がありません</h3>
      <p>人数、予算、距離、ジャンルを少し広げると候補が見つかりやすくなります。</p>
    </article>
  `;
}

function renderRecommendations() {
  if (state.venues.length === 0) {
    renderEmpty();
    return;
  }

  const walkLabel = state.searchMode === "gps" ? "現在地から徒歩" : "検索起点から徒歩";
  resultsMeta.textContent = `${state.venues.length}件表示`;
  resultsList.innerHTML = state.venues
    .map(
      (venue, index) => `
      <article class="result-card">
        <div class="result-top">
          <div class="rank">${index + 1}</div>
          <div class="result-headline">
            <h3>${venue.name}</h3>
            <p class="station">${walkLabel}${venue.walkMinutes}分</p>
          </div>
          <div class="price">${formatBudget(venue.priceRange)}</div>
        </div>
        <div class="meta">
          <span class="pill">徒歩${venue.walkMinutes}分</span>
          <span class="pill">${Math.round(venue.distanceMeters)}m</span>
          <span class="pill">営業 ${formatHour(venue.openUntilHour)}まで</span>
          <span class="pill">${venue.minPartySize}-${venue.maxPartySize}名</span>
        </div>
        <p class="genres">${venue.cuisines.map((item) => cuisineLabels[item]).join(" / ")}</p>
        <p class="features">${venue.features.join(" • ")}</p>
        <div class="result-actions">
          <a class="action-link primary" href="${buildMapLink(venue)}" target="_blank" rel="noreferrer">地図で開く</a>
          <a class="action-link secondary" href="https://www.google.com/search?q=${encodeURIComponent(
            `${venue.name} ${venue.nearestStation}`
          )}" target="_blank" rel="noreferrer">店を調べる</a>
        </div>
      </article>
    `
    )
    .join("");
}

function setLocationNote(message) {
  locationLabel.textContent = state.location.label;
  locationNote.textContent = message;
}

function updateSearchModeUi() {
  searchModeGroup.querySelectorAll(".chip").forEach((node) => {
    node.classList.toggle("active", node.dataset.mode === state.searchMode);
  });
  stationFields.hidden = state.searchMode !== "station";
}

function updateBudgetUi() {
  budgetGroup.querySelectorAll(".chip").forEach((node) => {
    node.classList.toggle("active", node.dataset.budget === state.budget);
  });
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
  searchModeGroup.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      state.searchMode = chip.dataset.mode;
      if (state.searchMode === "station") {
        state.location.label = `${state.selectedStation || "駅"}周辺`;
        setLocationNote("選択した駅を検索の起点にしています。『探す』を押すとおすすめを表示します。");
      } else {
        setLocationNote("現在地を取得してから『探す』を押すとおすすめを表示します。");
      }
      updateSearchModeUi();
    });
  });

  lineSelect.addEventListener("change", () => {
    state.selectedLine = lineSelect.value;
    renderStationOptions();
    state.location.label = `${state.selectedStation}駅周辺`;
    setLocationNote("選択した駅を検索の起点にしています。『探す』を押すとおすすめを表示します。");
  });

  stationSelect.addEventListener("change", () => {
    state.selectedStation = stationSelect.value;
    state.location.label = `${state.selectedStation}駅周辺`;
    setLocationNote("選択した駅を検索の起点にしています。『探す』を押すとおすすめを表示します。");
  });
}

function bindBudgetChips() {
  budgetGroup.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      state.budget = chip.dataset.budget;
      updateBudgetUi();
    });
  });
}

function bindForm() {
  return;
}

function bindGeolocation() {
  locateButton.addEventListener("click", () => {
    requestCurrentLocation(false);
  });
}

function requestCurrentLocation(isAutomatic) {
  if (!navigator.geolocation) {
    setLocationNote("このブラウザは位置情報に対応していません。駅を選んで周辺の店を探してください。");
    return;
  }

  locateButton.disabled = true;
  locateButton.textContent = "取得中...";

  navigator.geolocation.getCurrentPosition(
    (position) => {
      state.location = {
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        label: "現在地",
      };
      state.searchMode = "gps";
      setLocationNote(
        isAutomatic
          ? "現在地の利用が許可されました。「探す」を押すとおすすめを表示します。"
          : "現在地を取得しました。『探す』を押すとおすすめを表示します。"
      );
      locateButton.disabled = false;
      locateButton.textContent = "現在地を使う";
      updateSearchModeUi();
    },
    () => {
      setLocationNote(
        "位置情報を取得できませんでした。ブラウザ権限を確認するか、下の『駅から探す』を使ってください。"
      );
      locateButton.disabled = false;
      locateButton.textContent = "現在地を使う";
    },
    {
      enableHighAccuracy: false,
      timeout: 10000,
      maximumAge: 300000,
    }
  );
}

async function autoRequestCurrentLocation() {
  return Promise.resolve();
}

function applyFiltersFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const partySize = params.get("partySize");
  const searchMode = params.get("searchMode");
  const line = params.get("line");
  const station = params.get("station");
  const cuisine = params.get("cuisine");
  const distance = params.get("distance");
  const budget = params.get("budget");
  const openAfter21 = params.get("openAfter21");
  const latitude = Number.parseFloat(params.get("latitude"));
  const longitude = Number.parseFloat(params.get("longitude"));

  if (partySize) {
    partySizeInput.value = partySize;
  }

  if (searchMode === "gps" || searchMode === "station") {
    state.searchMode = searchMode;
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

  if (distance && distanceSelect.querySelector(`option[value="${distance}"]`)) {
    distanceSelect.value = distance;
  }

  if (budget && budgetGroup.querySelector(`[data-budget="${budget}"]`)) {
    state.budget = budget;
  }

  if (openAfter21 === "true" || openAfter21 === "false") {
    openAfter21Checkbox.checked = openAfter21 === "true";
  }

  if (Number.isFinite(latitude) && Number.isFinite(longitude)) {
    state.location.latitude = latitude;
    state.location.longitude = longitude;
    state.location.label = state.searchMode === "station" ? `${state.selectedStation}駅周辺` : "共有された位置";
    setLocationNote(
      state.searchMode === "station"
        ? "共有URLで指定された駅を検索の起点にしています。"
        : "共有URLの位置情報を検索の起点にしています。"
    );
  }

  updateBudgetUi();
  updateSearchModeUi();
}

function bindShareButton() {
  shareButton.addEventListener("click", async () => {
    const url = new URL(window.location.href);
    url.search = buildSearchParams().toString();

    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(url.toString());
        setStatusMessage("共有用URLをクリップボードにコピーしました。");
      } else {
        setStatusMessage(`共有用URL: ${url.toString()}`);
      }
    } catch (error) {
      setStatusMessage(`共有用URL: ${url.toString()}`);
    }
  });
}

function bindSearchButton() {
  [searchButton, searchButtonBottom].forEach((button) => {
    button.addEventListener("click", () => {
      loadVenues();
    });
  });
}

async function loadVenues() {
  const queryString = buildSearchParams().toString();
  state.lastQueryString = queryString;
  setStatusMessage("条件に合う店舗データを検索しています。");

  try {
    const response = await fetch(`./api/venues?${queryString}`, {
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to load venues: ${response.status}`);
    }

    const payload = await response.json();
    if (state.lastQueryString !== queryString) {
      return;
    }

    state.venues = Array.isArray(payload.venues) ? payload.venues : [];
    state.venueSource = "api";
    history.replaceState(null, "", `?${queryString}`);
    setStatusMessage(`条件に合う店舗が${payload.count ?? state.venues.length}件見つかりました。`);
    setSourceNote(
      payload.source === "live"
        ? `${payload.sourceLabel} を利用しています。${payload.attribution ?? ""}`.trim()
        : `${payload.sourceLabel} を表示しています。`
    );
  } catch (error) {
    if (state.lastQueryString !== queryString) {
      return;
    }

    state.venueSource = "fallback";
    state.venues = fallbackVenues;
    setStatusMessage("APIの取得に失敗したため、内蔵サンプルデータで表示しています。");
    setSourceNote("内蔵サンプルデータを表示しています。");
  }

  renderRecommendations();
}

bindBudgetChips();
bindForm();
bindGeolocation();
bindSearchMode();
bindShareButton();
bindSearchButton();

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
  try {
    await loadStations();
  } catch (error) {
    setStatusMessage("駅一覧の読み込みに失敗しました。現在地検索のみ利用できます。");
  }

  applyFiltersFromUrl();
  renderLineOptions();
  renderStationOptions();
  updateSearchModeUi();
  if (state.searchMode === "station" && state.selectedStation) {
    state.location.label = `${state.selectedStation}駅周辺`;
    setLocationNote("選択した駅を検索の起点にしています。『探す』を押すとおすすめを表示します。");
  }
  await autoRequestCurrentLocation();
}

bootstrap();
