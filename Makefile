VENV = venv

setup:
	python3 -m venv $(VENV)
	echo "Activate the virtual environment with: source $(VENV)/bin/activate"

install:
	pip install --upgrade pip
	pip install -r requirements.txt

run:
	python3 -m backend.main

frontend:
	npm install
	npm install react-scripts@5.0.1
	npm start

clean:
	find . -name "__pycache__" -type d -exec rm -r {} +
	clear
