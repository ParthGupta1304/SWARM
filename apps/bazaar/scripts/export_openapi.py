"""Export Bazaar's generated HTTP contract for offline consumers."""

import json
from pathlib import Path

from bazaar.main import app

output = Path("openapi.json")
output.write_text(json.dumps(app.openapi(), indent=2) + "\n")
print(f"Wrote {output}")
