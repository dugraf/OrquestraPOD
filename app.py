"""Servidor Flask: dashboard web do orquestrador de PODs.

Rotas:
  GET /             -> dashboard (HTML)
  GET /api/state    -> estado do cluster ao vivo (JSON, consumido por polling)
  GET /api/compare  -> comparação proposto x padrão K8s (JSON)
"""

from __future__ import annotations

from flask import Flask, jsonify, render_template

from cluster import Master, stats

app = Flask(__name__)

# Master único, iniciado quando o app sobe. As threads (produtor/consumidor/
# reaper) rodam em background e atualizam o estado continuamente.
master = Master(total_pods=18, intervalo_producao=1.2)
master.iniciar()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/state")
def api_state():
    return jsonify(master.snapshot())


@app.route("/api/compare")
def api_compare():
    return jsonify(stats.comparar())


if __name__ == "__main__":
    # threaded=True para servir o polling enquanto as threads do cluster rodam.
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
