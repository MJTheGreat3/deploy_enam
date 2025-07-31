// ✅ table_utils.js - supports datetime sorting for HH:mm:ss and HH:mm, nowrap/wrap columns, download icons, everything center-aligned

function loadTable(config) {
  const { id, controlsId, csv, dateField, columnMap, nowrapColumns = [] } = config;
  let portfolioCompanies = [];

  async function getPortfolio() {
    try {
      const res = await fetch("/api/portfolio");
      const portfolio = await res.json();
      portfolioCompanies = portfolio.map((item) => item.symbol);
      console.log("[INFO] Loaded portfolio for filtering:", portfolioCompanies);
    } catch (err) {
      console.error("[ERROR] Failed to load portfolio:", err);
    }
  }

  function parseDate(str) {
    if (!str) return null;
    try {
      return new Date(
        str.replace(/(\d{2})-([A-Za-z]{3})-(\d{4})/, (_, d, m, y) => {
          const months = {
            Jan: "01", Feb: "02", Mar: "03", Apr: "04", May: "05", Jun: "06",
            Jul: "07", Aug: "08", Sep: "09", Oct: "10", Nov: "11", Dec: "12"
          };
          return `${y}-${months[m]}-${d}`;
        })
      );
    } catch {
      return null;
    }
  }

  function filterData(data, range) {
    const now = new Date();
    const cutoff = new Date();

    if (range === "1day") cutoff.setDate(now.getDate() - 1);
    else if (range === "1week") cutoff.setDate(now.getDate() - 7);
    else if (range === "1month") cutoff.setMonth(now.getMonth() - 1);

    return data.filter((row) => {
      let dateOk = true;
      if (range !== "all_time") {
        const date = parseDate(row[dateField]);
        if (!(date instanceof Date) || isNaN(date)) return false;
        dateOk = date >= cutoff;
      }

      const stock = row["Stock"];
      const stockOk = portfolioCompanies.some(
        s => s && stock && stock.toLowerCase().includes(s.toLowerCase())
      );

      return dateOk && stockOk;
    });
  }

  function renderDateButtons(onChange) {
    const btnGroup = $(`
      <div class="date-button-group mb-3 text-center">
        <button class="btn btn-outline-primary filter-btn" data-range="1day">1 Day</button>
        <button class="btn btn-outline-primary filter-btn" data-range="1week">1 Week</button>
        <button class="btn btn-outline-primary filter-btn" data-range="1month">1 Month</button>
        <button class="btn btn-outline-primary filter-btn" data-range="all_time">All Time</button>
      </div>
    `);
    btnGroup.on("click", "button", function () {
      btnGroup.find("button").removeClass("active");
      $(this).addClass("active");
      onChange($(this).data("range"));
    });
    btnGroup.find('[data-range="all_time"]').addClass("active");
    return btnGroup;
  }

  Papa.parse(csv, {
    download: true,
    header: true,
    skipEmptyLines: true,
    complete: async function (results) {
      await getPortfolio();

      const originalData = results.data.filter((row) =>
        Object.values(row).some((cell) => (cell || "").trim() !== "")
      );

      let currentRange = "all_time";
      $(controlsId).append(renderDateButtons((range) => {
        currentRange = range;
        update();
      }));

      function update() {
        const filtered = filterData(originalData, currentRange);

        let displayData;
        let columns;

        if (columnMap && Object.keys(columnMap).length > 0) {
          // ✅ Apply mapping if provided
          displayData = filtered.map(row => {
            const newRow = {};
            Object.keys(columnMap).forEach(key => {
              newRow[columnMap[key]] = row[key];
            });
            return newRow;
          });

          columns = Object.values(columnMap).map(col => {
            if (col === "Attachment") {
              return {
                title: col,
                data: col,
                className: "text-center",
                render: renderAttachment
              };
            }
            const cellClass = `text-center ${nowrapColumns.includes(col) ? 'nowrap-cell' : 'wrap-cell'}`;
            return { title: col, data: col, className: cellClass };
          });

        } else {
          // ✅ No mapping: use CSV as-is
          displayData = [...filtered];

          const csvHeaders = Object.keys(originalData[0]);
          columns = csvHeaders.map(col => {
            if (col === "Attachment") {
              return {
                title: col,
                data: col,
                className: "text-center",
                render: renderAttachment
              };
            }
            const cellClass = `text-center ${nowrapColumns.includes(col) ? 'nowrap-cell' : 'wrap-cell'}`;
            return { title: col, data: col, className: cellClass };
          });
        }

        const timeIndex = columns.findIndex(c => c.title === "Time");

        if ($.fn.DataTable.isDataTable(id)) {
          $(id).DataTable().clear().rows.add(displayData).draw();
        } else {
          // ✅ Register both datetime formats for sorting
          $.fn.dataTable.moment('DD-MMM-YYYY HH:mm:ss');
          $.fn.dataTable.moment('DD-MMM-YYYY HH:mm');

          $(id).DataTable({
            data: displayData,
            columns: columns,
            pageLength: 10,
            responsive: true,
            autoWidth: false,
            order: timeIndex >= 0 ? [[timeIndex, 'desc']] : [],
            createdRow: function(row) {
              $(row).addClass('text-center');
            },
            headerCallback: function(thead) {
              $(thead).find('th').addClass('text-center');
            }
          });
        }
      }

      update();
    }
  });

  function renderAttachment(data) {
    if (!data) return '';
    return `
      <div style="text-align: center;">
        <a href="${data}" target="_blank">
          <img class="download-icon" src="/static/assets/img/download.svg" alt="Download" style="height:20px;width:20px;">
        </a>
      </div>`;
  }
}
