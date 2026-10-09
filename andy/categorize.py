"""Sort a merchant into a spending category."""

from __future__ import annotations

import re

CATEGORIES = [
    "Food delivery", "Dining out", "Groceries", "Shopping", "Transport", "Fuel", "Bills & utilities",
    "Rent", "Subscriptions", "Health", "Entertainment", "Travel", "Education", "Personal care",
    "EMI & loans", "Insurance", "Fees & charges", "Cash withdrawal", "Gifts & donations", "Other",
    # Not spending: money moving between your own pots. Excluded from expense totals.
    "Investments", "Transfers",
]
NOT_SPENDING = {"Investments", "Transfers"}

# Checked in order; the first match wins. Keywords match whole words in the merchant name or alert text.
_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("Fees & charges", ("late fee", "late payment", "finance charge", "penalty", "annual fee", "overlimit",
                        "convenience fee", "processing fee", "gst on", "interest charged")),
    ("Transfers", ("credit card payment", "cc payment", "card payment", "cred club", "cred", "bill payment to card",
                   "payment received", "has been received on your",
                   "self transfer", "own account")),
    ("Investments", ("zerodha", "groww", "kuvera", "coin by zerodha", "upstox", "angel one", "paytm money",
                     "mutual fund", "sip", "nps trust", "ppf", "iccl", "nsccl", "bse limited", "indian clearing")),
    ("Cash withdrawal", ("atm", "cash withdrawal", "nwd", "atw")),
    ("Food delivery", ("swiggy", "zomato", "eatsure", "box8", "faasos", "dominos", "domino's", "pizza hut")),
    ("Groceries", ("bigbasket", "blinkit", "zepto", "instamart", "dmart", "jiomart", "more retail", "nature's basket",
                   "reliance fresh", "spencer", "grofers", "milkbasket", "country delight", "kirana")),
    ("Subscriptions", ("netflix", "spotify", "prime video", "amazon prime", "hotstar", "jiohotstar", "disney",
                       "youtube premium", "google one", "icloud", "apple.com", "apple services", "sonyliv", "zee5",
                       "audible", "linkedin premium", "chatgpt", "openai", "anthropic", "claude", "notion",
                       "microsoft 365", "adobe", "canva", "gaana", "jiosaavn", "cult.fit", "cultfit")),
    ("Transport", ("uber", "ola", "rapido", "namma yatri", "metro", "irctc suburban", "blusmart")),
    ("Fuel", ("petrol", "fuel", "indian oil", "iocl", "hpcl", "bpcl", "bharat petroleum", "hindustan petroleum",
              "shell", "nayara")),
    ("Bills & utilities", ("electricity", "bescom", "tata power", "adani electricity", "msedcl", "bses", "water bill",
                           "gas bill", "indane", "bharat gas", "mahanagar gas", "airtel", "jio", "vodafone", "vi ",
                           "bsnl", "act fibernet", "broadband", "dth", "tata play", "recharge", "postpaid")),
    ("Rent", ("rent", "nobroker", "housing.com", "maintenance", "society")),
    ("Health", ("apollo", "pharmeasy", "1mg", "tata 1mg", "netmeds", "medplus", "hospital", "clinic", "diagnostic",
                "practo", "lab", "pharmacy", "chemist")),
    ("Insurance", ("insurance", "lic", "hdfc life", "icici pru", "max life", "star health", "niva bupa", "acko",
                   "policybazaar", "digit insurance")),
    ("EMI & loans", ("emi", "loan", "bajaj finance", "home credit", "nach")),
    ("Entertainment", ("bookmyshow", "pvr", "inox", "cinepolis", "steam", "playstation", "xbox", "district")),
    ("Travel", ("makemytrip", "goibibo", "cleartrip", "ixigo", "irctc", "indigo", "air india", "vistara", "akasa",
                "spicejet", "oyo", "airbnb", "booking.com", "agoda", "redbus", "yatra")),
    ("Education", ("udemy", "coursera", "byju", "unacademy", "school", "college", "university", "tuition")),
    ("Personal care", ("urban company", "salon", "spa", "nykaa", "barber", "parlour")),
    ("Shopping", ("amazon", "flipkart", "myntra", "ajio", "meesho", "tata cliq", "croma", "reliance digital",
                  "decathlon", "ikea", "lenskart", "snapdeal", "shoppers stop", "lifestyle", "westside", "zara",
                  "h&m", "uniqlo")),
    ("Dining out", ("restaurant", "cafe", "café", "starbucks", "third wave", "blue tokai", "chaayos", "mcdonald",
                    "kfc", "burger king", "subway", "barbeque", "haldiram", "bar ", "pub", "bistro", "dhaba")),
    ("Gifts & donations", ("donation", "charity", "temple", "giveindia", "ketto", "gift")),
]


def _contains(haystack: str, needle: str, loose: bool = False) -> bool:
    needle = needle.strip()
    if loose and len(needle) >= 6 and needle in haystack:  # e.g. "netflix" inside "netflixupi"
        return True
    return re.search(r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])", haystack) is not None


def categorize(merchant: str, text: str = "", rules: dict | None = None) -> str:
    """Category for a merchant. Shrey's own corrections (`rules`) win over the built-in list."""
    key = merchant_key(merchant)
    if rules and key in rules:
        return rules[key]
    name, context = merchant.lower(), text.lower()
    for category, keywords in _RULES:
        if any(_contains(name, kw, loose=True) or _contains(context, kw) for kw in keywords):
            return category
    return "Other"


def merchant_key(merchant: str) -> str:
    """Stable lower-case key used to remember Shrey's corrections for a merchant."""
    return re.sub(r"[^a-z0-9]+", " ", merchant.lower()).strip()
