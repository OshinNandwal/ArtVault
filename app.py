import streamlit as st
import pandas as pd
import sqlite3
import os
import re
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont


# ============================================================
# ART VAULT
# Digital Art Exhibition & Community Platform
# ============================================================

st.set_page_config(
    page_title="ArtVault",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# CONSTANTS
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CSV_FILE = os.path.join(BASE_DIR, "artworks.csv")
DB_FILE = os.path.join(BASE_DIR, "artvault.db")
IMAGE_DIR = os.path.join(BASE_DIR, "art_images")

os.makedirs(IMAGE_DIR, exist_ok=True)

NAV_PAGES = [
    "Home",
    "Exhibition",
    "Search",
    "Artists",
    "Favorites",
    "Marketplace",
    "Analytics"
]


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>

    .main-title {
        font-size: 42px;
        font-weight: 800;
        margin-bottom: 5px;
    }

    .subtitle {
        font-size: 17px;
        color: #666;
        margin-bottom: 25px;
    }

    .section-title {
        font-size: 28px;
        font-weight: 750;
        margin-top: 10px;
        margin-bottom: 18px;
    }

    .small-muted {
        color: #777;
        font-size: 14px;
    }

    .metric-box {
        padding: 18px;
        border-radius: 14px;
        border: 1px solid rgba(128,128,128,0.25);
        text-align: center;
    }

    .art-title {
        font-size: 19px;
        font-weight: 700;
        margin-top: 8px;
    }

    .artist-name {
        color: #777;
        font-size: 14px;
        margin-bottom: 5px;
    }

    .tag {
        display: inline-block;
        padding: 4px 9px;
        border-radius: 15px;
        background: rgba(128,128,128,0.12);
        font-size: 12px;
        margin-right: 4px;
        margin-bottom: 4px;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================
# DATABASE MIGRATION HELPERS
# ============================================================

def table_exists(conn, table_name):
    result = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table' AND name=?
        """,
        (table_name,)
    ).fetchone()

    return result is not None


def get_columns(conn, table_name):
    if not table_exists(conn, table_name):
        return []

    rows = conn.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return [row["name"] for row in rows]


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def initialize_database():

    conn = get_connection()

    # --------------------------------------------------------
    # LIKES TABLE
    # --------------------------------------------------------

    like_columns = get_columns(conn, "likes")

    if not like_columns:

        conn.execute(
            """
            CREATE TABLE likes (
                artwork_id TEXT PRIMARY KEY,
                like_count INTEGER NOT NULL DEFAULT 0
            )
            """
        )

    elif "like_count" not in like_columns:

        # Old versions may have used a column called "likes".
        old_columns = like_columns

        conn.execute("ALTER TABLE likes RENAME TO likes_legacy")

        conn.execute(
            """
            CREATE TABLE likes (
                artwork_id TEXT PRIMARY KEY,
                like_count INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        if "artwork_id" in old_columns:

            if "likes" in old_columns:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO likes
                    (artwork_id, like_count)
                    SELECT
                        artwork_id,
                        COALESCE(likes, 0)
                    FROM likes_legacy
                    """
                )

            elif "like_count" in old_columns:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO likes
                    (artwork_id, like_count)
                    SELECT
                        artwork_id,
                        COALESCE(like_count, 0)
                    FROM likes_legacy
                    """
                )

            else:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO likes
                    (artwork_id, like_count)
                    SELECT
                        artwork_id,
                        0
                    FROM likes_legacy
                    """
                )

        conn.execute("DROP TABLE likes_legacy")

    # --------------------------------------------------------
    # FAVORITES TABLE
    # --------------------------------------------------------

    favorite_columns = get_columns(conn, "favorites")

    required_favorite_columns = {
        "artwork_id",
        "created_at"
    }

    if not favorite_columns:

        conn.execute(
            """
            CREATE TABLE favorites (
                artwork_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL
            )
            """
        )

    elif not required_favorite_columns.issubset(set(favorite_columns)):

        old_columns = favorite_columns

        conn.execute(
            "ALTER TABLE favorites RENAME TO favorites_legacy"
        )

        conn.execute(
            """
            CREATE TABLE favorites (
                artwork_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL
            )
            """
        )

        if "artwork_id" in old_columns:

            if "created_at" in old_columns:

                conn.execute(
                    """
                    INSERT OR IGNORE INTO favorites
                    (artwork_id, created_at)
                    SELECT
                        artwork_id,
                        COALESCE(created_at, datetime('now'))
                    FROM favorites_legacy
                    """
                )

            else:

                conn.execute(
                    """
                    INSERT OR IGNORE INTO favorites
                    (artwork_id, created_at)
                    SELECT
                        artwork_id,
                        datetime('now')
                    FROM favorites_legacy
                    """
                )

        conn.execute("DROP TABLE favorites_legacy")

    # --------------------------------------------------------
    # REVIEWS TABLE
    # --------------------------------------------------------

    review_columns = get_columns(conn, "reviews")

    required_review_columns = {
        "id",
        "artwork_id",
        "reviewer",
        "rating",
        "comment",
        "created_at"
    }

    if not review_columns:

        conn.execute(
            """
            CREATE TABLE reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                artwork_id TEXT NOT NULL,
                reviewer TEXT NOT NULL,
                rating INTEGER NOT NULL,
                comment TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

    elif not required_review_columns.issubset(set(review_columns)):

        old_columns = review_columns

        conn.execute(
            "ALTER TABLE reviews RENAME TO reviews_legacy"
        )

        conn.execute(
            """
            CREATE TABLE reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                artwork_id TEXT NOT NULL,
                reviewer TEXT NOT NULL,
                rating INTEGER NOT NULL,
                comment TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        if "artwork_id" in old_columns:

            reviewer_expression = (
                "reviewer"
                if "reviewer" in old_columns
                else "''"
            )

            rating_expression = (
                "rating"
                if "rating" in old_columns
                else "5"
            )

            comment_expression = (
                "comment"
                if "comment" in old_columns
                else "''"
            )

            date_expression = (
                "created_at"
                if "created_at" in old_columns
                else "datetime('now')"
            )

            conn.execute(
                f"""
                INSERT INTO reviews
                (
                    artwork_id,
                    reviewer,
                    rating,
                    comment,
                    created_at
                )
                SELECT
                    artwork_id,
                    COALESCE({reviewer_expression}, ''),
                    COALESCE({rating_expression}, 5),
                    COALESCE({comment_expression}, ''),
                    COALESCE({date_expression}, datetime('now'))
                FROM reviews_legacy
                """
            )

        conn.execute("DROP TABLE reviews_legacy")

    # --------------------------------------------------------
    # INDEX
    # --------------------------------------------------------

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_reviews_artwork
        ON reviews(artwork_id)
        """
    )

    conn.commit()
    conn.close()


initialize_database()


# ============================================================
# ARTWORK DATA
# ============================================================

def load_artworks():

    if not os.path.exists(CSV_FILE):

        st.error(
            "artworks.csv was not found. Please keep artworks.csv "
            "inside the same folder as app.py."
        )

        st.stop()

    df = pd.read_csv(CSV_FILE)

    df.columns = [
        str(column).strip()
        for column in df.columns
    ]

    required_columns = [
        "Artwork_ID",
        "Artwork_Name",
        "Artist",
        "Category",
        "Medium",
        "Year",
        "Country",
        "Price_USD",
        "Rating"
    ]

    missing = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing:

        st.error(
            "Your artworks.csv is missing these columns: "
            + ", ".join(missing)
        )

        st.stop()

    df["Artwork_ID"] = df["Artwork_ID"].astype(str)
    df["Artwork_Name"] = df["Artwork_Name"].astype(str)
    df["Artist"] = df["Artist"].astype(str)
    df["Category"] = df["Category"].astype(str)
    df["Medium"] = df["Medium"].astype(str)
    df["Country"] = df["Country"].astype(str)

    df["Price_USD"] = pd.to_numeric(
        df["Price_USD"],
        errors="coerce"
    ).fillna(0)

    df["Rating"] = pd.to_numeric(
        df["Rating"],
        errors="coerce"
    ).fillna(0)

    return df


artworks = load_artworks()


# ============================================================
# IMAGE GENERATION
# ============================================================

def get_font(size=30):

    possible_fonts = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
    ]

    for font_path in possible_fonts:

        if os.path.exists(font_path):

            try:
                return ImageFont.truetype(
                    font_path,
                    size
                )
            except Exception:
                pass

    return ImageFont.load_default()


def create_artwork_image(row):

    artwork_id = str(row["Artwork_ID"])

    image_path = os.path.join(
        IMAGE_DIR,
        f"{artwork_id}.png"
    )

    if os.path.exists(image_path):
        return image_path

    width = 900
    height = 600

    image = Image.new(
        "RGB",
        (width, height),
        (235, 235, 235)
    )

    draw = ImageDraw.Draw(image)

    category = str(row["Category"])
    title = str(row["Artwork_Name"])
    artist = str(row["Artist"])

    # Simple deterministic visual variation.
    seed = sum(
        ord(character)
        for character in artwork_id
    )

    background = (
        100 + seed % 80,
        90 + (seed * 2) % 90,
        110 + (seed * 3) % 80
    )

    draw.rectangle(
        [0, 0, width, height],
        fill=background
    )

    # Abstract shapes
    for i in range(9):

        x1 = (seed * (i + 3) * 37) % width
        y1 = (seed * (i + 5) * 29) % height

        size = 80 + ((seed + i * 41) % 180)

        x2 = min(width, x1 + size)
        y2 = min(height, y1 + size)

        if i % 3 == 0:

            draw.ellipse(
                [x1, y1, x2, y2],
                outline=(245, 245, 245),
                width=6
            )

        elif i % 3 == 1:

            draw.rectangle(
                [x1, y1, x2, y2],
                outline=(245, 245, 245),
                width=6
            )

        else:

            draw.line(
                [x1, y1, x2, y2],
                fill=(245, 245, 245),
                width=8
            )

    # Overlay
    draw.rectangle(
        [35, height - 155, width - 35, height - 35],
        fill=(20, 20, 20)
    )

    title_font = get_font(30)
    artist_font = get_font(20)
    category_font = get_font(17)

    draw.text(
        (60, height - 140),
        title[:38],
        fill=(255, 255, 255),
        font=title_font
    )

    draw.text(
        (60, height - 95),
        artist[:45],
        fill=(220, 220, 220),
        font=artist_font
    )

    draw.text(
        (60, height - 58),
        category[:55],
        fill=(190, 190, 190),
        font=category_font
    )

    image.save(image_path)

    return image_path


def prepare_images(df):

    paths = {}

    for _, row in df.iterrows():

        artwork_id = str(row["Artwork_ID"])

        try:

            paths[artwork_id] = create_artwork_image(row)

        except Exception:

            paths[artwork_id] = None

    return paths


image_paths = prepare_images(artworks)


# ============================================================
# DATABASE FUNCTIONS
# ============================================================

def get_like_count(artwork_id):

    conn = get_connection()

    row = conn.execute(
        """
        SELECT like_count
        FROM likes
        WHERE artwork_id=?
        """,
        (artwork_id,)
    ).fetchone()

    conn.close()

    if row is None:
        return 0

    return int(row["like_count"])


def like_artwork(artwork_id):

    conn = get_connection()

    existing = conn.execute(
        """
        SELECT artwork_id
        FROM likes
        WHERE artwork_id=?
        """,
        (artwork_id,)
    ).fetchone()

    if existing:

        conn.execute(
            """
            UPDATE likes
            SET like_count = like_count + 1
            WHERE artwork_id=?
            """,
            (artwork_id,)
        )

    else:

        conn.execute(
            """
            INSERT INTO likes
            (artwork_id, like_count)
            VALUES (?, 1)
            """,
            (artwork_id,)
        )

    conn.commit()
    conn.close()


def get_all_like_counts():

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT artwork_id, like_count
        FROM likes
        """
    ).fetchall()

    conn.close()

    return {
        row["artwork_id"]: row["like_count"]
        for row in rows
    }


def is_favorite(artwork_id):

    conn = get_connection()

    row = conn.execute(
        """
        SELECT artwork_id
        FROM favorites
        WHERE artwork_id=?
        """,
        (artwork_id,)
    ).fetchone()

    conn.close()

    return row is not None


def toggle_favorite(artwork_id):

    conn = get_connection()

    existing = conn.execute(
        """
        SELECT artwork_id
        FROM favorites
        WHERE artwork_id=?
        """,
        (artwork_id,)
    ).fetchone()

    if existing:

        conn.execute(
            """
            DELETE FROM favorites
            WHERE artwork_id=?
            """,
            (artwork_id,)
        )

        status = False

    else:

        conn.execute(
            """
            INSERT INTO favorites
            (artwork_id, created_at)
            VALUES (?, ?)
            """,
            (
                artwork_id,
                datetime.now().isoformat()
            )
        )

        status = True

    conn.commit()
    conn.close()

    return status


def get_favorite_ids():

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT artwork_id
        FROM favorites
        ORDER BY created_at DESC
        """
    ).fetchall()

    conn.close()

    return [
        row["artwork_id"]
        for row in rows
    ]


