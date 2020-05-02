from quart import make_response, Quart, render_template, url_for, make_push_promise

app = Quart(__name__)

@app.route('/')
async def index():
    result = await render_template('index.html')
    response = await make_response(result)
    push_resources = [url_for('static', filename='index.js'), url_for('static', filename='index.css')]
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
