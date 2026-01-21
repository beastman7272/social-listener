from flask import Blueprint, render_template

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    return render_template("queue.html")


@bp.route("/queue")
def queue():
    return render_template("queue.html")


@bp.route("/threads")
def threads():
    return render_template("threads.html")


@bp.route("/config")
def config():
    return render_template("config.html")


@bp.route("/runs")
def runs():
    return render_template("runs.html")