def add_review(
    artwork_id,
    reviewer,
    rating,
    comment
):

    conn = get_connection()

    conn.execute(
        """
        INSERT INTO reviews
        (
            artwork_id,
            reviewer,
            rating,
            comment,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            artwork_id,
            reviewer,
            rating,
            comment,
            datetime.now().isoformat()
        )
    )

    conn.commit()
    conn.close()


def get_reviews(artwork_id):

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT
            reviewer,
            rating,
            comment,
            created_at
        FROM reviews
        WHERE artwork_id=?
        ORDER BY id DESC
        """,
        (artwork_id,)
    ).fetchall()

    conn.close()

    return rows


def get_community_rating(artwork_id):

    conn = get_connection()

    row = conn.execute(
        """
        SELECT
            AVG(rating) AS average_rating,
            COUNT(*) AS review_count
        FROM reviews
        WHERE artwork_id=?
        """,
        (artwork_id,)
    ).fetchone()

    conn.close()

    if row is None or row["average_rating"] is None:
        return None, 0

    return (
        float(row["average_rating"]),
        int(row["review_count"])
    )


# ============================================================
# SESSION STATE
# ============================================================

if "page" not in st.session_state:
    st.session_state.page = "Home"

if st.session_state.page not in NAV_PAGES:
    st.session_state.page = "Home"

