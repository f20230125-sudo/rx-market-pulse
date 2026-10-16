"""Copy a pinned public Trial Pipeline Benchmark export, with provenance hashes.

python tools/sync_pipeline.py ../trial-pipeline-benchmark
"""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = Path(sys.argv[1]).resolve()
commit = subprocess.run(
    ["git", "-c", f"safe.directory={source.as_posix()}", "rev-parse", "HEAD"],
    cwd=source,
    capture_output=True,
    text=True,
    check=True,
).stdout.strip()
target = root / "dashboard/public/data/pipeline"
target.mkdir(parents=True, exist_ok=True)
files = {}
for name in ("meta.json", "revenue.json", "msd_active.json"):
    path = source / "dashboard/public/data" / name
    json.loads(path.read_text(encoding="utf-8"))
    shutil.copyfile(path, target / name)
    files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
(target / "provenance.json").write_text(
    json.dumps(
        {
            "repository": "f20230125-sudo/trial-pipeline-benchmark",
            "commit": commit,
            "files": files,
            "source": f"https://github.com/f20230125-sudo/trial-pipeline-benchmark/tree/{commit}",
        },
        indent=2,
    ),
    encoding="utf-8",
)
print(f"Pinned {len(files)} files at {commit}")
