import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _seed_frontend_api(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'frontend_api.db'}")
    monkeypatch.setenv("AIPET_AUTH_ENABLED", "false")
    monkeypatch.setenv("AIPET_REQUIRE_LICENSE", "false")

    from app.database import SessionLocal, init_db
    from seed_data import seed_demo_data

    init_db()
    session = SessionLocal()
    try:
        seed_demo_data(session)
    finally:
        session.close()


def _app_source() -> str:
    return (PROJECT_ROOT / "frontend" / "src" / "App.vue").read_text(encoding="utf-8")


def _css_source() -> str:
    return (PROJECT_ROOT / "frontend" / "src" / "styles.css").read_text(encoding="utf-8")


def _view_block(source: str, start: str, end: str) -> str:
    return source.split(start, 1)[1].split(end, 1)[0]


def test_workbench_api_returns_frontend_bootstrap_data(tmp_path, monkeypatch):
    _seed_frontend_api(tmp_path, monkeypatch)

    from fastapi.testclient import TestClient
    from web.app import create_app

    response = TestClient(create_app()).get("/api/workbench")

    assert response.status_code == 200
    payload = response.json()
    assert payload["store"]["name"]
    assert payload["metrics"]["customers"] >= 1
    assert "pending_tasks" in payload["metrics"]
    assert "subscription" in payload
    assert isinstance(payload["reminders"], list)
    assert isinstance(payload["content_items"], list)
    assert isinstance(payload["quick_actions"], list)


def test_workbench_reminders_include_customer_profile_for_follow_up(tmp_path, monkeypatch):
    _seed_frontend_api(tmp_path, monkeypatch)

    from app.database import SessionLocal
    from app.models import Customer, FollowTask
    from fastapi.testclient import TestClient
    from web.app import create_app

    session = SessionLocal()
    try:
        customer = session.query(Customer).first()
        session.add(
            FollowTask(
                store_id=customer.store_id,
                customer_id=customer.id,
                pet_id=customer.pets[0].id,
                task_type="washing_reminder",
                priority="high",
                reason="No booking in the last 7 days.",
                suggested_action="Invite the customer to reserve a washing slot.",
                status="pending",
            )
        )
        session.commit()
    finally:
        session.close()

    response = TestClient(create_app()).get("/api/workbench")

    assert response.status_code == 200
    reminder = response.json()["reminders"][0]
    assert {
        "customer_id",
        "customer_phone",
        "customer_wechat_name",
        "customer_tags",
        "last_visit_time",
        "visit_count",
        "total_amount",
        "pet_type",
        "pet_breed",
        "pet_character_tags",
    } <= reminder.keys()


def test_vue_frontend_is_split_from_server_templates():
    package_json = PROJECT_ROOT / "frontend" / "package.json"
    app_vue = PROJECT_ROOT / "frontend" / "src" / "App.vue"
    vite_config = PROJECT_ROOT / "frontend" / "vite.config.js"

    assert package_json.exists()
    assert app_vue.exists()
    assert vite_config.exists()

    package_data = json.loads(package_json.read_text(encoding="utf-8"))
    assert "vue" in package_data["dependencies"]
    assert package_data["scripts"]["dev"].startswith("vite")
    assert package_data["scripts"]["build"].startswith("vite build")

    app_source = _app_source()
    for marker in ["app-shell", "sidebar", "topbar", "ai-layout", "ai-chat-area"]:
        assert marker in app_source
    assert "/api/workbench" in app_source


def test_fastapi_serves_built_vue_frontend(tmp_path, monkeypatch):
    frontend_dist = tmp_path / "dist"
    assets_dir = frontend_dist / "assets"
    assets_dir.mkdir(parents=True)
    (frontend_dist / "index.html").write_text(
        '<div id="app"></div><script type="module" src="/assets/app.js"></script>',
        encoding="utf-8",
    )
    (assets_dir / "app.js").write_text("console.log('vue app')", encoding="utf-8")

    monkeypatch.setenv("AIPET_AUTH_ENABLED", "false")
    monkeypatch.setenv("AIPET_REQUIRE_LICENSE", "false")

    import web.app as web_app

    monkeypatch.setattr(web_app, "FRONTEND_DIST_DIR", frontend_dist)

    from fastapi.testclient import TestClient

    client = TestClient(web_app.create_app())

    response = client.get("/")
    assert response.status_code == 200
    assert '<div id="app"></div>' in response.text

    asset_response = client.get("/assets/app.js")
    assert asset_response.status_code == 200
    assert "vue app" in asset_response.text


