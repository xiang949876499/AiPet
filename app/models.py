from datetime import datetime

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


class Staff(Base):
    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    role: Mapped[str] = mapped_column(String(40), default="店员")
    phone: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="启用")


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
    result: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    customer: Mapped[Customer] = relationship(back_populates="follow_tasks")
    pet: Mapped[Pet] = relationship(back_populates="follow_tasks")


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
