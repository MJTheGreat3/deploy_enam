$(document).ready(function () {
  let portfolio = [];

  async function fetchPortfolio() {
    try {
      const res = await fetch("/api/portfolio");
      portfolio = await res.json();
      console.log("[DEBUG] Portfolio loaded:", portfolio);
      renderPortfolio();
    } catch (err) {
      console.error("[ERROR] Failed to fetch portfolio:", err);
    }
  }

  async function addSymbol(symbol, name) {
    const res = await fetch("/api/portfolio", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, name }),
    });
    if (res.ok) await fetchPortfolio();
  }

  async function removeSymbol(symbol) {
    const res = await fetch("/api/portfolio", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol }),
    });
    if (res.ok) await fetchPortfolio();
  }

  function renderPortfolio() {
    const list = $("#companyList").empty();
    portfolio.forEach((item) => {
      list.append(`
        <div class="portfolio-badge">
          <span class="symbol">${item.symbol}</span>
          <span class="name">${item.name}</span>
          <button class="portfolio-remove" data-symbol="${item.symbol}">
            <img src="/static/assets/img/close.svg" alt="Remove" class="close-icon">
          </button>

        </div>
      `);
    });
    $(".remove-btn").on("click", function () {
      removeSymbol($(this).data("symbol"));
    });
  }

  function sortResults(results, query) {
    const q = query.toLowerCase();

    function rank(item) {
      const symbol = item.Symbol.toLowerCase();
      const name = item.Name.toLowerCase();

      if (symbol.startsWith(q)) return 1;
      if (name.startsWith(q)) return 2;
      if (symbol.includes(q)) return 3;
      if (name.includes(q)) return 4;
      return 5;
    }

    return results.sort((a, b) => rank(a) - rank(b));
  }

  $("#companySearch").on("input", function () {
    const val = $(this).val().toLowerCase();
    const results = $("#searchResults").empty().toggle(val.length >= 2);
    if (val.length < 2) return;

    Papa.parse("../static/assets/csv/symbols.csv", {
      download: true,
      header: true,
      complete: function (res) {
        let matches = res.data.filter(r =>
          r.Symbol && (r.Symbol.toLowerCase().includes(val) || r.Name.toLowerCase().includes(val))
        );

        matches = sortResults(matches, val);

        matches.forEach((c) => {
          results.append(`
            <a href="#" class="list-group-item company-option">
              <b>${c.Symbol}</b><br>
              <small>${c.Name}</small>
            </a>
          `);
        });
      },
    });
  });

  $("#searchResults").on("click", ".company-option", function (e) {
    e.preventDefault();
    const symbol = $(this).find("b").text();
    const name = $(this).find("small").text();
    addSymbol(symbol, name);
    $("#companySearch").val("");
    $("#searchResults").hide();
  });

  $(document).on("click", (e) => {
    if (!$(e.target).closest("#companySearch, #searchResults").length) {
      $("#searchResults").hide();
    }
  });

  $("#applyChangesBtn").on("click", async function () {
    $(this).prop("disabled", true).text("Applying...");
    try {
      const res = await fetch("/api/portfolio/apply", { method: "POST" });
      if (res.ok) {
        alert("Changes applied successfully!");
        await fetchPortfolio();
      } else {
        alert("Error applying changes!");
      }
    } catch (err) {
      console.error("[ERROR] Apply Changes:", err);
      alert("Error applying changes!");
    } finally {
      $(this).prop("disabled", false).text("Apply Changes");
    }
  });

  fetchPortfolio();
});