def test_launcher_uses_only_fixed_8000_port():
    source = (PROJECT_ROOT / "start.ps1").read_text(encoding="utf-8")

    assert "[int]$Port" not in source
    assert "$SelectedPort" not in source
    assert "--port\", \"8000\"" in source
    assert "Start with -Port" not in source
    assert "trying the next port" not in source
    assert "Stop-PreviousAipetServers" in source
    assert "start\\.bat|start\\.ps1" in source
    assert "protectedProcessIds" in source


def test_advisor_api_accepts_category_and_legacy_question(tmp_path, monkeypatch):
    _seed_frontend_api(tmp_path, monkeypatch)

    from fastapi.testclient import TestClient
    from web.app import create_app

    client = TestClient(create_app())
    category_response = client.post(
        "/api/advisor", json={"question": "客户嫌贵怎么回？", "category": "客户沟通"}
    )
    legacy_response = client.post("/api/advisor", json={"question": "会员日怎么做？"})

    assert category_response.status_code == 200
    assert category_response.json()["answer"]
    assert legacy_response.status_code == 200
    assert legacy_response.json()["answer"]


def test_topbar_removes_global_customer_search():
    source = _app_source()
    topbar = _view_block(source, '<header class="topbar">', "</header>")

    assert "shell-search" not in topbar
    assert "global-search" not in source
    assert "search-results-view" not in source
    assert "searchWorkbench" not in source
    assert "searchResults" not in source
    assert "customerSearchQuery" in source
    assert "filteredCustomers" in source


def test_dashboard_is_today_workbench_without_duplicate_customer_lists():
    source = _app_source()
    dashboard = _view_block(
        source,
        "v-if=\"activeView === 'dashboard'\"",
        "v-else-if=\"activeView === 'advisor'\"",
    )

    for marker in ["dashboardSummary", "todayPriorityActions", "quick-entry-list"]:
        assert marker in dashboard

    assert "客户机会" not in dashboard
    assert "待跟进任务" not in dashboard
    assert "内容草稿" not in dashboard
    assert "经营漏斗" not in dashboard


def test_customer_management_owns_customer_search_list_and_import():
    source = _app_source()
    css = _css_source()
    customers = _view_block(
        source,
        "v-else-if=\"activeView === 'customers'\"",
        "v-else-if=\"activeView === 'marketing'\"",
    )

    for marker in [
        "customerSearchQuery",
        "filteredCustomers",
        "loadCustomerIndex",
        "/api/customers",
        "customer-list-panel",
        "customer-search-input",
        "previewCustomerImport",
        "submitCustomerImport",
        "/api/customers/import/preview",
        "/api/customers/import/template",
    ]:
        assert marker in customers or marker in source

    assert "/api/customers/outreach-queue" not in customers
    assert "outreach-queue-panel" not in customers
    assert ".customer-list-panel" in css
    assert ".customer-row" in css


def test_task_center_owns_outreach_queue_and_promotion_publishing():
    source = _app_source()
    css = _css_source()
    tasks = _view_block(
        source,
        "v-else-if=\"activeView === 'tasks'\"",
        "v-else-if=\"activeView === 'reports'\"",
    )

    for marker in [
        "fetchOutreachQueue",
        "/api/customers/outreach-queue",
        "taskOutreachItems",
        "promotionItems",
        "generateOutreachMessage",
        "saveOutreachMessage",
        "skipOutreachTask",
        "copyContentItem",
        "publishContentItem",
        "recommended-customer-column",
        "promotion-publish-column",
    ]:
        assert marker in tasks or marker in source

    assert "task-center-grid" in tasks
    assert ".task-center-grid" in css
    assert ".promotion-item" in css


