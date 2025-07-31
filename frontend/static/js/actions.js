let allData = [];
let portfolioSymbols = [];
let choicesInstance;

function formatDateDisplay(dateStr) {
  if (!dateStr) return "";
  const parts = dateStr.trim().split(" ");
  if (parts.length === 3) {
    const d = parts[0];
    const m = parts[1];
    const y = parts[2].slice(-2);
    return `${d} ${m} ${y}`;
  }
  return dateStr;
}

function parseCSVDate(dateStr) {
  if (!dateStr) return null;
  const parts = dateStr.trim().split(" ");
  if (parts.length === 3) {
    const monthMap = {
      Jan: "01", Feb: "02", Mar: "03", Apr: "04", May: "05", Jun: "06",
      Jul: "07", Aug: "08", Sep: "09", Oct: "10", Nov: "11", Dec: "12"
    };
    const day = parts[0].padStart(2, '0');
    const month = monthMap[parts[1]];
    const year = parts[2];
    if (month) return `${year}-${month}-${day}`;
  }
  return null;
}

function createTooltipContent(row) {
  const lines = [];

  for (const [key, value] of Object.entries(row)) {
    if (!value || value.trim() === "-") continue;

    if (key === "Security Name" || key === "Security Code" || key === "Purpose") {
      continue;
    }

    if (key === "Company Name") {
      lines.push(value.trim());
    } else {
      lines.push(`${key}: ${value.trim()}`);
    }
  }

  return lines.join('\n');
}

function renderGrid(data) {
  const grid = document.getElementById('grid');
  grid.innerHTML = "";

  if (data.length === 0) {
    grid.innerHTML = "<p style='text-align:center;color:#888;'>No records match your filters.</p>";
    return;
  }

  data.forEach(row => {
    const badge = document.createElement('div');
    badge.className = 'badge';
    badge.title = createTooltipContent(row);

    const title = document.createElement('div');
    title.className = 'badge-title';
    title.textContent = row["Security Name"];

    const exDate = document.createElement('div');
    exDate.className = 'badge-text';
    exDate.textContent = `Ex Date: ${formatDateDisplay(row["Ex Date"])}`;

    const recordDate = document.createElement('div');
    recordDate.className = 'badge-text';
    recordDate.textContent = `Record Date: ${formatDateDisplay(row["Record Date"])}`;

    const purpose = document.createElement('div');
    purpose.className = 'badge-text';
    purpose.textContent = row["Purpose"];

    badge.appendChild(title);
    badge.appendChild(exDate);
    badge.appendChild(recordDate);
    badge.appendChild(purpose);

    grid.appendChild(badge);
  });
}

function applyFilters() {
  const selectedSecurities = choicesInstance.getValue(true).map(s => s.toLowerCase());
  const exDateVal = document.getElementById('exDateFilter').value;
  const recordDateVal = document.getElementById('recordDateFilter').value;

  const filtered = allData.filter(row => {
    const sec = (row["Security Name"] || "").toLowerCase();
    const exDateParsed = parseCSVDate(row["Ex Date"]);
    const recordDateParsed = parseCSVDate(row["Record Date"]);

    const secMatch = selectedSecurities.length === 0 || selectedSecurities.includes(sec);
    const exMatch = !exDateVal || exDateVal === exDateParsed;
    const recMatch = !recordDateVal || recordDateVal === recordDateParsed;

    return secMatch && exMatch && recMatch;
  });

  renderGrid(filtered);
}

function populateSecurityFilterOptions(data) {
  const uniqueNames = [...new Set(data.map(row => row["Security Name"]).filter(Boolean))].sort();
  const securityFilter = document.getElementById('securityFilter');
  securityFilter.innerHTML = "";
  uniqueNames.forEach(name => {
    const option = document.createElement('option');
    option.value = name;
    option.textContent = name;
    securityFilter.appendChild(option);
  });
  if (choicesInstance) choicesInstance.destroy();
  choicesInstance = new Choices(securityFilter, {
    removeItemButton: true,
    searchEnabled: true,
    shouldSort: false,
    placeholderValue: 'Select securities...'
  });
}

async function loadUserPortfolio() {
  console.log("[INFO] Fetching user portfolio from /api/portfolio ...");
  try {
    const res = await fetch("/api/portfolio");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const portfolio = await res.json();
    portfolioSymbols = portfolio
      .map(item => item.symbol && item.symbol.trim().toLowerCase())
      .filter(Boolean);
    console.log("[INFO] Loaded user portfolio symbols:", portfolioSymbols);
  } catch (err) {
    console.error("[ERROR] Failed to fetch user portfolio:", err);
  }
}

async function loadCorporateActions() {
  console.log("[INFO] Loading corp_actions.csv ...");
  return new Promise((resolve, reject) => {
    Papa.parse("/static/assets/csv/corp_actions.csv", {
      header: true,
      download: true,
      skipEmptyLines: true,
      complete: (results) => {
        console.log("[INFO] Loaded corp_actions.csv records:", results.data.length);
        resolve(results.data);
      },
      error: (err) => {
        console.error("[ERROR] Failed to load corp_actions.csv:", err);
        reject(err);
      }
    });
  });
}

async function loadAndRender() {
  try {
    await loadUserPortfolio();
    const corpActions = await loadCorporateActions();

    allData = corpActions.filter(row => {
      const securityName = row["Security Name"];
      return securityName && portfolioSymbols.includes(securityName.trim().toLowerCase());
    });

    console.log(`[INFO] Filtered corporate actions to ${allData.length} portfolio-matching records.`);

    populateSecurityFilterOptions(allData);
    renderGrid(allData);
  } catch (err) {
    console.error("[ERROR] loadAndRender failed:", err);
  }
}

// Event Listeners
document.getElementById('applySecurityBtn').addEventListener('click', applyFilters);
document.getElementById('exDateFilter').addEventListener('change', applyFilters);
document.getElementById('recordDateFilter').addEventListener('change', applyFilters);

// Init
window.addEventListener('load', () => {
  loadAndRender();
});
