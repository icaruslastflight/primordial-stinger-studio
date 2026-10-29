# VJTB Stinger Studio <-> TouchDesigner bridge
# -----------------------------------------------------------------------------
# Setup (or let your AI agent do it — see the AI Wizard tab in the web app):
#   1. Add a Web Server DAT. Port 9980 (must match the app's TD URL), Active = On.
#      NOTE: the community Pantani/tdmcp bridge also defaults to 9980 — change one of them if both run.
#   2. Point its Callbacks DAT parameter at a Text DAT containing this file.
#   3. In the web app press "Push to Live Host". A baseCOMP named `vjtb` is built next to the
#      Web Server DAT:  logo_in (Movie File In) -> pass0..N (GLSL TOP) [+ fb_* Feedback TOPs] -> out1 (Null).
#   4. Live slider / LFO / audio changes arrive as {"t":"params"} and set GLSL TOP uniforms directly.
#   5. The network remembers which effect it was built for (stored on the vjtb COMP). The 'pushed' reply and the
#      'hello' reply carry "effect": <effect id>, so the app can offer "Send preset" (parameters only, no shader)
#      for an effect TD already holds. {"t":"params"} messages that name a different effect are ignored, so
#      browsing the deck never changes what is on air.
#
# API notes (verified against docs.derivative.ca, 2026-10):
#   callbacks take `dat` first; send with dat.webSocketSendText(client, text);
#   GLSL TOP: pixeldat, outputresolution='custom', resolutionw/h, format='rgba32float';
#   vector uniforms are the `vec` sequence (vec0name, vec0valuex..w; seq.vec.numBlocks).
#   TouchDesigner has no built-in time uniform, so TIME is bound to absTime.seconds.
# Older builds that still use uniname0/value0x are handled by the fallback in _set_uniforms().
# -----------------------------------------------------------------------------
import json
import base64
import os
import traceback

CONTAINER = 'vjtb'
HELD_KEY = 'vjtb_effect'          # effect id the network was last pushed for (COMP storage, survives save / reopen)
SERVE_FILE = 'vjtb_studio.html'   # optional: put the single-file build next to your .toe to serve it on GET /


def _root(dat):
    par = dat.parent()
    c = par.op(CONTAINER)
    if c is None:
        c = par.create(baseCOMP, CONTAINER)
        c.nodeX = dat.nodeX + 220
        c.nodeY = dat.nodeY
    return c


def _ensure(c, optype, name, x, y):
    o = c.op(name)
    if o is not None and o.OPType != optype.__name__:
        o.destroy()
        o = None
    if o is None:
        o = c.create(optype, name)
    o.nodeX = x
    o.nodeY = y
    return o


def _send(dat, client, obj):
    dat.webSocketSendText(client, json.dumps(obj))


def _held(dat):
    """Effect id the vjtb network currently holds, or None."""
    c = dat.parent().op(CONTAINER)
    if c is None:
        return None
    return c.fetch(HELD_KEY, None, search=False)


def _write_logo(c, b64):
    folder = os.path.join(project.folder, 'vjtb_assets')
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, 'vjtb_logo.png')
    with open(path, 'wb') as f:
        f.write(base64.b64decode(b64))
    m = _ensure(c, moviefileinTOP, 'logo_in', 0, 0)
    m.par.file = path
    try:
        m.par.reloadpulse.pulse()
    except Exception:
        pass
    return m


def _set_par(p, value=None, expr=None):
    if expr:
        p.expr = expr
        p.mode = ParMode.EXPRESSION
    else:
        p.mode = ParMode.CONSTANT
        p.val = value


def _set_uniforms(g, uniforms):
    """Configure the GLSL TOP Vectors page. Returns {uniform name: block index}."""
    mapping = {}
    seq = getattr(g.seq, 'vec', None) if hasattr(g, 'seq') else None
    if seq is not None:
        seq.numBlocks = max(1, len(uniforms))
        for i, u in enumerate(uniforms):
            getattr(g.par, 'vec%dname' % i).val = u['name']
            vals = list(u.get('value', [])) + [0.0, 0.0, 0.0, 0.0]
            for j, comp in enumerate('xyzw'):
                p = getattr(g.par, 'vec%dvalue%s' % (i, comp))
                _set_par(p, float(vals[j]), u.get('expr') if j == 0 else None)
            mapping[u['name']] = ('vec', i)
    else:  # legacy builds
        for i, u in enumerate(uniforms):
            getattr(g.par, 'uniname%d' % i).val = u['name']
            vals = list(u.get('value', [])) + [0.0, 0.0, 0.0, 0.0]
            for j, comp in enumerate('xyzw'):
                p = getattr(g.par, 'value%d%s' % (i, comp))
                _set_par(p, float(vals[j]), u.get('expr') if j == 0 else None)
            mapping[u['name']] = ('legacy', i)
    g.store('vjtb_map', mapping)
    return mapping


