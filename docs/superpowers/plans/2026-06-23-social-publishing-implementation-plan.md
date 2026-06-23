# Social Publishing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the Xiaohongshu, Douyin, and Moments content publishing workflow with manual publishing, adapter-based publishing placeholders, image-generation placeholders, status tracking, and tests.

**Architecture:** Extend the existing `ContentItem` model instead of adding a media table. Add focused `content_engine.assets` and `content_engine.publishing` modules so real image-generation and platform publishing APIs can be plugged in later without changing Web routes. Keep external publishing disabled by default and preserve a safe semi-manual workflow.

**Tech Stack:** Python 3.11, FastAPI, Jinja2, SQLAlchemy, SQLite, pytest.

---

## File Structure

- Modify: `app/models.py`
  - Add publishing and asset tracking fields to `ContentItem`.
- Modify: `app/database.py`
  - Add SQLite-compatible `ALTER TABLE` guards for new `content_items` columns.
- Create: `content_engine/assets.py`
  - Own image-generation request/result types and placeholder adapter.
- Create: `content_engine/publishing.py`
  - Own publishing request/result types, platform adapter selection, manual/disabled/mock adapters, and status helpers.
- Modify: `content_engine/calendar.py`
  - Include new status fields in calendar dictionaries.
- Modify: `web/app.py`
  - Add routes for preparing assets, adapter publishing, manual publish marking, and interaction backfill.
- Modify: `web/templates/content_calendar.html`
  - Render status, asset controls, publishing controls, external links, errors, and interaction backfill.
- Create: `tests/test_content_engine/test_assets.py`
  - Unit tests for image-generation placeholders.
- Create: `tests/test_content_engine/test_publishing.py`
  - Unit tests for publisher adapters and item status updates.
- Modify: `tests/test_content_engine/test_calendar.py`
  - Cover new calendar fields.
- Modify: `tests/test_web/test_operations.py`
  - Cover content workflow routes.
- Modify: `docs/superpowers/specs/2026-06-23-social-publishing-design.md`
  - Mark implementation status after completion.

## Implementation Notes

- Platform codes must remain the existing values used by templates: `moments`, `xiaohongshu`, `douyin`.
- Real external posting remains disabled unless a future adapter explicitly enables it.
- Image generation must not call an external service in this plan.
- `interaction_data` remains JSON text with keys `likes`, `comments`, `shares`, and `consultations`.
- All new routes redirect back to `/content/calendar`.

---

### Task 1: Extend `ContentItem` Persistence

**Files:**
- Modify: `app/models.py`
- Modify: `app/database.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing model test**

Add this test to `tests/test_models.py`:

```python
def test_content_item_tracks_assets_and_platform_publish_state(db_session, sample_records):
    from datetime import date
    from app.models import ContentItem

    item = ContentItem(
        store_id=sample_records["store"].id,
        channel="xiaohongshu",
        topic="洗护复购",
        title="奶茶洗护日记",
        body="今天适合提醒客户复购洗护。",
        hashtags="宠物洗护,宠物店",
        image_prompt="一只干净的泰迪在宠物店前台",
        scheduled_date=date.today(),
        publish_mode="manual",
        external_url="https://www.xiaohongshu.com/explore/demo",
        external_post_id="xhs-demo-id",
        publish_error="",
        asset_status="placeholder_ready",
        asset_url="",
        asset_error="",
        status="asset_ready",
    )
    db_session.add(item)
    db_session.commit()

    saved = db_session.get(ContentItem, item.id)
    assert saved.publish_mode == "manual"
    assert saved.external_post_id == "xhs-demo-id"
    assert saved.external_url.endswith("/demo")
    assert saved.publish_error == ""
    assert saved.asset_status == "placeholder_ready"
    assert saved.asset_url == ""
    assert saved.asset_error == ""
