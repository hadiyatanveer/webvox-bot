VENV = venv

setup:
	python3 -m venv $(VENV)
	. $(VENV)/bin/activate

clean:
	rm -rf $(VENV)