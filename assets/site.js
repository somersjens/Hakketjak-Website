(function () {
  var locales = ["nl", "en"];
  var storageKey = "hakketjakLocale";

  function hashLocale() {
    return (window.location.hash || "").replace("#", "").toLowerCase();
  }

  function initialLocale() {
    var hash = hashLocale();
    if (locales.indexOf(hash) !== -1) return hash;
    try {
      var stored = window.localStorage.getItem(storageKey);
      if (locales.indexOf(stored) !== -1) return stored;
    } catch (error) {}
    var browser = (navigator.language || "").slice(0, 2).toLowerCase();
    if (locales.indexOf(browser) !== -1) return browser;
    return "nl";
  }

  function applyLocale(locale, updateHash) {
    var lang = locales.indexOf(locale) === -1 ? "nl" : locale;
    document.documentElement.lang = lang;

    var title = document.documentElement.getAttribute("data-title-" + lang);
    var description = document.documentElement.getAttribute("data-description-" + lang);
    if (title) document.title = title;
    var meta = document.querySelector('meta[name="description"]');
    if (meta && description) meta.setAttribute("content", description);

    var select = document.getElementById("language-select");
    if (select) select.value = lang;

    try { window.localStorage.setItem(storageKey, lang); } catch (error) {}

    if (updateHash && window.location.hash !== "#" + lang) {
      history.replaceState(null, "", "#" + lang);
    }
  }

  var select = document.getElementById("language-select");
  if (select) {
    select.addEventListener("change", function (event) {
      applyLocale(event.target.value, true);
    });
  }

  window.addEventListener("hashchange", function () {
    var hash = hashLocale();
    if (locales.indexOf(hash) !== -1) applyLocale(hash, false);
  });

  applyLocale(initialLocale(), window.location.hash === "");
})();
