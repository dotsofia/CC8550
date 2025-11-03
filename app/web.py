# app/web.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, Response
from app.service import AnimeService, ValidationError, NotFoundError
import csv, io, json, logging
from typing import List, Optional

logger = logging.getLogger(__name__)

bp = Blueprint("main", __name__, url_prefix="")  # blueprint name = 'main'

def register_routes(app, service: AnimeService):
    """
    Register blueprint and ensure SERVICE is in app.config.
    Call this once during app creation (run.create_app does this).
    """
    if "SERVICE" not in app.config:
        app.config["SERVICE"] = service
    app.register_blueprint(bp)
    logger.debug("Registered blueprint 'main' and injected SERVICE")

def register_error_handlers(app):
    """Centralized handlers for service exceptions."""
    @app.errorhandler(ValidationError)
    def handle_validation_error(e):
        logger.warning("ValidationError: %s", e)
        return render_template("error.html", message=str(e)), 400

    @app.errorhandler(NotFoundError)
    def handle_not_found(e):
        logger.info("NotFoundError: %s", e)
        return render_template("error.html", message=str(e)), 404

# helper to get service instance
def current_service() -> AnimeService:
    return current_app.config["SERVICE"]

# -----------------------
# Basic pages
# -----------------------
@bp.route("/")
def index():
    return render_template("index.html")

# -----------------------
# Users
# -----------------------
@bp.route("/users")
def users():
    svc = current_service()
    users = svc.list_users()
    return render_template("user_list.html", users=users)

@bp.route("/users/new", methods=["GET", "POST"])
def user_new():
    svc = current_service()
    if request.method == "POST":
        name = request.form.get("username", "").strip()
        try:
            svc.create_user(name)
            flash("User created.", "success")
            return redirect(url_for("main.users"))
        except ValidationError as e:
            flash(str(e), "danger")
    return render_template("user_form.html", user=None)

@bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
def user_edit(user_id: int):
    svc = current_service()
    try:
        u = svc.get_user(user_id)
    except NotFoundError:
        flash("User not found", "danger")
        return redirect(url_for("main.users"))
    if request.method == "POST":
        try:
            svc.update_user(user_id, request.form.get("username", ""))
            flash("Updated.", "success")
            return redirect(url_for("main.users"))
        except ValidationError as e:
            flash(str(e), "danger")
    return render_template("user_form.html", user=u)

@bp.route("/users/<int:user_id>/delete", methods=["POST"])
def user_delete(user_id: int):
    svc = current_service()
    svc.delete_user(user_id)
    flash("Deleted user", "info")
    return redirect(url_for("main.users"))

# -----------------------
# Studios
# -----------------------
@bp.route("/studios")
def studios():
    svc = current_service()
    studios = svc.list_studios()
    return render_template("studio_list.html", studios=studios)

@bp.route("/studios/new", methods=["GET", "POST"])
def studio_new():
    svc = current_service()
    if request.method == "POST":
        try:
            svc.create_studio(request.form.get("name", ""))
            flash("Studio created", "success")
            return redirect(url_for("main.studios"))
        except ValidationError as e:
            flash(str(e), "danger")
    return render_template("studio_form.html", studio=None)

@bp.route("/studios/<int:sid>/edit", methods=["GET", "POST"])
def studio_edit(sid: int):
    svc = current_service()
    try:
        s = svc.repo.get_studio(sid)
        if not s:
            raise NotFoundError("studio not found")
    except NotFoundError:
        flash("Studio not found", "danger")
        return redirect(url_for("main.studios"))
    if request.method == "POST":
        try:
            svc.update_studio(sid, request.form.get("name", ""))
            flash("Updated", "success")
            return redirect(url_for("main.studios"))
        except ValidationError as e:
            flash(str(e), "danger")
    return render_template("studio_form.html", studio=s)

@bp.route("/studios/<int:sid>/delete", methods=["POST"])
def studio_delete(sid: int):
    svc = current_service()
    svc.delete_studio(sid)
    flash("Studio deleted", "info")
    return redirect(url_for("main.studios"))

# -----------------------
# Tags
# -----------------------
@bp.route("/tags")
def tags():
    svc = current_service()
    return render_template("tag_list.html", tags=svc.list_tags())

@bp.route("/tags/new", methods=["GET", "POST"])
def tag_new():
    svc = current_service()
    if request.method == "POST":
        try:
            svc.create_tag(request.form.get("name", ""))
            flash("Tag created", "success")
            return redirect(url_for("main.tags"))
        except ValidationError as e:
            flash(str(e), "danger")
    return render_template("tag_form.html", tag=None)