if "selected_artwork" not in st.session_state:
    st.session_state.selected_artwork = None


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown("## 🎨 ArtVault")

    st.caption(
        "Digital Art Exhibition & Community Platform"
    )

    st.divider()

    selected_page = st.radio(
        "Navigate",
        NAV_PAGES,
        index=NAV_PAGES.index(
            st.session_state.page
        )
    )

    st.session_state.page = selected_page

    st.divider()

    st.markdown("### Collection")

    st.write(
        f"🖼️ {len(artworks)} artworks"
    )

    st.write(
        f"👨‍🎨 {artworks['Artist'].nunique()} artists"
    )

    st.write(
        f"🌍 {artworks['Country'].nunique()} countries"
    )

    st.divider()

    st.caption(
        "ArtVault is a portfolio demonstration "
        "of data-driven art discovery."
    )


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def money(value):

    try:

        value = float(value)

        if value >= 1_000_000_000:
            return f"${value / 1_000_000_000:.1f}B"

        if value >= 1_000_000:
            return f"${value / 1_000_000:.1f}M"

        if value >= 1_000:
            return f"${value / 1_000:.1f}K"

        return f"${value:,.0f}"

    except Exception:

        return "N/A"


def safe_year(value):

    try:

        if pd.isna(value):
            return "Unknown"

        return str(int(float(value)))

    except Exception:

        return str(value)


