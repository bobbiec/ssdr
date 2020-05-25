.PHONY: run-all proxy proxy-tui web11 web2 web2-no-push clean

venv:
	virtualenv -p python3 venv
	. venv/bin/activate; pip install -r requirements.txt

run-all: venv
	tmux attach || \
	tmux new-session -s ssdr \
	  "make web11 ; read" \; \
	  split-window "make web2 ; read" \; \
	  split-window "make web2-no-push ; read" \; \
	  split-window "make proxy ; read" \; \
	  select-layout tiled

proxy: venv
	-. venv/bin/activate; \
	mitmdump --set confdir=./mitmconf

proxy-tui: venv
	-. venv/bin/activate; \
	mitmproxy --set confdir=./mitmconf

web2: venv certs
	. venv/bin/activate; \
	SERVER_PUSH=1 hypercorn --config web/hypercorn-http2.toml web/run:app

web2-no-push: venv certs
	. venv/bin/activate; \
	hypercorn --config web/hypercorn-http2.toml --bind=0.0.0.0:5030 web/run:app

web11: venv certs
	. venv/bin/activate; \
	hypercorn --config web/hypercorn-http11.toml web/run:app

# Based on https://medium.com/python-pandemonium/how-to-serve-http-2-using-python-5e5bbd1e7ff1
certs: web/key.pem
web/key.pem:
	openssl req -x509 -newkey rsa:4096 \
	  -keyout web/key.pem -out web/cert.pem \
	  -subj "/C=US/ST=Pennsylvania/L=Pittsburgh/O=18-845/CN=localhost" \
	  -days 365 -nodes

clean:
	rm -rf venv *.pyc mitmproxy/mitmproxy* web/*.pem

