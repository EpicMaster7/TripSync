from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=10, max_length=128)

    @field_validator('email')
    @classmethod
    def email_format(cls, v):
        v = v.strip().lower()
        if v.count('@') != 1 or '.' not in v.split('@')[1]:
            raise ValueError('Invalid email address')
        return v

class Register(Credentials):
    name: str = Field(min_length=1, max_length=100)

class UserOut(Out):
    id: int
    email: str
    name: str

class TripFields(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    destination: str = Field(min_length=1, max_length=160)
    timezone: str
    start_date: date
    end_date: date

    @field_validator('timezone')
    @classmethod
    def valid_zone(cls, v):
        try: ZoneInfo(v)
        except ZoneInfoNotFoundError: raise ValueError('Use a valid IANA timezone')
        return v

    @model_validator(mode='after')
    def valid_dates(self):
        if self.end_date < self.start_date: raise ValueError('End date precedes start date')
        return self

class TripPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    destination: str | None = Field(default=None, min_length=1, max_length=160)
    timezone: str | None = None
    start_date: date | None = None
    end_date: date | None = None

    @field_validator('timezone')
    @classmethod
    def valid_zone(cls, v):
        if v is not None: TripFields.valid_zone(v)
        return v

class TripOut(TripFields, Out):
    id: int
    owner_id: int

class ItemBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    starts_at: datetime
    ends_at: datetime
    location: str = Field(default='', max_length=255)
    notes: str = Field(default='', max_length=5000)
    link: HttpUrl | None = None
    position: int = Field(default=0, ge=0)
    owner_id: int | None = None

    @model_validator(mode='after')
    def correct_times(self):
        if self.starts_at.utcoffset() is None or self.ends_at.utcoffset() is None:
            raise ValueError('Timestamp must include a timezone offset')
        if self.ends_at <= self.starts_at: raise ValueError('End must be later than start')
        return self

class ItemPatch(BaseModel):
    version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    location: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=5000)
    link: HttpUrl | None = None
    position: int | None = Field(default=None, ge=0)
    owner_id: int | None = None

class ItemOut(Out):
    id: int
    trip_id: int
    title: str
    starts_at: datetime
    ends_at: datetime
    location: str
    notes: str
    link: str | None
    position: int
    created_by_id: int | None
    owner_id: int | None
    source: str
    version: int

class Subscribe(BaseModel):
    url: str = Field(min_length=1, max_length=2048)

class SubscriptionOut(Out):
    id: int
    trip_id: int
    url: str
    status: str
    error: str | None
    last_fetched_at: datetime | None

class RunOut(Out):
    id: int
    subscription_id: int
    started_at: datetime
    finished_at: datetime | None
    status: str
    created: int
    updated: int
    deleted: int
    error: str | None