def get_artwork(artwork_id):

    result = artworks[
        artworks["Artwork_ID"] == artwork_id
    ]

    if result.empty:
        return None

    return result.iloc[0]


def open_artwork(artwork_id):

    st.session_state.selected_artwork = artwork_id
    st.rerun()


def render_artwork_card(row, prefix="card"):

    artwork_id = str(row["Artwork_ID"])

    image_path = image_paths.get(artwork_id)

    with st.container(border=True):

        if image_path and os.path.exists(image_path):

            st.image(
                image_path,
                width="stretch"
            )

        else:

            st.info("Artwork preview unavailable.")

        st.markdown(
            f"**{row['Artwork_Name']}**"
        )

        st.caption(
            f"by {row['Artist']}"
        )

        st.write(
            f"🎨 {row['Category']}"
        )

        st.write(
            f"⭐ {float(row['Rating']):.1f}   "
            f"❤️ {get_like_count(artwork_id)}"
        )

        button_col1, button_col2 = st.columns(2)

        with button_col1:

            if st.button(
                "View",
                key=f"{prefix}_view_{artwork_id}",
                width="stretch"
            ):

                open_artwork(artwork_id)

        with button_col2:

            favorite_text = (
                "★ Saved"
                if is_favorite(artwork_id)
                else "☆ Save"
            )

            if st.button(
                favorite_text,
                key=f"{prefix}_fav_{artwork_id}",
                width="stretch"
            ):

                toggle_favorite(artwork_id)
                st.rerun()


def render_grid(df, prefix="grid"):

    if df.empty:

        st.info(
            "No artworks match your selection."
        )

        return

    rows = list(
        df.iterrows()
    )

    for start in range(0, len(rows), 3):

        batch = rows[start:start + 3]

        columns = st.columns(3)

        for column, (_, row) in zip(
            columns,
            batch
        ):

            with column:

                render_artwork_card(
                    row,
                    prefix=prefix
                )


# ============================================================
# ARTWORK DETAIL
# ============================================================

