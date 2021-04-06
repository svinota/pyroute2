import json
import bottle
from collections import OrderedDict

stats = {}


@bottle.post('/v1/report/')
def post_report():
    global stats
    req = json.loads(bottle
                     .request
                     .body
                     .getvalue()
                     .decode('utf-8'))

    worker = req['worker']
    run_id = req['run_id']

    if worker not in stats:
        stats[worker] = OrderedDict()
    if run_id not in stats[worker]:
        stats[worker][run_id] = req['report']
    return bottle.template('{{!code}}', code=len(tuple(stats[worker].keys())))


@bottle.put('/v1/report/<worker>/<run_id>/')
def put_report(worker, run_id):
    global stats

    log = (bottle
           .request
           .body
           .getvalue()
           .decode('utf-8'))

    stats[worker][run_id]['log'] = log
    return bottle.template('{{!run_id}}', run_id=run_id)


@bottle.get('/v1/report/')
def get_report():
    global stats
    ret = {x: [] for x in stats}
    for worker in stats:
        for run in stats[worker]:
            ret[worker].append((run, stats[worker][run]))
    ret = json.dumps(ret)
    return bottle.template('{{!ret}}', ret=ret)


bottle.run(host='0.0.0.0', port=8080)
