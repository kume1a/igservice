install:
	python -m pip install --upgrade pip &&\
		python -m pip install -r requirements.txt

lint:
	pylint --disable=R,C,W1203,W0702 app.py

debug:
	flask run --host=0.0.0.0

run:
	waitress-serve src.app:app