def _apply_values(g, values):
    mapping = g.fetch('vjtb_map', {}, search=False)
    for name, vals in values.items():
        hit = mapping.get(name)
        if not hit:
            continue
        kind, i = hit
        for j, comp in enumerate('xyzw'[:len(vals)]):
            pname = ('vec%dvalue%s' % (i, comp)) if kind == 'vec' else ('value%d%s' % (i, comp))
            p = getattr(g.par, pname)
            if p.mode == ParMode.CONSTANT:
                p.val = float(vals[j])


def _push(dat, client, m):
    c = _root(dat)
    w, h = m.get('resolution', [1280, 720])
    logo = c.op('logo_in') or _ensure(c, moviefileinTOP, 'logo_in', 0, 0)
    for o in list(c.findChildren(depth=1)):
        if o.name.startswith(('pass', 'fb_', 'shader_')) or o.name == 'out1':
            o.destroy()
    passes = m['passes']
    nodes = {}
    for p in passes:
        k = p['index']
        txt = _ensure(c, textDAT, 'shader_%d' % k, 220 + 260 * k, -220)
        txt.text = p['code']
        g = _ensure(c, glslTOP, 'pass%d' % k, 220 + 260 * k, 0)
        g.par.pixeldat = txt.name
        g.par.outputresolution = 'custom'
        g.par.resolutionw = int(w)
        g.par.resolutionh = int(h)
        g.par.format = 'rgba32float' if p.get('float') else 'rgba8fixed'
        nodes[k] = g
    producer = {p['target']: p['index'] for p in passes if p.get('target')}
    for p in passes:
        g = nodes[p['index']]
        for slot in sorted(m['inputs'], key=lambda s: s['index']):
            src = logo
            if slot['kind'] == 'buffer':
                pk = producer.get(slot['name'])
                if pk is not None and pk < p['index']:
                    src = nodes[pk]
                elif pk is not None:
                    fb = _ensure(c, feedbackTOP, 'fb_%s' % slot['name'], 220 + 260 * pk, 220)
                    fb.par.top = nodes[pk].name
                    fb.inputConnectors[0].connect(logo)
                    src = fb
            g.inputConnectors[slot['index']].connect(src)
        _set_uniforms(g, m['uniforms'])
    last = nodes[max(nodes)]
    out = _ensure(c, nullTOP, 'out1', 220 + 260 * (max(nodes) + 1), 0)
    out.inputConnectors[0].connect(last)
    errs = [n.errors() for n in nodes.values() if n.errors()]
    effect = m.get('effect')
    c.store(HELD_KEY, effect)
    _send(dat, client, {'t': 'pushed', 'op': out.path, 'uniforms': len(m['uniforms']), 'errors': errs, 'effect': effect})


def _params(dat, m):
    c = dat.parent().op(CONTAINER)
    if c is None:
        return
    want = m.get('effect')
    held = c.fetch(HELD_KEY, None, search=False)
    if want and held and want != held:
        return  # values for an effect this network does not hold: ignore until it is pushed
    for g in c.findChildren(type=glslTOP, depth=1):
        _apply_values(g, m.get('values', {}))


def onWebSocketReceiveText(dat, client, data):
    try:
        m = json.loads(data)
        t = m.get('t')
        if t == 'params':
            _params(dat, m)
        elif t == 'ping':
            _send(dat, client, {'t': 'pong', 'id': m.get('id')})
        elif t == 'hello':
            reply = {'t': 'hello', 'build': '%s.%s' % (app.version, app.build)}
            held = _held(dat)
            if held:
                reply['effect'] = held
            _send(dat, client, reply)
        elif t == 'logo':
            _write_logo(_root(dat), m['png_b64'])
        elif t == 'push':
            _push(dat, client, m)
    except Exception as e:
        _send(dat, client, {'t': 'error', 'error': '%s: %s' % (type(e).__name__, e), 'trace': traceback.format_exc()[-800:]})
    return


def onWebSocketReceiveBinary(dat, client, data):
    return


def onWebSocketOpen(dat, client, uri):
    return


def onWebSocketClose(dat, client):
    return


def onWebSocketReceivePing(dat, client, data):
    dat.webSocketSendPong(client, data=data)
    return


def onWebSocketReceivePong(dat, client, data):
    return


def onHTTPRequest(dat, request, response):
    path = os.path.join(project.folder, SERVE_FILE)
    if request.get('uri', '/') in ('/', '/index.html') and os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            response['data'] = f.read()
        response['content-type'] = 'text/html'
    else:
        response['data'] = json.dumps({'vjtb': 'touchdesigner-bridge', 'container': CONTAINER, 'serve': SERVE_FILE})
        response['content-type'] = 'application/json'
    response['statusCode'] = 200
    response['statusReason'] = 'OK'
    return response


def onServerStart(dat):
    return


def onServerStop(dat):
    return
