"""Acquire immutable original sources; never substitute demo data on failure."""
import csv
import io
import json
import re
import shutil
import zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import AGREEMENT, BRANDS, CONTRACT_YEAR, ENROLLMENT_LANDING, LAYOUT, MONTHS, ROOT
from .io import dump_json, sha256


def session():
    s = requests.Session()
    s.headers["User-Agent"] = "PayerAccessIntelligence/0.1 (independent public-data portfolio)"
    s.mount("https://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])))
    return s


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.urls.extend(v for k, v in attrs if k == "href" and v)


def formulary_url(index, month):
    candidates = set()
    for dataset in index.get("dataset", []):
        if dataset.get("title", "").split(" : ")[0] != "Monthly Prescription Drug Plan Formulary and Pharmacy Network Information":
            continue
        for dist in dataset.get("distribution", []):
            url = dist.get("downloadURL", "")
            name = url.rsplit("/", 1)[-1]
            if re.search(rf"^{CONTRACT_YEAR}[_.]{month.replace('-', '')}\d{{2}}\.zip$", name):
                candidates.add(url)
    if len(candidates) != 1:
        raise ValueError(f"Expected one official {month} CY{CONTRACT_YEAR} bundle, found {len(candidates)}. Supply --source-map with verified URLs.")
    return candidates.pop()


def download(s, url, target):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_suffix(target.suffix + ".part")
    with s.get(url, stream=True, timeout=(30, 180)) as r:
        r.raise_for_status()
        with part.open("wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                f.write(chunk)
    part.replace(target)
    return {"url": url, "path": str(target.relative_to(ROOT)), "sha256": sha256(target), "bytes": target.stat().st_size,
            "fetched_at": datetime.now(timezone.utc).isoformat()}


def unpack_tables(path, dest):
    """CMS bundles contain nested archives. Ignore the multi-GB pharmacy network."""
    dest.mkdir(parents=True, exist_ok=True)
    selected = {}

    def scan(z):
        for member in z.infolist():
            name = member.filename.lower()
            if member.is_dir() or "sample" in name:
                continue
            kind = next((k for k, terms in {"plans": ["plan information", "plan_information"],
                                          "formulary": ["basic drugs formulary", "basic_drugs_formulary"],
                                          "indications": ["indication based", "indication_based"]}.items()
                         if any(t in name for t in terms)), None)
            if name.endswith(".zip") and kind:
                with z.open(member) as src:
                    with zipfile.ZipFile(io.BytesIO(src.read())) as nested:
                        scan(nested)
            elif name.endswith((".txt", ".csv")) and kind:
                if kind in selected:
                    raise ValueError(f"Ambiguous {kind} members in {path}")
                out = dest / (kind + ".txt")
                with z.open(member) as src, out.open("wb") as f:
                    shutil.copyfileobj(src, f)
                selected[kind] = {"member": member.filename, "sha256": sha256(out), "bytes": out.stat().st_size}

    with zipfile.ZipFile(path) as z:
        scan(z)
    if not {"plans", "formulary"} <= selected.keys():
        raise ValueError(f"Required CMS tables missing in {path}; found {list(selected)}")
    return selected


def product_catalog(s, raw):
    catalog, records = [], []
    for brand, config in BRANDS.items():
        label_url = f"https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/{config['setid']}.xml"
        records.append(download(s, label_url, raw / "products" / f"{brand}.xml"))
        lookup_url = f"https://rxnav.nlm.nih.gov/REST/rxcui.json?name={brand}&search=2"
        lookup = s.get(lookup_url, timeout=45)
        lookup.raise_for_status()
        ids = lookup.json().get("idGroup", {}).get("rxnormId", [])
        if len(ids) != 1:
            raise ValueError(f"Ambiguous RxNorm brand identity: {brand}: {ids}")
        url = f"https://rxnav.nlm.nih.gov/REST/rxcui/{ids[0]}/allrelated.json"
        target = raw / "products" / f"{brand}_rxnorm.json"
        records.append(download(s, url, target))
        groups = json.loads(target.read_text())["allRelatedGroup"].get("conceptGroup", [])
        found = set()
        for group in groups:
            if group.get("tty") != "SBD":
                continue
            for concept in group.get("conceptProperties", []):
                name = concept["name"]
                match = re.search(r" (\d+(?:\.\d+)?) MG Oral Tablet \[" + brand + r"\]$", name, re.I)
                if match:
                    mg = float(match[1])
                    if mg in config["strengths"]:
                        found.add(mg)
                        catalog.append({"brand": brand, "ingredient": config["ingredient"], "strength_mg": mg,
                                        "rxcui": concept["rxcui"], "name": name, "setid": config["setid"]})
        if found != set(config["strengths"]):
            raise ValueError(f"Incomplete marketed-strength catalog for {brand}: {sorted(found)}")
    dump_json(raw / "products" / "catalog.json", catalog)
    return records


def fetch(source_map=None):
    raw = ROOT / "data" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    s = session()
    overrides = json.loads(Path(source_map).read_text()) if source_map else {}
    manifest = {"mode": "real", "contract_year": CONTRACT_YEAR, "sources": [], "snapshots": []}
    try:
        if not overrides:
            meta = s.get("https://data.cms.gov/data.json", timeout=120)
            meta.raise_for_status()
            index = meta.json()
        else:
            index = {}
        for month in MONTHS:
            folder = raw / month
            folder.mkdir(exist_ok=True)
            url = overrides.get(month, {}).get("formulary") or formulary_url(index, month)
            if urlparse(url).hostname != "data.cms.gov":
                raise ValueError("Original CMS bundles must be downloaded from data.cms.gov")
            source = download(s, url, folder / "formulary.zip")
            manifest["sources"].append(source)
            members = unpack_tables(folder / "formulary.zip", folder)
            enrollment_url = overrides.get(month, {}).get("enrollment")
            landing = f"{ENROLLMENT_LANDING}/monthly-enrollment-plan-{month}"
            if not enrollment_url:
                page = s.get(landing, timeout=60)
                page.raise_for_status()
                links = Links()
                links.feed(page.text)
                candidates = sorted({urljoin(landing, u) for u in links.urls if u.lower().split('?')[0].endswith(".zip")})
                if len(candidates) != 1:
                    raise ValueError(f"Ambiguous enrollment download for {month}; supply --source-map")
                enrollment_url = candidates[0]
            if urlparse(enrollment_url).hostname not in {"www.cms.gov", "cms.gov"}:
                raise ValueError("Enrollment originals must be hosted by CMS")
            manifest["sources"].append(download(s, enrollment_url, folder / "enrollment.zip"))
            with zipfile.ZipFile(folder / "enrollment.zip") as z:
                files = [n for n in z.namelist() if n.lower().endswith(".csv")]
                if len(files) != 1:
                    raise ValueError(f"Expected one plan enrollment CSV; found {files}")
                with z.open(files[0]) as src, (folder / "enrollment.csv").open("wb") as f:
                    shutil.copyfileobj(src, f)
            manifest["snapshots"].append({"month": month, "formulary_url": url, "enrollment_url": enrollment_url,
                                           "members": members, "enrollment_sha256": sha256(folder / "enrollment.csv")})
        manifest["sources"].extend(product_catalog(s, raw))
        manifest["sources"].append(download(s, LAYOUT, raw / "PUFRecordLayout-2026.pdf"))
        manifest["sources"].append(download(s, AGREEMENT, raw / "AGREEMENT-FOR-USE.pdf"))
        manifest["status"] = "complete"
        dump_json(raw / "manifest.json", manifest)
        print("Acquired and hashed both original CMS snapshots and product references.")
    except Exception as e:
        manifest.update(status="failed", error=str(e))
        dump_json(raw / "acquisition-status.json", manifest)
        raise
