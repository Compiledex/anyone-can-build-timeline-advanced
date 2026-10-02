"""Fill timeline.db with made-up people, posts, replies, reposts, quotes, likes, follows, bookmarks
and messages, so the app looks alive. Notifications come by themselves: the model makes them.

Run it on an empty timeline:  make reset seed   (or: python3 seed.py)

Six of the made-up posts get pictures: simple drawings made by drawings.py. To add them to a
timeline that was filled before they existed:  make pictures

Then give your own account something to see:  make welcome NAME=Alex
(or: python3 seed.py --welcome Alex). The made-up people follow you, mention you, react to a post
of yours, and send you messages, and you get some bookmarks, all in the last two hours.

Every made-up person has the same password, PASSWORD below, so you can log in as any of them.
Everything is saved through the model in model.py, so the made-up data follows the same
rules as real data. The people, their posts and their messages are invented.
"""

import argparse
import random
import time

import drawings
import model

PASSWORD = "timeline123"

# The people, and their bios.
PEOPLE = {
    "Aiko": "Hirakata local, 3rd year. English & Japanese. Ask me about ramen near campus 🍜",
    "Ben": "Exchange student from Canada. Learning kanji one stroke at a time.",
    "Sofia": "From Madrid. Economics and Japanese. Coffee first.",
    "Kenta": "Student staff at the international office. Happy to help!",
    "Lucas": "Brazil → Osaka. Weekend trip planner.",
    "Mei": "Curry critic. Runs the JLPT N3 study group.",
    "Yuki": "Literature major. Meiji novels and too much tea.",
    "Emma": "Photography and temples 📷",
    "Daniel": "Homestay life in Hirakata. Learning to cook.",
    "Hana": "Language exchange host. 日本語 ⇄ English",
    "Nora": "From Norway. Specialist in losing umbrellas.",
    "Ravi": "Cooking club. Okonomiyaki convert.",
}