def render_artwork_detail():

    artwork_id = st.session_state.selected_artwork

    row = get_artwork(artwork_id)

    if row is None:

        st.session_state.selected_artwork = None
        st.rerun()

    if st.button(
        "← Back to collection",
        key="detail_back"
    ):

        st.session_state.selected_artwork = None
        st.rerun()

    st.markdown(
        f"# {row['Artwork_Name']}"
    )

    st.caption(
        f"Artwork ID: {row['Artwork_ID']}"
    )

    left, right = st.columns(
        [1.35, 1]
    )

    with left:

        image_path = image_paths.get(
            artwork_id
        )

        if image_path and os.path.exists(image_path):

            st.image(
                image_path,
                width="stretch"
            )

    with right:

        st.markdown(
            f"### {row['Artwork_Name']}"
        )

        st.write(
            f"**Artist:** {row['Artist']}"
        )

        st.write(
            f"**Category:** {row['Category']}"
        )

        st.write(
            f"**Medium:** {row['Medium']}"
        )

        st.write(
            f"**Year:** {safe_year(row['Year'])}"
        )

        st.write(
            f"**Country:** {row['Country']}"
        )

        st.write(
            f"**Listed Value:** {money(row['Price_USD'])}"
        )

        st.write(
            f"⭐ **Original Rating:** "
            f"{float(row['Rating']):.1f}/5"
        )

        community_rating, review_count = (
            get_community_rating(artwork_id)
        )

        if community_rating is not None:

            st.write(
                f"🌟 **Community Rating:** "
                f"{community_rating:.1f}/5 "
                f"({review_count} reviews)"
            )

        else:

            st.write(
                "🌟 **Community Rating:** "
                "No reviews yet"
            )

        st.write(
            f"❤️ **Likes:** "
            f"{get_like_count(artwork_id)}"
        )

        like_col, fav_col = st.columns(2)

        with like_col:

            if st.button(
                "❤️ Like Artwork",
                key=f"detail_like_{artwork_id}",
                width="stretch"
            ):

                like_artwork(artwork_id)
                st.rerun()

        with fav_col:

            favorite_text = (
                "★ Remove Favorite"
                if is_favorite(artwork_id)
                else "☆ Add Favorite"
            )

            if st.button(
                favorite_text,
                key=f"detail_fav_{artwork_id}",
                width="stretch"
            ):

                toggle_favorite(artwork_id)
                st.rerun()

    st.divider()

    st.markdown("## 💬 Community Reviews")

    reviews = get_reviews(artwork_id)

    if reviews:

        for review in reviews:

            with st.container(border=True):

                st.markdown(
                    f"**{review['reviewer']}**"
                )

                st.write(
                    "⭐ " * int(review["rating"])
                )

                st.write(
                    review["comment"]
                )

                st.caption(
                    review["created_at"][:16]
                )

    else:

        st.info(
            "No reviews yet. Be the first to review this artwork."
        )

    st.markdown("### Add a Review")

    with st.form(
        f"review_form_{artwork_id}"
    ):

        reviewer = st.text_input(
            "Your name"
        )

        rating = st.slider(
            "Rating",
            min_value=1,
            max_value=5,
            value=5
        )

        comment = st.text_area(
            "Your review",
            max_chars=500
        )

        submitted = st.form_submit_button(
            "Submit Review",
            width="stretch"
        )

        if submitted:

            if not reviewer.strip():

                st.warning(
                    "Please enter your name."
                )

            elif not comment.strip():

                st.warning(
                    "Please write a review."
                )

            else:

                add_review(
                    artwork_id,
                    reviewer.strip(),
                    rating,
                    comment.strip()
                )

                st.success(
                    "Review added successfully!"
                )

                st.rerun()


# ============================================================
# HOME
# ============================================================

