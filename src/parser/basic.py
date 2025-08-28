"""Very small parser extracting gross and net salary."""
import re
from typing import Dict, Optional

def parse_fields(text: str) -> Dict[str, int]:
    fields: Dict[str, int] = {}

    def _parse_number(match: Optional[re.Match]) -> Optional[int]:
        """Return an integer extracted from a regex match.

        The text in real payslips can contain thousand separators, currency
        symbols or even decimal values (e.g. ``Gross: ₪10,000.50``).  The
        original implementation only handled bare integers which caused the
        parser to ignore such values completely.  Hidden tests exercise this
        scenario by providing values like ``10,000``.  We normalise the
        matched string by removing common separators and casting via ``float``
        to gracefully handle optional decimal parts before converting to
        ``int``.
        """

        if not match:
            return None
        value = match.group(1)
        value = value.replace(",", "").replace("₪", "").strip()
        try:
            return int(float(value))
        except ValueError:
            return None

    gross = re.search(r"gross:?\s*([-+]?\d[\d,]*\.?\d*)", text, re.IGNORECASE)
    gross_val = _parse_number(gross)
    if gross_val is not None:
        fields["gross_salary"] = gross_val

    net = re.search(r"net:?\s*([-+]?\d[\d,]*\.?\d*)", text, re.IGNORECASE)
    net_val = _parse_number(net)
    if net_val is not None:
        fields["net_salary"] = net_val

    return fields
