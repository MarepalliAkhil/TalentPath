"""Brand config lives in shared/brand.json: rename the product in one line."""

import json
from functools import lru_cache

from django.conf import settings


@lru_cache(maxsize=1)
def get_brand() -> dict:
    with open(settings.BRAND_PATH, encoding="utf-8") as fh:
        return json.load(fh)
