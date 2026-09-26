if (typeof window !== "undefined" && typeof require !== "undefined") {
  try {
    const teamsJs = require("@microsoft/teams-js");
    module.exports = teamsJs;
  } catch (e) {
    console.warn("@microsoft/teams-js not available:", e.message);
    module.exports = null;
  }
}
