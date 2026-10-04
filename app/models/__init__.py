from datetime import datetime, timezone
from app.extensions import db
from app.utils.uuid7 import generate_uuid7

def utc_now():
    return datetime.now(timezone.utc)

class PenName(db.Model):
    __tablename__ = "pen_names"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid7)
    handle = db.Column(db.String(40), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)

    dispatches = db.relationship("Dispatch", back_populates="author", cascade="all, delete-orphan", lazy="dynamic")
    votes = db.relationship("Vote", back_populates="author", cascade="all, delete-orphan", lazy="dynamic")

    def __repr__(self):
        return f"<PenName {self.handle}>"


class Branch(db.Model):
    __tablename__ = "branches"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid7)
    slug = db.Column(db.String(60), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    dispatches = db.relationship("Dispatch", back_populates="branch", cascade="all, delete-orphan", lazy="dynamic")

    def __repr__(self):
        return f"<Branch /{self.slug}>"


class Dispatch(db.Model):
    __tablename__ = "dispatches"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid7)
    branch_id = db.Column(db.String(36), db.ForeignKey("branches.id"), nullable=False, index=True)
    author_id = db.Column(db.String(36), db.ForeignKey("pen_names.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    content_html = db.Column(db.Text, nullable=False)
    image_path = db.Column(db.String(255), nullable=True)
    upvotes_count = db.Column(db.Integer, default=0, nullable=False)
    downvotes_count = db.Column(db.Integer, default=0, nullable=False)
    published_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    branch = db.relationship("Branch", back_populates="dispatches")
    author = db.relationship("PenName", back_populates="dispatches")
    votes = db.relationship("Vote", back_populates="dispatch", cascade="all, delete-orphan", lazy="dynamic")
    reports = db.relationship("Report", back_populates="dispatch", cascade="all, delete-orphan", lazy="dynamic")

    __table_args__ = (
        db.Index("idx_dispatches_feed", "published_at", "id"),
        db.Index("idx_dispatches_branch_feed", "branch_id", "published_at", "id"),
        db.Index("idx_dispatches_author", "author_id", "published_at"),
    )

    @property
    def score(self) -> int:
        return self.upvotes_count - self.downvotes_count

    def __repr__(self):
        return f"<Dispatch '{self.title}' by {self.author_id}>"


class Vote(db.Model):
    __tablename__ = "votes"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid7)
    dispatch_id = db.Column(db.String(36), db.ForeignKey("dispatches.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id = db.Column(db.String(36), db.ForeignKey("pen_names.id", ondelete="CASCADE"), nullable=False, index=True)
    value = db.Column(db.SmallInteger, nullable=False)  # +1 for upvote, -1 for downvote
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    dispatch = db.relationship("Dispatch", back_populates="votes")
    author = db.relationship("PenName", back_populates="votes")

    __table_args__ = (
        db.UniqueConstraint("dispatch_id", "author_id", name="uq_dispatch_author_vote"),
    )

    def __repr__(self):
        return f"<Vote {self.value} on {self.dispatch_id} by {self.author_id}>"


class Report(db.Model):
    __tablename__ = "reports"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid7)
    dispatch_id = db.Column(db.String(36), db.ForeignKey("dispatches.id", ondelete="CASCADE"), nullable=False, index=True)
    reporter_id = db.Column(db.String(36), db.ForeignKey("pen_names.id", ondelete="SET NULL"), nullable=True)
    reason = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default="open", nullable=False, index=True)  # open, reviewing, resolved, dismissed
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    dispatch = db.relationship("Dispatch", back_populates="reports")
    reporter = db.relationship("PenName")

    def __repr__(self):
        return f"<Report {self.reason} on {self.dispatch_id}>"
