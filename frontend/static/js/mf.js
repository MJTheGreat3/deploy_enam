let originalData = [];
let stockChoices;
let activeFunds = new Set();
let allStocks = [];

async function loadData() {
  const response = await fetch("../static/assets/csv/mutual_fund_data.xlsx");
  const arrayBuffer = await response.arrayBuffer();
  const workbook = XLSX.read(arrayBuffer, { type: "array" });
  const sheet = workbook.Sheets[workbook.SheetNames[0]];
  const rawData = XLSX.utils.sheet_to_json(sheet, { defval: null });

  const tableData = [];

  for (const row of rawData) {
    const stock = row["Stock"]?.toString().trim();
    const fund = row["Fund"]?.toString().trim();
    const buy = typeof row["Buy"] === "number" ? row["Buy"] : null;
    const sell = typeof row["Sell"] === "number" ? row["Sell"] : null;

    if (!stock || !fund || (buy === null && sell === null)) continue;

    tableData.push({ Stock: stock, Fund: fund, Buy: buy, Sell: sell });
  }

  return tableData;
}

function renderFundBadges(funds) {
  const container = document.getElementById("fundBadges");
  container.innerHTML = "";

  funds.forEach((fund) => {
    const badge = document.createElement("div");
    badge.classList.add("fund-badge", "active");
    badge.textContent = fund;
    badge.addEventListener("click", () => toggleFundBadge(badge, fund));
    container.appendChild(badge);
    activeFunds.add(fund);
  });
}

function toggleFundBadge(badge, fund) {
  if (badge.classList.contains("active")) {
    badge.classList.remove("active");
    badge.classList.add("inactive");
    activeFunds.delete(fund);
  } else {
    badge.classList.remove("inactive");
    badge.classList.add("active");
    activeFunds.add(fund);
  }
  applyFilters();
}

function toggleAllFunds(select = true) {
  const badges = document.querySelectorAll(".fund-badge");
  badges.forEach((badge) => {
    const fund = badge.textContent;
    if (select) {
      badge.classList.remove("inactive");
      badge.classList.add("active");
      activeFunds.add(fund);
    } else {
      badge.classList.remove("active");
      badge.classList.add("inactive");
      activeFunds.delete(fund);
    }
  });
  applyFilters();
}

function populateStockSelect(stocks) {
  allStocks = stocks; // Save for resetting later
  const stockBar = document.querySelector(".stock-bar");
  stockBar.innerHTML = `
    <div class="stock-bar-header">
      <h5>STOCKS</h5>
      <button id="clearStockFilters">Remove All</button>
    </div>
    <select id="stockFilter" multiple></select>
  `;

  const stockSelect = document.getElementById("stockFilter");

  stockChoices = new Choices(stockSelect, {
    removeItemButton: true,
    searchEnabled: true,
    placeholderValue: "Search or select stocks...",
    shouldSort: true,
    position: "bottom",
    renderChoiceLimit: -1,
    searchChoices: true,
  });

  stockChoices.setChoices(
    stocks.map((s) => ({ value: s, label: s })),
    "value",
    "label",
    true
  );

  document.getElementById("clearStockFilters").addEventListener("click", () => {
    stockChoices.removeActiveItems(); // Only remove selection, keep choices
    applyFilters();
  });
}

function populateFilters(data) {
  const stocks = [...new Set(data.map((d) => d.Stock))].sort();
  const funds = [...new Set(data.map((d) => d.Fund))].sort();

  renderFundBadges(funds);
  populateStockSelect(stocks);
}

function getSelectedStocks() {
  return stockChoices ? stockChoices.getValue(true) : [];
}

function applyFilters() {
  const selectedStocks = getSelectedStocks();

  const filtered = originalData.filter((row) => {
    const stockMatch =
      selectedStocks.length === 0 || selectedStocks.includes(row.Stock);
    const fundMatch = activeFunds.size === 0 || activeFunds.has(row.Fund);
    return stockMatch && fundMatch;
  });

  renderTableWithRowspan(filtered);
}

function renderTableWithRowspan(data) {
  const output = document.getElementById("output");

  if (data.length === 0) {
    output.innerHTML =
      "<div class='no-data-message'>No data found matching your filters.</div>";
    return;
  }

  const grouped = {};
  data.forEach((row) => {
    if (!grouped[row.Stock]) grouped[row.Stock] = [];
    grouped[row.Stock].push(row);
  });

  let html = `
    <div class="table-container">
      <div class="table-responsive">
        <table class="table table-hover">
          <thead class="sticky-header">
            <tr>
              <th>Stock</th>
              <th>Fund</th>
              <th>Buy</th>
              <th>Sell</th>
            </tr>
          </thead>
          <tbody>`;

  for (const stock in grouped) {
    const rows = grouped[stock];
    rows.forEach((row, idx) => {
      const buyClass = row.Buy ? "buy-cell" : "";
      const sellClass = row.Sell ? "sell-cell" : "";
      const rowClass = row.Buy ? "hover-green" : row.Sell ? "hover-red" : "";

      html += `<tr class="${rowClass}">`;

      if (idx === 0) {
        html += `<td rowspan="${rows.length}" class="align-middle table-dark-text rowspan-stock">${stock}</td>`;
      }

      html += `<td class="table-dark-text">${row.Fund}</td>`;
      html += `<td class="text-center ${buyClass} table-dark-text">${
        row.Buy ? row.Buy.toLocaleString("en-IN") : "-"
      }</td>`;
      html += `<td class="text-center ${sellClass} table-dark-text">${
        row.Sell ? row.Sell.toLocaleString("en-IN") : "-"
      }</td>`;

      html += `</tr>`;
    });
  }

  html += `
          </tbody>
        </table>
      </div>
    </div>`;

  output.innerHTML = html;
}

$(async function () {
  originalData = await loadData();
  if (originalData.length === 0) {
    $("#output").html(
      "<div class='no-data-message'>No valid data found in the source file.</div>"
    );
    return;
  }

  populateFilters(originalData);
  renderTableWithRowspan(originalData);

  $(document).on("change", "#stockFilter", applyFilters);
  $("#selectAllFunds").on("click", () => toggleAllFunds(true));
  $("#deselectAllFunds").on("click", () => toggleAllFunds(false));
});
