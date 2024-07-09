install:
	pip3 install --upgrade pip &&\
		pip3 install -r requirements.txt

lint:
	pylint --disable=R,C,W1203,W0702 app.py

run:
	python3 app.py