def page_home():

    st.markdown(
        '<div class="main-title">🎨 ArtVault</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="subtitle">'
        'Discover, explore and interact with artworks '
        'from different artists, styles and cultures.'
        '</div>',
        unsafe_allow_html=True
    )

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    like_counts = get_all_like_counts()

    total_likes = sum(
        like_counts.values()
    )

    total_artists = artworks[
        "Artist"
    ].nunique()

    total_categories = artworks[
        "Category"
    ].nunique()

    total_countries = artworks[
        "Country"
    ].nunique()

    metric1, metric2, metric3, metric4 = st.columns(4)

    with metric1:

        st.metric(
            "Artworks",
            len(artworks)
        )

    with metric2:

        st.metric(
            "Artists",
            total_artists
        )

    with metric3:

        st.metric(
            "Categories",
            total_categories
        )

    with metric4:

        st.metric(
            "Community Likes",
            total_likes
        )

    st.divider()

    # --------------------------------------------------------
    # Featured Artwork
    # --------------------------------------------------------

    st.markdown(
        "## ✨ Featured Artwork"
    )

    featured = artworks.sort_values(
        by=["Rating", "Artwork_Name"],
        ascending=[False, True]
    ).iloc[0]

    left, right = st.columns(
        [1.3, 1]
    )

    with left:

        featured_id = str(
            featured["Artwork_ID"]
        )

        featured_path = image_paths.get(
            featured_id
        )

        if featured_path:

            st.image(
                featured_path,
                width="stretch"
            )

    with right:

        st.markdown(
            f"### {featured['Artwork_Name']}"
        )

        st.write(
            f"**Artist:** {featured['Artist']}"
        )

        st.write(
            f"**Category:** {featured['Category']}"
        )

        st.write(
            f"**Medium:** {featured['Medium']}"
        )

        st.write(
            f"**Rating:** ⭐ "
            f"{float(featured['Rating']):.1f}/5"
        )

        if st.button(
            "Explore Artwork",
            key="home_featured",
            width="stretch"
        ):

            open_artwork(featured_id)

    st.divider()

    # --------------------------------------------------------
    # Popular Artworks
    # --------------------------------------------------------

    st.markdown(
        "## 🔥 Popular in ArtVault"
    )

    popular = artworks.copy()

    popular["Likes"] = popular[
        "Artwork_ID"
    ].map(
        like_counts
    ).fillna(0)

    popular = popular.sort_values(
        by=["Likes", "Rating"],
        ascending=False
    ).head(6)

    render_grid(
        popular,
        prefix="home_popular"
    )

    st.divider()

    # --------------------------------------------------------
    # Explore Categories
    # --------------------------------------------------------

    st.markdown(
        "## 🧭 Explore Categories"
    )

    categories = sorted(
        artworks["Category"]
        .dropna()
        .unique()
        .tolist()
    )

    category_columns = st.columns(
        min(4, max(1, len(categories)))
    )

    for index, category in enumerate(categories):

        with category_columns[
            index % len(category_columns)
        ]:

            count = len(
                artworks[
                    artworks["Category"] == category
                ]
            )

            st.metric(
                category,
                count
            )


# ============================================================
# EXHIBITION
# ============================================================