```

- [ ] **Step 2: Run the test to verify RED**

Run:

```bash
uv run pytest tests/test_models.py::test_content_item_tracks_assets_and_platform_publish_state -q
```

Expected: FAIL with a `TypeError` or mapped-column error because the new `ContentItem` fields do not exist.

- [ ] **Step 3: Add model fields**

In `app/models.py`, extend `ContentItem` after `published_at`:

```python
    publish_mode: Mapped[str] = mapped_column(String(40), default="manual")
    external_url: Mapped[str | None] = mapped_column(String(500))
    external_post_id: Mapped[str | None] = mapped_column(String(160))
    publish_error: Mapped[str | None] = mapped_column(Text)
    asset_status: Mapped[str] = mapped_column(String(40), default="not_requested")
    asset_url: Mapped[str | None] = mapped_column(String(500))
    asset_error: Mapped[str | None] = mapped_column(Text)
```

- [ ] **Step 4: Add SQLite migration guard**

In `app/database.py`, add these columns to the existing `content_items` migration section or create one if absent:

```python
def _ensure_content_item_publish_columns(connection):
    columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(content_items)").fetchall()}
    additions = {
        "publish_mode": "VARCHAR(40) DEFAULT 'manual'",
        "external_url": "VARCHAR(500)",
        "external_post_id": "VARCHAR(160)",
        "publish_error": "TEXT",
        "asset_status": "VARCHAR(40) DEFAULT 'not_requested'",
        "asset_url": "VARCHAR(500)",
        "asset_error": "TEXT",
    }
    for column, ddl in additions.items():
        if column not in columns:
            connection.exec_driver_sql(f"ALTER TABLE content_items ADD COLUMN {column} {ddl}")
```

Call it from the database initialization path after base metadata creation:

```python
with engine.begin() as connection:
    _ensure_content_item_publish_columns(connection)
```

- [ ] **Step 5: Run the model test to verify GREEN**

Run:

```bash
uv run pytest tests/test_models.py::test_content_item_tracks_assets_and_platform_publish_state -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/models.py app/database.py tests/test_models.py
git commit -m "feat: track content publishing assets"
```

---

### Task 2: Add Image Generation Placeholder Boundary

**Files:**
- Create: `content_engine/assets.py`
- Create: `tests/test_content_engine/test_assets.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_content_engine/test_assets.py`:

```python
from content_engine.assets import ImageGenerationRequest, PlaceholderImageGenerator, prepare_content_asset
from app.models import ContentItem, Store


def test_placeholder_image_generator_returns_prompt_only_result():
    generator = PlaceholderImageGenerator()
    request = ImageGenerationRequest(
        content_id=12,
        channel="xiaohongshu",
        title="洗护前后对比",
        prompt="明亮宠物店里一只蓬松小狗",
    )

    result = generator.generate(request)

    assert result.status == "placeholder_ready"
    assert result.asset_url == ""
    assert result.error == ""
    assert "明亮宠物店" in result.prompt


def test_prepare_content_asset_updates_item_with_placeholder(db_session):
    store = Store(name="豆豆宠物")
    db_session.add(store)
    db_session.commit()
    item = ContentItem(
        store_id=store.id,
        channel="douyin",
        topic="洗护过程",
        title="洗护过程短视频脚本",
        body="三段式洗护过程。",
        image_prompt="宠物洗护过程分镜",
        status="draft",
    )
    db_session.add(item)
    db_session.commit()

    result = prepare_content_asset(db_session, item.id, PlaceholderImageGenerator())

    assert result.status == "placeholder_ready"
    assert item.asset_status == "placeholder_ready"
    assert item.asset_error == ""
    assert item.status == "asset_ready"
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
uv run pytest tests/test_content_engine/test_assets.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'content_engine.assets'`.

- [ ] **Step 3: Implement `content_engine/assets.py`**

Create `content_engine/assets.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.models import ContentItem


@dataclass(frozen=True)
class ImageGenerationRequest:
    content_id: int
    channel: str
    title: str
    prompt: str


@dataclass(frozen=True)
class ImageGenerationResult:
    status: str
    prompt: str
    asset_url: str = ""
    error: str = ""


class ImageGenerator(Protocol):
    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        ...


class PlaceholderImageGenerator:
    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        return ImageGenerationResult(
            status="placeholder_ready",
            prompt=request.prompt,
            asset_url="",
            error="",
        )


