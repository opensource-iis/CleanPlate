import os
import uuid
from datetime import datetime

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.utils import secure_filename

from .models import Badge, Provider, PointsTransaction, Redemption, Reward, SurplusListing, User, db
from .plate_logic import evaluate_plate_image

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "consumer")

        if not name or not email or not password:
            flash("Please complete all fields.")
            return render_template("register.html")

        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.")
            return render_template("register.html")

        user = User(name=name, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        if role == "provider":
            provider = Provider(
                user_id=user.id,
                name=f"{name}'s food hub",
                category="Dining provider",
                location="Main campus",
                description="Helping local diners save more food.",
            )
            db.session.add(provider)

        db.session.commit()
        login_user(user)
        flash("Welcome to Waste Less!")
        return redirect(url_for("main.dashboard"))

    return render_template("register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash("Logged in successfully.")
            return redirect(url_for("main.dashboard"))

        flash("Incorrect email or password.")

    return render_template("login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.")
    return redirect(url_for("main.index"))


@bp.route("/dashboard")
@login_required
def dashboard():
    recent_transactions = sorted(current_user.transactions, key=lambda item: item.created_at, reverse=True)[:5]
    submissions = sorted(current_user.plate_submissions, key=lambda item: item.created_at, reverse=True)[:5]
    leaderboard = User.query.order_by(User.points.desc()).limit(5).all()

    if current_user.role == "provider":
        provider = current_user.provider
        rewards = provider.rewards if provider else []
        return render_template("provider_dashboard.html", provider=provider, rewards=rewards, leaderboard=leaderboard)

    return render_template(
        "dashboard.html",
        recent_transactions=recent_transactions,
        submissions=submissions,
        leaderboard=leaderboard,
    )


@bp.route("/plate-check", methods=["GET", "POST"])
@login_required
def plate_check():
    if request.method == "POST":
        file = request.files.get("photo")
        if not file or file.filename == "":
            flash("Please upload a plate photo before submitting.")
            return render_template("plate_check.html")

        filename = secure_filename(file.filename)
        extension = os.path.splitext(filename)[1].lower()
        if extension not in {".jpg", ".jpeg", ".png"}:
            flash("Please upload a JPG or PNG image.")
            return render_template("plate_check.html")

        unique_name = f"{uuid.uuid4().hex}{extension}"
        upload_dir = current_app.config["UPLOAD_FOLDER"]
        os.makedirs(upload_dir, exist_ok=True)
        image_path = os.path.join(upload_dir, unique_name)
        file.save(image_path)

        result = evaluate_plate_image(file)
        points_earned = result["points"]

        if result["status"] == "invalid":
            current_user.adjust_points(points_earned, "penalty", "Invalid plate photo")
            status = "invalid"
            notes = "The uploaded image did not look like a real plate photo."
            message = result["message"].replace("{total_points}", str(current_user.points))
        elif points_earned > 0:
            current_user.award_points(points_earned, "earn", "Clean plate challenge")
            status = "approved"
            notes = "Empty plate verified by demo vision model."
            message = result["message"].replace("{total_points}", str(current_user.points))
        else:
            current_user.adjust_points(points_earned, "penalty", "Food left on plate")
            status = "needs_improvement"
            notes = "Some food remained on the plate. Points were reduced."
            message = result["message"].replace("{total_points}", str(current_user.points))

        from .models import PlateSubmission as PlateModel

        new_submission = PlateModel(
            user_id=current_user.id,
            image_filename=unique_name,
            status=status,
            notes=notes,
            points_awarded=points_earned,
            created_at=datetime.utcnow(),
        )
        db.session.add(new_submission)
        db.session.commit()

        flash(message)
        return redirect(url_for("main.dashboard"))

    return render_template("plate_check.html")


@bp.route("/rewards")
@login_required
def rewards():
    rewards = Reward.query.filter_by(is_active=True).all()
    return render_template("rewards.html", rewards=rewards)


@bp.route("/reward/<int:reward_id>/redeem", methods=["POST"])
@login_required
def redeem_reward(reward_id):
    reward = Reward.query.get_or_404(reward_id)

    if current_user.points < reward.cost:
        flash("You do not have enough points for this reward.")
        return redirect(url_for("main.rewards"))

    if current_user.spend_points(reward.cost, f"Redeemed {reward.title}"):
        redemption = Redemption(user_id=current_user.id, reward_id=reward.id, status="redeemed")
        db.session.add(redemption)
        db.session.commit()
        flash(f"Reward redeemed: {reward.title}!")
    else:
        flash("Something went wrong while redeeming this reward.")

    return redirect(url_for("main.rewards"))


@bp.route("/leaderboard")
@login_required
def leaderboard():
    users = User.query.order_by(User.points.desc()).all()
    return render_template("leaderboard.html", users=users)


@bp.route("/provider")
@login_required
def provider_dashboard():
    if current_user.role != "provider":
        flash("Only provider accounts can view this page.")
        return redirect(url_for("main.dashboard"))

    provider = current_user.provider
    if not provider:
        flash("Your provider profile is missing.")
        return redirect(url_for("main.dashboard"))

    rewards = Reward.query.filter_by(provider_id=provider.id).all()
    return render_template("provider_dashboard.html", provider=provider, rewards=rewards)


@bp.route("/provider/reward/create", methods=["GET", "POST"])
@login_required
def create_reward():
    if current_user.role != "provider":
        flash("Only provider accounts can create perks.")
        return redirect(url_for("main.dashboard"))

    provider = current_user.provider
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        cost = int(request.form.get("cost", 100))

        if not title or not description:
            flash("Reward title and description are required.")
            return render_template("reward_form.html", provider=provider)

        reward = Reward(provider_id=provider.id, title=title, description=description, cost=cost)
        db.session.add(reward)
        db.session.commit()
        flash("Reward created successfully.")
        return redirect(url_for("main.provider_dashboard"))

    return render_template("reward_form.html", provider=provider)


@bp.route("/provider/impact")
@login_required
def provider_impact():
    provider = current_user.provider
    if not provider:
        flash("Provider profile not found.")
        return redirect(url_for("main.dashboard"))

    listings = SurplusListing.query.filter_by(provider_id=provider.id).all()
    rewards = Reward.query.filter_by(provider_id=provider.id).all()
    return render_template("provider_impact.html", provider=provider, listings=listings, rewards=rewards)