# Everything that is posted, oldest first, because a post's id gives its place on the timeline.
# Each one: a key (so that later ones can name it), who, how many minutes ago, the words,
# and what it is: None for a post, "key" for a reply to that post,
# ("repost", "key") for a repost, or ("quote", "key") for a quote.
POSTS = [
    ("welcome", "Kenta", 4300, "Welcome to all the new exchange students! If you need help "
                               "finding anything around #Hirakata, just ask 😊", None),
    (None, "Sofia", 4290, "Thank you! Where is the closest supermarket to the dorms?", "welcome"),
    (None, "Kenta", 4280, "Down the hill, then left at the bakery. It's open until 11 pm.", "welcome"),

    ("quiz", "Ben", 4100, "First #kanji quiz tomorrow. 42 characters. Wish me luck.", None),
    (None, "Yuki", 4090, "頑張って！ Write each one five times, it really works.", "quiz"),
    (None, "Ben", 4080, "Five times each... that's 210. Okay. Coffee first.", "quiz"),

    ("curry", "Mei", 3800, "The cafeteria curry is 450 yen and honestly the best thing on campus. #foodie", None),

    ("kyoto", "Lucas", 3500, "Anyone want to go to #Kyoto on Saturday? Thinking Fushimi Inari early, "
                             "before the crowds.", None),
    (None, "Emma", 3490, "Yes! What time?", "kyoto"),
    (None, "Lucas", 3480, "Train at 7:10 from Hirakatashi. Meet at the ticket gates.", "kyoto"),
    (None, "Hana", 3470, "Bring water, the walk to the top is longer than it looks.", "kyoto"),
    ("kyoto-repost", "Emma", 3460, "", ("repost", "kyoto")),

    ("exchange", "Hana", 2900, "Language exchange table at lunch today. I help with Japanese, you "
                               "help with English. Everyone welcome! #languageexchange", None),
    (None, "Daniel", 2890, "I'll be there. My keigo needs serious help.", "exchange"),

    ("essay", "Yuki", 2600, "Finally finished my essay on Meiji-era literature. 3,000 words. "
                            "Time to sleep for 12 hours.", None),

    ("okonomiyaki", "Ravi", 2300, "Tried okonomiyaki in #Osaka for the first time. I understand now. "
                                  "I understand everything. #foodie", None),
    (None, "Mei", 2290, "Wait until you try takoyaki from a street stall in Dotonbori.", "okonomiyaki"),
    ("okonomiyaki-quote", "Aiko", 2280, "Welcome to Kansai, @Ravi. There is no going back now 😄",
     ("quote", "okonomiyaki")),

    ("umbrella", "Nora", 2000, "Lost a blue umbrella in the library, 2nd floor. If you find it, "
                               "it misses me.", None),
    (None, "Kenta", 1990, "Try the lost and found at the front desk!", "umbrella"),
    (None, "Nora", 1980, "Found it! Thank you @Kenta 🙏", "umbrella"),

    ("inari", "Emma", 1400, "Fushimi Inari at 8 am was magical. Thousands of gates and almost "
                            "nobody there. Thanks for planning, @Lucas! #Kyoto", None),
    ("inari-repost", "Lucas", 1390, "", ("repost", "inari")),

    ("miso", "Daniel", 1100, "My homestay family taught me to make miso soup. First try: salty. "
                             "Second try: good! #homestay", None),
    (None, "Sofia", 1090, "Recipe please!!", "miso"),

    ("notes", "Sofia", 900, "Does anyone have the notes from Tuesday's economics class?", None),
    (None, "Ravi", 890, "I'll share mine after class.", "notes"),

    ("quiz-result", "Ben", 300, "Got 40 out of 42 on the #kanji quiz!!! 書いて覚える really works.", None),
    (None, "Yuki", 290, "すごい！Told you 😄", "quiz-result"),
    (None, "Aiko", 280, "Congrats @Ben!", "quiz-result"),
    ("quiz-quote", "Mei", 270, "This is the energy we need at the #JLPT study group tonight",
     ("quote", "quiz-result")),

    ("leaves", "Aiko", 200, "The leaves on campus are starting to turn red. Perfect walking "
                            "weather 🍁 #autumn #Hirakata", None),
    ("leaves-repost", "Hana", 190, "", ("repost", "leaves")),

    ("jlpt", "Mei", 120, "#JLPT N3 study group tonight, room 204, 7 pm. Bring snacks.", None),
    (None, "Hana", 110, "I'll bring onigiri.", "jlpt"),
    (None, "Ben", 100, "Count me in. @Aiko are you coming?", "jlpt"),

    ("typhoon", "Lucas", 45, "typhoon tomorow?? classes??", None),
    (None, "Kenta", 40, "Check the university website in the morning. They post any changes there.",
     "typhoon"),

    ("gyoza", "Ravi", 10, "Just joined the cooking club. Next week: gyoza from scratch! #foodie", None),
]

# Posts their authors edited afterwards, and posts their authors deleted.
EDITS = {"typhoon": "Is there a typhoon coming tomorrow? Does anyone know if classes are cancelled?"}
DELETES = ["notes"]

# Posts some people saved: who, and the keys of the posts.
BOOKMARKS = {"Aiko": ["jlpt", "miso"], "Ben": ["kyoto"], "Sofia": ["welcome", "miso"]}

# Conversations: who sent it, to whom, how many minutes ago, and the words. Oldest first.
MESSAGES = [
    ("Mei", "Aiko", 2500, "Hi Aiko! Are you coming to the study group this week?"),
    ("Aiko", "Mei", 2490, "Yes! Can I bring Ben? He just started kanji."),
    ("Mei", "Aiko", 2480, "Of course, the more the better."),
    ("Kenta", "Aiko", 600, "Hey, could you help at the welcome desk on Friday?"),
    ("Aiko", "Kenta", 590, "Sure, what time?"),
    ("Kenta", "Aiko", 95, "From 10 to 12. Thank you so much!"),
    ("Kenta", "Aiko", 94, "I'll bring coffee ☕"),
    ("Lucas", "Emma", 3450, "Still on for 7:10 tomorrow?"),
    ("Emma", "Lucas", 3440, "Yes! I'll bring the camera."),
    ("Yuki", "Ben", 4070, "If you want, I can quiz you before the test."),
    ("Ben", "Yuki", 4060, "That would be amazing, thank you!"),
    ("Ben", "Yuki", 295, "40 out of 42!! Thank you for the quiz 🙏"),
]


