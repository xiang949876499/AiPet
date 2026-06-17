from datetime import datetime, timedelta


def test_sample_agent_creates_followup_for_yesterday_trial(db_session, sample_records):
    from agents.sample import SampleAgent
    from app.models import Product, SampleTrial

    product = Product(store_id=sample_records["store"].id, name="冻干试吃装", category="零食")
    db_session.add(product)
    db_session.flush()
    trial = SampleTrial(
        store_id=sample_records["store"].id,
        customer_id=sample_records["customer"].id,
        pet_id=sample_records["pet"].id,
        product_id=product.id,
        receive_time=datetime.utcnow() - timedelta(days=1),
    )
    db_session.add(trial)
    db_session.commit()

    result = SampleAgent(db_session).execute({"store_id": sample_records["store"].id})

    assert result["created"] == 1
    assert trial.follow_time is not None