@bp.route("/tags/<int:tid>/edit", methods=["GET", "POST"])
def tag_edit(tid: int):
    svc = current_service()
    t = svc.repo.get_tag(tid)
    if not t:
        flash("Tag not found", "danger")
        return redirect(url_for("main.tags"))
    if request.method == "POST":
        try:
            svc.update_tag(tid, request.form.get("name", ""))
            flash("Updated", "success")
            return redirect(url_for("main.tags"))
        except ValidationError as e:
            flash(str(e), "danger")
    return render_template("tag_form.html", tag=t)

@bp.route("/tags/<int:tid>/delete", methods=["POST"])
def tag_delete(tid: int):
    svc = current_service()
    svc.delete_tag(tid)
    flash("Deleted", "info")
    return redirect(url_for("main.tags"))

# -----------------------
# Animes
# -----------------------
@bp.route("/animes")
def animes():
    svc = current_service()
    q = request.args.get("q")
    tag = request.args.get("tag")  # tag id
    studio = request.args.get("studio")
    order = request.args.get("order", "title")
    tag_id = int(tag) if tag and tag.isdigit() else None
    studio_id = int(studio) if studio and studio.isdigit() else None
    animes = svc.list_animes(q=q, order_by=order, tag_id=tag_id, studio_id=studio_id)
    studios = svc.list_studios()
    tags = svc.list_tags()
    studios_map = {s.id: s.name for s in studios}
    return render_template("anime_list.html", animes=animes, studios_map=studios_map, tags=tags, selected_tag=tag_id, selected_studio=studio_id, selected_order=order)


@bp.route("/animes/new", methods=["GET", "POST"])
def anime_new():
    svc = current_service()
    tags = svc.list_tags()
    studios = svc.list_studios()
    if request.method == "POST":
        try:
            total_raw = request.form.get("total_episodes", "").strip()
            total = int(total_raw) if total_raw != "" else None
            studio_raw = request.form.get("studio", "")
            studio = int(studio_raw) if studio_raw else None
            anime = svc.create_anime(request.form.get("title", ""), total, studio)
            tag_ids = request.form.getlist("tag_ids")
            if tag_ids:
                svc.repo.set_anime_tags(anime.id, [int(x) for x in tag_ids])
            flash("Anime created", "success")
            return redirect(url_for("main.animes"))
        except (ValidationError, ValueError) as e:
            flash(str(e), "danger")
    return render_template("anime_form.html", anime=None, tags=tags, studios=studios, selected_tags=[])

@bp.route("/animes/<int:aid>/edit", methods=["GET", "POST"])
def anime_edit(aid: int):
    svc = current_service()
    try:
        a = svc.get_anime(aid)
    except NotFoundError:
        flash("Anime not found", "danger")
        return redirect(url_for("main.animes"))
    tags = svc.list_tags()
    studios = svc.list_studios()
    selected_tags = [t.id for t in svc.repo.get_anime_tags(aid)]
    if request.method == "POST":
        try:
            total_raw = request.form.get("total_episodes", "").strip()
            total = int(total_raw) if total_raw != "" else None
            studio_raw = request.form.get("studio", "")
            studio = int(studio_raw) if studio_raw else None
            tag_ids = [int(x) for x in request.form.getlist("tag_ids")]
            svc.update_anime(aid, request.form.get("title", ""), total, studio, tag_ids)
            flash("Anime updated", "success")
            return redirect(url_for("main.animes"))
        except (ValidationError, ValueError) as e:
            flash(str(e), "danger")
    return render_template("anime_form.html", anime=a, tags=tags, studios=studios, selected_tags=selected_tags)

@bp.route("/animes/<int:aid>/delete", methods=["POST"])
def anime_delete(aid: int):
    svc = current_service()
    force = request.form.get("force", "") == "1"
    try:
        svc.delete_anime(aid, force=force)
        flash("Deleted anime", "info")
    except ValidationError as e:
        flash(str(e), "danger")
    return redirect(url_for("main.animes"))

# -----------------------
# Watchlist (watches)
# -----------------------
@bp.route("/users/<int:uid>/watchlist")
def watchlist(uid: int):
    svc = current_service()
    status = request.args.get("status")
    min_score_raw = request.args.get("min_score")
    order = request.args.get("order", "updated_at")
    min_score = int(min_score_raw) if min_score_raw and min_score_raw.isdigit() else None
    u = svc.get_user(uid)  # raises NotFoundError if missing
    watches = svc.list_user_watchlist(uid, status=status, min_score=min_score, order_by=order)
    items = []
    for w in watches:
        a = svc.repo.get_anime(w.anime_id)
        items.append((w, a))
    return render_template("watch_list.html", user=u, items=items, selected_status=status, selected_min_score=min_score, selected_order=order)

