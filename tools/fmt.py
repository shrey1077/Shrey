"""Formatting helpers shared by the tools."""


def inr(amount: float, symbol: str = "₹") -> str:
    """Format rupees with Indian digit grouping: 1234567 -> ₹12,34,567."""
    sign = "-" if amount < 0 else ""
    digits = str(int(round(abs(amount))))
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join(groups) + "," + tail
    return f"{sign}{symbol}{digits}"


def pct(value: float, places: int = 1) -> str:
    return f"{value * 100:.{places}f}%"


def lakhs(amount: float) -> str:
    """Short human form: 1250000 -> '12.5 lakh', 25000000 -> '2.5 crore'."""
    if abs(amount) >= 1_00_00_000:
        return f"{amount / 1_00_00_000:.2f}".rstrip("0").rstrip(".") + " crore"
    if abs(amount) >= 1_00_000:
        return f"{amount / 1_00_000:.2f}".rstrip("0").rstrip(".") + " lakh"
    return inr(amount)
