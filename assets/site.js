(function () {
  var storageKey = "hakketjakLocale";

  function supportedLocales() {
    var select = document.getElementById("language-select");
    if (!select) return ["nl", "en"];
    return Array.prototype.map.call(select.options, function (option) {
      return option.value;
    });
  }

  function hashLocale() {
    return (window.location.hash || "").replace(/^#/, "").toLowerCase();
  }

  function englishLocale(supported) {
    if (supported.indexOf("en") !== -1) return "en";
    if (supported.indexOf("en-gb") !== -1) return "en-gb";
    if (supported.indexOf("en-us") !== -1) return "en-us";
    return supported[0] || "en";
  }

  function isEnglish(locale) {
    return locale === "en" || locale === "en-gb" || locale === "en-us";
  }

  function resolveLocale(locale, supported) {
    var requested = (locale || "").toLowerCase();
    if (requested && supported.indexOf(requested) !== -1) return requested;
    if (isEnglish(requested)) return englishLocale(supported);
    if (requested) return englishLocale(supported);
    if (supported.indexOf("nl") !== -1) return "nl";
    return englishLocale(supported);
  }

  function browserCandidates(full) {
    var alias = {
      "zh-cn": "zh-hans",
      "zh-sg": "zh-hans",
      "zh-tw": "zh-hant",
      "zh-hk": "zh-hant",
      "zh-mo": "zh-hant",
      "pt-br": "pt-br",
      "pt": "pt-pt",
      "es-mx": "es-mx",
      "es": "es-es",
      "en-gb": "en-gb",
      "en-us": "en-us",
      "fr-ca": "fr-ca",
      no: "nb",
      nn: "nb",
      tl: "fil"
    };
    var primary = full.split("-")[0];
    var list = [];
    function add(value) {
      if (value && list.indexOf(value) === -1) list.push(value);
    }
    add(full);
    add(alias[full]);
    add(primary);
    add(alias[primary]);
    if (primary === "en") {
      add("en");
      add("en-gb");
      add("en-us");
    }
    return list;
  }

  function initialLocale() {
    var hash = hashLocale();
    if (hash) return hash;
    try {
      var stored = window.localStorage.getItem(storageKey);
      if (stored) return stored.toLowerCase();
    } catch (error) {}
    var full = (navigator.language || "").toLowerCase();
    var supported = supportedLocales();
    var candidates = browserCandidates(full);
    for (var i = 0; i < candidates.length; i++) {
      if (supported.indexOf(candidates[i]) !== -1) return candidates[i];
    }
    if (supported.indexOf("nl") !== -1) return "nl";
    return englishLocale(supported);
  }

  function syncSelectSizers() {
    document.querySelectorAll(".language-select-wrap select").forEach(function (select) {
      var wrap = select.parentElement;
      if (!wrap) return;
      var sizer = wrap.querySelector(".select-sizer");
      if (!sizer) {
        sizer = document.createElement("span");
        sizer.className = "select-sizer";
        sizer.setAttribute("aria-hidden", "true");
        wrap.insertBefore(sizer, select);
      }
      var option = select.options[select.selectedIndex];
      sizer.textContent = option ? option.textContent : "";
    });
  }

  function textFrom(element, prefix, lang) {
    return element.getAttribute(prefix + lang)
      || element.getAttribute(prefix + "en")
      || element.getAttribute(prefix + "en-gb")
      || element.getAttribute(prefix + "en-us")
      || "";
  }

  function applyLocale(locale, updateHash) {
    var supported = supportedLocales();
    var requested = (locale || "").toLowerCase();
    var lang = resolveLocale(requested, supported);
    var root = document.documentElement;
    root.lang = lang;
    root.dir = lang === "ar" || lang === "he" ? "rtl" : "ltr";

    var title = textFrom(root, "data-title-", lang);
    var description = textFrom(root, "data-description-", lang);
    if (title) document.title = title;
    var meta = document.querySelector('meta[name="description"]');
    if (meta && description) meta.setAttribute("content", description);

    var select = document.getElementById("language-select");
    if (select && supported.indexOf(lang) !== -1) select.value = lang;

    document.querySelectorAll("#app-select option[data-label-en], #app-select option[data-label-nl]").forEach(function (option) {
      var label = textFrom(option, "data-label-", lang);
      if (label) option.textContent = label;
    });

    document.querySelectorAll("[data-placeholder-en], [data-placeholder-nl], [data-placeholder-en-gb]").forEach(function (field) {
      var placeholder = textFrom(field, "data-placeholder-", lang);
      if (placeholder) field.placeholder = placeholder;
    });

    document.querySelectorAll("img[data-alt-en], img[data-alt-nl], img[data-alt-en-gb]").forEach(function (image) {
      var alt = textFrom(image, "data-alt-", lang);
      if (alt) image.alt = alt;
    });

    syncSelectSizers();

    try { window.localStorage.setItem(storageKey, lang); } catch (error) {}

    var hashShouldUpdate = updateHash || (requested && requested !== lang);
    if (hashShouldUpdate && window.location.hash !== "#" + lang) {
      history.replaceState(null, "", "#" + lang);
    }
  }

  var select = document.getElementById("language-select");
  if (select) {
    select.addEventListener("change", function (event) {
      applyLocale(event.target.value, true);
    });
  }

  function pageSection() {
    var path = window.location.pathname;
    if (/\/contact\/?$/.test(path)) return "contact/";
    if (/\/privacy\/?$/.test(path)) return "privacy/";
    return "";
  }

  var appSelect = document.getElementById("app-select");
  if (appSelect) {
    appSelect.addEventListener("change", function () {
      var lang = document.documentElement.lang || "en";
      var target = appSelect.value || "/";
      if (target.slice(-1) !== "/") target += "/";
      var section = target === "/" ? "" : pageSection();
      window.location.assign(target + section + "#" + lang);
    });
  }

  window.addEventListener("hashchange", function () {
    var hash = hashLocale();
    if (hash) applyLocale(hash, false);
  });

  applyLocale(initialLocale(), window.location.hash === "");
})();