def stamp(minutes_ago):
    """The time some minutes ago, in the form the database keeps: 2026-10-02 15:42."""
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time() - minutes_ago * 60))


def at(minutes_ago):
    """Set the model's clock back, so that what happens next says the right time.

    The model asks model.now() for the time of everything it saves: a like, a follow,
    a notification. Made-up events happened in the past, so the seed sets the clock back
    for each one. Only the seed does this; the server always uses the real time.
    """
    model.now = lambda: stamp(minutes_ago)


def seed(db_path):
    real_now = model.now
    try:
        return fill(db_path)
    finally:
        model.now = real_now   # the real clock again, whatever happened


def fill(db_path):
    model.create_tables(db_path)
    connection = model.connect(db_path)
    people_already = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    connection.close()
    if people_already:
        raise SystemExit("The timeline is not empty, so nothing was added. "
                         "Run `make reset seed` to start again with only the made-up data.")

    chance = random.Random(2026)   # a fixed start, so the made-up likes are the same every time

    # People, with their bios: each joined a few days before the first post.
    user_ids = {}
    for name, bio in PEOPLE.items():
        at(chance.randint(4400, 7000))
        token = model.sign_up(db_path, name, PASSWORD)
        user_ids[name] = model.user_for_token(db_path, token)["id"]
        model.log_out(db_path, token)
        model.edit_profile(db_path, user_ids[name], bio)

    # Follows: everyone follows between 3 and 7 others, before the first post.
    names = list(PEOPLE)
    follows = 0
    for name in names:
        for other in chance.sample([o for o in names if o != name], chance.randint(3, 7)):
            at(chance.randint(4310, 4390))
            model.follow(db_path, user_ids[name], other)
            follows += 1

    # Posts, replies, reposts and quotes, oldest first.
    post_ids = {}
    posted = []   # (id, author, minutes ago, whether it can be liked much)
    for key, author, minutes_ago, text, what in POSTS:
        at(minutes_ago)
        if isinstance(what, tuple) and what[0] == "repost":
            row = model.repost(db_path, user_ids[author], post_ids[what[1]])
        elif isinstance(what, tuple) and what[0] == "quote":
            row = model.save_post(db_path, user_ids[author], text, quote_of=post_ids[what[1]])
        else:
            reply_to = post_ids[what] if what else None
            row = model.save_post(db_path, user_ids[author], text, reply_to)
        if key:
            post_ids[key] = row["id"]
        if not (isinstance(what, tuple) and what[0] == "repost"):
            posted.append((row["id"], author, minutes_ago, what is None))

    # Likes: a post gets up to 7, a reply up to 3, never from its own author,
    # each a little while after the post.
    for post_id, author, minutes_ago, is_post in posted:
        others = [name for name in names if name != author]
        for name in chance.sample(others, chance.randint(1 if is_post else 0, 7 if is_post else 3)):
            at(max(1, minutes_ago - chance.randint(1, 60)))
            model.like_post(db_path, user_ids[name], post_id)

    for key, text in EDITS.items():
        author = next(author for k, author, _, _, _ in POSTS if k == key)
        at(next(m for k, _, m, _, _ in POSTS if k == key) - 2)
        model.edit_post(db_path, user_ids[author], post_ids[key], text)
    for key in DELETES:
        author = next(author for k, author, _, _, _ in POSTS if k == key)
        at(next(m for k, _, m, _, _ in POSTS if k == key) - 30)
        model.delete_post(db_path, user_ids[author], post_ids[key])

    add_pictures(db_path)

    for name, keys in BOOKMARKS.items():
        for key in keys:
            at(next(m for k, _, m, _, _ in POSTS if k == key) - 5)
            model.bookmark(db_path, user_ids[name], post_ids[key])

    for sender, receiver, minutes_ago, text in MESSAGES:
        at(minutes_ago)
        model.send_message(db_path, user_ids[sender], receiver, text)
    # Each person has read the messages sent to them, except the ones from the last two hours,
    # so that there is something new to see. Their older notifications are read too.
    at(120)
    for name in names:
        for other in names:
            if other != name:
                model.read_conversation(db_path, user_ids[name], other, before=stamp(120))
        model.read_notifications(db_path, user_ids[name], before=stamp(120))

    # Counted at the end: deleting a post also deletes its likes.
    likes = sum(row["likes"] for row in model.like_counts(db_path))
    return {"people": len(PEOPLE), "posts": len(POSTS), "likes": likes, "follows": follows,
            "messages": len(MESSAGES)}


