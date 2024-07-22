install:
	python -m pip install --upgrade pip &&\
		python -m pip install -r requirements.txt

lint:
	pylint --disable=R,C,W1203,W0702 app.py

run:
	python src/app.py

protogen:
	python -m grpc_tools.protoc --proto_path=./proto proto/*.proto --python_out=./proto --grpc_python_out=./proto