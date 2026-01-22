from flask import Blueprint, redirect, render_template, request, url_for

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


@bp.route("/queue/<int:thread_pk>/draft", methods=["POST"])
def save_draft(thread_pk):
    from app.repo.drafts import save_edited_draft

    draft_text = request.form.get("draft_text", "")
    save_edited_draft(thread_pk, draft_text)
    return redirect(url_for("main.queue_detail", thread_pk=thread_pk))


@bp.route("/threads")
def threads():
    from app.repo.threads import list_recent_threads

    recent_threads = list_recent_threads()
    return render_template("threads.html", threads=recent_threads)


@bp.route("/config")
def config():
    return render_template("config.html")


@bp.route("/runs")
def runs():
    from app.repo.runs import list_recent_runs

    recent_runs = list_recent_runs()
    return render_template("runs.html", runs=recent_runs)
