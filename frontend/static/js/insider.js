$(document).ready(function () {
  loadTable({
    id: "#insiderTable",
    controlsId: "#insiderControls",
    csv: "../static/assets/csv/insider_trading.csv",
    dateField: "Broadcast Date/Time",
    format: "dd-mmm-yyyy",
    nowrapColumns: ["Stock", "Amount", "Value", "Attachment", "Time"]
  });
});
