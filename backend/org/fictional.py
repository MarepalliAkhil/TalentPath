"""Guard for D-84: companies on this site are fictional. Names of well-known real companies
(and the HR-tech companies this portfolio is aimed at) are refused, in seed data (tested)
and when an admin adds or renames a company."""

import re

REAL_COMPANY_BLOCKLIST = (
    "accenture",
    "adobe",
    "amazon",
    "apple",
    "atlassian",
    "byju",
    "capgemini",
    "cognizant",
    "darwinbox",
    "deloitte",
    "flipkart",
    "freshworks",
    "google",
    "hcl",
    "ibm",
    "infosys",
    "keka",
    "meta",
    "microsoft",
    "netflix",
    "ola",
    "oracle",
    "paytm",
    "phenom",
    "reliance",
    "salesforce",
    "samsung",
    "sap",
    "swiggy",
    "tata",
    "tcs",
    "tech mahindra",
    "turbohire",
    "uber",
    "wipro",
    "zoho",
    "zomato",
)


def looks_real(name: str) -> str:
    """The blocked real company a name contains, or ""."""
    words = " " + re.sub(r"[^a-z0-9]+", " ", (name or "").lower()) + " "
    for real in REAL_COMPANY_BLOCKLIST:
        if f" {real} " in words:
            return real
    return ""
