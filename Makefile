.PHONY: run run-dump run-proxy clean

run-dump:
	-mitmdump --set confdir=./mitmconf

run: run-proxy
run-proxy:
	-mitmproxy --set confdir=./mitmconf

venv:
	virtualenv -p python3 venv
	pip install -r requirements.txt

clean:
	rm -rf venv *.pyc