@bp.route("/users/<int:uid>/watch/new", methods=["GET", "POST"])
def watch_new(uid: int):
    svc = current_service()
    user = svc.get_user(uid)
    animes = svc.list_animes()
    if request.method == "POST":
        try:
            anime_id = int(request.form.get("anime_id"))
            eps = int(request.form.get("episodes_watched") or 0)
            svc.add_watch_entry(uid, anime_id, eps)
            flash("Added to watchlist", "success")
            return redirect(url_for("main.watchlist", uid=uid))
        except (ValidationError, ValueError, NotFoundError) as e:
            flash(str(e), "danger")
    return render_template("watch_form.html", user=user, animes=animes, watch=None)

@bp.route("/watches/<int:wid>/edit", methods=["GET", "POST"])
def watch_edit(wid: int):
    svc = current_service()
    w = svc.repo.get_watch(wid)
    if not w:
        flash("watch entry not found", "danger")
        return redirect(url_for("main.index"))
    if request.method == "POST":
        if "episodes_watched" in request.form:
            try:
                eps = int(request.form.get("episodes_watched", "0"))
                svc.update_watch_episodes(wid, eps)
                flash("Updated episodes", "success")
                return redirect(url_for("main.watchlist", uid=w.user_id))
            except (ValidationError, ValueError) as e:
                flash(str(e), "danger")
        elif "score" in request.form:
            try:
                sc = request.form.get("score")
                sc = int(sc) if sc != "" else None
                svc.update_watch_score(wid, sc)
                flash("Score updated", "success")
                return redirect(url_for("main.watchlist", uid=w.user_id))
            except (ValidationError, ValueError) as e:
                flash(str(e), "danger")
    anime = svc.repo.get_anime(w.anime_id)
    return render_template("watch_form.html", user=svc.repo.get_user(w.user_id), animes=[anime], watch=w)

@bp.route("/watches/<int:wid>/delete", methods=["POST"])
def watch_delete(wid: int):
    svc = current_service()
    svc.delete_watch(wid)
    flash("Watch deleted", "info")
    # redirect back to referring user's watchlist if possible
    # safe fallback to index
    return redirect(request.referrer or url_for("main.index"))

# -----------------------
# Import / Export endpoints
# -----------------------
@bp.route("/users/<int:uid>/watchlist/export")
def export_watchlist(uid: int):
    svc = current_service()
    fmt = request.args.get("format", "csv").lower()
    rows = svc.export_watchlist(uid)
    if fmt == "json":
        return Response(json.dumps(rows, ensure_ascii=False), mimetype="application/json")
    # CSV
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["anime_id", "anime_title", "episodes_watched", "score", "status", "updated_at"])
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    csv_bytes = output.getvalue().encode("utf-8")
    return Response(csv_bytes, mimetype="text/csv", headers={"Content-Disposition": f"attachment; filename=watchlist_{uid}.csv"})

@bp.route("/users/<int:uid>/watchlist/import", methods=["GET", "POST"])
def import_watchlist(uid: int):
    svc = current_service()
    if request.method == "POST":
        file = request.files.get("file")
        if not file:
            flash("No file uploaded", "danger")
            return redirect(url_for("main.watchlist", uid=uid))
        filename = file.filename or ""
        content = file.read()
        rows = []
        try:
            text = content.decode("utf-8")
            if filename.lower().endswith(".json") or text.lstrip().startswith(("[","{")):
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    rows = parsed
                else:
                    flash("JSON must be a list of objects", "danger")
                    return redirect(url_for("main.watchlist", uid=uid))
            else:
                text_io = io.StringIO(text)
                reader = csv.DictReader(text_io)
                for r in reader:
                    rows.append(r)
        except Exception as e:
            logger.exception("Failed to parse uploaded file")
            flash(f"Failed to parse file: {e}", "danger")
            return redirect(url_for("main.watchlist", uid=uid))

        created, errors = svc.import_watchlist_from_rows(uid, rows)
        flash(f"Imported: created={created}, errors={len(errors)}", "info")
        return redirect(url_for("main.watchlist", uid=uid))
    # GET: show upload UI
    u = current_service().get_user(uid)
    return render_template("watch_import.html", user=u)

