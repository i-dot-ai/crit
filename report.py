from pathlib import Path
import json
from crit.compare import generate_crit_report

with Path.open("findings.json") as file:
    j = json.load(file)

generate_crit_report(j, "my-report.html")
