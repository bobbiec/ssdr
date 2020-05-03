import os

from quart import make_response, Quart, render_template, url_for, make_push_promise

app = Quart(__name__)
SERVER_PUSH = os.getenv('SERVER_PUSH')


@app.route('/')
@app.route('/0')
async def index():
    result = await render_template('index.html')
    response = await make_response(result)
    push_resources = [url_for('static', filename='index.js'), url_for('static', filename='index.css')]
    if SERVER_PUSH:
        for item in push_resources:
            await make_push_promise(item)
    return response

@app.route('/<int:depth>')
async def iframes(depth: int):
    result = await render_template('recursive-iframes.html', depth=depth)
    response = await make_response(result)
    push_resources = [
        url_for('static', filename='index.js'),
        url_for('static', filename='index.css'),
        *(f"/{d}" for d in range(depth)[-10:]),
    ]
    if SERVER_PUSH:
        for item in push_resources:
            await make_push_promise(item)
    return response

if __name__ == '__main__':
    app.run(
        host='localhost',
        port=5000,
        certfile='cert.pem',
        keyfile='key.pem',
    )