def prepare_content_asset(session, content_id: int, generator: ImageGenerator | None = None) -> ImageGenerationResult:
    item = session.get(ContentItem, content_id)
    if item is None:
        raise ValueError("content_item_not_found")
    active_generator = generator or PlaceholderImageGenerator()
    request = ImageGenerationRequest(
        content_id=item.id,
        channel=item.channel,
        title=item.title,
        prompt=item.image_prompt or item.title,
    )
    result = active_generator.generate(request)
    item.asset_status = result.status
    item.asset_url = result.asset_url
    item.asset_error = result.error
    if result.status in {"placeholder_ready", "ready"} and item.status == "draft":
        item.status = "asset_ready"
    elif result.status == "failed":
        item.status = "failed"
    session.commit()
    return result
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
uv run pytest tests/test_content_engine/test_assets.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add content_engine/assets.py tests/test_content_engine/test_assets.py
git commit -m "feat: add content asset generation placeholder"
```

---

### Task 3: Add Publisher Adapter Boundary

**Files:**
- Create: `content_engine/publishing.py`
- Create: `tests/test_content_engine/test_publishing.py`

- [ ] **Step 1: Write failing publishing tests**

Create `tests/test_content_engine/test_publishing.py`:

```python
from app.models import ContentItem, Store
from content_engine.publishing import (
    DisabledPublisher,
    ManualPublisher,
    MockPublisher,
    PublishRequest,
    mark_manual_publish,
    publish_content_item,
)


def _content_item(db_session, channel="xiaohongshu"):
    store = Store(name="豆豆宠物")
    db_session.add(store)
    db_session.commit()
    item = ContentItem(
        store_id=store.id,
        channel=channel,
        topic="洗护复购",
        title="洗护复购提醒",
        body="今天适合提醒老客回来洗护。",
        hashtags="宠物店,洗护",
        image_prompt="宠物店门口的小狗",
        asset_status="placeholder_ready",
        status="asset_ready",
    )
    db_session.add(item)
    db_session.commit()
    return item


def test_disabled_publisher_returns_visible_error():
    result = DisabledPublisher("xiaohongshu").publish(
        PublishRequest(
            content_id=1,
            channel="xiaohongshu",
            title="标题",
            body="正文",
            hashtags=["宠物店"],
            asset_url="",
        )
    )

    assert result.success is False
    assert result.status == "failed"
    assert "未配置" in result.error


def test_mock_publisher_returns_external_ids():
    result = MockPublisher().publish(
        PublishRequest(
            content_id=7,
            channel="douyin",
            title="标题",
            body="正文",
            hashtags=["宠物店"],
            asset_url="",
        )
    )

    assert result.success is True
    assert result.status == "published"
    assert result.external_post_id == "mock-douyin-7"
    assert result.external_url.endswith("/mock-douyin-7")


def test_publish_content_item_records_disabled_failure(db_session):
    item = _content_item(db_session, "xiaohongshu")

    result = publish_content_item(db_session, item.id, DisabledPublisher("xiaohongshu"))

    assert result.success is False
    assert item.status == "failed"
    assert item.publish_mode == "adapter"
    assert "未配置" in item.publish_error


def test_mark_manual_publish_records_external_link(db_session):
    item = _content_item(db_session, "moments")

    mark_manual_publish(db_session, item.id, "https://example.com/post/1")

    assert item.status == "published"
    assert item.publish_mode == "manual"
    assert item.external_url == "https://example.com/post/1"
    assert item.publish_error == ""
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
uv run pytest tests/test_content_engine/test_publishing.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'content_engine.publishing'`.

- [ ] **Step 3: Implement `content_engine/publishing.py`**

Create `content_engine/publishing.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.models import ContentItem


@dataclass(frozen=True)
class PublishRequest:
    content_id: int
    channel: str
    title: str
    body: str
    hashtags: list[str]
    asset_url: str


@dataclass(frozen=True)
class PublishResult:
    success: bool
    status: str
    external_post_id: str = ""
    external_url: str = ""
    error: str = ""
    raw_response: dict | None = None


class PublisherAdapter(Protocol):
    def publish(self, request: PublishRequest) -> PublishResult:
        ...


class DisabledPublisher:
    def __init__(self, channel: str):
        self.channel = channel

    def publish(self, request: PublishRequest) -> PublishResult:
        return PublishResult(
            success=False,
            status="failed",
            error=f"{self.channel} 真实发布未配置，请先人工发布或接入平台适配器",
        )


