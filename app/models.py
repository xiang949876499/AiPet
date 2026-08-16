from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    owner_name: Mapped[str | None] = mapped_column(String(80))
    phone: Mapped[str | None] = mapped_column(String(40))
    address: Mapped[str | None] = mapped_column(String(255))
    business_type: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customers: Mapped[list["Customer"]] = relationship(back_populates="store")
    pets: Mapped[list["Pet"]] = relationship(back_populates="store")
    subscriptions: Mapped[list["StoreSubscription"]] = relationship(back_populates="store")
    content_items: Mapped[list["ContentItem"]] = relationship(back_populates="store")
    outreach_rules: Mapped[list["OutreachRule"]] = relationship(back_populates="store")


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    monthly_price: Mapped[int] = mapped_column(Integer, nullable=False)
    annual_price: Mapped[int] = mapped_column(Integer, nullable=False)
    ai_quota_monthly: Mapped[int] = mapped_column(Integer, default=100)
    features: Mapped[str] = mapped_column(Text, default="")
    is_recommended: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    subscriptions: Mapped[list["StoreSubscription"]] = relationship(back_populates="plan")


class StoreSubscription(Base):
    __tablename__ = "store_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    plan_id: Mapped[int] = mapped_column(ForeignKey("subscription_plans.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="trial")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime)
    current_period_ends_at: Mapped[datetime | None] = mapped_column(DateTime)
    ai_quota_used: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    store: Mapped[Store] = relationship(back_populates="subscriptions")
    plan: Mapped[SubscriptionPlan] = relationship(back_populates="subscriptions")

    @property
    def remaining_ai_quota(self) -> int:
        return max((self.plan.ai_quota_monthly if self.plan else 0) - self.ai_quota_used, 0)


class ContentItem(Base):
    __tablename__ = "content_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    topic: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    hashtags: Mapped[str | None] = mapped_column(Text)
    image_prompt: Mapped[str | None] = mapped_column(Text)
    scheduled_date: Mapped[date | None] = mapped_column(Date)
    interaction_data: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="draft")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    store: Mapped[Store] = relationship(back_populates="content_items")


class Staff(Base):
    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    role: Mapped[str] = mapped_column(String(40), default="店员")
    phone: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="启用")
    wecom_userid: Mapped[str | None] = mapped_column(String(120))
    wecom_corp_id: Mapped[str | None] = mapped_column(String(120))
    wecom_name: Mapped[str | None] = mapped_column(String(120))
    wecom_avatar: Mapped[str | None] = mapped_column(String(255))
    wecom_bound_at: Mapped[datetime | None] = mapped_column(DateTime)


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40))
    wechat_name: Mapped[str | None] = mapped_column(String(80))
    source: Mapped[str | None] = mapped_column(String(80))
    tags: Mapped[str | None] = mapped_column(Text)
    last_visit_time: Mapped[datetime | None] = mapped_column(DateTime)
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    visit_count: Mapped[int] = mapped_column(Integer, default=0)
    do_not_disturb: Mapped[bool] = mapped_column(Boolean, default=False)
    dnd_until: Mapped[datetime | None] = mapped_column(DateTime)
    dnd_channels: Mapped[str | None] = mapped_column(Text)
    dnd_message_types: Mapped[str | None] = mapped_column(Text)
    external_userid: Mapped[str | None] = mapped_column(String(120))
    push_consent_status: Mapped[str] = mapped_column(String(40), default="unknown")
    note: Mapped[str | None] = mapped_column(Text)

    store: Mapped[Store] = relationship(back_populates="customers")
    pets: Mapped[list["Pet"]] = relationship(back_populates="customer")
    service_records: Mapped[list["ServiceRecord"]] = relationship(back_populates="customer")
    follow_tasks: Mapped[list["FollowTask"]] = relationship(back_populates="customer")


