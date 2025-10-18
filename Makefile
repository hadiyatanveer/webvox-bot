VENV = venv

setup:
	python3 -m venv $(VENV)
	echo "Activate the virtual environment with: source $(VENV)/bin/activate"

install:
	pip install --upgrade pip
	pip install -r requirements.txt

clean:
	find . -name "__pycache__" -type d -exec rm -r {} +
	clear
