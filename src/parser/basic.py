"""Very small parser extracting gross and net salary."""
import re
from typing import Dict

def parse_fields(text: str) -> Dict[str, int]:
    fields: Dict[str, int] = {}
    gross = re.search(r"gross:?\s*(\d+)", text, re.IGNORECASE)
    if gross:
        fields["gross_salary"] = int(gross.group(1))
    net = re.search(r"net:?\s*(\d+)", text, re.IGNORECASE)
    if net:
        fields["net_salary"] = int(net.group(1))
    return fields
