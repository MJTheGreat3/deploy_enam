document.addEventListener('DOMContentLoaded', async () => {
  await loadUserPortfolio();
  if (state.portfolioSymbols && state.portfolioSymbols.size) {
    setupFilterAndLoad('../static/assets/csv/trd_deviation.csv', 'trd', 'AVG_TTL_TRD_QNTY', 'NEW_TTL_TRD_QNTY');
    setupFilterAndLoad('../static/assets/csv/deliv_deviation.csv', 'deliv', 'AVG_DELIV_QTY', 'NEW_DELIV_QTY');
  } else {
    console.error("[ERROR] No portfolio symbols loaded. Cannot display deviations.");
  }
});

const state = {};

// === Fetch user portfolio from /api/portfolio ===
async function loadUserPortfolio() {
  console.log("[INFO] Fetching user portfolio from /api/portfolio ...");
  try {
    const res = await fetch("/api/portfolio");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const portfolio = await res.json();
    const symbols = portfolio
      .map(item => item.symbol && item.symbol.trim().toLowerCase())
      .filter(Boolean);

    state.portfolioSymbols = new Set(symbols);
    console.log("[INFO] Loaded user portfolio symbols:", Array.from(state.portfolioSymbols));
  } catch (err) {
    console.error("[ERROR] Failed to fetch user portfolio:", err);
    state.portfolioSymbols = new Set();
  }
}

// === Load and filter deviation data ===
function setupFilterAndLoad(csvFile, section, avgField, newField) {
  Papa.parse(csvFile, {
    header: true,
    download: true,
    complete: results => {
      const data = results.data.filter(row => {
        const sym = row.SYMBOL?.trim().toLowerCase();
        return sym && row[avgField] && state.portfolioSymbols.has(sym);
      });

      state[section] = { data, avgField, newField, filter: [] };

      initFilter(section, data);
      renderAll(section);
    }
  });
}

function initFilter(section, data) {
  const select = document.getElementById(`${section}-filter`);
  select.innerHTML = '';

  const symbols = Array.from(new Set(data.map(d => d.SYMBOL))).sort();
  symbols.forEach(sym => {
    const option = document.createElement('option');
    option.value = sym;
    option.textContent = sym;
    select.appendChild(option);
  });

  const choices = new Choices(select, {
    removeItemButton: true,
    searchEnabled: true,
    placeholderValue: 'Filter symbols',
  });

  select.addEventListener('change', () => {
    state[section].filter = Array.from(select.selectedOptions).map(o => o.value);
    renderAll(section);
  });
}

function renderAll(section) {
  const { data, avgField, newField, filter } = state[section];
  const filtered = filter.length ? data.filter(d => filter.includes(d.SYMBOL)) : data;
  renderGraphView(filtered, section, avgField, newField);
}

function renderGraphView(data, section, avgField, newField) {
  const container = document.getElementById(`${section}-graph-view`);
  container.innerHTML = '';

  const tooltip = d3.select("#tooltip");

  if (!data.length) {
    container.innerHTML = '<p>No data for selected symbols.</p>';
    return;
  }

  data.forEach(row => {
    const symbol = row.SYMBOL;
    const avg = +row[avgField];
    const actual = +row[newField];
    const pct = +row.PCT_DEVIATION;

    let maxValue = Math.max(avg, actual);
    const buffer = avg * 0.5;
    let maxScale = maxValue + buffer;
    if (maxScale === 0) maxScale = 1;

    const color = pct > 10 ? "green" : pct < -10 ? "red" : "orange";

    const scale = d3.scaleLinear()
      .domain([0, maxScale])
      .range([50, 300]);

    const svg = d3.create("svg");

    // Background track
    svg.append("rect")
      .attr("x", 50)
      .attr("y", 20)
      .attr("width", 250)
      .attr("height", 10)
      .attr("fill", "#eee");

    // Actual bar
    svg.append("rect")
      .attr("x", 50)
      .attr("y", 20)
      .attr("width", Math.max(0, scale(actual) - 50))
      .attr("height", 10)
      .attr("fill", color)
      .attr("opacity", 0.8);

    // AVG marker line
    const avgX = Math.max(50, Math.min(300, scale(avg)));
    svg.append("line")
      .attr("x1", avgX)
      .attr("x2", avgX)
      .attr("y1", 15)
      .attr("y2", 35)
      .attr("stroke", "black")
      .attr("stroke-width", 2);

    // Hover overlay
    svg.append("rect")
      .attr("x", 0)
      .attr("y", 0)
      .attr("width", 400)
      .attr("height", 50)
      .attr("fill", "transparent")
      .on("mouseover", () => {
        tooltip.style("opacity", 1)
          .html(`<strong>${symbol}</strong><br/>Avg: ${avg}<br/>New: ${actual}<br/>% Change: ${pct.toFixed(2)}%`);
      })
      .on("mousemove", (event) => {
        tooltip
          .style("left", (event.pageX + 15) + "px")
          .style("top", (event.pageY - 28) + "px");
      })
      .on("mouseout", () => tooltip.style("opacity", 0));

    // Card container
    const card = document.createElement('div');
    card.className = 'graph-card';

    // Stock name on top
    const stockName = document.createElement('div');
    stockName.className = 'stock-name';
    stockName.textContent = symbol;
    card.appendChild(stockName);

    // Graph row
    const graphRow = document.createElement('div');
    graphRow.className = 'graph-row';
    graphRow.appendChild(svg.node());

    const pctText = document.createElement('div');
    pctText.className = 'percent-text';
    pctText.textContent = `${pct.toFixed(2)}%`;
    pctText.style.color = color;
    graphRow.appendChild(pctText);

    card.appendChild(graphRow);

    container.appendChild(card);
  });
}