class ManualPublisher:
    def publish(self, request: PublishRequest) -> PublishResult:
        return PublishResult(success=False, status="manual_required", error="请复制内容并人工发布")


class MockPublisher:
    def publish(self, request: PublishRequest) -> PublishResult:
        post_id = f"mock-{request.channel}-{request.content_id}"
        return PublishResult(
            success=True,
            status="published",
            external_post_id=post_id,
            external_url=f"https://example.com/{request.channel}/{post_id}",
            raw_response={"mock": True},
        )


def hashtags_from_text(value: str | None) -> list[str]:
    return [part.strip().lstrip("#") for part in (value or "").split(",") if part.strip()]


def build_publish_request(item: ContentItem) -> PublishRequest:
    return PublishRequest(
        content_id=item.id,
        channel=item.channel,
        title=item.title,
        body=item.body,
        hashtags=hashtags_from_text(item.hashtags),
        asset_url=item.asset_url or "",
    )


def publish_content_item(session, content_id: int, adapter: PublisherAdapter) -> PublishResult:
    item = session.get(ContentItem, content_id)
    if item is None:
        raise ValueError("content_item_not_found")
    result = adapter.publish(build_publish_request(item))
    item.publish_mode = "adapter"
    item.publish_error = result.error
    if result.success:
        item.status = "published"
        item.external_post_id = result.external_post_id
        item.external_url = result.external_url
        item.published_at = datetime.utcnow()
    else:
        item.status = "failed"
    session.commit()
    return result


def mark_manual_publish(session, content_id: int, external_url: str = "") -> ContentItem:
    item = session.get(ContentItem, content_id)
    if item is None:
        raise ValueError("content_item_not_found")
    item.publish_mode = "manual"
    item.status = "published"
    item.external_url = external_url.strip()
    item.publish_error = ""
    item.published_at = datetime.utcnow()
    session.commit()
    return item


def update_interactions(session, content_id: int, likes: int, comments: int, shares: int, consultations: int) -> ContentItem:
    item = session.get(ContentItem, content_id)
    if item is None:
        raise ValueError("content_item_not_found")
    item.interaction_data = json.dumps(
        {
            "likes": max(likes, 0),
            "comments": max(comments, 0),
            "shares": max(shares, 0),
            "consultations": max(consultations, 0),
        },
        ensure_ascii=False,
    )
    session.commit()
    return item
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
uv run pytest tests/test_content_engine/test_publishing.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add content_engine/publishing.py tests/test_content_engine/test_publishing.py
git commit -m "feat: add content publisher adapters"
```

---

### Task 4: Expose New Fields In Content Calendar

**Files:**
- Modify: `content_engine/calendar.py`
- Modify: `tests/test_content_engine/test_calendar.py`

- [ ] **Step 1: Write failing calendar test**

Append this test to `tests/test_content_engine/test_calendar.py`:

```python
def test_content_calendar_includes_asset_and_publish_metadata(db_session):
    from datetime import date
    from app.models import ContentItem, Store
    from content_engine.calendar import build_content_calendar

    store = Store(name="豆豆宠物")
    db_session.add(store)
    db_session.commit()
    item = ContentItem(
        store_id=store.id,
        channel="xiaohongshu",
        topic="洗护复购",
        title="洗护复购提醒",
        body="正文",
        hashtags="宠物店,洗护",
        image_prompt="宠物店门口的小狗",
        scheduled_date=date.today(),
        status="failed",
        publish_mode="adapter",
        publish_error="xiaohongshu 真实发布未配置",
        external_url="",
        asset_status="placeholder_ready",
        asset_url="",
    )
    db_session.add(item)
    db_session.commit()

    rows = build_content_calendar(db_session, store.id)

    row = rows[0]
    assert row["asset_status"] == "placeholder_ready"
    assert row["publish_mode"] == "adapter"
    assert row["publish_error"] == "xiaohongshu 真实发布未配置"
    assert row["external_url"] == ""
