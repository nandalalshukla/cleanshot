from __future__ import annotations

import csv
import io
import time
import zipfile

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from cleanshot_worker.jobs.models import BatchStatus, ImageStatus
from cleanshot_worker.main import create_app

from .fakes import product_photo, to_bytes

HEADERS = {"X-Client-Id": "phone-a"}


def wait_for(client, batch_id, *, until=lambda b: b["status"] == "completed", timeout=15.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/v1/batches/{batch_id}", headers=HEADERS).json()
        if until(body):
            return body
        time.sleep(0.05)
    raise AssertionError(f"batch did not settle: {body}")


def create(client, **options):
    res = client.post("/v1/batches", json={"name": "Kurtis", "options": options}, headers=HEADERS)
    assert res.status_code == 201, res.text
    return res.json()


def upload(client, batch_id, *photos):
    files = [("files", (f"p{i}.jpg", to_bytes(p), "image/jpeg")) for i, p in enumerate(photos)]
    return client.post(f"/v1/batches/{batch_id}/images", files=files, headers=HEADERS)


def test_full_batch_flow_produces_zip(client):
    batch = create(client, presets=["amazon", "instagram_portrait"])
    assert batch["status"] == "draft"

    res = upload(client, batch["id"], product_photo(), product_photo(color=(20, 120, 40)))
    assert res.status_code == 201
    assert [i["status"] for i in res.json()] == ["uploaded", "uploaded"]

    res = client.post(f"/v1/batches/{batch['id']}/start", headers=HEADERS)
    assert res.status_code == 200
    done = wait_for(client, batch["id"])
    assert done["progress"] == 1.0
    assert done["counts"]["done"] == 2
    img = done["images"][0]
    assert [o["preset"] for o in img["outputs"]] == ["amazon", "instagram_portrait"]

    preview = client.get(img["preview_url"], headers=HEADERS)
    assert preview.status_code == 200 and preview.headers["content-type"] == "image/jpeg"
    output = client.get(img["outputs"][1]["url"], headers=HEADERS)
    assert Image.open(io.BytesIO(output.content)).size == (1080, 1350)
    cutout = client.get(img["cutout_url"], headers=HEADERS)
    assert Image.open(io.BytesIO(cutout.content)).mode == "RGBA"

    z = client.get(done["download_url"], headers=HEADERS)
    assert z.status_code == 200 and z.headers["content-type"] == "application/zip"
    names = zipfile.ZipFile(io.BytesIO(z.content)).namelist()
    assert sorted(names) == sorted(
        [
            "amazon_2000x2000/p0.jpg",
            "amazon_2000x2000/p1.jpg",
            "instagram_portrait_1080x1350/p0.jpg",
            "instagram_portrait_1080x1350/p1.jpg",
            "report.csv",
        ]
    )


def test_failed_photo_is_reported_and_retryable(client):
    batch = create(client, presets=["meesho"])
    blank = Image.new("RGB", (300, 300), (240, 240, 240))
    upload(client, batch["id"], product_photo(), blank)
    client.post(f"/v1/batches/{batch['id']}/start", headers=HEADERS)
    done = wait_for(client, batch["id"])
    assert done["counts"] == {**done["counts"], "done": 1, "failed": 1}
    failed = next(i for i in done["images"] if i["status"] == "failed")
    assert "No product" in failed["error"]

    z = client.get(done["download_url"], headers=HEADERS)
    report = zipfile.ZipFile(io.BytesIO(z.content)).read("report.csv").decode()
    rows = list(csv.DictReader(io.StringIO(report)))
    assert {r["status"] for r in rows} == {"done", "failed"}

    # Retake: replace the bad photo with a good one; it re-processes automatically.
    res = client.put(
        f"/v1/batches/{batch['id']}/images/{failed['id']}",
        files={"file": ("retake.jpg", to_bytes(product_photo()), "image/jpeg")},
        headers=HEADERS,
    )
    assert res.status_code == 200 and res.json()["status"] == "queued"
    done = wait_for(
        client, batch["id"], until=lambda b: b["counts"]["done"] == 2 and b["status"] == "completed"
    )
    assert done["status"] == "completed"
    assert done["images"][1]["filename"] == "retake.jpg"


def test_retry_failed(client):
    batch = create(client)
    upload(client, batch["id"], Image.new("RGB", (100, 100), "white"))
    client.post(f"/v1/batches/{batch['id']}/start", headers=HEADERS)
    wait_for(client, batch["id"])
    res = client.post(f"/v1/batches/{batch['id']}/retry", headers=HEADERS)
    assert res.status_code == 200
    done = wait_for(client, batch["id"])
    assert done["images"][0]["attempts"] == 2


def test_uploads_rejected_after_start_and_for_bad_files(client):
    batch = create(client)
    bad = client.post(
        f"/v1/batches/{batch['id']}/images",
        files=[("files", ("x.jpg", b"nope", "image/jpeg"))],
        headers=HEADERS,
    )
    assert bad.status_code == 415
    assert client.post(f"/v1/batches/{batch['id']}/start", headers=HEADERS).status_code == 409

    upload(client, batch["id"], product_photo())
    client.post(f"/v1/batches/{batch['id']}/start", headers=HEADERS)
    assert upload(client, batch["id"], product_photo()).status_code == 409


def test_batch_size_limit(settings, registry):
    settings.max_images_per_batch = 1
    with TestClient(create_app(settings, registry)) as client:
        batch = create(client)
        assert upload(client, batch["id"], product_photo()).status_code == 201
        assert upload(client, batch["id"], product_photo()).status_code == 413


def test_download_before_anything_finished(client):
    batch = create(client)
    assert client.get(batch["download_url"], headers=HEADERS).status_code == 409


def test_batches_are_scoped_per_client(client):
    batch = create(client)
    other = {"X-Client-Id": "phone-b"}
    assert client.get(f"/v1/batches/{batch['id']}", headers=other).status_code == 404
    assert client.get("/v1/batches", headers=other).json() == []
    listed = client.get("/v1/batches", headers=HEADERS).json()
    assert [b["id"] for b in listed] == [batch["id"]]


def test_cancel_and_delete(client, settings):
    batch = create(client)
    upload(client, batch["id"], product_photo())
    res = client.post(f"/v1/batches/{batch['id']}/cancel", headers=HEADERS)
    assert res.json()["status"] == "cancelled"
    assert res.json()["images"][0]["status"] == "cancelled"

    assert client.delete(f"/v1/batches/{batch['id']}", headers=HEADERS).status_code == 204
    assert client.get(f"/v1/batches/{batch['id']}", headers=HEADERS).status_code == 404
    assert not (settings.batches_dir / batch["id"]).exists()


def test_delete_single_image(client):
    batch = create(client)
    img = upload(client, batch["id"], product_photo(), product_photo()).json()[0]
    res = client.delete(f"/v1/batches/{batch['id']}/images/{img['id']}", headers=HEADERS)
    assert res.status_code == 204
    assert client.get(f"/v1/batches/{batch['id']}", headers=HEADERS).json()["total"] == 1


@pytest.mark.parametrize("path", ["original", "preview", "cutout", "outputs/amazon"])
def test_unknown_image_404(client, path):
    batch = create(client)
    res = client.get(f"/v1/batches/{batch['id']}/images/nope/{path}", headers=HEADERS)
    assert res.status_code == 404


def test_restart_requeues_unfinished_work(settings, registry):
    from fastapi.testclient import TestClient

    from cleanshot_worker.main import create_app

    app = create_app(settings, registry)
    svc = app.state.batches
    batch = svc.create(
        None,
        __import__(
            "cleanshot_worker.pipeline.options", fromlist=["ProcessOptions"]
        ).ProcessOptions(),
        "phone-a",
    )
    img = svc.add_image(batch.id, "a.jpg", to_bytes(product_photo()))
    # Simulate a crash mid-processing.
    svc.store.set_batch_status(batch.id, BatchStatus.PROCESSING)
    svc.store.update_image(img.id, status=ImageStatus.PROCESSING)

    with TestClient(create_app(settings, registry)) as c:
        done = wait_for(c, batch.id)
    assert done["images"][0]["status"] == "done"


def test_explicit_positions_preserve_client_order(client):
    batch = create(client)
    for pos, name in [(2, "c.jpg"), (0, "a.jpg"), (1, "b.jpg")]:
        client.post(
            f"/v1/batches/{batch['id']}/images",
            files=[("files", (name, to_bytes(product_photo()), "image/jpeg"))],
            data={"position": str(pos)},
            headers=HEADERS,
        )
    images = client.get(f"/v1/batches/{batch['id']}", headers=HEADERS).json()["images"]
    assert [i["filename"] for i in images] == ["a.jpg", "b.jpg", "c.jpg"]


def test_quality_report_is_exposed_per_image_and_counted(client):
    batch = create(client, presets=["meesho"])
    tiny = product_photo(size=(1600, 1200), box=(780, 580, 830, 640))
    upload(client, batch["id"], product_photo(size=(1600, 1200), box=(400, 250, 1200, 1000)), tiny)
    client.post(f"/v1/batches/{batch['id']}/start", headers=HEADERS)
    done = wait_for(client, batch["id"])
    good, bad = done["images"]
    assert good["quality"]["verdict"] == "ok"
    assert bad["quality"]["verdict"] == "retake"
    assert "product_too_small" in {f["code"] for f in bad["quality"]["flags"]}
    assert done["needs_retake"] == 1 and done["warnings"] == 0

    report = (
        zipfile.ZipFile(io.BytesIO(client.get(done["download_url"], headers=HEADERS).content))
        .read("report.csv")
        .decode()
    )
    assert "product_too_small" in report


def test_failed_no_product_carries_retake_verdict(client):
    batch = create(client)
    upload(client, batch["id"], Image.new("RGB", (300, 300), (240, 240, 240)))
    client.post(f"/v1/batches/{batch['id']}/start", headers=HEADERS)
    img = wait_for(client, batch["id"])["images"][0]
    assert img["status"] == "failed"
    assert img["quality"]["verdict"] == "retake"