def page_exhibition():

    st.markdown(
        '<div class="section-title">'
        '🖼️ Exhibition'
        '</div>',
        unsafe_allow_html=True
    )

    st.caption(
        "Browse the complete ArtVault collection."
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        categories = [
            "All"
        ] + sorted(
            artworks["Category"]
            .dropna()
            .unique()
            .tolist()
        )

        category = st.selectbox(
            "Category",
            categories,
            key="exhibition_category"
        )

    with col2:

        countries = [
            "All"
        ] + sorted(
            artworks["Country"]
            .dropna()
            .unique()
            .tolist()
        )

        country = st.selectbox(
            "Country",
            countries,
            key="exhibition_country"
        )

    with col3:

        sort_option = st.selectbox(
            "Sort by",
            [
                "Rating",
                "Artwork Name",
                "Artist",
                "Year",
                "Price"
            ],
            key="exhibition_sort"
        )

    filtered = artworks.copy()

    if category != "All":

        filtered = filtered[
            filtered["Category"] == category
        ]

    if country != "All":

        filtered = filtered[
            filtered["Country"] == country
        ]

    if sort_option == "Rating":

        filtered = filtered.sort_values(
            "Rating",
            ascending=False
        )

    elif sort_option == "Artwork Name":

        filtered = filtered.sort_values(
            "Artwork_Name"
        )

    elif sort_option == "Artist":

        filtered = filtered.sort_values(
            "Artist"
        )

    elif sort_option == "Year":

        filtered = filtered.sort_values(
            "Year",
            ascending=False
        )

    elif sort_option == "Price":

        filtered = filtered.sort_values(
            "Price_USD",
            ascending=False
        )

    st.write(
        f"Showing **{len(filtered)}** artworks"
    )

    render_grid(
        filtered,
        prefix="exhibition"
    )


# ============================================================
# SEARCH
# ============================================================

def page_search():

    st.markdown(
        '<div class="section-title">'
        '🔎 Search ArtVault'
        '</div>',
        unsafe_allow_html=True
    )

    query = st.text_input(
        "Search artworks, artists, categories, countries or mediums",
        placeholder="Try: Van Gogh, India, Oil, Impressionism..."
    )

    filtered = artworks.copy()

    if query.strip():

        search_query = query.strip()

        mask = (
            filtered["Artwork_Name"]
            .str.contains(
                search_query,
                case=False,
                regex=False,
                na=False
            )
            |
            filtered["Artist"]
            .str.contains(
                search_query,
                case=False,
                regex=False,
                na=False
            )
            |
            filtered["Category"]
            .str.contains(
                search_query,
                case=False,
                regex=False,
                na=False
            )
            |
            filtered["Medium"]
            .str.contains(
                search_query,
                case=False,
                regex=False,
                na=False
            )
            |
            filtered["Country"]
            .str.contains(
                search_query,
                case=False,
                regex=False,
                na=False
            )
        )

        filtered = filtered[mask]

    st.write(
        f"**{len(filtered)}** result(s)"
    )

    render_grid(
        filtered,
        prefix="search"
    )


# ============================================================
# ARTISTS
# ============================================================

def page_artists():

    st.markdown(
        '<div class="section-title">'
        '👨‍🎨 Artist Explorer'
        '</div>',
        unsafe_allow_html=True
    )

    artist_summary = (
        artworks
        .groupby("Artist")
        .agg(
            Artworks=("Artwork_ID", "count"),
            Average_Rating=("Rating", "mean"),
            Countries=("Country", "nunique")
        )
        .reset_index()
        .sort_values(
            "Artworks",
            ascending=False
        )
    )

    selected_artist = st.selectbox(
        "Select an artist",
        [
            "All Artists"
        ] + artist_summary["Artist"].tolist()
    )

    if selected_artist == "All Artists":

        st.dataframe(
            artist_summary,
            hide_index=True,
            width="stretch"
        )

        st.divider()

        st.markdown(
            "## Featured Artists"
        )

        featured_artists = artist_summary.head(6)

        columns = st.columns(3)

        for index, (_, artist) in enumerate(
            featured_artists.iterrows()
        ):

            with columns[index % 3]:

                st.metric(
                    artist["Artist"],
                    int(artist["Artworks"])
                )

                st.caption(
                    f"Average rating: "
                    f"{artist['Average_Rating']:.1f}/5"
                )

    else:

        artist_df = artworks[
            artworks["Artist"] == selected_artist
        ]

        st.markdown(
            f"## {selected_artist}"
        )

        metric1, metric2, metric3 = st.columns(3)

        with metric1:

            st.metric(
                "Artworks",
                len(artist_df)
            )

        with metric2:

            st.metric(
                "Average Rating",
                f"{artist_df['Rating'].mean():.1f}"
            )

        with metric3:

            st.metric(
                "Countries",
                artist_df["Country"].nunique()
            )

        st.divider()

        render_grid(
            artist_df,
            prefix="artist"
        )


# ============================================================
# FAVORITES
# ============================================================

def page_favorites():

    st.markdown(
        '<div class="section-title">'
        '⭐ My Favorites'
        '</div>',
        unsafe_allow_html=True
    )

    favorite_ids = get_favorite_ids()

    if not favorite_ids:

        st.info(
            "You have no favorite artworks yet."
        )

        st.write(
            "Use the ☆ Save button on any artwork "
            "to add it to your favorites."
        )

        return

    favorite_df = artworks[
        artworks["Artwork_ID"].isin(
            favorite_ids
        )
    ].copy()

    # Preserve favorite order
    favorite_df["_order"] = favorite_df[
        "Artwork_ID"
    ].apply(
        lambda x: (
            favorite_ids.index(x)
            if x in favorite_ids
            else 99999
        )
    )

    favorite_df = favorite_df.sort_values(
        "_order"
    )

    st.write(
        f"You have saved "
        f"**{len(favorite_df)}** artwork(s)."
    )

    render_grid(
        favorite_df,
        prefix="favorites"
    )


# ============================================================
# MARKETPLACE
# ============================================================

def page_marketplace():

    st.markdown(
        '<div class="section-title">'
        '🛍️ Art Marketplace'
        '</div>',
        unsafe_allow_html=True
    )

    st.caption(
        "A demonstration marketplace layer for exploring "
        "artwork values. No real transactions are processed."
    )

    min_price = float(
        artworks["Price_USD"].min()
    )

    max_price = float(
        artworks["Price_USD"].max()
    )

    if max_price <= min_price:

        filtered = artworks.copy()

        st.info(
            "All artworks currently have the same listed value."
        )

    else:

        price_range = st.slider(
            "Maximum listed value",
            min_value=0.0,
            max_value=max_price,
            value=max_price,
            step=max(
                1.0,
                max_price / 100
            ),
            format="$%.0f"
        )

        filtered = artworks[
            artworks["Price_USD"] <= price_range
        ]

    col1, col2 = st.columns(2)

    with col1:

        st.metric(
            "Available Listings",
            len(filtered)
        )

    with col2:

        if not filtered.empty:

            average_price = filtered[
                "Price_USD"
            ].mean()

            st.metric(
                "Average Listed Value",
                money(average_price)
            )

    st.divider()

    if filtered.empty:

        st.warning(
            "No artworks fall within this price range."
        )

    else:

        marketplace_df = filtered.sort_values(
            "Price_USD",
            ascending=True
        )

        render_grid(
            marketplace_df,
            prefix="marketplace"
        )


# ============================================================
# ANALYTICS
# ============================================================

def page_analytics():

    st.markdown(
        '<div class="section-title">'
        '📊 ArtVault Analytics'
        '</div>',
        unsafe_allow_html=True
    )

    like_counts = get_all_like_counts()

    analytics_df = artworks.copy()

    analytics_df["Likes"] = (
        analytics_df["Artwork_ID"]
        .map(like_counts)
        .fillna(0)
        .astype(int)
    )

    # --------------------------------------------------------
    # KPI
    # --------------------------------------------------------

    total_value = analytics_df[
        "Price_USD"
    ].sum()

    average_rating = analytics_df[
        "Rating"
    ].mean()

    most_liked = analytics_df.sort_values(
        "Likes",
        ascending=False
    ).iloc[0]

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    with kpi1:

        st.metric(
            "Total Artworks",
            len(analytics_df)
        )

    with kpi2:

        st.metric(
            "Average Rating",
            f"{average_rating:.2f}/5"
        )

    with kpi3:

        st.metric(
            "Collection Value",
            money(total_value)
        )

    with kpi4:

        st.metric(
            "Most Liked",
            most_liked["Artwork_Name"][:18]
        )

    st.divider()

    # --------------------------------------------------------
    # CATEGORY ANALYSIS
    # --------------------------------------------------------

    left, right = st.columns(2)

    with left:

        st.markdown(
            "### 🎨 Artworks by Category"
        )

        category_counts = (
            analytics_df["Category"]
            .value_counts()
        )

        st.bar_chart(
            category_counts
        )

    with right:

        st.markdown(
            "### 🌍 Artworks by Country"
        )

        country_counts = (
            analytics_df["Country"]
            .value_counts()
            .head(10)
        )

        st.bar_chart(
            country_counts
        )

    st.divider()

    # --------------------------------------------------------
    # RATING DISTRIBUTION
    # --------------------------------------------------------

    left, right = st.columns(2)

    with left:

        st.markdown(
            "### ⭐ Rating Distribution"
        )

        rating_data = (
            analytics_df["Rating"]
            .round(0)
            .value_counts()
            .sort_index()
        )

        st.bar_chart(
            rating_data
        )

    with right:

        st.markdown(
            "### ❤️ Community Engagement"
        )

        engagement = analytics_df[
            [
                "Artwork_Name",
                "Artist",
                "Likes"
            ]
        ].sort_values(
            "Likes",
            ascending=False
        ).head(10)

        st.dataframe(
            engagement,
            hide_index=True,
            width="stretch"
        )

    st.divider()

    # --------------------------------------------------------
    # TOP ARTWORKS
    # --------------------------------------------------------

    st.markdown(
        "### 🏆 Top Rated Artworks"
    )

    top_rated = analytics_df[
        [
            "Artwork_Name",
            "Artist",
            "Category",
            "Rating",
            "Likes"
        ]
    ].sort_values(
        "Rating",
        ascending=False
    ).head(10)

    st.dataframe(
        top_rated,
        hide_index=True,
        width="stretch"
    )

    st.divider()

    # --------------------------------------------------------
    # DOWNLOAD DATA
    # --------------------------------------------------------

    csv_data = analytics_df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "⬇️ Download Analytics CSV",
        data=csv_data,
        file_name="artvault_analytics.csv",
        mime="text/csv",
        width="content"
    )


# ============================================================
# MAIN ROUTER
# ============================================================

# Detail view is controlled separately from sidebar navigation.
# This prevents the old "Details is not in list" session-state bug.

if st.session_state.selected_artwork:

    render_artwork_detail()

else:

    if st.session_state.page == "Home":

        page_home()

    elif st.session_state.page == "Exhibition":

        page_exhibition()

    elif st.session_state.page == "Search":

        page_search()

    elif st.session_state.page == "Artists":

        page_artists()

    elif st.session_state.page == "Favorites":

        page_favorites()

    elif st.session_state.page == "Marketplace":

        page_marketplace()

    elif st.session_state.page == "Analytics":

        page_analytics()

    else:

        st.session_state.page = "Home"
        st.rerun()