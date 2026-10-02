"""Fill timeline.db with made-up people, posts, replies, likes and follows, so the app looks alive.

Run it on an empty timeline:  make reset seed   (or: python3 seed.py)

Every made-up person has the same password, PASSWORD below, so you can log in as any of them.
Everything is saved through the model in server.py, so the made-up data follows the same
rules as real data. The people and their posts are invented.
"""

import random
import time

import server

PASSWORD = "timeline123"

PEOPLE = ["Aiko", "Ben", "Sofia", "Kenta", "Lucas", "Mei",
          "Yuki", "Emma", "Daniel", "Hana", "Nora", "Ravi"]

# The posts, oldest first, because a post's id gives its place on the timeline.
# Each one: a key (so that a reply can name the post it answers), who wrote it,
# how many minutes ago, what it says, and the key of the post it answers (or None).
POSTS = [
    ("welcome", "Kenta", 4300, "Welcome to all the new exchange students! If you need help "
                               "finding anything around Hirakata, just ask 😊", None),
    (None, "Sofia", 4290, "Thank you! Where is the closest supermarket to the dorms?", "welcome"),
    (None, "Kenta", 4280, "Down the hill, then left at the bakery. It's open until 11 pm.", "welcome"),

    ("quiz", "Ben", 4100, "First kanji quiz tomorrow. 42 characters. Wish me luck.", None),
    (None, "Yuki", 4090, "頑張って！ Write each one five times, it really works.", "quiz"),
    (None, "Ben", 4080, "Five times each... that's 210. Okay. Coffee first.", "quiz"),

    ("curry", "Mei", 3800, "The cafeteria curry is 450 yen and honestly the best thing on campus.", None),

    ("kyoto", "Lucas", 3500, "Anyone want to go to Kyoto on Saturday? Thinking Fushimi Inari early, "
                             "before the crowds.", None),
    (None, "Emma", 3490, "Yes! What time?", "kyoto"),
    (None, "Lucas", 3480, "Train at 7:10 from Hirakatashi. Meet at the ticket gates.", "kyoto"),
    (None, "Hana", 3470, "Bring water, the walk to the top is longer than it looks.", "kyoto"),

    ("exchange", "Hana", 2900, "Language exchange table at lunch today. I help with Japanese, you "
                               "help with English. Everyone welcome!", None),
    (None, "Daniel", 2890, "I'll be there. My keigo needs serious help.", "exchange"),

    ("essay", "Yuki", 2600, "Finally finished my essay on Meiji-era literature. 3,000 words. "
                            "Time to sleep for 12 hours.", None),

    ("okonomiyaki", "Ravi", 2300, "Tried okonomiyaki in Osaka for the first time. I understand now. "
                                  "I understand everything.", None),
    (None, "Mei", 2290, "Wait until you try takoyaki from a street stall in Dotonbori.", "okonomiyaki"),

    ("umbrella", "Nora", 2000, "Lost a blue umbrella in the library, 2nd floor. If you find it, "
                               "it misses me.", None),
    (None, "Kenta", 1990, "Try the lost and found at the front desk!", "umbrella"),
    (None, "Nora", 1980, "Found it! Thank you Kenta 🙏", "umbrella"),

    ("inari", "Emma", 1400, "Fushimi Inari at 8 am was magical. Thousands of gates and almost "
                            "nobody there. Thanks for planning, Lucas!", None),

    ("miso", "Daniel", 1100, "My homestay family taught me to make miso soup. First try: salty. "
                             "Second try: good!", None),
    (None, "Sofia", 1090, "Recipe please!!", "miso"),

    ("notes", "Sofia", 900, "Does anyone have the notes from Tuesday's economics class?", None),
    (None, "Ravi", 890, "I'll share mine after class.", "notes"),

    ("quiz-result", "Ben", 300, "Got 40 out of 42 on the kanji quiz!!! 書いて覚える really works.", None),
    (None, "Yuki", 290, "すごい！Told you 😄", "quiz-result"),
    (None, "Aiko", 280, "Congrats Ben!", "quiz-result"),

    ("leaves", "Aiko", 200, "The leaves on campus are starting to turn red. Perfect walking "
                            "weather 🍁", None),

    ("jlpt", "Mei", 120, "JLPT N3 study group tonight, room 204, 7 pm. Bring snacks.", None),
    (None, "Hana", 110, "I'll bring onigiri.", "jlpt"),

    ("typhoon", "Lucas", 45, "typhoon tomorow?? classes??", None),
    (None, "Kenta", 40, "Check the university website in the morning. They post any changes there.",
     "typhoon"),

    ("gyoza", "Ravi", 10, "Just joined the cooking club. Next week: gyoza from scratch!", None),
]

# Posts their authors edited afterwards, and posts their authors deleted.
EDITS = {"typhoon": "Is there a typhoon coming tomorrow? Does anyone know if classes are cancelled?"}
DELETES = ["notes"]


def stamp(minutes_ago):
    """The time some minutes ago, in the form the database keeps: 2026-10-02 15:42."""
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time() - minutes_ago * 60))


def seed(db_path):
    server.create_tables(db_path)
    connection = server.connect(db_path)
    people_already = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    connection.close()
    if people_already:
        raise SystemExit("The timeline is not empty, so nothing was added. "
                         "Run `make reset seed` to start again with only the made-up data.")

    chance = random.Random(2026)   # a fixed start, so the made-up likes are the same every time

    # People: each joined a few days before the first post.
    user_ids = {}
    for name in PEOPLE:
        token = server.sign_up(db_path, name, PASSWORD, joined_at=stamp(chance.randint(4400, 7000)))
        user_ids[name] = server.user_for_token(db_path, token)["id"]
        server.log_out(db_path, token)

    # Posts and replies, oldest first.
    post_ids = {}
    all_post_ids = []
    for key, author, minutes_ago, text, answers in POSTS:
        reply_to = post_ids[answers] if answers else None
        row = server.save_post(db_path, user_ids[author], text, reply_to, posted_at=stamp(minutes_ago))
        all_post_ids.append((row["id"], author, answers is None))
        if key:
            post_ids[key] = row["id"]

    # Likes: a post gets up to 7, a reply up to 3, never from its own author.
    for post_id, author, is_post in all_post_ids:
        others = [name for name in PEOPLE if name != author]
        for name in chance.sample(others, chance.randint(1 if is_post else 0, 7 if is_post else 3)):
            server.like_post(db_path, user_ids[name], post_id)

    # Follows: everyone follows between 3 and 7 others.
    follows = 0
    for name in PEOPLE:
        others = [other for other in PEOPLE if other != name]
        for other in chance.sample(others, chance.randint(3, 7)):
            server.follow(db_path, user_ids[name], other)
            follows += 1

    for key, text in EDITS.items():
        author = next(author for k, author, _, _, _ in POSTS if k == key)
        server.edit_post(db_path, user_ids[author], post_ids[key], text)
    for key in DELETES:
        author = next(author for k, author, _, _, _ in POSTS if k == key)
        server.delete_post(db_path, user_ids[author], post_ids[key])

    # Counted at the end: deleting a post also deletes its likes.
    likes = sum(row["likes"] for row in server.like_counts(db_path))
    return {"people": len(PEOPLE), "posts": len(POSTS), "likes": likes, "follows": follows}


if __name__ == "__main__":
    made = seed(server.DB_PATH)
    print(f"Made {made['people']} people, {made['posts']} posts and replies, "
          f"{made['likes']} likes and {made['follows']} follows.")
    print(f"Log in as any of them with the password {PASSWORD}, for example: "
          + ", ".join(PEOPLE[:3]) + ".")
