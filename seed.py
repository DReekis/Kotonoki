from app.extensions import db
from app.models import Branch, PenName, Dispatch
from app.services.branch_service import BranchService

def remove_demo_posts():
    """Remove legacy sample/seed dispatches and fake authors."""
    try:
        demo_handles = ["kenji_notes", "wandering_lens", "cast_iron_cook"]
        authors = PenName.query.filter(PenName.handle.in_(demo_handles)).all()
        if authors:
            for a in authors:
                db.session.delete(a)
            db.session.commit()
            print(f"Removed {len(authors)} demo authors and their associated made-up posts.")
            return True
        return False
    except Exception as e:
        db.session.rollback()
        print(f"Cleanup note: {e}")
        return False

def ensure_default_branches():
    """Ensure core default branches exist without creating any dummy dispatches."""
    try:
        default_branches = ["cooking", "books", "midnight-thoughts", "hardware"]
        for b in default_branches:
            BranchService.get_or_create(b)
        return True
    except Exception as e:
        db.session.rollback()
        print(f"Branch init note: {e}")
        return False

def seed_initial_data():
    """Clean legacy demo posts and ensure clean default state."""
    remove_demo_posts()
    ensure_default_branches()
    return True

if __name__ == "__main__":
    from app import create_app
    app = create_app()
    with app.app_context():
        seed_initial_data()
        print(f"Current live dispatches count: {Dispatch.query.count()}")
