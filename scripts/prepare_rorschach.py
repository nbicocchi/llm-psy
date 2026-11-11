"""Archive ten unnormalized Commons reproductions and their provenance.

The first invocation requires network access. Subsequent invocations use the
saved manifest, never silently refreshing file versions or licensing metadata.
Use --verify for a strictly offline integrity check.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
COMMONS = "https://commons.wikimedia.org"
GALLERY = COMMONS + "/wiki/Rorschach_inkblot_test"
USER_AGENT = "LocalModelObservatory/0.1 (local research stimulus archive)"


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                data = response.read(10_000_001)
            break
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 503) or attempt == 2:
                raise
            retry_after = exc.headers.get("Retry-After", "")
            delay = int(retry_after) if retry_after.isdigit() else 15 * (attempt + 1)
            if delay > 120:
                raise RuntimeError(f"Commons requests a {delay}s pause; rerun preparation later") from exc
            print(f"Commons rate limit; retrying this request in {delay}s", flush=True)
            time.sleep(delay)
    if len(data) > 10_000_000:
        raise ValueError("Unexpectedly large Commons response")
    return data


def validate_image(content, entry):
    if not content.startswith(b"\xff\xd8\xff"):
        raise ValueError(f"Not a JPEG: {entry['id']}")
    if len(content) != entry["bytes"]:
        raise ValueError(f"File size mismatch: {entry['id']}")
    if hashlib.sha1(content).hexdigest() != entry["commons_sha1"]:
        raise ValueError(f"Commons SHA-1 mismatch: {entry['id']}")
    digest = hashlib.sha256(content).hexdigest()
    if entry.get("sha256") and digest != entry["sha256"]:
        raise ValueError(f"Local SHA-256 mismatch: {entry['id']}")
    return digest


def discover():
    titles = [f"File:Rorschach blot {number:02d}.jpg" for number in range(1, 11)]
    query = urllib.parse.urlencode({
        "action": "query", "format": "json", "prop": "imageinfo|revisions",
        "titles": "|".join(titles), "iiprop": "url|size|sha1|timestamp|extmetadata",
        "rvprop": "ids|timestamp",
    })
    result = json.loads(fetch(COMMONS + "/w/api.php?" + query))
    pages = {page["title"]: page for page in result["query"]["pages"].values()}
    entries = []
    for number, title in enumerate(titles, start=1):
        page = pages[title]
        info = page["imageinfo"][0]
        metadata = info.get("extmetadata", {})
        license_name = metadata.get("LicenseShortName", {}).get("value", "")
        if license_name != "Public domain":
            raise ValueError(f"Unexpected licensing for {title}: {license_name}; review manually")
        url = urllib.parse.urlsplit(info["url"])
        if url.scheme != "https" or url.netloc != "upload.wikimedia.org":
            raise ValueError(f"Unexpected original-file host: {info['url']}")
        entries.append({
            "id": f"rorschach-{number:02d}", "plate": number,
            "file": f"assets/rorschach/plate-{number:02d}.jpg",
            "title": title,
            "source_page": COMMONS + "/wiki/" + urllib.parse.quote(title.replace(" ", "_"), safe=":"),
            "source_revision": COMMONS + "/w/index.php?" + urllib.parse.urlencode({"oldid": page["revisions"][0]["revid"]}),
            "download_url": urllib.parse.urlunsplit((url.scheme, url.netloc, url.path, "", "")),
            "file_timestamp": info["timestamp"],
            "commons_sha1": info["sha1"], "bytes": info["size"],
            "width": info["width"], "height": info["height"],
            "license": license_name, "metadata": metadata,
        })
    return {"schema_version": 1, "series": "Rorschach blot 01.jpg through Rorschach blot 10.jpg (unnormalized)", "author": "Hermann Rorschach (1884–1922)", "original_publication_year": 1921, "source_gallery": GALLERY, "retrieved_at": datetime.now(timezone.utc).isoformat(), "stimuli": entries}


def prepare(root, verify_only=False):
    manifest_path = root / "assets/rorschach/manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    elif verify_only:
        raise ValueError("No saved Rorschach manifest; prepare the stimuli online first")
    else:
        manifest = discover()
        # Freeze provenance before downloading: interrupted downloads resume from
        # the same source hashes, rather than rediscovering a potentially new set.
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    # Validate the entire archive before updating its public copies.
    verified = []
    for entry in manifest["stimuli"]:
        path = root / entry["file"]
        if path.exists():
            content = path.read_bytes()
        elif verify_only:
            raise ValueError(f"Missing local stimulus: {path}")
        else:
            print(f"Downloading {entry['title']}", flush=True)
            content = fetch(entry["download_url"])
        entry["sha256"] = validate_image(content, entry)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        verified.append((entry, content))
    if not verify_only:
        encoded = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
        manifest_path.write_text(encoded, encoding="utf-8")
        public_dir = root / "site/assets/rorschach"
        public_dir.mkdir(parents=True, exist_ok=True)
        for entry, content in verified:
            destination = public_dir / Path(entry["file"]).name
            if destination.exists() and destination.read_bytes() != content:
                raise ValueError(f"Refusing to overwrite modified public stimulus: {destination}")
            destination.write_bytes(content)
        (public_dir / "manifest.json").write_text(encoded, encoding="utf-8")
        data_dir = root / "site/_data"
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "rorschach.json").write_text(encoded, encoding="utf-8")
    print(f"Verified {len(verified)} Rorschach reproductions")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="Verify the local archive without network access or writes")
    args = parser.parse_args()
    prepare(ROOT, verify_only=args.verify)
