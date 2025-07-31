$(document).ready(function () {
  loadTable({
    id: "#announcementTable",
    controlsId: "#announcementControls",
    csv: "../static/assets/csv/announcements.csv",
    dateField: "Broadcast Date/Time",
    format: "dd-mmm-yyyy",
    nowrapColumns: ["Stock", "Attachment", "Time"]
  });
});