# ---- Pictures for the made-up posts: make pictures ----

def add_pictures(db_path):
    """Draw a picture for each made-up post in drawings.FOR_POSTS that has none yet, and add it,
    through the model, as its author would. Running it twice does no harm. Returns how many."""
    added = 0
    for key, draw in drawings.FOR_POSTS.items():
        connection = model.connect(db_path)
        post_id = made_up_post(connection, key)
        post = connection.execute("SELECT author_id, posted_at, picture_id FROM posts WHERE id = ?",
                                  (post_id,)).fetchone() if post_id else None
        connection.close()
        if post is None or post["picture_id"] is not None:
            continue   # the post is not here, or it has its picture already
        at(minutes_since(post["posted_at"]))
        upload = model.save_upload(db_path, post["author_id"], draw())
        model.add_picture(db_path, post["author_id"], post_id, upload["id"])
        added += 1
    return added


def pictures(db_path):
    real_now = model.now
    try:
        model.create_tables(db_path)
        return add_pictures(db_path)
    finally:
        model.now = real_now   # the real clock again, whatever happened


# ---- Activity for a real account: make welcome NAME=Alex ----

# If the account has no posts yet, this one is posted in its name for the others to react to.
WELCOME_POST = "Hello Timeline! 👋 Just joined."

# What the made-up people do, oldest first: (who, how many minutes ago, what, words or the post).
# "post" is the account's own post. Every one of these makes a notification, except the messages.
WELCOME = [
    ("Kenta", 140, "follow", None),
    ("Hana", 138, "follow", None),
    ("Mei", 135, "follow", None),
    ("Kenta", 130, "like", "post"),
    ("Hana", 125, "reply", "Welcome! 🎉 Come to the language exchange table at lunch, everyone is welcome."),
    ("Mei", 110, "mention", "Say hi to @{name}, new on Timeline! #welcome"),
    ("Lucas", 100, "repost", "post"),
    ("Aiko", 90, "quote", "Another new face in #Hirakata 🍁"),
    ("Ben", 80, "like", "post"),
    ("Sofia", 70, "like", "post"),
    ("Yuki", 60, "like", "post"),
    ("Ben", 50, "follow", None),
    ("Kenta", 45, "message", "Welcome! If you need help with anything on campus, just ask."),
    ("Ravi", 35, "mention", "Cooking club this Friday: gyoza! @{name} you should come 🥟"),
    ("Aiko", 30, "message", "Hi! Are you coming to the JLPT study group tonight? Room 204, 7 pm."),
    ("Aiko", 29, "message", "Mei says bring snacks 😄"),
    ("Emma", 20, "like", "post"),
]

# Posts the account saves to its bookmarks, by their key in POSTS; and people it follows.
WELCOME_BOOKMARKS = ["jlpt", "kyoto", "miso"]
WELCOME_FOLLOWS = ["Aiko", "Mei", "Kenta"]


def welcome(db_path, name):
    real_now = model.now
    try:
        return fill_welcome(db_path, name)
    finally:
        model.now = real_now   # the real clock again, whatever happened


def minutes_since(stamp):
    """How many minutes ago a time like 2026-10-02 15:42 was."""
    return max(0.0, (time.time() - time.mktime(time.strptime(stamp, "%Y-%m-%d %H:%M"))) / 60)


def made_up_post(connection, key):
    """The id of a made-up post, found by its words, or None."""
    words = next(text for k, _, _, text, _ in POSTS if k == key)
    row = connection.execute("SELECT id FROM posts WHERE text = ? AND deleted_at IS NULL", (words,)).fetchone()
    return row["id"] if row else None


