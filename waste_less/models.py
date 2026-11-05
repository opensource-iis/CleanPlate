from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), default="consumer")
    points = db.Column(db.Integer, default=0)
    level = db.Column(db.String(30), default="Seedling")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    provider = db.relationship("Provider", back_populates="user", uselist=False)
    transactions = db.relationship("PointsTransaction", back_populates="user", cascade="all, delete-orphan")
    plate_submissions = db.relationship("PlateSubmission", back_populates="user", cascade="all, delete-orphan")
    redemptions = db.relationship("Redemption", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def award_points(self, amount, category="earn", description=""):
        if amount <= 0:
            return
        self.points += amount
        transaction = PointsTransaction(
            user_id=self.id,
            amount=amount,
            category=category,
            description=description,
        )
        db.session.add(transaction)

    def adjust_points(self, amount, category="adjust", description=""):
        if amount == 0:
            return False
        self.points += amount
        transaction = PointsTransaction(
            user_id=self.id,
            amount=amount,
            category=category,
            description=description,
        )
        db.session.add(transaction)
        return True

    def spend_points(self, amount, description=""):
        if amount <= 0:
            return False
        if self.points < amount:
            return False
        self.points -= amount
        transaction = PointsTransaction(
            user_id=self.id,
            amount=-amount,
            category="redeem",
            description=description,
        )
        db.session.add(transaction)
        return True

    @property
    def total_points(self):
        return self.points


class Provider(db.Model):
    __tablename__ = "providers"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(80), default="Food provider")
    location = db.Column(db.String(120), default="City center")
    description = db.Column(db.Text, default="Helping rescue surplus food")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="provider")
    rewards = db.relationship("Reward", back_populates="provider", cascade="all, delete-orphan")
    surplus_listings = db.relationship("SurplusListing", back_populates="provider", cascade="all, delete-orphan")


class Reward(db.Model):
    __tablename__ = "rewards"

    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(db.Integer, db.ForeignKey("providers.id"), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    cost = db.Column(db.Integer, nullable=False, default=100)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    provider = db.relationship("Provider", back_populates="rewards")
    redemptions = db.relationship("Redemption", back_populates="reward", cascade="all, delete-orphan")


class Redemption(db.Model):
    __tablename__ = "redemptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    reward_id = db.Column(db.Integer, db.ForeignKey("rewards.id"), nullable=False)
    status = db.Column(db.String(30), default="redeemed")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="redemptions")
    reward = db.relationship("Reward", back_populates="redemptions")


class PointsTransaction(db.Model):
    __tablename__ = "points_transactions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(40), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="transactions")


class PlateSubmission(db.Model):
    __tablename__ = "plate_submissions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    image_filename = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(30), default="pending")
    notes = db.Column(db.String(255), default="Vision check to be verified")
    points_awarded = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="plate_submissions")


class SurplusListing(db.Model):
    __tablename__ = "surplus_listings"

    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(db.Integer, db.ForeignKey("providers.id"), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    quantity = db.Column(db.Integer, default=1)
    price = db.Column(db.Float, default=0.0)
    pickup_window = db.Column(db.String(100), default="Today, 6:30 PM")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    provider = db.relationship("Provider", back_populates="surplus_listings")
    reservations = db.relationship("Reservation", back_populates="listing", cascade="all, delete-orphan")


class Reservation(db.Model):
    __tablename__ = "reservations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    listing_id = db.Column(db.Integer, db.ForeignKey("surplus_listings.id"), nullable=False)
    status = db.Column(db.String(30), default="reserved")
    pickup_code = db.Column(db.String(20), default="QR-001")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    listing = db.relationship("SurplusListing", back_populates="reservations")


class Badge(db.Model):
    __tablename__ = "badges"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, nullable=False)
    icon = db.Column(db.String(40), default="🏅")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