```

- [ ] **Step 2: Run the test to verify RED**

Run:

```bash
uv run pytest tests/test_content_engine/test_calendar.py::test_content_calendar_includes_asset_and_publish_metadata -q
```

Expected: FAIL with `KeyError: 'asset_status'`.

- [ ] **Step 3: Update calendar output**

In `content_engine/calendar.py`, include these keys for each content item:

```python
{
    "id": item.id,
    "date": item.scheduled_date.isoformat() if item.scheduled_date else "",
    "channel": item.channel,
    "template_code": item.topic,
    "title": item.title,
    "body": item.body,
    "hashtags": item.hashtags or "",
    "image_prompt": item.image_prompt or "",
    "status": item.status,
    "asset_status": item.asset_status or "not_requested",
    "asset_url": item.asset_url or "",
    "asset_error": item.asset_error or "",
    "publish_mode": item.publish_mode or "manual",
    "external_url": item.external_url or "",
    "external_post_id": item.external_post_id or "",
    "publish_error": item.publish_error or "",
    "interaction_data": item.interaction_data or "",
}
```

- [ ] **Step 4: Run test to verify GREEN**

Run:

```bash
uv run pytest tests/test_content_engine/test_calendar.py::test_content_calendar_includes_asset_and_publish_metadata -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add content_engine/calendar.py tests/test_content_engine/test_calendar.py
git commit -m "feat: expose publishing metadata in content calendar"
```

---

### Task 5: Add Web Routes For Assets, Publishing, And Interactions

**Files:**
- Modify: `web/app.py`
- Modify: `tests/test_web/test_operations.py`

- [ ] **Step 1: Write failing Web route test**

Add this test to `tests/test_web/test_operations.py`:

```python
def test_content_calendar_asset_publish_and_interaction_actions(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'content_publish.db'}")
    monkeypatch.setenv("AIPET_AUTH_ENABLED", "false")
    monkeypatch.setenv("AIPET_REQUIRE_LICENSE", "false")

    from app.database import SessionLocal, init_db
    from app.models import ContentItem, Store
    from fastapi.testclient import TestClient
    from web.app import create_app

    init_db()
    session = SessionLocal()
    try:
        store = Store(name="豆豆宠物")
        session.add(store)
        session.commit()
        item = ContentItem(
            store_id=store.id,
            channel="xiaohongshu",
            topic="洗护复购",
            title="洗护复购提醒",
            body="正文",
            hashtags="宠物店,洗护",
            image_prompt="宠物店门口的小狗",
            status="draft",
        )
        session.add(item)
        session.commit()
        content_id = item.id
    finally:
        session.close()

    client = TestClient(create_app())

    assert client.post(f"/content/{content_id}/prepare-asset").status_code == 303
    assert client.post(f"/content/{content_id}/publish-adapter").status_code == 303
    assert client.post(
        f"/content/{content_id}/mark-published",
        data={"external_url": "https://www.xiaohongshu.com/explore/demo"},
    ).status_code == 303
    assert client.post(
        f"/content/{content_id}/interactions",
        data={"likes": "11", "comments": "2", "shares": "1", "consultations": "3"},
    ).status_code == 303

    session = SessionLocal()
    try:
        saved = session.get(ContentItem, content_id)
        assert saved.asset_status == "placeholder_ready"
        assert saved.status == "published"
        assert saved.publish_mode == "manual"
        assert saved.external_url == "https://www.xiaohongshu.com/explore/demo"
        assert '"likes": 11' in saved.interaction_data
        assert '"consultations": 3' in saved.interaction_data
    finally:
        session.close()
```

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
uv run pytest tests/test_web/test_operations.py::test_content_calendar_asset_publish_and_interaction_actions -q
```

Expected: FAIL with 404 for `/content/{content_id}/prepare-asset`.

- [ ] **Step 3: Add imports**

In `web/app.py`, add imports:

```python
from content_engine.assets import prepare_content_asset
from content_engine.publishing import DisabledPublisher, mark_manual_publish, publish_content_item, update_interactions
```

- [ ] **Step 4: Add route handlers**

Inside `create_app`, near the existing content routes, add:

```python
    @app.post("/content/{content_id}/prepare-asset")
    def content_prepare_asset(content_id: int):
        init_db()
        session = SessionLocal()
        try:
            prepare_content_asset(session, content_id)
            return RedirectResponse("/content/calendar", status_code=303)
        finally:
            session.close()

    @app.post("/content/{content_id}/publish-adapter")
    def content_publish_adapter(content_id: int):
        init_db()
        session = SessionLocal()
        try:
            item = session.get(ContentItem, content_id)
            if item is None:
                raise HTTPException(status_code=404, detail="content_item_not_found")
            publish_content_item(session, content_id, DisabledPublisher(item.channel))
            return RedirectResponse("/content/calendar", status_code=303)
        finally:
            session.close()

    @app.post("/content/{content_id}/mark-published")
    async def content_mark_published(content_id: int, request: Request):
        form = await request.form()
        init_db()
        session = SessionLocal()
        try:
            mark_manual_publish(session, content_id, str(form.get("external_url", "")))
            return RedirectResponse("/content/calendar", status_code=303)
        finally:
            session.close()

    @app.post("/content/{content_id}/interactions")
    async def content_update_interactions(content_id: int, request: Request):
        form = await request.form()
        init_db()
        session = SessionLocal()
        try:
            update_interactions(
                session,
                content_id,
                _form_int(form.get("likes")),
                _form_int(form.get("comments")),
                _form_int(form.get("shares")),
                _form_int(form.get("consultations")),
            )
            return RedirectResponse("/content/calendar", status_code=303)
        finally:
            session.close()
```

- [ ] **Step 5: Run test to verify GREEN**

Run:

```bash
uv run pytest tests/test_web/test_operations.py::test_content_calendar_asset_publish_and_interaction_actions -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/app.py tests/test_web/test_operations.py
git commit -m "feat: add content publishing workflow routes"
```

---

### Task 6: Update Content Calendar UI

**Files:**
- Modify: `web/templates/content_calendar.html`
- Modify: `tests/test_web/test_operations.py`

- [ ] **Step 1: Write failing UI test**

Add this test to `tests/test_web/test_operations.py`:

```python
def test_content_calendar_renders_publishing_controls(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'content_publish_ui.db'}")
    monkeypatch.setenv("AIPET_AUTH_ENABLED", "false")
    monkeypatch.setenv("AIPET_REQUIRE_LICENSE", "false")

    from app.database import SessionLocal, init_db
    from app.models import ContentItem, Store
    from fastapi.testclient import TestClient
    from web.app import create_app

    init_db()
    session = SessionLocal()
    try:
        store = Store(name="豆豆宠物")
        session.add(store)
        session.commit()
        item = ContentItem(
            store_id=store.id,
            channel="douyin",
            topic="洗护过程",
            title="洗护过程短视频脚本",
            body="正文",
            hashtags="宠物店,洗护",
            image_prompt="宠物店门口的小狗",
            status="failed",
            publish_mode="adapter",
            publish_error="douyin 真实发布未配置",
            asset_status="placeholder_ready",
        )
        session.add(item)
        session.commit()
        content_id = item.id
    finally:
        session.close()

    response = TestClient(create_app()).get("/content/calendar")

    assert response.status_code == 200
    assert f'/content/{content_id}/prepare-asset' in response.text
    assert f'/content/{content_id}/publish-adapter' in response.text
    assert f'/content/{content_id}/mark-published' in response.text
    assert f'/content/{content_id}/interactions' in response.text
    assert "素材：placeholder_ready" in response.text
    assert "douyin 真实发布未配置" in response.text
```

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
uv run pytest tests/test_web/test_operations.py::test_content_calendar_renders_publishing_controls -q
```

Expected: FAIL because the template does not render the new action routes or status labels.

- [ ] **Step 3: Update template**

In `web/templates/content_calendar.html`, inside each content-item card or table row, render this block:

```html
<div class="content-publish-panel">
  <p class="muted-line">素材：{{ item.asset_status or "not_requested" }} · 发布：{{ item.status }}</p>
  {% if item.asset_url %}
    <a class="btn-secondary" href="{{ item.asset_url }}" target="_blank" rel="noreferrer">查看素材</a>
  {% endif %}
  {% if item.asset_error %}
    <div class="empty-state">{{ item.asset_error }}</div>
  {% endif %}
  {% if item.publish_error %}
    <div class="empty-state">{{ item.publish_error }}</div>
  {% endif %}
  {% if item.external_url %}
    <p><a href="{{ item.external_url }}" target="_blank" rel="noreferrer">查看已发布内容</a></p>
  {% endif %}
  <div class="button-row">
    <form method="post" action="/content/{{ item.id }}/prepare-asset">
      <button class="btn-secondary" type="submit">准备素材</button>
    </form>
    <form method="post" action="/content/{{ item.id }}/publish-adapter">
      <button class="btn-secondary" type="submit">尝试平台发布</button>
    </form>
  </div>
  <form class="stack" method="post" action="/content/{{ item.id }}/mark-published">
    <input class="app-search" name="external_url" placeholder="粘贴小红书/抖音链接后标记已发布" value="{{ item.external_url or '' }}">
    <button class="btn-primary" type="submit">人工发布完成</button>
  </form>
  <form class="compact-form" method="post" action="/content/{{ item.id }}/interactions">
    <input class="app-search" name="likes" type="number" min="0" placeholder="点赞">
    <input class="app-search" name="comments" type="number" min="0" placeholder="评论">
    <input class="app-search" name="shares" type="number" min="0" placeholder="分享">
    <input class="app-search" name="consultations" type="number" min="0" placeholder="咨询">
    <button class="btn-secondary" type="submit">回填互动</button>
  </form>
