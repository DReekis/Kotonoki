import datetime
from app.extensions import db
from app.models import Dispatch
from app.services.auth_service import AuthService
from app.services.branch_service import BranchService

def seed_initial_data():
    """Seed initial dispatches if database is currently empty."""
    if db.session.execute(db.select(Dispatch)).scalar() is None:
        print("Seeding initial authentic dispatches...")

        # Create authors
        author1, _ = AuthService.register("kenji_notes", "QuietJournalPass1!")
        author2, _ = AuthService.register("wandering_lens", "QuietJournalPass2!")
        author3, _ = AuthService.register("cast_iron_cook", "QuietJournalPass3!")

        # Create branches
        b_cooking, _ = BranchService.get_or_create("cooking")
        b_books, _ = BranchService.get_or_create("books")
        b_thoughts, _ = BranchService.get_or_create("midnight-thoughts")
        b_hardware, _ = BranchService.get_or_create("hardware")

        now = datetime.datetime.now(datetime.timezone.utc)

        d1 = Dispatch(
            branch_id=b_cooking.id,
            author_id=author3.id,
            title="The 40-Year Skillet and Burnt Butter",
            content_html=(
                "<p>There is a specific rhythm to cooking eggs on an old cast iron pan. "
                "You do not rush the preheat. You drop in a sliver of unsalted butter and listen for the foaming to subside. "
                "<mark>The quiet patience of the metal</mark> rewards you with an edge that is crisp, lace-like, and fragrant.</p>"
                "<blockquote>Cooking is not performance; it is attending to small heat.</blockquote>"
            ),
            upvotes_count=18,
            downvotes_count=1,
            published_at=now - datetime.timedelta(hours=6)
        )

        d2 = Dispatch(
            branch_id=b_thoughts.id,
            author_id=author1.id,
            title="Silence in the Third Floor Window",
            content_html=(
                "<p>At 2:40 AM, the street lamps cast amber geometric pools against the wet pavement. "
                "No cars pass for twenty minutes. You realize how much of modern daylight is filled with unnecessary assertion. "
                "Here, in the dark, thoughts arrive without asking for an audience.</p>"
            ),
            upvotes_count=24,
            downvotes_count=0,
            published_at=now - datetime.timedelta(hours=4)
        )

        d3 = Dispatch(
            branch_id=b_books.id,
            author_id=author2.id,
            title="Re-reading Tanizaki's In Praise of Shadows",
            content_html=(
                "<p>Tanizaki writes about the beauty of lacquerware seen not in electric glare, but in the subdued depth of an alcove. "
                "We have eliminated darkness from modern software interfaces, filling every pixel with notifications, banners, and demands. "
                "A quiet page with black text on cream paper is an act of restoration.</p>"
            ),
            upvotes_count=31,
            downvotes_count=2,
            published_at=now - datetime.timedelta(hours=1)
        )

        db.session.add_all([d1, d2, d3])
        db.session.commit()
        print("Database seeded with initial dispatches.")
        return True
    return False

if __name__ == "__main__":
    from app import create_app
    app = create_app()
    with app.app_context():
        if seed_initial_data():
            print("Done seeding.")
        else:
            print("Database already contains dispatches.")
