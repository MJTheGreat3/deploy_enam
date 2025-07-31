$(document).ready(() => {
  loadDealsTable({
    id: "#blockDealsTable",
    csv: "/static/assets/csv/block_deals.csv",
    dateField: "Deal Date",
    format: "dd/mm/yyyy"
  });
});
