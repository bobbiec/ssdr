"""
This script auto-inlines images and Javascript via mitmproxy.

TODO: CSS
"""
import base64
import functools
import requests

from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from mitmproxy import http, ctx


MAX_WORKERS = 6


def img_retrieve_source_base64(base_uri: str, old_src: str):
    try:
        resp = requests.get(old_src)
    except requests.exceptions.MissingSchema:
        new_uri = f"{base_uri}/{old_src}"
        resp = requests.get(new_uri)
    except Exception as e:
        ctx.log.error(f"Error in img {old_src}: {e}")
        return old_src
    return f"data:{resp.headers['content-type']};base64,{base64.b64encode(resp.content).decode()}"


def script_get_source_string(base_uri: str, old_src: str):
    try:
        resp = requests.get(old_src)
    except requests.exceptions.MissingSchema:
        new_uri = f"{base_uri}/{old_src}"
        resp = requests.get(new_uri)
    except Exception as e:
        ctx.log.error(f"Error in img {old_src}: {e}")
        return ''
    return resp.content.decode()


def response(flow: http.HTTPFlow) -> None:
    # flow: a mitmproxy.http.HTTPFlow
    original_base_uri = f"{flow.request.scheme}://{flow.request.host}:{flow.request.port}"
    new_base_uri = f"{flow.request.scheme}://{ctx.options.listen_host}:{ctx.options.listen_port}"

    html = BeautifulSoup(flow.response.content, "html.parser")
    if html.body:
        scripts = [script for script in html.findAll('script') if script.get('src')]
        images = [img for img in html.findAll('img') if img.get('src')]
        styles = []  # TODO: styles

        num_workers = MAX_WORKERS or (len(scripts) + len(images) + len(styles))
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            image_results = [
                executor.submit(functools.partial(img_retrieve_source_base64, original_base_uri), image['src'])
                for image in images
            ]
            script_results = [
                executor.submit(functools.partial(script_get_source_string, original_base_uri), script['src'])
                for script in scripts
            ]

            for (image, result) in zip(images, image_results):
                image['src'] = result.result()

            for (script, result) in zip(scripts, script_results):
                del script['src']
                script.string = result.result()

        flow.response.content = str(html).encode("utf8")

    flow.replace(original_base_uri, new_base_uri)
