#!/usr/bin/env python3
"""Move In ontwikkeling apps onto Educatie voor kinderen once they are live.

The source of truth is the public developer page
https://apps.apple.com/us/developer/jens-somers/id1847195635
and each app's US App Store page. An app is updated only when its card is
still in the homepage In ontwikkeling section and its name appears on that
developer page. Apps already in another section, and store apps that have
no In ontwikkeling card, are left untouched.

Running this writes nothing when there is no such match.
"""

from __future__ import annotations

import html
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEVELOPER_URL = "https://apps.apple.com/us/developer/jens-somers/id1847195635"
# Buzzkill is already on the site and on this developer page. A response
# that does not include it is not a trustworthy listing.
REQUIRED_APP_ID = "6754295660"
MIN_STORE_APPS = 8
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)
APP_PATH = re.compile(r"/us/app/[A-Za-z0-9\-]+/id(\d+)\Z")
CARD_RE = re.compile(
    r'\n[ \t]*<li>\s*<a class="card app-card" href="([^"]+)">.*?\n[ \t]*</li>',
    re.S,
)
SIZE_RE = re.compile(r"\d+(?:\.\d+)? (?:MB|GB)\Z")
SKIP_DIRS = {"Dino Time", "hakketjak-website", ".git"}


@dataclass(frozen=True)
class StoreApp:
    name: str
    url: str
    app_id: str


@dataclass(frozen=True)
class Card:
    name: str
    href: str
    html: str


@dataclass(frozen=True)
class Release:
    href: str
    name: str
    url: str
    size: str
    languages: int


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"self-test failed: {message}")


