from flask import Blueprint, abort, render_template

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    return queue()


@bp.route("/queue")
def queue():
    from app.repo.threads import list_flagged_threads

    threads = list_flagged_threads()
    return render_template("queue.html", threads=threads, selected=None)


@bp.route("/queue/<int:thread_pk>")
def queue_detail(thread_pk):
    from app.repo.threads import get_thread_detail, list_flagged_threads

    threads = list_flagged_threads()
    detail = get_thread_detail(thread_pk)
    return render_template(
        "queue.html",
        threads=threads,
        selected=detail,
        not_found=detail is None,
    )


@bp.route("/threads")
def threads():
    return render_template("threads.html")


@bp.route("/config")
def config():
    return render_template("config.html")


@bp.route("/runs")
def runs():
    return render_template("runs.html")
