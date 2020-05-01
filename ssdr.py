"""
This script auto-inlines images, Javascript, and CSS.

It also resolves iframes to depth MAX_DEPTH (3).
"""
import base64
import functools
import logging
import re
import requests
import sys

from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from mitmproxy import http, ctx
from mitmproxy.script import concurrent


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


MAX_DEPTH = 3


def img_retrieve_source_base64(base_uri: str, old_src: str):
    try:
        resp = requests.get(old_src)
    except requests.exceptions.MissingSchema:
        new_uri = f"{base_uri}/{old_src}"
        resp = requests.get(new_uri)

    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        # we can't signal an error here, so let the browser handle the 404
        logger.info(f"Error in img {old_src}: {e}")
        return None

    return f"data:{resp.headers['content-type']};base64,{base64.b64encode(resp.content).decode()}"


def script_get_source_string(base_uri: str, old_src: str):
    logger.debug(f"script called for {old_src}")

    try:
        resp = requests.get(old_src)
    except requests.exceptions.MissingSchema:
        new_uri = f"{base_uri}/{old_src}"
        resp = requests.get(new_uri)

    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        logger.info(f"HTTPError for {old_src}: {e}")
        return None

    return resp.text


# Regex matching relative CSS urls; 3rd group contains the relative url
# tested on examples from https://developer.mozilla.org/en-US/docs/Web/CSS/url()
# using https://regex101.com/
CSS_URL_REGEX = re.compile(r"url\(([\'\"]?)(?!(https?://|data:|#))([^\'\"\s\)]*)\1\)")


def absolutize_css_urls(base_uri: str, match: re.Match) -> str:
    logger.debug(f'replacing {match.group(0)} with url({match.group(1)}{base_uri}/{match.group(3)}{match.group(1)})')
    return f'url({match.group(1)}{base_uri}/{match.group(3)}{match.group(1)})'


def css_get_source_string(base_uri: str, old_src: str):
    logger.debug(f"css called for {old_src}")

    uri = old_src
    try:
        resp = requests.get(old_src)
    except requests.exceptions.MissingSchema:
        uri = f"{base_uri}/{old_src}"
        resp = requests.get(uri)

    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        logger.info(f"HTTPError for {old_src}: {e}")
        return None

    # URLs will be relative to the base_uri here, so we need to make them absolute
    uri_dir = uri[:uri.rfind('/')]
    result = re.sub(CSS_URL_REGEX, functools.partial(absolutize_css_urls, uri_dir), resp.text)
    return result


def iframe_get_source_string(base_uri: str, old_src: str, executor: ThreadPoolExecutor, depth: int):
    logger.debug(f"iframe called for {old_src}")

    try:
        resp = requests.get(old_src)
        resp.raise_for_status()
    except requests.exceptions.MissingSchema:
        new_uri = f"{base_uri}/{old_src}"
        resp = requests.get(new_uri)

    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        logger.info(f"HTTPError for {old_src}: {e}")
        return None

    html = BeautifulSoup(resp.content, "html.parser")
    logger.debug(f'recursing for {old_src} with depth {depth+1}')
    return str(inline_html(html, base_uri, executor, depth=depth+1))  # recursively resolve iframes


def inline_html(html: BeautifulSoup, base_uri: str, executor: ThreadPoolExecutor, depth: int = 0) -> BeautifulSoup:
    if not html.body or depth > MAX_DEPTH:
        return html

    scripts = [script for script in html.findAll('script') if script.get('src')]
    images = [img for img in html.findAll('img') if img.get('src')]
    styles = [
        link for link in html.findAll('link')
        if link.get('rel') and
            len(link['rel']) > 0 and
            link['rel'][0] == 'stylesheet' and
            link.get('href')
    ]
    iframes = [iframe for iframe in html.findAll('iframe') if iframe.get('src')]

    image_results = [
        executor.submit(functools.partial(img_retrieve_source_base64, base_uri), image['src'])
        for image in images
    ]
    script_results = [
        executor.submit(functools.partial(script_get_source_string, base_uri), script['src'])
        for script in scripts
    ]
    style_results = [
        executor.submit(functools.partial(css_get_source_string, base_uri), style['href'])
        for style in styles
    ]
    iframe_results = [
        executor.submit(
            functools.partial(iframe_get_source_string, base_uri, executor=executor, depth=depth), iframe['src']
        )
        for iframe in iframes
    ]

    for (image, result) in zip(images, image_results):
        r = result.result()
        if r:
            image['src'] = r

    for (script, result) in zip(scripts, script_results):
        r = result.result()
        if r:
            del script['src']
            script.string = r

    for (style, result) in zip(styles, style_results):
        r = result.result()
        if r:
            new_style = html.new_tag('style')
            new_style.string = r
            style.insert_after(new_style)
            style.decompose()

    for (iframe, result) in zip(iframes, iframe_results):
        r = result.result()
        if r:
            iframe['srcdoc'] = r

    return html

class SSDR:
    max_workers = 6  # same as Firefox default

    # def __init__(self):
    #     self.executor = ThreadPoolExecutor(max_workers=self.max_workers)

    # def __del__(self):
    #     self.executor.shutdown(wait=False)

    @concurrent
    def response(self, flow: http.HTTPFlow) -> None:
        original_base_uri = f"{flow.request.scheme}://{flow.request.host}"
        if flow.request.port not in [80, 443]:
            # only add the port if it's nonstandard; this allows the replace to work as expected
            original_base_uri += f':{flow.request.port}'

        html = BeautifulSoup(flow.response.content, "html.parser")
        if html.body:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                flow.response.text = str(inline_html(html, original_base_uri, executor))

            new_base_uri = f"{flow.request.scheme}://{ctx.options.listen_host}:{ctx.options.listen_port}"
            flow.replace(original_base_uri, new_base_uri)


addons = [
    SSDR()
]