def test_marketing_view_is_three_step_campaign_flow():
    source = _app_source()
    css = _css_source()
    marketing = _view_block(
        source,
        "v-else-if=\"activeView === 'marketing'\"",
        "v-else-if=\"activeView === 'tasks'\"",
    )

    for marker in ["marketing-step", "campaignDirections", "marketingGeneratedCopy", "marketingContentItems"]:
        assert marker in marketing

    assert "数据给出的营销建议" not in marketing
    assert "发布复盘" not in marketing
    assert "approachComparison" not in marketing
    assert ".marketing-step" in css


def test_reports_show_only_operating_metrics_logic():
    source = _app_source()
    reports = _view_block(source, "v-else-if=\"activeView === 'reports'\"", "</main>")

    for marker in [
        "reportStats",
        "经营漏斗",
        "客户健康",
        "触达策略效果",
        "approachComparisonRows",
    ]:
        assert marker in reports or marker in source

    assert "今日任务" not in reports
    assert "内容草稿" not in reports
    assert "客户机会" not in reports
    assert "outreach-item" not in reports


def test_advisor_frontend_sends_category_context():
    source = _app_source()
    advisor = _view_block(
        source,
        "v-else-if=\"activeView === 'advisor'\"",
        "v-else-if=\"activeView === 'customers'\"",
    )

    for marker in [
        "advisorCategory",
        "askAdvisorQuestion(question, category.title)",
        "category: advisorCategory.value",
        "advisor-category-card",
    ]:
        assert marker in advisor or marker in source


def test_marketing_copy_api_uses_content_specific_prompt(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _seed_frontend_api(tmp_path, monkeypatch)

    from fastapi.testclient import TestClient
    from web.app import create_app

    response = TestClient(create_app()).post(
        "/api/workbench/marketing-copy",
        json={
            "title": "老客复购提醒",
            "goal": "把本周洗护机会收回来",
            "target": "王姐 / 小七 等高意向客户",
            "offer": "会员日护理包",
            "channel": "朋友圈 + 私聊触达",
            "action": "先生成朋友圈预热，再给重点客户发提醒",
            "sample": "主角客户：王姐，宠物：小七",
            "output_type": "朋友圈发布文案",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "老客复购提醒 · 朋友圈发布文案"
    assert "王姐 / 小七" in payload["body"]
    assert "会员日护理包" in payload["body"]
    assert "医疗诊断" not in payload["body"]


def test_diagnosis_uses_workbench_diagnosis_endpoint_not_advisor():
    source = _app_source()
    diagnosis_block = source.split("async function submitDiagnosis()", 1)[1].split(
        "function askMarketingAdvice()", 1
    )[0]

    assert "/api/workbench/diagnosis" in diagnosis_block
    assert "/api/advisor" not in diagnosis_block


def test_reminder_friendly_message_api_generates_and_persists_copy(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _seed_frontend_api(tmp_path, monkeypatch)

    from app.database import SessionLocal
    from app.models import Customer, FollowTask
    from fastapi.testclient import TestClient
    from web.app import create_app

    session = SessionLocal()
    try:
        customer = session.query(Customer).first()
        pet = customer.pets[0]
        task = FollowTask(
            store_id=customer.store_id,
            customer_id=customer.id,
            pet_id=pet.id,
            task_type="washing_reminder",
            priority="high",
            reason="No booking in the last 7 days.",
            suggested_action="Invite the customer to reserve a washing slot.",
            status="pending",
        )
        session.add(task)
        session.commit()
        task_id = task.id
    finally:
        session.close()

    client = TestClient(create_app())

    response = client.post(f"/api/reminders/{task_id}/friendly-message")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == task_id
    assert payload["ai_message"]
    assert payload["customer_name"] in payload["ai_message"]
    assert payload["pet_name"] in payload["ai_message"]
    assert len(payload["ai_message"]) <= 180

    refreshed = client.get("/api/reminders").json()
    persisted = next(task for task in refreshed if task["id"] == task_id)
    assert persisted["ai_message"] == payload["ai_message"]
