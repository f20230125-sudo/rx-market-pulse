"""Strict identifiers and three-valued restriction flags."""
import re
import codecs


def text_encoding(path):
    decoder=codecs.getincrementaldecoder('utf-8-sig')('strict')
    try:
        with path.open('rb') as f:
            for chunk in iter(lambda:f.read(1024*1024),b''):
                decoder.decode(chunk)
            decoder.decode(b'',final=True)
        return 'utf-8-sig'
    except UnicodeDecodeError:
        return 'cp1252'


def identifier(value, width):
    value = str(value).strip()
    if not value.isdigit() or len(value) > width:
        raise ValueError(f"Invalid {width}-digit identifier: {value!r}")
    return value.zfill(width)


def ndc11(value):
    value = str(value).strip()
    if re.fullmatch(r"\d{11}", value):
        return value
    parts = value.split("-")
    if tuple(map(len, parts)) in {(4, 4, 2), (5, 3, 2), (5, 4, 1), (5, 4, 2)} and all(p.isdigit() for p in parts):
        return parts[0].zfill(5) + parts[1].zfill(4) + parts[2].zfill(2)
    raise ValueError(f"Ambiguous or invalid NDC: {value!r}")


def flag(value):
    value = str(value).strip().upper()
    if value in {"Y", "1"}:
        return True
    if value in {"N", "0"}:
        return False
    if value in {"", "*", "NA", "N/A"}:
        return None
    raise ValueError(f"Invalid restriction flag: {value!r}")


def enrollment(value):
    value = str(value).strip()
    if value in {"", "*", "**", "N/A"} or "10 or" in value.lower():
        return None
    value = value.replace(",", "")
    if not value.isdigit():
        raise ValueError(f"Invalid enrollment: {value!r}")
    return int(value)


def normalized_header(row):
    return {re.sub(r"[^A-Z0-9]+", "_", str(k).strip().upper()).strip("_"): str(v or "").strip()
            for k, v in row.items() if k is not None}
