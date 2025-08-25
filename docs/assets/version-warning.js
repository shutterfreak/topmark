// topmark:header:start
//
//   file         : version-warning.js
//   file_relpath : docs/assets/version-warning.js
//   project      : TopMark
//   license      : MIT
//   copyright    : (c) 2025 Olivier Biot
//
// topmark:header:end

(function () {
  // If running on Read the Docs, this is populated with metadata (including "version")
  var data = window.READTHEDOCS_DATA || null;
  var isRTD = !!data;

  // Determine if we should show the banner
  var isLatest;
  if (isRTD) {
    // On RTD, only show for the "latest" (development) version
    isLatest = data.version === "latest";
  } else {
    // Local dev: assume we're previewing the development docs.
    // If you later serve a tagged copy locally under /en/stable or /en/vX.Y.Z, this will hide the banner.
    var path = window.location.pathname;
    isLatest = !/\/en\/(stable|v\d+\.\d+(?:\.\d+)?)\//.test(path);
  }

  if (!isLatest) return;

  // Always link to the published stable docs on RTD to avoid local 404s
  var stableUrl = "https://topmark.readthedocs.io/en/stable/";

  var bar = document.createElement("div");
  bar.setAttribute("role", "note");
  bar.style.cssText =
    "position:sticky;top:0;z-index:1000;padding:.6rem 1rem;" +
    "background:#fff3cd;border-bottom:1px solid #ffe58f;" +
    "font:500 14px/1.4 system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Cantarell,Helvetica Neue,Arial,sans-serif;" +
    "color:#593d00";
  bar.innerHTML =
    'You are viewing the <strong>development version</strong> of TopMark’s docs. ' +
    'See the <a href="' + stableUrl + '" style="text-decoration:underline">stable docs</a>.';

  // Insert at the very top of the body
  document.body.insertBefore(bar, document.body.firstChild);
})();