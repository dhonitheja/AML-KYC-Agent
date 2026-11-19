"""Load OFAC's legacy SDN XML format. Default source is a fictional fixture."""
import hashlib
import os
import re
import tempfile
import unicodedata
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

from defusedxml import ElementTree
from rapidfuzz import fuzz, process

URL = "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.XML"
DEFAULT = "watchlists/sample.xml"


def normalize(name):
    text = unicodedata.normalize("NFKD", name.casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(sorted(re.findall(r"[^\W_]+", text, flags=re.UNICODE)))


def full_date(raw):
    for fmt in ("%Y-%m-%d", "%d %b %Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


@dataclass
class Snapshot:
    version: str
    entries: list
    choices: list
    aliases: list

    def screen(self, name, dob: date | None = None):
        key = normalize(name)
        if not key:
            raise ValueError("A screenable name is required")
        best = {}
        for _, score, index in process.extract_iter(key, self.choices, scorer=fuzz.ratio, score_cutoff=88):
            entry_index, alias = self.aliases[index]
            entry = self.entries[entry_index]
            uid = entry["uid"]
            if uid in best and best[uid]["score"] >= score:
                continue
            decision = "possible_match"
            reason = "Name similarity meets threshold; identity requires analyst review."
            dates = entry["dates"]
            if dob and dob in dates:
                decision = "corroborated_match"
                reason = "Name similarity and a complete date of birth match."
            elif dob and dates and all(dates):
                decision = "conflicting_dob"
                reason = "Name similarity meets threshold but all listed birth dates differ; review the discrepancy."
            best[uid] = dict(entry_id=uid, listed_name=entry["name"], matched_name=alias,
                             score=round(score,2), disposition=decision, reason=reason)
        return dict(name=name, snapshot=self.version, threshold=88,
                    hits=sorted(best.values(),key=lambda h:(-h["score"],h["entry_id"])))


def parse(data):
    root = ElementTree.fromstring(data)
    for node in root.iter():
        node.tag = node.tag.split("}")[-1]
    if root.tag != "sdnList":
        raise ValueError("Expected SDN XML")
    entries, choices, aliases = [], [], []
    def name(node):
        return " ".join(filter(None,[node.findtext("firstName"),node.findtext("lastName")]))
    for entry in root.findall("sdnEntry"):
        uid, primary = entry.findtext("uid"), name(entry)
        if not uid or not normalize(primary):
            raise ValueError("Incomplete SDN entry")
        entry_index = len(entries)
        entries.append(dict(uid=uid,name=primary,dates=[full_date(d.text or "") for d in
                            entry.findall("./dateOfBirthList/dateOfBirthItem/dateOfBirth")]))
        for alias in [primary]+[name(a) for a in entry.findall("./akaList/aka")]:
            if normalize(alias):
                aliases.append((entry_index,alias))
                choices.append(normalize(alias))
    expected=root.findtext("publshInformation/Record_Count")
    if not entries or (expected and int(expected)!=len(entries)):
        raise ValueError("Incomplete SDN snapshot")
    return Snapshot(hashlib.sha256(data).hexdigest(), entries, choices, aliases)


@lru_cache(maxsize=2)
def cached(path, mtime, size):
    return parse(path.read_bytes())


def active():
    path=Path(os.environ.get("SDN_FILE",DEFAULT))
    stat=path.stat()
    return cached(path, stat.st_mtime_ns, stat.st_size)


def refresh():
    destination=Path("watchlists/sdn.xml")
    with urllib.request.urlopen(URL,timeout=90) as response:
        data=response.read(128*1024*1024+1)
    if len(data)>128*1024*1024:
        raise ValueError("Oversized SDN response")
    snapshot=parse(data)
    with tempfile.NamedTemporaryFile(dir=destination.parent,delete=False) as temp:
        temp.write(data)
    os.chmod(temp.name,0o644)
    os.replace(temp.name,destination)
    print(f"Loaded {len(snapshot.entries)} entries; SHA-256 {snapshot.version}")


if __name__=="__main__":
    refresh()