class Pet(Base):
    __tablename__ = "pets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    pet_type: Mapped[str] = mapped_column(String(40), default="狗")
    breed: Mapped[str | None] = mapped_column(String(80))
    gender: Mapped[str | None] = mapped_column(String(20))
    birthday: Mapped[datetime | None] = mapped_column(Date)
    vaccine_next_date: Mapped[date | None] = mapped_column(Date)
    deworming_last_date: Mapped[date | None] = mapped_column(Date)
    weight: Mapped[float | None] = mapped_column(Numeric(6, 2))
    hair_type: Mapped[str | None] = mapped_column(String(40))
    character_tags: Mapped[str | None] = mapped_column(Text)
    care_cycle_days: Mapped[int] = mapped_column(Integer, default=21)
    note: Mapped[str | None] = mapped_column(Text)

    store: Mapped[Store] = relationship(back_populates="pets")
    customer: Mapped[Customer] = relationship(back_populates="pets")
    service_records: Mapped[list["ServiceRecord"]] = relationship(back_populates="pet")
    follow_tasks: Mapped[list["FollowTask"]] = relationship(back_populates="pet")


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    pet_id: Mapped[int] = mapped_column(ForeignKey("pets.id"), nullable=False)
    service_type: Mapped[str] = mapped_column(String(80), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(DateTime)
    staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff.id"))
    status: Mapped[str] = mapped_column(String(40), default="待确认")
    note: Mapped[str | None] = mapped_column(Text)


class ServiceRecord(Base):
    __tablename__ = "service_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    pet_id: Mapped[int] = mapped_column(ForeignKey("pets.id"), nullable=False)
    service_type: Mapped[str] = mapped_column(String(80), nullable=False)
    service_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff.id"))
    next_suggest_time: Mapped[datetime | None] = mapped_column(DateTime)
    note: Mapped[str | None] = mapped_column(Text)

    customer: Mapped[Customer] = relationship(back_populates="service_records")
    pet: Mapped[Pet] = relationship(back_populates="service_records")


class FollowTask(Base):
    __tablename__ = "follow_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    pet_id: Mapped[int] = mapped_column(ForeignKey("pets.id"), nullable=False)
    task_type: Mapped[str] = mapped_column(String(80), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="中")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_action: Mapped[str] = mapped_column(Text, nullable=False)
    due_date: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(40), default="待处理")
    staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff.id"))
    ai_message: Mapped[str | None] = mapped_column(Text)
    decision_card: Mapped[str | None] = mapped_column(Text)
    send_mode: Mapped[str] = mapped_column(String(40), default="manual_confirm")
    result: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    customer: Mapped[Customer] = relationship(back_populates="follow_tasks")
    pet: Mapped[Pet] = relationship(back_populates="follow_tasks")
    push_tasks: Mapped[list["PushTask"]] = relationship(back_populates="follow_task")


class OutreachRule(Base):
    __tablename__ = "outreach_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    message_type: Mapped[str] = mapped_column(String(80), default="service")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    send_mode: Mapped[str] = mapped_column(String(40), default="manual_confirm")
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    store: Mapped[Store] = relationship(back_populates="outreach_rules")


class OutreachLog(Base):
    __tablename__ = "outreach_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    pet_id: Mapped[int | None] = mapped_column(ForeignKey("pets.id"))
    follow_task_id: Mapped[int | None] = mapped_column(ForeignKey("follow_tasks.id"))
    rule_code: Mapped[str] = mapped_column(String(80), default="")
    channel: Mapped[str] = mapped_column(String(40), default="wecom_external")
    message_type: Mapped[str] = mapped_column(String(80), default="service")
    send_mode: Mapped[str] = mapped_column(String(40), default="manual_confirm")
    content: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="pending_confirm")
    decision_card: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_message: Mapped[str | None] = mapped_column(Text)
    response_time: Mapped[datetime | None] = mapped_column(DateTime)
    response_content: Mapped[str | None] = mapped_column(Text)
    appointment_created: Mapped[bool] = mapped_column(Boolean, default=False)
    appointment_time: Mapped[datetime | None] = mapped_column(DateTime)
    service_within_7d: Mapped[bool] = mapped_column(Boolean, default=False)
    linked_service_record_id: Mapped[int | None] = mapped_column(ForeignKey("service_records.id"))
    attributed_revenue: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ContentTemplate(Base):
    __tablename__ = "content_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id"))
    code: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PushTask(Base):
    __tablename__ = "push_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    follow_task_id: Mapped[int | None] = mapped_column(ForeignKey("follow_tasks.id"))
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    receiver_type: Mapped[str] = mapped_column(String(40), nullable=False)
    receiver_id: Mapped[str] = mapped_column(String(160), nullable=False)
    scene: Mapped[str] = mapped_column(String(80), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="pending")
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("staff.id"))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    follow_task: Mapped[FollowTask | None] = relationship(back_populates="push_tasks")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str | None] = mapped_column(String(80))
    spec: Mapped[str | None] = mapped_column(String(80))
    price: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    consume_cycle_days: Mapped[int] = mapped_column(Integer, default=30)
    status: Mapped[str] = mapped_column(String(40), default="上架")


class ProductPurchase(Base):
    __tablename__ = "product_purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    pet_id: Mapped[int] = mapped_column(ForeignKey("pets.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    purchase_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    next_remind_time: Mapped[datetime | None] = mapped_column(DateTime)


class SampleTrial(Base):
    __tablename__ = "sample_trials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    pet_id: Mapped[int] = mapped_column(ForeignKey("pets.id"), nullable=False)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    receive_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    follow_time: Mapped[datetime | None] = mapped_column(DateTime)
    feedback: Mapped[str | None] = mapped_column(String(80))
    converted: Mapped[bool] = mapped_column(Boolean, default=False)
    converted_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
