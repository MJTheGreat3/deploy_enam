$(document).ready(() => {
  const userName = document.body.dataset.userName;
  if (userName) {
    $("#welcomeMessage").html(`Welcome, <strong>${userName}</strong>!`);
  }
});