def norm(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def name_matches(site_name: str, store_name: str) -> bool:
    site = norm(site_name).casefold()
    store = norm(store_name).casefold()
    if not site or not store.startswith(site):
        return False
    rest = store[len(site) :]
    return rest == "" or rest.startswith(":") or rest.startswith(" :")


def canonical_app_url(href: str) -> tuple[str, str] | None:
    href = html.unescape(href.strip())
    if href.startswith("/us/app/"):
        href = "https://apps.apple.com" + href
    parts = urllib.parse.urlsplit(href)
    if parts.scheme != "https" or parts.netloc != "apps.apple.com":
        return None
    match = APP_PATH.fullmatch(parts.path)
    if not match:
        return None
    return f"https://apps.apple.com{parts.path}", match.group(1)


def fetch(url: str) -> str:
    last_error: Exception | None = None
    for attempt in range(2):
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            raise SystemExit(f"could not fetch {url}: HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt == 0:
                time.sleep(2)
    raise SystemExit(f"could not fetch {url}: {last_error}")


def parse_store(page: str) -> list[StoreApp]:
    found: dict[str, StoreApp] = {}
    for tag in re.findall(r"<a\b[^>]*>", page, re.I):
        label = re.search(r'\baria-label="([^"]*)"', tag)
        href = re.search(r'\bhref="([^"]+)"', tag)
        if not label or not href:
            continue
        parsed = canonical_app_url(href.group(1))
        if not parsed or parsed[1] in found:
            continue
        url, app_id = parsed
        found[app_id] = StoreApp(norm(html.unescape(label.group(1))), url, app_id)
    return list(found.values())


def ensure_store(apps: list[StoreApp]) -> None:
    if len(apps) < MIN_STORE_APPS or all(app.app_id != REQUIRED_APP_ID for app in apps):
        raise SystemExit(
            f"developer page did not look complete ({len(apps)} apps); the site was not changed"
        )


def parse_size(page: str) -> str:
    match = re.search(r">Size</dt>\s*<dd>\s*([^<]+?)\s*</dd>", page)
    if not match:
        match = re.search(r'"title"\s*:\s*"Size"\s*,\s*"summary"\s*:\s*"([^"]+)"', page)
    if not match:
        raise SystemExit("the app page has no Size value; the site was not changed")
    size = re.sub(r"\s+", " ", html.unescape(match.group(1))).strip()
    if not SIZE_RE.fullmatch(size):
        raise SystemExit(f"unexpected size {size!r}; the site was not changed")
    return size


def parse_languages(page: str) -> int:
    match = re.search(r">Languages</dt>(.*?)(?:<dt\b|</section>|$)", page, re.S)
    if not match:
        raise SystemExit("the app page has no Languages value; the site was not changed")
    block = match.group(1)
    listed = re.search(r"<!-- HTML_TAG_START -->(.*?)<!-- HTML_TAG_END -->", block, re.S)
    if listed:
        text = html.unescape(re.sub(r"<[^>]+>", "", listed.group(1)))
        names = [part.strip() for part in text.split(",") if part.strip()]
        if names:
            return _checked_language_count(len(names))
    summary = re.search(r">\s*[^<]*?\s+and\s+(\d+)\s+more", block, re.I)
    if summary:
        return _checked_language_count(int(summary.group(1)) + 1)
    plain = re.search(r"<dd[^>]*>\s*(?:<[^>]+>\s*)*([^<]+)", block, re.S)
    if plain:
        text = html.unescape(plain.group(1)).strip()
        if re.fullmatch(r"[A-Za-z][A-Za-z \-']*", text):
            return 1
    raise SystemExit("could not read the language list; the site was not changed")


def _checked_language_count(count: int) -> int:
    if not 1 <= count <= 200:
        raise SystemExit(f"unexpected language count {count}; the site was not changed")
    return count


def dutch_size(size: str) -> str:
    return size.replace(".", ",")


def section_bounds(page: str, title_id: str) -> tuple[int, int]:
    marker = f'aria-labelledby="{title_id}"'
    pos = page.find(marker)
    if pos < 0:
        raise SystemExit(f"homepage is missing {title_id}")
    start = page.rfind("<section", 0, pos)
    end = page.find("</section>", pos)
    if start < 0 or end < 0:
        raise SystemExit(f"homepage section {title_id} is broken")
    return start, end + len("</section>")


def split_grid(section: str) -> tuple[re.Match[str], list[Card]]:
    match = re.search(r'(<ul class="app-grid">)(.*?)(\n[ \t]*</ul>)', section, re.S)
    if not match:
        raise SystemExit("homepage is missing an app grid")
    inner = match.group(2)
    cards: list[Card] = []
    pos = 0
    for card in CARD_RE.finditer(inner):
        if card.start() != pos:
            raise SystemExit("unexpected markup between homepage app cards")
        pos = card.end()
        name = re.search(r"<h2>([^<]+)", card.group(0))
        if not name:
            raise SystemExit(f"app card {card.group(1)} has no title")
        cards.append(Card(name.group(1).strip(), card.group(1), card.group(0)))
    if pos != len(inner):
        raise SystemExit("unexpected markup after the last homepage app card")
    return match, cards


def grid_cards(page: str, title_id: str) -> list[Card]:
    start, end = section_bounds(page, title_id)
    _, cards = split_grid(page[start:end])
    return cards


def option_order(page: str) -> list[str]:
    hrefs: list[str] = []
    for title_id in ("productivity-title", "education-title", "development-title"):
        hrefs.extend(card.href for card in grid_cards(page, title_id))
    return ["/", *hrefs]


def select_options(page: str) -> list[tuple[str, str]]:
    match = re.search(r'<select id="app-select"[^>]*>(.*?)</select>', page, re.S)
    if not match:
        raise SystemExit("a page is missing the app menu")
    options = re.findall(r"[ \t]*<option\b.*?</option>", match.group(1), re.S)
    parsed: list[tuple[str, str]] = []
    for option in options:
        value = re.search(r'\bvalue="([^"]*)"', option)
        if not value:
            raise SystemExit("an app menu option has no value")
        parsed.append((value.group(1), option.strip()))
    return parsed


def select_values(page: str) -> list[str]:
    return [value for value, _option in select_options(page)]


def assert_selects_match_homepage(index: str, files: dict[str, str]) -> None:
    order = option_order(index)
    homepage_values = select_values(index)
    if homepage_values != order:
        raise SystemExit("the homepage app menu does not follow the homepage sections")
    for rel, content in files.items():
        if 'id="app-select"' not in content:
            continue
        if select_values(content) != order:
            raise SystemExit(f"{rel} app menu does not match the homepage")


def plan(index: str, store: list[StoreApp]) -> list[tuple[Card, StoreApp]]:
    cards = grid_cards(index, "development-title")
    claimed: set[str] = set()
    pairs: list[tuple[Card, StoreApp]] = []
    for card in sorted(cards, key=lambda item: len(item.name), reverse=True):
        hits = [
            app
            for app in store
            if app.app_id not in claimed and name_matches(card.name, app.name)
        ]
        if not hits:
            continue
        hits.sort(
            key=lambda app: (
                0 if norm(app.name).casefold() == norm(card.name).casefold() else 1,
                len(app.name),
            )
        )
        chosen = hits[0]
        claimed.add(chosen.app_id)
        pairs.append((card, chosen))
    positions = {card.href: position for position, card in enumerate(cards)}
    pairs.sort(key=lambda pair: positions[pair[0].href])
    return pairs


def with_meta(card_html: str, size: str, languages: int) -> str:
    if 'class="app-meta"' in card_html:
        raise SystemExit("an In ontwikkeling card already has a size line; the site was not changed")
    if languages == 1:
        nl_languages, en_languages = "1 taal", "1 language"
    else:
        nl_languages, en_languages = f"{languages} talen", f"{languages} languages"
    meta = (
        '<p class="app-meta">'
        f'<span class="nl">{dutch_size(size)} · {nl_languages}</span>'
        f'<span class="en">{size} · {en_languages}</span>'
        "</p>"
    )
    match = re.search(r"</h2>\n([ \t]*)", card_html)
    if not match:
        raise SystemExit("an app card has no title; the site was not changed")
    indent = match.group(1)
    replacement = f"</h2>\n{indent}{meta}\n{indent}"
    return card_html[: match.start()] + replacement + card_html[match.end() :]


def move_cards(index: str, releases: list[Release]) -> str:
    edu_start, edu_end = section_bounds(index, "education-title")
    dev_start, dev_end = section_bounds(index, "development-title")
    if not edu_start < edu_end <= dev_start < dev_end:
        raise SystemExit("homepage sections are in an unexpected order")
    education = index[edu_start:edu_end]
    development = index[dev_start:dev_end]
    edu_grid, edu_cards = split_grid(education)
    dev_grid, dev_cards = split_grid(development)
    by_href = {release.href: release for release in releases}
    staying: list[Card] = []
    moving: list[Card] = []
    for card in dev_cards:
        release = by_href.get(card.href)
        if release is None:
            staying.append(card)
            continue
        moving.append(Card(card.name, card.href, with_meta(card.html, release.size, release.languages)))
    if len(moving) != len(releases):
        raise SystemExit("a matched app is no longer in In ontwikkeling; the site was not changed")
    new_education = (
        education[: edu_grid.start(2)]
        + "".join(card.html for card in [*edu_cards, *moving])
        + education[edu_grid.start(3) :]
    )
    new_development = (
        development[: dev_grid.start(2)]
        + "".join(card.html for card in staying)
        + development[dev_grid.start(3) :]
    )
    return index[:edu_start] + new_education + index[edu_end:dev_start] + new_development + index[dev_end:]


def reorder_select(page: str, order: list[str]) -> str:
    match = re.search(r'(<select id="app-select"[^>]*>)(.*?)(</select>)', page, re.S)
    if not match:
        return page
    options = select_options(page)
    values = [value for value, _option in options]
    if values == order:
        return page
    if set(values) != set(order):
        raise SystemExit("the app menu and the homepage list different apps; the site was not changed")
    by_value = {value: option for value, option in options}
    lines = [f"          {by_value[value]}" for value in order]
    inner = "\n" + "\n".join(lines) + "\n        "
    return page[: match.start(2)] + inner + page[match.end(2) :]


def add_store_link(page: str, url: str) -> str:
    match = re.search(r'<div class="cta">(.*?)</div>', page, re.S)
    if not match:
        raise SystemExit("a released app page has no button row; the site was not changed")
    block = match.group(1)
    if url in block:
        return page
    if "apps.apple.com" in block:
        raise SystemExit("a released app page already has a different App Store link; the site was not changed")
    indent_match = re.search(r"\n([ \t]*)<a\b", block)
    indent = indent_match.group(1) if indent_match else "              "
    button = f'\n{indent}<a class="btn" href="{url}" target="_blank" rel="noopener noreferrer">App Store</a>'
    return page[: match.start(1)] + button + page[match.start(1) :]


def page_href(rel: str) -> str | None:
    parts = rel.split("/")
    if len(parts) < 2 or parts[-1] != "index.html":
        return None
    return f"/{parts[0]}/"


def render(index: str, files: dict[str, str], releases: list[Release]) -> dict[str, str]:
    moved = move_cards(index, releases)
    order = option_order(moved)
    updated_index = reorder_select(moved, order)
    updates: dict[str, str] = {}
    if updated_index != index:
        updates["index.html"] = updated_index
    released = {release.href: release for release in releases}
    for rel, content in files.items():
        updated = reorder_select(content, order) if 'id="app-select"' in content else content
        href = page_href(rel)
        release = released.get(href or "")
        if release is not None:
            updated = add_store_link(updated, release.url)
        if updated != content:
            updates[rel] = updated
    return updates


def iter_site_html(root: Path) -> list[tuple[str, Path]]:
    found: list[tuple[str, Path]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in SKIP_DIRS and not name.startswith("."))
        for name in sorted(filenames):
            if not name.endswith(".html") or name.startswith("."):
                continue
            path = Path(dirpath) / name
            rel = path.relative_to(root).as_posix()
            if rel != "index.html":
                found.append((rel, path))
    return found


def load(root: Path) -> tuple[str, dict[str, str]]:
    index = (root / "index.html").read_text(encoding="utf-8")
    files = {rel: path.read_text(encoding="utf-8") for rel, path in iter_site_html(root)}
    return index, files


def released_page_paths(href: str) -> list[str]:
    slug = href.strip("/")
    return [f"{slug}/index.html", f"{slug}/privacy/index.html", f"{slug}/contact/index.html"]


def run_self_test(root: Path) -> None:
    check(name_matches("Dino Time", "Dino Time: Learn the Clock"), "subtitle match")
    check(name_matches("Space Lion", "space lion"), "case match")
    check(not name_matches("Honey Slide", "Honey"), "short store name")
    check(not name_matches("Dino Time", "Dino Timer"), "longer word")
    check(not name_matches("Honey", "Honey Slide"), "longer store name")

    sample_store = """
    <a aria-label="Hungry Frog: Math &amp; Play" href="https://apps.apple.com/us/app/hungry-frog/id6797658197"></a>
    <a aria-label="Hungry Frog: Math &amp; Play" href="https://apps.apple.com/us/app/hungry-frog/id6797658197?mt=8"></a>
    <a aria-label="Famous Chef" href="https://apps.apple.com/us/app/famous-chef/id6758932844"></a>
    """
    parsed_store = parse_store(sample_store)
    check(len(parsed_store) == 2, "store links were not deduped")
    check(parsed_store[0].name == "Hungry Frog: Math & Play", "store name was not unescaped")

    sample_app = """
    <dt class="x">Size</dt> <dd>15.4 MB</dd>
    <dt class="x">Languages</dt> <dd><details><summary>English and 13 more</summary>
    <li><!-- HTML_TAG_START -->English, Arabic, Dutch<!-- HTML_TAG_END --></li></details></dd>
    <dt class="x">Age Rating</dt>
    """
    check(parse_size(sample_app) == "15.4 MB", "size")
    check(parse_languages(sample_app) == 3, "language list wins over the summary")
    check(parse_languages("<dt>Languages</dt> <dd><summary>English and 2 more</summary></dd>") == 3, "summary count")
    check(parse_languages("<dt>Languages</dt> <dd>English</dd>") == 1, "single language")

    index, files = load(root)
    assert_selects_match_homepage(index, files)
    ignored = plan(
        index,
        [
            StoreApp("Famous Chef", "https://apps.apple.com/us/app/famous-chef/id6758932844", "6758932844"),
            StoreApp("Honey", "https://apps.apple.com/us/app/honey/id1000000003", "1000000003"),
            StoreApp("Jumping Fox: Learn Math", "https://apps.apple.com/us/app/jumping-fox-learn-math/id6792367412", "6792367412"),
        ],
    )
    check(ignored == [], "an app outside In ontwikkeling was selected")

    cards = grid_cards(index, "development-title")
    if len(cards) < 2:
        print("self-test ok")
        return
    first, last = cards[0], cards[-1]
    middle = cards[1:-1]
    first_url = "https://apps.apple.com/us/app/first-released-app/id1000000001"
    last_url = "https://apps.apple.com/us/app/last-released-app/id1000000002"
    matched = plan(
        index,
        [
            StoreApp(last.name, last_url, "1000000002"),
            StoreApp(f"{first.name}: Example", first_url, "1000000001"),
            StoreApp("Famous Chef", "https://apps.apple.com/us/app/famous-chef/id6758932844", "6758932844"),
            StoreApp("Honey", "https://apps.apple.com/us/app/honey/id1000000003", "1000000003"),
        ],
    )
    check([card.href for card, _app in matched] == [first.href, last.href], "promotion order")
    releases = [
        Release(first.href, first.name, first_url, "12.3 MB", 5),
        Release(last.href, last.name, last_url, "9 MB", 1),
    ]
    updates = render(index, files, releases)
    new_index = updates["index.html"]
    education = new_index[slice(*section_bounds(new_index, "education-title"))]
    development = new_index[slice(*section_bounds(new_index, "development-title"))]
    check(education.count(f'href="{first.href}"') == 1, "first app missing from education")
    check(education.count(f'href="{last.href}"') == 1, "last app missing from education")
    check(f'href="{first.href}"' not in development, "first app still in development")
    check(f'href="{last.href}"' not in development, "last app still in development")
    check([card.href for card in grid_cards(new_index, "development-title")] == [card.href for card in middle], "middle apps moved")
    check("12,3 MB · 5 talen" in education and "12.3 MB · 5 languages" in education, "first size line")
    check("9 MB · 1 taal" in education and "9 MB · 1 language" in education, "singular size line")
    check("app-meta" not in development, "a development card gained a size line")
    check("Famous Chef" not in new_index and "famous-chef" not in new_index, "Famous Chef was added")
    check(new_index.count('class="card app-card"') == index.count('class="card app-card"'), "card count changed")
    check(select_values(new_index) == option_order(new_index), "homepage menu order")
    expected_tail = [card.href for card in grid_cards(index, "education-title")] + [first.href, last.href]
    check(select_values(new_index)[-len(expected_tail) - len(middle) :][: len(expected_tail)] == expected_tail, "education menu position")
    check(select_values(new_index)[-len(middle) :] == [card.href for card in middle], "remaining development menu")
    check('value="/" selected' in new_index, "homepage selection changed")

    for release, url in ((releases[0], first_url), (releases[1], last_url)):
        for rel in released_page_paths(release.href):
            updated = updates[rel]
            original = files[rel]
            check(updated.count(url) == 1, f"{rel} store link")
            cta = re.search(r'<div class="cta">.*?</div>', updated, re.S)
            check(cta is not None, f"{rel} buttons")
            assert cta is not None
            anchors = [line for line in cta.group(0).split("\n") if "<a " in line]
            check(anchors[0].lstrip().startswith(f'<a class="btn" href="{url}"'), f"{rel} button is not first")
            check('class="btn secondary"' in anchors[1], f"{rel} second button")
            check(
                len(anchors[0]) - len(anchors[0].lstrip()) == len(anchors[1]) - len(anchors[1].lstrip()),
                f"{rel} button indent",
            )
            check(language_block(updated) == language_block(original), f"{rel} language menu")
            selected = re.search(r'<option\b[^>]*\bselected\b[^>]*>', updated)
            check(selected is not None and f'value="{release.href}"' in selected.group(0), f"{rel} selection")
            if rel.endswith("contact/index.html"):
                check('type="submit"' in updated, f"{rel} contact form")

    for card in middle:
        for rel in released_page_paths(card.href):
            check("apps.apple.com" not in updates[rel], f"{rel} gained a store link")
    fox = updates.get("jumping-fox/index.html", files["jumping-fox/index.html"])
    check(fox.count("apps.apple.com") == files["jumping-fox/index.html"].count("apps.apple.com"), "existing store link changed")
    check(plan(new_index, [StoreApp(first.name, first_url, "1000000001"), StoreApp(last.name, last_url, "1000000002")]) == [], "promoted twice")
    check(all(path.endswith(".html") and ".." not in path.split("/") for path in updates), "unexpected output path")
    print("self-test ok")


def language_block(page: str) -> str:
    match = re.search(r'<select id="language-select".*?</select>', page, re.S)
    return match.group(0) if match else ""


def join_names(names: list[str]) -> str:
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + ", and " + names[-1]


def live(root: Path) -> None:
    index, files = load(root)
    assert_selects_match_homepage(index, files)
    store = parse_store(fetch(DEVELOPER_URL))
    ensure_store(store)
    print(f"store {len(store)} apps")
    matched = plan(index, store)
    if not matched:
        print("promoted none")
        return
    releases: list[Release] = []
    for card, app in matched:
        app_page = fetch(app.url)
        releases.append(Release(card.href, card.name, app.url, parse_size(app_page), parse_languages(app_page)))
    for release in releases:
        for rel in released_page_paths(release.href):
            if rel not in files:
                raise SystemExit(f"missing {rel}; the site was not changed")
    updates = render(index, files, releases)
    for rel in sorted(updates):
        if not rel.endswith(".html") or rel.startswith("/") or ".." in rel.split("/"):
            raise SystemExit(f"refusing to write {rel}")
        (root / rel).write_text(updates[rel], encoding="utf-8")
        print(f"changed {rel}")
    for release in releases:
        print(f"promoted {release.name} | {release.url} | {release.size} | {release.languages}")
    print(
        "summary Move "
        + join_names([release.name for release in releases])
        + " from In ontwikkeling to Educatie voor kinderen."
    )


def main() -> None:
    run_self_test(ROOT)
    if "--self-test" in sys.argv:
        return
    live(ROOT)


if __name__ == "__main__":
    main()