def fill_welcome(db_path, name):
    model.create_tables(db_path)   # so that an empty database gets a clear answer, not a crash
    connection = model.connect(db_path)
    try:
        try:
            person = model.find_user(connection, name)
        except model.NotFound:
            raise SystemExit(f"There is no account called {name}. Sign up with that name first.")
        ids = {}
        for made_up in PEOPLE:
            row = connection.execute("SELECT id FROM users WHERE name = ?", (made_up,)).fetchone()
            if row is None:
                raise SystemExit("The made-up people are not here. Run `make seed` first.")
            ids[made_up] = row["id"]
        if person["name"] in PEOPLE:
            raise SystemExit(f"{person['name']} is one of the made-up people. Give your own account's name.")
        own = connection.execute(
            "SELECT id, posted_at FROM posts WHERE author_id = ? AND reply_to IS NULL AND repost_of IS NULL "
            "AND deleted_at IS NULL ORDER BY id DESC LIMIT 1", (person["id"],)).fetchone()
        bookmarks = [made_up_post(connection, key) for key in WELCOME_BOOKMARKS]
    finally:
        connection.close()

    # The made-up times in WELCOME are fitted into the account's own life: nothing happens before
    # it joined, and nothing reacts to the post before the post was written.
    joined = minutes_since(person["joined_at"])
    if own is None:
        at(min(150, joined))
        post_id = model.save_post(db_path, person["id"], WELCOME_POST)["id"]
        posted = min(150, joined)
    else:
        post_id, posted = own["id"], minutes_since(own["posted_at"])

    def when(minutes_ago, about_the_post):
        limit = min(joined, posted) if about_the_post else joined
        return minutes_ago * min(1.0, limit / 150)

    done = {"follows": 0, "likes": 0, "replies": 0, "mentions": 0, "reposts": 0, "quotes": 0,
            "messages": 0, "bookmarks": 0}
    for who, minutes_ago, what, words in WELCOME:
        at(when(minutes_ago, what in ("like", "reply", "repost", "quote")))
        try:
            if what == "follow":
                model.follow(db_path, ids[who], person["name"])
                done["follows"] += 1
            elif what == "like":
                model.like_post(db_path, ids[who], post_id)
                done["likes"] += 1
            elif what == "reply":
                model.save_post(db_path, ids[who], words, reply_to=post_id)
                done["replies"] += 1
            elif what == "mention":
                model.save_post(db_path, ids[who], words.format(name=person["name"]))
                done["mentions"] += 1
            elif what == "repost":
                model.repost(db_path, ids[who], post_id)
                done["reposts"] += 1
            elif what == "quote":
                model.save_post(db_path, ids[who], words, quote_of=post_id)
                done["quotes"] += 1
            elif what == "message":
                model.send_message(db_path, ids[who], person["name"], words)
                done["messages"] += 1
        except model.RuleBroken:
            pass   # already done before (welcome was run twice): skip it

    at(when(10, False))
    for post in bookmarks:
        if post is not None:
            try:
                model.bookmark(db_path, person["id"], post)
                done["bookmarks"] += 1
            except model.RuleBroken:
                pass
    for other in WELCOME_FOLLOWS:
        try:
            model.follow(db_path, person["id"], other)
        except model.RuleBroken:
            pass
    return done


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fill the timeline with made-up data.")
    parser.add_argument("--welcome", metavar="NAME",
                        help="give this existing account made-up notifications, messages and bookmarks")
    parser.add_argument("--pictures", action="store_true",
                        help="add the drawings to the made-up posts of a timeline filled before")
    arguments = parser.parse_args()
    name = arguments.welcome
    if arguments.pictures:
        added = pictures(model.DB_PATH)
        print(f"Added {added} pictures to the made-up posts." if added
              else "Nothing to add: the made-up posts have their pictures, or are not here (make seed).")
    elif name:
        done = welcome(model.DB_PATH, name)
        print(f"{name} got {done['follows']} new followers, {done['likes']} likes, {done['replies']} reply, "
              f"{done['mentions']} mentions, {done['reposts']} repost, {done['quotes']} quote, "
              f"{done['messages']} messages and {done['bookmarks']} bookmarks. Log in as {name} to see them.")
    else:
        made = seed(model.DB_PATH)
        print(f"Made {made['people']} people, {made['posts']} posts, replies, reposts and quotes, "
              f"{made['likes']} likes, {made['follows']} follows and {made['messages']} messages.")
        print(f"Log in as any of them with the password {PASSWORD}, for example: "
              + ", ".join(list(PEOPLE)[:3]) + ".")
        print("To give your own account something to see as well: make welcome NAME=YourName")
