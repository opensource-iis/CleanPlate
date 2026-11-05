from pathlib import Path

from flask import Flask
from flask_login import LoginManager

from .extensions import db
from .models import Badge, PlateSubmission, Provider, Reward, SurplusListing, User


def seed_demo_data():
    if User.query.filter_by(email="provider@wasteless.com").first():
        return

    provider_user = User(name="Green Canteen", email="provider@wasteless.com", role="provider")
    provider_user.set_password("password123")
    provider_user.points = 0
    db.session.add(provider_user)
    db.session.flush()

    provider = Provider(
        user_id=provider_user.id,
        name="Green Canteen",
        category="Campus Café",
        location="North Hall",
        description="Fresh daily meals and discounted rescue bags.",
    )
    db.session.add(provider)
    db.session.flush()

    rewards = [
        Reward(
            provider_id=provider.id,
            title="Free Tea",
            description="Enjoy a complimentary tea with any meal.",
            cost=100,
        ),
        Reward(
            provider_id=provider.id,
            title="Lunch Discount",
            description="£2 off your next lunch bowl.",
            cost=180,
        ),
    ]
    db.session.add_all(rewards)

    demo_user = User(name="Maya Chen", email="maya@wasteless.com", role="consumer")
    demo_user.set_password("password123")
    demo_user.points = 250
    db.session.add(demo_user)
    db.session.flush()

    demo_user.award_points(130, "earn", "7 day zero waste streak")
    demo_user.award_points(120, "earn", "Clean plate challenge")

    second_user = User(name="Leo Martin", email="leo@wasteless.com", role="consumer")
    second_user.set_password("password123")
    second_user.points = 95
    db.session.add(second_user)
    db.session.flush()

    second_user.award_points(95, "earn", "Rescue bag pickup")

    db.session.add_all(
        [
            PlateSubmission(
                user_id=demo_user.id,
                image_filename="demo-plate-1.jpg",
                status="approved",
                notes="Empty plate verified by demo vision model.",
                points_awarded=120,
            ),
            SurplusListing(
                provider_id=provider.id,
                title="Vegetable wrap bundle",
                description="Three wraps left from today’s lunch rush.",
                quantity=3,
                price=2.50,
                pickup_window="Today, 6:00 PM",
            ),
            SurplusListing(
                provider_id=provider.id,
                title="Fruit salad cups",
                description="Cups left from this afternoon service.",
                quantity=5,
                price=1.25,
                pickup_window="Today, 7:00 PM",
            ),
            Badge(name="Plate Hero", description="Verified five empty plates.", icon="🥗"),
            Badge(name="Rescue Ranger", description="Collected two surplus bags.", icon="🧺"),
        ]
    )
    db.session.commit()


login_manager = LoginManager()


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "waste-less-demo-secret"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///waste_less.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["UPLOAD_FOLDER"] = str(Path(__file__).resolve().parent.parent / "uploads")

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "main.login"

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    with app.app_context():
        db.create_all()
        seed_demo_data()

    from .routes import bp

    app.register_blueprint(bp)
    return app
