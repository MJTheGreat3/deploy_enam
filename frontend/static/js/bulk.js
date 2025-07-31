$(document).ready(() => {
  loadDealsTable({
    id: "#bulkDealsTable",
    csv: "/static/assets/csv/bulk_deals.csv",
    dateField: "Deal Date",
    format: "dd/mm/yyyy"
  });
});
