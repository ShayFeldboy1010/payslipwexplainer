import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from parser import parse_fields

def test_parse_fields_gross_net():
    text = "Gross: 10000\nNet: 8000"
    fields = parse_fields(text)
    assert fields["gross_salary"] == 10000
    assert fields["net_salary"] == 8000
