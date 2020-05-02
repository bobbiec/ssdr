.PHONY: run run-dump run-proxy run-web2 run-web11 clean

run-dump: venv
	-. venv/bin/activate; \
	mitmdump --set confdir=./mitmconf

run: run-proxy
run-proxy: venv
	-. venv/bin/activate; \
	mitmproxy --set confdir=./mitmconf

web2: venv certs
	. venv/bin/activate; \
	hypercorn --config web/hypercorn-http2.toml web/run:app

web11: venv certs
	. venv/bin/activate; \
	hypercorn --config web/hypercorn-http11.toml web/run:app

certs: web/key.pem
web/key.pem:
	openssl req -x509 -newkey rsa:4096 \
	  -keyout web/key.pem -out web/cert.pem \
	  -subj "/C=US/ST=Pennsylvania/L=Pittsburgh/O=18-845/CN=localhost" \
	  -days 365 -nodes

venv:
	virtualenv -p python3 venv
	. venv/bin/activate; pip install -r requirements.txt

clean:
	rm -rf venv *.pyc mitmproxy/mitmproxy* web/*.pem

