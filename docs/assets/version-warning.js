// topmark:header:start
//
//   project      : TopMark
//   file         : version-warning.js
//   file_relpath : docs/assets/version-warning.js
//   license      : MIT
//   copyright    : (c) 2025 Olivier Biot
//
// topmark:header:end

(function () {
  var bannerId = "topmark-rtd-version-warning";
  // If running on Read the Docs, this is populated with metadata (including "version")
  var rtdData = window.READTHEDOCS_DATA || null;
  var hostname = window.location.hostname;
  var isLocalPreview =
    window.location.protocol === "file:" ||
    hostname === "localhost" ||
    hostname === "127.0.0.1" ||
    hostname === "[::1]" ||
    hostname === "::1";
  var isDevelopmentVersion = rtdData ? rtdData.version === "latest" : isLocalPreview;

  // The version is global to a deployed site, so prevent duplicate banners if a future theme
  // release re-evaluates configured scripts during instant navigation.
  if (!isDevelopmentVersion || document.getElementById(bannerId)) return;

  var bar = document.createElement("div");
  var emphasis = document.createElement("strong");
  var stableLink = document.createElement("a");

  bar.id = bannerId;
  bar.setAttribute("role", "note");
  bar.style.cssText =
    "box-sizing:border-box;margin:0;padding:.6rem 1rem;background:#fff3cd;" +
    "border-bottom:1px solid #ffe58f;" +
    "font:500 14px/1.4 system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Cantarell,Helvetica Neue,Arial,sans-serif;" +
    "color:#593d00";

  emphasis.textContent = "development version";

  // Always link to the published stable docs on RTD to avoid local 404s
  stableLink.href = "https://topmark.readthedocs.io/en/stable/";
  stableLink.textContent = "stable docs";
  stableLink.style.textDecoration = "underline";

  bar.appendChild(document.createTextNode("You are viewing the "));
  bar.appendChild(emphasis);
  bar.appendChild(document.createTextNode(" of TopMark’s docs. See the "));
  bar.appendChild(stableLink);
  bar.appendChild(document.createTextNode("."));

  // Keep the notice in normal document flow so it cannot overlap Zensical's fixed UI.
  document.body.insertBefore(bar, document.body.firstChild);
})();