</div>
```

- [ ] **Step 4: Add minimal CSS if needed**

If the template lacks layout classes, add to `web/static/app.css`:

```css
.content-publish-panel {
  display: grid;
  gap: 10px;
  margin-top: 12px;
  border-top: 1px solid var(--color-border);
  padding-top: 12px;
}

.button-row,
.compact-form {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.compact-form input {
  max-width: 120px;
}
```

- [ ] **Step 5: Run UI test to verify GREEN**

Run:

```bash
uv run pytest tests/test_web/test_operations.py::test_content_calendar_renders_publishing_controls -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/templates/content_calendar.html web/static/app.css tests/test_web/test_operations.py
git commit -m "feat: expose content publishing controls"
```

---

### Task 7: Full Verification And Documentation Closure

**Files:**
- Modify: `docs/superpowers/specs/2026-06-23-social-publishing-design.md`
- Optional modify: `README.md` if the existing README has a content workflow section.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/test_content_engine tests/test_web/test_operations.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full app tests**

Run:

```bash
uv run pytest tests/ -q
```

Expected: PASS.

- [ ] **Step 3: Update the design status**

In `docs/superpowers/specs/2026-06-23-social-publishing-design.md`, change:

```markdown
> 日期：2026-06-23 | 状态：设计完成，待实施
```

to:

```markdown
> 日期：2026-06-23 | 状态：已实施
```

Add this implementation note below the header:

```markdown
## 实施状态

- 已实现内容素材占位生成接口，后续可替换为用户提供的生图 adapter。
- 已实现发布 adapter 边界，小红书和抖音默认 disabled，不会误发。
- 已实现人工发布完成、外部链接记录、失败原因展示和互动数据回填。
- 已通过内容引擎、Web 工作流和全量测试验证。
```

- [ ] **Step 4: Commit docs closure**

```bash
git add docs/superpowers/specs/2026-06-23-social-publishing-design.md
git commit -m "docs: close social publishing design"
```

- [ ] **Step 5: Sync CodeGraph after commits**

Run:

```bash
if (Test-Path .codegraph) { codegraph sync } else { codegraph init -i }
```

Expected: command completes successfully.

---

## Self-Review

- Spec coverage: Tasks cover model persistence, image placeholder boundary, publisher adapter boundary, calendar metadata, Web actions, UI controls, tests, and docs closure.
- Placeholder scan: The plan intentionally uses placeholder adapter names as concrete implementation classes. There are no unresolved "TBD" or "TODO" instructions.
- Type consistency: `ImageGenerationRequest`, `ImageGenerationResult`, `PublishRequest`, `PublishResult`, `prepare_content_asset`, `publish_content_item`, `mark_manual_publish`, and `update_interactions` are introduced before route and UI tasks use them.
- Safety: Real external Xiaohongshu/Douyin posting is disabled by default; no third-party credentials or network calls are introduced.

## Execution Options

Plan complete and saved to `docs/superpowers/plans/2026-06-23-social-publishing-implementation-plan.md`. Two execution options:

1. **Subagent-Driven (recommended)** - Dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
