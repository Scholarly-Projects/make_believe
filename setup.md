## Setup

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

python renumber_citations.py

python export.py

deactivate

