from datetime import datetime, timezone
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

def utcnow():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(Text)

class Trip(Base):
    __tablename__ = 'trips'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    destination: Mapped[str] = mapped_column(String(160))
    timezone: Mapped[str] = mapped_column(String(80))
    start_date: Mapped[datetime] = mapped_column(Date)
    end_date: Mapped[datetime] = mapped_column(Date)
    owner_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    members = relationship('TripMember', cascade='all, delete-orphan', passive_deletes=True)
    items = relationship('ItineraryItem', cascade='all, delete-orphan', passive_deletes=True)
    subscriptions = relationship('CalendarSubscription', cascade='all, delete-orphan', passive_deletes=True)
    invites = relationship('TripInvite', cascade='all, delete-orphan', passive_deletes=True)
    runs = relationship('SyncRun', cascade='all, delete-orphan', passive_deletes=True)

class TripMember(Base):
    __tablename__ = 'trip_members'
    trip_id: Mapped[int] = mapped_column(ForeignKey('trips.id', ondelete='CASCADE'), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    role: Mapped[str] = mapped_column(String(20), default='member')

class TripInvite(Base):
    __tablename__ = 'trip_invites'
    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey('trips.id', ondelete='CASCADE'), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class ItineraryItem(Base):
    __tablename__ = 'itinerary_items'
    __table_args__ = (UniqueConstraint('subscription_id', 'external_uid', name='uq_feed_uid'), Index('ix_trip_start', 'trip_id', 'starts_at'))
    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey('trips.id', ondelete='CASCADE'))
    title: Mapped[str] = mapped_column(String(200))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    location: Mapped[str] = mapped_column(String(255), default='')
    notes: Mapped[str] = mapped_column(Text, default='')
    link: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    source: Mapped[str] = mapped_column(String(12), default='manual')
    version: Mapped[int] = mapped_column(Integer, default=1)
    subscription_id: Mapped[int | None] = mapped_column(ForeignKey('calendar_subscriptions.id', ondelete='CASCADE'), nullable=True)
    external_uid: Mapped[str | None] = mapped_column(String(255), nullable=True)

class CalendarSubscription(Base):
    __tablename__ = 'calendar_subscriptions'
    __table_args__ = (UniqueConstraint('trip_id', 'url', name='uq_trip_feed'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey('trips.id', ondelete='CASCADE'))
    owner_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    url: Mapped[str] = mapped_column(Text)
    etag: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_modified: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='pending')
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

class SyncRun(Base):
    __tablename__ = 'sync_runs'
    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey('trips.id', ondelete='CASCADE'), index=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey('calendar_subscriptions.id', ondelete='CASCADE'))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='running')
    created: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    deleted: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
