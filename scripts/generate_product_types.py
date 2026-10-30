"""Export schemas without starting services or reading installed credentials."""

import json
from pathlib import Path

from contextbridge.api import create_app
from contextbridge.product.app import create_product_app

root = Path(__file__).resolve().parents[1]
core = create_app().openapi()
product = create_product_app(root).openapi()
core["paths"].update(product["paths"])
core["components"]["schemas"].update(product["components"]["schemas"])
output = root / ".contextbridge" / "openapi-product.json"
output.parent.mkdir(exist_ok=True)
output.write_text(json.dumps(core), encoding="utf-8")
