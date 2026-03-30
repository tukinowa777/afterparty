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

const searchButtonBottom = document.getElementById("searchButtonBottom");
const lineSelect = document.getElementById("lineSelect");
const stationSelect = document.getElementById("stationSelect");
const cuisineSelect = document.getElementById("cuisine");
const openAfter21Checkbox = document.getElementById("openAfter21");
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
}

function getFilters() {
  return {
    searchMode: "station",
    line: state.selectedLine,
    station: state.selectedStation,
    maxBudget: "mid",
    cuisine: cuisineSelect.value,
    requireOpenAfter21: openAfter21Checkbox.checked,
  };
}

function buildSearchParams() {
  const filters = getFilters();
  const params = new URLSearchParams();

  params.set("searchMode", filters.searchMode);
  params.set("line", filters.line);
  params.set("station", filters.station);
  params.set("cuisine", filters.cuisine);
  params.set("openAfter21", String(filters.requireOpenAfter21));

  return params;
}

function renderEmpty() {
  resultsHeader.hidden = false;
  resultsPager.hidden = true;
  resultsMeta.textContent = "0件ヒット";
  resultsList.innerHTML = `
    <article class="empty">
      <h3>条件に合う店がありません</h3>
      <p>指定駅から徒歩10分以内とホットペッパーで確認できる店が見つかりませんでした。路線や駅、料理ジャンルを変えると候補が見つかりやすくなります。</p>
    </article>
  `;
}

function renderRecommendations() {
  if (state.venues.length === 0) {
    renderEmpty();
    return;
  }

  resultsHeader.hidden = false;
  const searchOriginLabel = `${state.selectedStation}駅`;
  const pageSize = 3;
  const pageCount = Math.ceil(state.venues.length / pageSize);
  resultsPager.hidden = pageCount <= 1;
  resultsMeta.textContent = `全${state.venues.length}件`;
  resultsList.innerHTML = Array.from({ length: pageCount }, (_, pageIndex) => {
    const startIndex = pageIndex * pageSize;
    const visibleVenues = state.venues.slice(startIndex, startIndex + pageSize);
    return `
      <section class="results-page" aria-label="${startIndex + 1}件目から${Math.min(startIndex + visibleVenues.length, state.venues.length)}件目">
        ${visibleVenues
          .map(
            (venue, index) => `
      <article class="result-card">
        <div class="result-top">
          <div class="rank">${startIndex + index + 1}</div>
          <div class="result-headline">
            <h3>${venue.name}</h3>
            <p class="station">${searchOriginLabel}から徒歩${venue.walkMinutes}分</p>
          </div>
          <div class="price">${formatBudget(venue.priceRange)}</div>
        </div>
        <div class="meta">
          <span class="pill">徒歩${venue.walkMinutes}分</span>
          <span class="pill">${formatBusinessHours(venue)}</span>
          <span class="pill">${venue.smokingLabel || "要確認"}</span>
        </div>
        <p class="genres">${venue.cuisines.map((item) => cuisineLabels[item]).join(" / ")}</p>
        <p class="features">${venue.features.join(" • ")}</p>
        <div class="result-actions">
          <a class="action-link primary" href="${buildMapLink(venue)}" target="_blank" rel="noreferrer">地図で開く</a>
          <a class="action-link secondary" href="${
            venue.hotpepperUrl ||
            `https://www.google.com/search?q=${encodeURIComponent(`${venue.name} ${venue.nearestStation}`)}`
          }" target="_blank" rel="noreferrer">ホットペッパーでみる</a>
        </div>
      </article>
    `
          )
          .join("")}
      </section>
    `;
  }).join("");
  resultsList.scrollTo({ left: 0, behavior: "auto" });
  prevResultsButton.disabled = true;
  nextResultsButton.disabled = pageCount <= 1;
}

function updateSearchModeUi() {
  stationFields.hidden = false;
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
  const line = params.get("line");
  const station = params.get("station");
  const cuisine = params.get("cuisine");
  const openAfter21 = params.get("openAfter21");

  if (line) {
    state.selectedLine = line;
  }

  if (station) {
    state.selectedStation = station;
  }

  if (cuisine && cuisineSelect.querySelector(`option[value="${cuisine}"]`)) {
    cuisineSelect.value = cuisine;
  }

  if (openAfter21 === "true" || openAfter21 === "false") {
    openAfter21Checkbox.checked = openAfter21 === "true";
  }

  updateSearchModeUi();
}

function bindSearchButton() {
  searchButtonBottom.addEventListener("click", () => {
    state.searchMode = "station";
    loadVenues();
  });
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
  prevResultsButton.disabled = resultsList.scrollLeft < 20;
  nextResultsButton.disabled = resultsList.scrollLeft >= maxScrollLeft - 20;
}

async function loadVenues() {
  const queryString = buildSearchParams().toString();
  state.lastQueryString = queryString;
  setLoadingState(true);
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
    state.currentPage = 0;
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
    state.venues = fallbackVenues.slice(0, 3);
    state.currentPage = 0;
    setStatusMessage("APIの取得に失敗したため、内蔵サンプルデータを3件表示しています。");
    setSourceNote("内蔵サンプルデータを表示しています。");
  }

  if (state.lastQueryString === queryString) {
    renderRecommendations();
  }

  if (state.lastQueryString === queryString) {
    setLoadingState(false);
  }
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
