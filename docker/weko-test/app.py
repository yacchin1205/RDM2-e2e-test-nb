"""HTTPS peer for the RDM JAIRO Cloud integration notebooks."""
import os
import secrets
from functools import wraps
from urllib.parse import urlencode

from flask import Flask, abort, jsonify, redirect, render_template_string, request, session, url_for

from datetime import datetime, timezone
from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile
import json
import mimetypes

from flask import send_file
from records import datasets, metadata

app = Flask(__name__)
app.json.ensure_ascii = False
app.jinja_env.policies['json.dumps_kwargs'] = {'ensure_ascii': False}
app.secret_key = secrets.token_bytes(32)
app.config.update(SESSION_COOKIE_NAME='weko_test', SESSION_COOKIE_SECURE=True)
admin = os.environ['WEKO_ADMIN_EMAIL']
accounts = {admin: os.environ['WEKO_ADMIN_PASSWORD'],
            os.environ['WEKO_USER_EMAIL']: os.environ['WEKO_USER_PASSWORD']}
clients = {}
codes = {}
tokens = {}


def signed_in(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if 'email' not in session:
            session['next'] = request.full_path
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapped


def administrator(view):
    @wraps(view)
    @signed_in
    def wrapped(*args, **kwargs):
        if session['email'] != admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


@app.get('/')
def home():
    return render_template_string("""
    <title>WEKO test service</title><h1>WEKO test service</h1>
    {% if session.email %}
      <a href="/account/settings/profile/"><i class="fa fa-user"></i>Profile</a>
      <div class="navbar-form"><button class="dropdown-toggle" onclick="this.nextElementSibling.hidden=false">{{session.email}}</button>
      <div hidden><a href="/account/settings/applications/">Applications</a> <a href="/logout/">Logout</a></div></div>
      <a href="/workflow/">WorkFlow</a>
    {% else %}<a class="login-button" href="/login/">Login</a>{% endif %}
    """)


@app.route('/login/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        if email not in accounts or not secrets.compare_digest(accounts[email], request.form['password']):
            abort(401)
        session['email'] = email
        return redirect(session.pop('next', '/'))
    return '<form method="post"><input id="email" name="email"><input id="password" type="password" name="password"><button type="submit">Log in</button></form>'


@app.get('/logout/')
def logout():
    session.clear()
    return redirect('/')


@app.get('/account/settings/applications/')
@administrator
def applications():
    return '<strong>Developer Applications</strong> <a href="/account/settings/applications/new">New application</a>'


@app.route('/account/settings/applications/new', methods=['GET', 'POST'])
@administrator
def new_application():
    if request.method == 'GET':
        return """<strong>New OAuth Application</strong><form method="post">
        <input name="name" required><textarea name="description"></textarea><input name="website">
        <textarea name="redirect_uris" required></textarea><button type="submit">Register</button></form>"""
    key = secrets.token_urlsafe(18)
    clients[key] = {'uri': request.form['redirect_uris'], 'secret': secrets.token_urlsafe(32)}
    return render_template_string('<p><strong>Client ID</strong><code>{{key}}</code></p><p><strong>Client Secret</strong><code>{{secret}}</code></p>',
                                  key=key, secret=clients[key]['secret'])


@app.route('/oauth/authorize', methods=['GET', 'POST'])
@signed_in
def authorize():
    key = request.args['client_id']
    if key not in clients or clients[key]['uri'] != request.args['redirect_uri']:
        abort(400)
    if request.method == 'GET':
        return '<form method="post"><button type="submit">Authorize application</button></form>'
    code = secrets.token_urlsafe(32)
    codes[code] = (key, session['email'])
    return redirect(clients[key]['uri'] + '?' + urlencode({'state': request.args['state'], 'code': code}))


@app.post('/oauth/token')
def token():
    auth = request.authorization
    key, password = (auth.username, auth.password) if auth else (request.form['client_id'], request.form['client_secret'])
    if key not in clients or clients[key]['secret'] != password:
        abort(401)
    code = request.form['code']
    if code not in codes or codes[code][0] != key or request.form['redirect_uri'] != clients[key]['uri']:
        abort(400)
    access = secrets.token_urlsafe(32)
    tokens[access] = codes.pop(code)
    return jsonify(access_token=access, token_type='Bearer')


def identity():
    access = request.headers.get('Authorization', '').removeprefix('Bearer ')
    if access not in tokens:
        abort(401)
    return tokens[access]


@app.get('/api/get_profile_info/')
def profile():
    return jsonify(results={'subitem_mail_address': identity()[1]})


@app.get('/api/tree')
def tree():
    language = request.accept_languages.best_match(['en', 'ja'])
    return jsonify([{'id': '1', 'name': 'サンプルインデックス' if language == 'ja' else 'Sample Index', 'children': []},
                    {'id': '2', 'name': '別のインデックス' if language == 'ja' else 'Other Index', 'children': []}])


records = {}
activities = {}


def api_record(record):
    return {'id': record['id'], 'metadata': record['metadata'], 'updated': record['metadata']['updated']}


@app.get('/api/index/')
def index():
    selected = [api_record(r) for r in records.values() if r['public'] and request.args['q'] in r['indices']]
    size, page = int(request.args.get('size', 1000)), int(request.args.get('page', 1))
    return jsonify(hits={'hits': selected[(page - 1)*size:page*size], 'total': len(selected)})


@app.get('/api/records/<int:key>')
def api_item(key):
    if key not in records or not records[key]['public']:
        abort(404)
    return jsonify(api_record(records[key]))


@app.post('/sword/service-document')
@app.put('/sword/deposit/<int:key>')
def deposit(key=None):
    client, _ = identity()
    registration = clients[client].get('registration')
    if registration is None:
        abort(403)
    if key is not None and (key not in records or records[key]['client'] != client):
        abort(404)
    review = registration['mode'] == 'workflow'
    links = []
    pending = {}
    with ZipFile(request.files['file'].stream) as bag:
        crate = json.loads(bag.read('data/ro-crate-metadata.json'))
        items = datasets(crate)
        if not items or (key is not None and len(items) != 1):
            abort(400)
        for item in items:
            identifier = key if key is not None else max(records, default=2000000) + len(pending) + 1
            fields = metadata(item, registration['mapping'])
            title = item.get('dc:title', item.get('name', []))
            titles = [t['value'] if isinstance(t, dict) else t for t in (title if isinstance(title, list) else [title])]
            primary_title = item.get('name') or next(iter(titles), '')
            fields.update(title=[primary_title], updated=datetime.now(timezone.utc).isoformat())
            files = {}
            file_field = next((f for f in fields if f.startswith('item_') and fields[f]['attribute_name'] == 'File'), 'item_files')
            file_metadata = fields.get(file_field, {}).get('attribute_value_mlt', [])
            file_entries = []
            for pos, part in enumerate(item.get('hasPart', [])):
                path = part['@id'].removeprefix('./')
                if not path.startswith('files/'):
                    continue
                filename = path.removeprefix('files/')
                files[filename] = bag.read('data/' + path)
                entry = file_metadata[pos].copy() if pos < len(file_metadata) else {}
                content_type = entry.get('format') or mimetypes.guess_type(filename)[0] or 'application/octet-stream'
                entry.update(filename=filename, version_id=str(uuid4()), format=content_type, mimetype=content_type,
                             url={'url': url_for('file_download', key=identifier, name=filename, _external=True), 'label': filename})
                file_entries.append(entry)
            fields[file_field] = {'attribute_name': 'File', 'attribute_type': 'file', 'attribute_value_mlt': file_entries}
            indices = item['wk:index']
            indices = indices if isinstance(indices, list) else [indices]
            pending[identifier] = dict(id=identifier, indices=[str(index) for index in indices], metadata=fields, public=not review, client=client, files=files)
            links.append({'@id': url_for('item_page', key=identifier, _external=True), 'rel': ['alternate'], 'contentType': 'text/html'})
            if review:
                links.append({'@id': url_for('activity', key=identifier, _external=True),
                              'rel': ['related'], 'contentType': 'text/html'})
            record_url = url_for('item_page', key=identifier, _external=True)
            for entry in file_entries:
                links.append({'@id': entry['url']['url'], 'rel': ['http://purl.org/net/sword/3.0/terms/fileSetFile'],
                              'contentType': entry['format'], 'derivedFrom': record_url})
    records.update(pending)
    if review:
        activities.update(dict.fromkeys(pending, False))
    state = 'inWorkflow' if review else 'ingested'
    return jsonify({'@id': request.url_root + 'sword/deposit/' + str(identifier),
                    'state': [{'@id': 'http://purl.org/net/sword/3.0/state/' + state}], 'links': links}), 201


@app.get('/records/<int:key>')
def item_page(key):
    record = records.get(key)
    if not record or not record['public']:
        abort(404)
    return render_template_string("""
      <aside id="test-notice">WEKO test service
        <button onclick="sessionStorage.setItem('wekoNotice','accepted');this.parentElement.hidden=true">That's ok</button></aside>
      <script>document.getElementById('test-notice').hidden = !!sessionStorage.getItem('wekoNotice')</script>
      <a href="/workflow/">WorkFlow</a><h1>{{record.metadata.title|join(' / ')}}</h1><p id="public_status_form">Public</p>
      <a href="{{url_for('api_item',key=record.id)}}">JSON</a>
      {% for name in record.files %}<span class="filename"><a href="{{url_for('file_download',key=record.id,name=name)}}">{{name}}</a></span>{% endfor %}
      <table class="detail-table">{% for field in record.metadata.values() if field is mapping %}
      <tr><th>{{field.attribute_name}}</th><td class="multiple-line">{{field.get('attribute_value_mlt', field.get('attribute_value'))|tojson}}</td></tr>
      {% endfor %}</table>""", record=record)


@app.get('/records/<int:key>/files/<path:name>')
def file_download(key, name):
    if key not in records or not records[key]['public'] or name not in records[key]['files']:
        abort(404)
    return send_file(BytesIO(records[key]['files'][name]), download_name=name, as_attachment=True)


@app.get('/workflow/')
@administrator
def workflow():
    return render_template_string("""
      <div id="myTabContent"><div class="table-responsive"><table><tr><th>Activity</th></tr>
      {% for key in keys %}<tr><td><a class="activity-link" href="{{url_for('activity',key=key)}}">{{key}}</a></td></tr>{% endfor %}
      </table></div></div>""", keys=reversed(activities))


@app.route('/workflow/activity/detail/<int:key>', methods=['GET', 'POST'])
@administrator
def activity(key):
    if key not in activities:
        abort(404)
    if request.method == 'POST':
        activities[key] = True
        records[key]['public'] = True
    if activities[key]:
        return render_template_string('<form action="{{url_for(\'item_page\',key=key)}}"><button>Access</button></form>', key=key)
    return '<form method="post"><button>Approval</button></form>'


@app.post('/test/sword-clients/<client>')
def register(client):
    if request.remote_addr not in {'127.0.0.1','::1'}:
        abort(403)
    if client not in clients:
        abort(404)
    data = request.get_json()
    if data['mode'] not in {'direct','workflow'} or data['mapping'] not in {30002,51000}:
        abort(400)
    clients[client]['registration'] = data
    return '', 204
