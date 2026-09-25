import logging
import os
import secrets
import time
from collections import defaultdict
from pathlib import Path

import azure.functions as func
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings

from analysis import analyze
from report import render

MAX_BYTES = 1_000_000
UPLOADS_PER_MINUTE = 10
UPLOAD_PAGE = (Path(__file__).parent / "upload.html").read_text()

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)
blobs = BlobServiceClient(os.environ["STORAGE_URL"], credential=DefaultAzureCredential())
recent_uploads = defaultdict(list)


def rate_limited(ip):
    now = time.time()
    recent_uploads[ip] = [t for t in recent_uploads[ip] if now - t < 60]
    recent_uploads[ip].append(now)
    return len(recent_uploads[ip]) > UPLOADS_PER_MINUTE


def html(body, status=200):
    return func.HttpResponse(body, status_code=status, mimetype="text/html")


@app.route(route="", methods=["GET"])
def home(req: func.HttpRequest) -> func.HttpResponse:
    return html(UPLOAD_PAGE)


@app.route(route="upload", methods=["POST"])
def upload(req: func.HttpRequest) -> func.HttpResponse:
    ip = req.headers.get("x-forwarded-for", "unknown").split(",")[0].split(":")[0]
    if rate_limited(ip):
        return html("<p>Too many uploads. Try again in a minute.</p>", 429)

    file = req.files.get("file")
    if not file or not file.filename.lower().endswith(".csv"):
        return html("<p>Please choose a .csv file.</p>", 400)
    data = file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        return html("<p>File is over 1 MB.</p>", 413)

    started = time.perf_counter()
    try:
        result = analyze(data.decode("utf-8-sig", errors="replace"))
    except ValueError as e:
        logging.warning("analysis rejected: %s", type(e).__name__)
        return html("<p>Couldn't read that file: it doesn't look like a bank CSV export.</p><p><a href='/'>Try again</a></p>", 400)

    report_id = secrets.token_urlsafe(16)
    blobs.get_blob_client("uploads", f"{report_id}.csv").upload_blob(data)
    blobs.get_blob_client("reports", f"{report_id}.html").upload_blob(
        render(result), content_settings=ContentSettings(content_type="text/html"))

    logging.info("analysis done rows=%d ms=%d format=%s", result["rows"],
                 (time.perf_counter() - started) * 1000, result["format"])
    return func.HttpResponse(status_code=303, headers={"Location": f"/r/{report_id}"})


@app.route(route="r/{report_id}", methods=["GET"])
def view_report(req: func.HttpRequest) -> func.HttpResponse:
    report_id = req.route_params["report_id"]
    try:
        body = blobs.get_blob_client("reports", f"{report_id}.html").download_blob().readall()
    except ResourceNotFoundError:
        return html("<p>Report not found. Reports are deleted after 7 days.</p>", 404)
    return html(body)
