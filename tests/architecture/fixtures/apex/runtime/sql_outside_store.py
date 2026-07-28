"""Invalid: SQL writes belong only in journal/store.py."""

QUERY = "UPDATE events SET payload = ?"
