# SSDR: Server-side dependency resolution

## Setup

First, install mitmproxy from binary: https://mitmproxy.org/

Then:

```shell
make install
. venv/bin/activate

make web11 # run the webserver with HTTP/1.1 only
make web2  # run the webserver with HTTP/2 server push

make run-dump  # run the non-interactive mitmdump to the webserver
make run       # run the TUI mitmproxy
```

The webserver runs at https://localhost:5000 . Note that HTTPS is required.

The reverse proxy runs at http://localhost:8080 and https://localhost:8080.

## References

https://medium.com/python-pandemonium/how-to-serve-http-2-using-python-5e5bbd1e7ff1
