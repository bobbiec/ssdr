# SSDR: Server-side dependency resolution
SSDR is a dependency-inlining reverse proxy
[(paper)](server-side-dependency-resolution.pdf).

It is implemented as an [mitmproxy](https://mitmproxy.org/) addon in
[ssdr.py](ssdr.py). The [web](web) directory contains a toy webserver which
allows generating pages with various depths of dependencies.

This project was done at CMU as part of Dave O' Hallaron's excellent course
Internet Services (18-845).

* [Motivation](#motivation)
* [Paper Summary](#paper-summary)
* [Usage](#usage)
  + [Setup](#setup)
  + [Overview](#overview)
  + [Webserver](#webserver)
  + [Individual commands](#individual-commands)
* [Browser Behavior](#browser-behavior)
* [Related Work and Resources](#related-work-and-resources)

<small><i><a href='http://ecotrust-canada.github.io/markdown-toc/'>
Table of contents generated with markdown-toc
</a></i></small>

## Motivation
Normally webpages require multiple round-trips to resolve. For example, the
initial page load returns an `<img src="image.png" />`, which then requires the
browser to make a new request to `image.png` to retrieve the actual content.
The SSDR proxy is hosted on the same server as the origin server and instead
resolves these dependencies over the high-speed localhost connection. It
inlines CSS, Javascript, images (as base64 url), and iframes (using the srcdoc
attribute).

This is useful for users who experience high last-mile latency, like 3G mobile
users and users in rural locations, improving their full-page load times from
(dependency-tree-depth) * (round-trip-time) to a single round-trip-time in the
best case.

This project is potentially an example of an "HTTPS sharding proxy" as described
in Netravali et al's [WatchTower: Fast, Secure Mobile Page Loads Using Remote
Dependency Resolution](https://doi.org/10.1145/3307334.3326104). Note that
due to time constraints, the implementation in this repo _does_ resolve
dependencies from a different origin, so the security benefits do not apply.

## Paper Summary
See [the paper](server-side-dependency-resolution.pdf) for details.
A brief summary is below.

We find that the SSDR proxy provides improvements to full page load time
comparable to HTTP/2 server push, without requiring client or server protocol
upgrades. This comes at the cost of slower time-to-first-paint, slightly
larger payloads, and worse caching behavior for dependencies shared between
pages.

Performance
- The SSDR proxy improves full page load times as the dependency depth increases.
  - This comes directly from reducing the number of RTTs.
  - This is roughly equivalent to HTTP/2 server pushing all dependencies.
- The SSDR proxy increases the time-to-first-paint, which may harm user experience.
  - This is because the initial request contains more content.
- We did not evaluate the effect of caching, but expect that SSDR performs poorly
  with respect to caching.
  - This is because inlined resources cannot be cached.
  - This would most noticeably affect resources that are used on every page of a
    site (e.g. a common CSS file, a header image, or a shared Javascript library
    like jQuery).
- We did not evaluate the computational requirements of running the SSDR proxy.

Limitations of the current implementation
- Resolves dependencies from not-same-origin; this means that HTTPS guarantees
  are not preserved.
  - This can be fixed by checking the origin of dependencies before resolving.
- Uses the Python requests library; this means that dependencies injected via
  Javascript cannot be inlined.
  - This can be fixed by resolving with a headless browser rather than requests;
    we did not due to time constraints.
- Not robust and will probably crash when given malformed HTML.
- Mitmproxy does not handle HTTP 3XX redirects, so these cannot be resolved.


## Usage

### Setup
`make venv` to install dependencies, and then `make run-all` to run the four
webservers.

### Overview
The makefile provides four webservers that run on https://0.0.0.0:\<port\>.

Port | Make command | Server | Description
-----|--------------|--------|-------------
5011 | web11 | HTTP/1.1 | An HTTP/1.1 server as a baseline |
5020 | web2 | HTTP/2 with server push | An HTTP/2 server which server pushes all dependencies |
5030 | web2-no-push | HTTP/2 without server push | An HTTP/2 server without server push; used to isolate the effect of server push |
8080 | proxy (or proxy-tui) | SSDR reverse proxy | An HTTP/1.1 server reverse proxying 5011 using SSDR to inline dependencies |

`make run-all` runs a convenience tmux command to start all servers in one
tmux session.

There are only two routes:
- `/` or `/0` is a simple "Hello World!" page which references two dependencies,
  `index.js` and `index.css`.
- `/<number>` creates `<number>` nested iframes: `/10` contains an iframe which
  points to `/9`, which points to `/8`, etc. until it reaches `/0` (the root).
  Note that [in Firefox, no more than 10 iframes will be shown](#browser-behavior)

### Webserver
The webserver is in the `web` directory. It consists of a [Quart](https://pgjones.gitlab.io/quart/)
server (effectively Flask for asyncio) and is run using [Hypercorn](https://pgjones.gitlab.io/hypercorn/).
To make changes to the site, see the Quart docs.

### Individual commands
```shell
make web11
```
Runs the HTTP/1.1 server at https://0.0.0.0:5011 .

```shell
make web2
```
Runs the HTTP/2 server, with server push, at https://0.0.0.0:5020 .

```shell
make web2-no-push
```
Runs the HTTP/2 server, with server push disabled, at https://0.0.0.0:5030 .

```shell
make proxy
```
Runs the non-interactive mitmdump at https://0.0.0.0:8080 .
If you are not familiar with mitmproxy, you should use this one.

```shell
make proxy-tui
```
Runs the interactive TUI mitmproxy at https://0.0.0.0:8080 .
See [mitmproxy docs](https://docs.mitmproxy.org/stable/) for usage.

```shell
make certs
```
Generates self-signed certs for the HTTPS servers to use.
You shouldn't have to run this manually.

```shell
make clean
```
Cleans up the repo by deleting the virtualenv and certificates.

## Browser Behavior

This project was tested using a combination of Mozilla Firefox 76 and Google
Chrome 81. There are a few interesting browser behaviors to note:

Mozilla Firefox
- [Does not resolve iframes nested more than 10 deep](https://bugzilla.mozilla.org/show_bug.cgi?id=285395)
- [Does not show what resources are server pushed](https://bugzilla.mozilla.org/show_bug.cgi?id=1592529)

It also seems that Firefox does not accept the server-pushed resources from the
`web2` server in this project, even though it does work on Chrome. I poked
around a bit with [nghttp2](https://github.com/nghttp2/nghttp2) and suspect
that this might actually be a hypercorn/Quart bug, but needs more investigation
to say for sure.

Google Chrome
- Network throttling does not work for nested iframes.
  The delay is applied for the first iframe loaded, and then all nested iframes
  are loaded without the throttling settings applied. I did not test this for
  other nested dependencies (e.g. image url in CSS) but suspect it may also
  cause issues.

Both browsers
- When iframes content is provided via srcdoc (as it is in the SSDR script),
  the resulting iframe has a small fixed height (193 in Firefox, 150 in Chrome).
  This can be overridden by injecting an inline `height: 100%` on the html and
  body tags of the iframe content, but I'm unsure if that negatively affects
  rendering in other ways.

## Related Work and Resources
- [A Cloud-based Content Gathering Network (Debopam Bhattacherjee et al.)](https://www.usenix.org/conference/hotcloud17/program/presentation/bhattacherjee)
  presents the idea of a content _gathering_ network (CGN), which hosts CGN
  nodes (RDR proxies) in public clouds close to popular sites. One limitation
  here is that clients must trust the CGN node to MITM their HTTPS traffic.
  Shoutout to Adrian Colyer's blog [The Morning Paper](https://blog.acolyer.org/2017/08/24/a-cloud-based-content-gathering-network/)
  for introducing me to this idea.

- [WatchTower (Ravi Netravali et al.)](https://doi.org/10.1145/3307334.3326104) uses
  HTTPS sharding and a system which dynamically predicts when RDR will actually
  increase load times to only proxy when it helps.

- [High Performance Browser Networking (Ilya Grigorik)](https://hpbn.co/) is
  a great resource for understanding web performance at a network/protocol level.

- [HTTP/2 Server Push](https://tools.ietf.org/html/rfc7540#section-8.2) is a
  protocol-level implementation of pushing dependencies proactively. This
  captures the benefits of inlining while preserving caching. Deciding exactly
  which resources to push can be an interesting problem.

- [WProf (Xiao Sophia Wang et al.)](https://homes.cs.washington.edu/~arvind/papers/wprof.pdf)
  [(site)](http://wprof.cs.washington.edu/) identifies precise browser behavior
  with respect to dependencies. This would be useful for developing better
  inlining/server push policies that improve the user experience.

In addition to CGN and WatchTower, there are many other _proxy-based_ or
_split-browser_ systems to improve page load times, like Flywheel (Google),
Silk (Amazon), Shandian (Xiao Sophia Wang et al.), and Prophecy
(Ravi Netravali et al.).
