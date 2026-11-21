from core.brand import get_brand


def test_brand_config_holds_product_and_assistant_names():
    brand = get_brand()
    assert brand["name"] and brand["tagline"]
    assistant = brand["assistant"]
    assert assistant["name"] == "HIRA"
    assert assistant["fullName"] == "Hiring Intelligence & Recruiting Assistant"
    assert assistant["display"] == "HIRA · Hiring Intelligence & Recruiting Assistant"
    assert assistant["display"] == f"{assistant['name']} · {assistant['fullName']}"
    assert all(value.startswith("#") for value in brand["colors"].values())
