"""
This script auto-inlines images, Javascript, and CSS.

It also resolves iframes to depth 1.
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

    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        # we can't signal an error here, so let the browser handle the 404
        ctx.log.error(f"Error in img {old_src}: {e}")
        return old_src

    return f"data:{resp.headers['content-type']};base64,{base64.b64encode(resp.content).decode()}"


def script_get_source_string(base_uri: str, old_src: str):
    try:
        resp = requests.get(old_src)
        resp.raise_for_status()
    except requests.exceptions.MissingSchema:
        new_uri = f"{base_uri}/{old_src}"
        resp = requests.get(new_uri)

    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        ctx.log.error(f"HTTPError for {old_src}: {e}")
        return f'/* Error fetching {old_src}: {e} */'

    return resp.text


def css_get_source_string(base_uri: str, old_src: str):
    # currently same as script, but separate function in case that might change later
    return script_get_source_string(base_uri, old_src)


def iframe_get_source_string(base_uri: str, old_src: str):
    # TODO: recursively resolve iframes
    return script_get_source_string(base_uri, old_src)


def response(flow: http.HTTPFlow) -> None:
    original_base_uri = f"{flow.request.scheme}://{flow.request.host}:{flow.request.port}"

    html = BeautifulSoup(flow.response.content, "html.parser")
    if html.body:
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
            style_results = [
                executor.submit(functools.partial(css_get_source_string, original_base_uri), style['href'])
                for style in styles
            ]
            iframe_results = [
                executor.submit(functools.partial(iframe_get_source_string, original_base_uri), iframe['src'])
                for iframe in iframes
            ]

            for (image, result) in zip(images, image_results):
                image['src'] = result.result()

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

        flow.response.text = str(html)

    new_base_uri = f"{flow.request.scheme}://{ctx.options.listen_host}:{ctx.options.listen_port}"
    flow.replace(original_base_uri, new_base_uri)
