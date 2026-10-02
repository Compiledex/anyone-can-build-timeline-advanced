// Every word the page itself shows, in English (the original) and Japanese.
// The words people write (posts, bios, messages) are not here: those are translated one post at a
// time, with the Translate button. The Japanese follows the words of the Japanese social app people
// know: ホーム, ポストする, いいね, リポスト, フォロー中.
//
// t("nav.home") gives the word in the language chosen now. {name} in a phrase is filled in:
// t("post.reposted", { name: "Ben" }) gives "Ben reposted" or "Benさんがリポストしました".

import { currentLanguage } from "./settings.js";

const WORDS = {
  en: {
    "app.name": "Timeline",
    "nav.main": "Main menu",
    "nav.homeLink": "Timeline, home",
    "nav.home": "Home",
    "nav.explore": "Explore",
    "nav.notifications": "Notifications",
    "nav.notificationsNew": "Notifications, {count} new",
    "nav.messages": "Messages",
    "nav.messagesNew": "Messages, {count} unread",
    "nav.bookmarks": "Bookmarks",
    "nav.profile": "Profile",
    "nav.post": "Post",
    "nav.logOut": "Log out",

    "theme.system": "System",
    "theme.light": "Light",
    "theme.dark": "Dark",
    "theme.label": "Colours: {mode}. Press to change.",
    "theme.title": "Colours: {mode}",
    "language.other": "日本語",
    "language.label": "Show the page in Japanese",

    "compose.placeholder": "What is happening?",
    "compose.post": "Post",
    "picture.add": "Add a picture",
    "picture.remove": "Take the picture out",
    "picture.adding": "Adding the picture…",
    "picture.alt": "The picture you added",

    "search.label": "Search",
    "search.placeholder": "Search posts, people and #tags",
    "search.side": "Search",
    "message.label": "Your message",
    "message.placeholder": "Start a new message",
    "message.send": "Send",
    "sidebar.label": "More",

    "join.title": "Don't miss what's happening",
    "join.text": "People on Timeline are the first to know.",
    "login.logIn": "Log in",
    "login.signUp": "Sign up",
    "login.titleLogIn": "Log in to Timeline",
    "login.titleSignUp": "Join Timeline",
    "login.name": "Name",
    "login.password": "Password",
    "login.passwordHint": "(at least 8 characters)",
    "login.haveAccount": "Already have an account? ",
    "login.noAccount": "Don't have an account? ",
    "close": "Close",

    "write.yourText": "Your text",
    "write.title.post": "New post",
    "write.title.reply": "Reply",
    "write.title.quote": "Quote",
    "write.title.edit": "Edit your post",
    "write.button.post": "Post",
    "write.button.reply": "Reply",
    "write.button.quote": "Post",
    "write.button.edit": "Save",
    "write.placeholder.reply": "Post your reply",
    "write.placeholder.quote": "Add a comment",

    "profileDialog.title": "Edit profile",
    "profileDialog.changePicture": "Change picture",
    "profileDialog.removePicture": "Remove picture",
    "profileDialog.bio": "Bio",
    "profileDialog.bioHint": "(up to 160 characters)",
    "profileDialog.save": "Save",

    "tab.everyone": "For everyone",
    "tab.following": "Following",
    "empty.nothingYet": "Nothing here yet",
    "empty.followingText": "When people you follow post, it shows up here. Open a profile and press Follow.",
    "empty.beFirst": "Be the first to post.",
    "loading": "Loading…",

    "messages.you": "You: ",
    "messages.welcome": "Welcome to your inbox",
    "messages.welcomeText": "To start a conversation, open someone's profile and press Message.",
    "messages.all": "All conversations",
    "messages.seen": "Seen",
    "messages.sayHello": "Say hello to {name}.",
    "noOne": "There is no one called {name}.",

    "notif.like": " liked your post",
    "notif.repost": " reposted your post",
    "notif.quote": " quoted your post",
    "notif.reply": " replied to you",
    "notif.mention": " mentioned you",
    "notif.follow": " followed you",
    "notif.nothing": "Nothing yet",
    "notif.nothingText": "When someone likes, reposts, quotes or replies to your posts, mentions you or follows you, you will see it here.",

    "bookmarks.logIn": "Log in to see your bookmarks",
    "bookmarks.empty": "Save posts for later",
    "bookmarks.emptyText": "Press 🔖 under a post to save it here. Only you can see your bookmarks.",

    "explore.trendingWeek": "Trending this week",
    "explore.searchTitle": "Search Timeline",
    "explore.searchText": "Find posts, people and #tags. Try #kyoto or #kanji.",
    "explore.searching": "Searching…",
    "explore.nothing": "Nothing to search for",
    "explore.people": "People",
    "explore.posts": "Posts",
    "explore.noResults": "No results for {query}",
    "explore.noResultsText": "Try other words, or a #tag.",

    "post.title": "Post",
    "post.back": "Back to the timeline",
    "post.missing": "This post does not exist",
    "post.deleted": "This post was deleted.",
    "post.youReposted": "You reposted",
    "post.reposted": "{name} reposted",
    "post.edited": "· edited",
    "post.replyingTo": "Replying to ",
    "post.pictureAlt": "A picture posted by {name}",

    "action.reply": "Reply",
    "action.like": "Like",
    "action.unlike": "Unlike",
    "action.bookmark": "Bookmark",
    "action.unbookmark": "Remove from Bookmarks",
    "action.repost": "Repost",
    "action.reposted": "Reposted",
    "action.undoRepost": "Undo repost",
    "action.quote": "Quote",
    "action.more": "More",
    "action.edit": "Edit",
    "action.delete": "Delete",

    "profile.edit": "Edit profile",
    "profile.message": "Message",
    "profile.messageName": "Message {name}",
    "profile.follow": "Follow",
    "profile.following": "Following",
    "profile.unfollowName": "Unfollow {name}",
    "profile.joined": "Joined {date}",
    "profile.followingCount": "Following",
    "profile.followers.one": "Follower",
    "profile.followers.many": "Followers",
    "profile.posts.one": "Post",
    "profile.posts.many": "Posts",
    "profile.tab.posts": "Posts",
    "profile.tab.replies": "Replies",
    "profile.notReplied": "{name} has not replied to anyone yet",
    "profile.notPosted": "{name} has not posted yet",

    "side.newTitle": "New to Timeline?",
    "side.newText": "Sign up to post, reply, like and follow.",
    "side.happening": "What's happening",
    "side.trending": "{place} · Trending",
    "side.posts.one": "{count} post",
    "side.posts.many": "{count} posts",
    "side.whoToFollow": "Who to follow",
    "side.follow": "Follow",
    "side.followName": "Follow {name}",
    "side.about": "Timeline · a class project. Colours and fonts after the Kansai Gaidai Asian Studies Program site.",

    "toast.reposted": "Reposted",
    "toast.repostUndone": "Your repost was taken back",
    "toast.bookmarkAdded": "Added to your Bookmarks",
    "toast.bookmarkRemoved": "Removed from your Bookmarks",
    "toast.deleted": "Your post was deleted",
    "toast.followNow": "You follow {name} now",
    "toast.profileSaved": "Your profile was saved",
    "toast.sent.post": "Your post was sent",
    "toast.sent.reply": "Your reply was sent",
    "toast.sent.quote": "Your post was sent",
    "toast.sent.edit": "Your post was saved",
    "toast.loggedOut": "You are logged out",
    "confirm.delete": "Delete this post? It cannot be undone.",
    "status.cannotReach": "Cannot reach the server. Trying again every second.",

    "time.now": "now",
    "time.minutes": "{count}m",
    "time.hours": "{count}h",
  },

  ja: {
    "app.name": "Timeline",
    "nav.main": "メインメニュー",
    "nav.homeLink": "Timeline ホーム",
    "nav.home": "ホーム",
    "nav.explore": "話題を検索",
    "nav.notifications": "通知",
    "nav.notificationsNew": "通知、新着{count}件",
    "nav.messages": "メッセージ",
    "nav.messagesNew": "メッセージ、未読{count}件",
    "nav.bookmarks": "ブックマーク",
    "nav.profile": "プロフィール",
    "nav.post": "ポストする",
    "nav.logOut": "ログアウト",

    "theme.system": "システム",
    "theme.light": "ライト",
    "theme.dark": "ダーク",
    "theme.label": "配色: {mode}。押すと切り替わります。",
    "theme.title": "配色: {mode}",
    "language.other": "English",
    "language.label": "英語で表示する",

    "compose.placeholder": "いまどうしてる？",
    "compose.post": "ポストする",
    "picture.add": "画像を追加",
    "picture.remove": "画像を外す",
    "picture.adding": "画像を追加しています…",
    "picture.alt": "追加した画像",

    "search.label": "検索",
    "search.placeholder": "ポスト、ユーザー、#タグを検索",
    "search.side": "検索",
    "message.label": "メッセージ",
    "message.placeholder": "新しいメッセージを作成",
    "message.send": "送信",
    "sidebar.label": "その他",

    "join.title": "いま起きていることを見逃さないように",
    "join.text": "Timelineなら、誰よりも早く知ることができます。",
    "login.logIn": "ログイン",
    "login.signUp": "アカウント作成",
    "login.titleLogIn": "Timelineにログイン",
    "login.titleSignUp": "Timelineに登録",
    "login.name": "名前",
    "login.password": "パスワード",
    "login.passwordHint": "（8文字以上）",
    "login.haveAccount": "アカウントをお持ちの場合は ",
    "login.noAccount": "アカウントをお持ちでない場合は ",
    "close": "閉じる",

    "write.yourText": "本文",
    "write.title.post": "新しいポスト",
    "write.title.reply": "返信",
    "write.title.quote": "引用",
    "write.title.edit": "ポストを編集",
    "write.button.post": "ポストする",
    "write.button.reply": "返信",
    "write.button.quote": "ポストする",
    "write.button.edit": "保存",
    "write.placeholder.reply": "返信をポスト",
    "write.placeholder.quote": "コメントを追加",

    "profileDialog.title": "プロフィールを編集",
    "profileDialog.changePicture": "画像を変更",
    "profileDialog.removePicture": "画像を削除",
    "profileDialog.bio": "自己紹介",
    "profileDialog.bioHint": "（160文字まで）",
    "profileDialog.save": "保存",

    "tab.everyone": "すべて",
    "tab.following": "フォロー中",
    "empty.nothingYet": "まだ何もありません",
    "empty.followingText": "フォローしている人がポストすると、ここに表示されます。プロフィールを開いて「フォローする」を押してください。",
    "empty.beFirst": "最初のポストをしてみましょう。",
    "loading": "読み込み中…",

    "messages.you": "あなた: ",
    "messages.welcome": "メッセージへようこそ",
    "messages.welcomeText": "会話を始めるには、相手のプロフィールを開いて「メッセージ」を押してください。",
    "messages.all": "すべての会話",
    "messages.seen": "既読",
    "messages.sayHello": "{name}さんにあいさつしましょう。",
    "noOne": "{name}というユーザーはいません。",

    "notif.like": "さんがあなたのポストをいいねしました",
    "notif.repost": "さんがあなたのポストをリポストしました",
    "notif.quote": "さんがあなたのポストを引用しました",
    "notif.reply": "さんがあなたに返信しました",
    "notif.mention": "さんがあなたをメンションしました",
    "notif.follow": "さんがあなたをフォローしました",
    "notif.nothing": "まだ通知はありません",
    "notif.nothingText": "いいね、リポスト、引用、返信、メンション、フォローがあると、ここに表示されます。",

    "bookmarks.logIn": "ブックマークを見るにはログインしてください",
    "bookmarks.empty": "ポストを保存して後で読もう",
    "bookmarks.emptyText": "ポストの下の🔖を押すと、ここに保存されます。ブックマークはあなただけが見られます。",

    "explore.trendingWeek": "今週のトレンド",
    "explore.searchTitle": "Timelineを検索",
    "explore.searchText": "ポスト、ユーザー、#タグを探せます。#kyoto や #kanji で試してみてください。",
    "explore.searching": "検索中…",
    "explore.nothing": "検索する言葉がありません",
    "explore.people": "ユーザー",
    "explore.posts": "ポスト",
    "explore.noResults": "「{query}」の検索結果はありません",
    "explore.noResultsText": "別の言葉か #タグ で試してください。",

    "post.title": "ポスト",
    "post.back": "タイムラインに戻る",
    "post.missing": "このポストは存在しません",
    "post.deleted": "このポストは削除されました。",
    "post.youReposted": "リポストしました",
    "post.reposted": "{name}さんがリポストしました",
    "post.edited": "· 編集済み",
    "post.replyingTo": "返信先: ",
    "post.pictureAlt": "{name}さんがポストした画像",

    "action.reply": "返信",
    "action.like": "いいね",
    "action.unlike": "いいねを取り消す",
    "action.bookmark": "ブックマーク",
    "action.unbookmark": "ブックマークから削除",
    "action.repost": "リポスト",
    "action.reposted": "リポスト済み",
    "action.undoRepost": "リポストを取り消す",
    "action.quote": "引用",
    "action.more": "その他",
    "action.edit": "編集",
    "action.delete": "削除",

    "profile.edit": "プロフィールを編集",
    "profile.message": "メッセージ",
    "profile.messageName": "{name}さんにメッセージ",
    "profile.follow": "フォローする",
    "profile.following": "フォロー中",
    "profile.unfollowName": "{name}さんのフォローを解除",
    "profile.joined": "{date}から利用しています",
    "profile.followingCount": "フォロー",
    "profile.followers.one": "フォロワー",
    "profile.followers.many": "フォロワー",
    "profile.posts.one": "ポスト",
    "profile.posts.many": "ポスト",
    "profile.tab.posts": "ポスト",
    "profile.tab.replies": "返信",
    "profile.notReplied": "{name}さんはまだ返信していません",
    "profile.notPosted": "{name}さんはまだポストしていません",

    "side.newTitle": "Timelineを使ってみよう",
    "side.newText": "登録すると、ポスト、返信、いいね、フォローができます。",
    "side.happening": "いま話題のこと",
    "side.trending": "{place}位 · トレンド",
    "side.posts.one": "{count}件のポスト",
    "side.posts.many": "{count}件のポスト",
    "side.whoToFollow": "おすすめユーザー",
    "side.follow": "フォローする",
    "side.followName": "{name}さんをフォロー",
    "side.about": "Timeline · 授業のプロジェクト。色とフォントは関西外国語大学アジア研究プログラムのサイトを参考にしています。",

    "toast.reposted": "リポストしました",
    "toast.repostUndone": "リポストを取り消しました",
    "toast.bookmarkAdded": "ブックマークに追加しました",
    "toast.bookmarkRemoved": "ブックマークから削除しました",
    "toast.deleted": "ポストを削除しました",
    "toast.followNow": "{name}さんをフォローしました",
    "toast.profileSaved": "プロフィールを保存しました",
    "toast.sent.post": "ポストを送信しました",
    "toast.sent.reply": "返信を送信しました",
    "toast.sent.quote": "ポストを送信しました",
    "toast.sent.edit": "ポストを保存しました",
    "toast.loggedOut": "ログアウトしました",
    "confirm.delete": "このポストを削除しますか？元に戻すことはできません。",
    "status.cannotReach": "サーバーに接続できません。1秒ごとに再試行しています。",

    "time.now": "今",
    "time.minutes": "{count}分",
    "time.hours": "{count}時間",
  },
};

// The server's messages are in English. Each one we know is recognised by its pattern and shown in
// Japanese; $1 is the part the pattern caught (a name, a number). An unknown one stays as it is.
const SERVER_MESSAGES = [
  [/^The name must not be empty\.$/, "名前を入力してください。"],
  [/^The name must be (\d+) characters or fewer\.$/, "名前は$1文字以内にしてください。"],
  [/^A name may only have letters, numbers and _, with no spaces\.$/, "名前に使えるのは文字、数字、_ だけです（スペースは使えません）。"],
  [/^The password must be at least (\d+) characters\.$/, "パスワードは$1文字以上にしてください。"],
  [/^The password must be (\d+) characters or fewer\.$/, "パスワードは$1文字以内にしてください。"],
  [/^The name (.+) is taken\. Pick another name, or log in\.$/, "「$1」はすでに使われています。別の名前にするか、ログインしてください。"],
  [/^Wrong name or password\.$/, "名前かパスワードが違います。"],
  [/^Please log in first\.$/, "先にログインしてください。"],
  [/^The post must not be empty\.$/, "ポストを入力してください。"],
  [/^The post must be (\d+) characters or fewer\.$/, "ポストは$1文字以内にしてください。"],
  [/^There is no post (\d+)\.$/, "ポスト$1は存在しません。"],
  [/^Post (\d+) was deleted\.$/, "ポスト$1は削除されています。"],
  [/^You can only edit your own post\.$/, "自分のポストだけを編集できます。"],
  [/^You can only delete your own post\.$/, "自分のポストだけを削除できます。"],
  [/^You already liked this post\.$/, "このポストはすでにいいねしています。"],
  [/^You have not liked this post\.$/, "このポストはいいねしていません。"],
  [/^You already reposted this post\.$/, "このポストはすでにリポストしています。"],
  [/^You have not reposted this post\.$/, "このポストはリポストしていません。"],
  [/^A repost has no words to edit\.$/, "リポストには編集する本文がありません。"],
  [/^A post can answer a post or quote one, not both\.$/, "返信と引用を同時にすることはできません。"],
  [/^You already saved this post\.$/, "このポストはすでにブックマークしています。"],
  [/^You have not saved this post\.$/, "このポストはブックマークしていません。"],
  [/^You cannot follow yourself\.$/, "自分をフォローすることはできません。"],
  [/^You already follow (.+)\.$/, "$1さんはすでにフォローしています。"],
  [/^You do not follow (.+)\.$/, "$1さんをフォローしていません。"],
  [/^There is no one called (.+)\.$/, "$1というユーザーはいません。"],
  [/^The bio must be (\d+) characters or fewer\.$/, "自己紹介は$1文字以内にしてください。"],
  [/^Only JPEG, PNG, GIF and WebP pictures are allowed\.$/, "JPEG、PNG、GIF、WebPの画像だけを使えます。"],
  [/^A picture must be (\d+) MB or smaller\.$/, "画像は$1MB以下にしてください。"],
  [/^The picture is empty\.$/, "画像が空です。"],
  [/^You can only use your own pictures\.$/, "自分の画像だけを使えます。"],
  [/^That picture is already used\.$/, "その画像はすでに使われています。"],
  [/^Type something to search for\.$/, "検索する言葉を入力してください。"],
  [/^A search must be (\d+) characters or fewer\.$/, "検索は$1文字以内にしてください。"],
  [/^The message must not be empty\.$/, "メッセージを入力してください。"],
  [/^A message must be (\d+) characters or fewer\.$/, "メッセージは$1文字以内にしてください。"],
  [/^You cannot send a message to yourself\.$/, "自分にメッセージを送ることはできません。"],
  [/^A repost cannot have a picture\.$/, "リポストに画像は付けられません。"],
  [/^This post already has a picture\.$/, "このポストにはすでに画像があります。"],
  [/^You can only add a picture to your own post\.$/, "自分のポストにだけ画像を追加できます。"],
  [/^There is no picture (\d+)\.$/, "画像$1は存在しません。"],
  [/^There is no such picture\.$/, "その画像は存在しません。"],
  [/^The bio must be text\.$/, "自己紹介は文字で入力してください。"],
  [/^'(\w+)' must be a whole number\.$/, "「$1」は整数で指定してください。"],
  [/^The request must be JSON\.$/, "リクエストはJSONで送ってください。"],
  [/^The request must be a JSON object\.$/, "リクエストはJSONオブジェクトで送ってください。"],
  [/^The request must say how long the picture is\.$/, "画像の大きさが分かりません。"],
];

// A phrase in the language chosen now, with {name}-style places filled in.
export function t(key, values = {}) {
  const phrase = WORDS[currentLanguage()][key] ?? WORDS.en[key] ?? key;
  return phrase.replace(/\{(\w+)\}/g, (whole, name) => (name in values ? String(values[name]) : whole));
}

// A phrase for a number: "1 post", "2 posts". Japanese has one form for both.
export function tCount(key, count) {
  return t(key + (count === 1 ? ".one" : ".many"), { count: count });
}

// A message from the server, in the language chosen now.
export function fromServer(message) {
  if (currentLanguage() !== "ja" || !message) {
    return message;
  }
  for (const [pattern, japanese] of SERVER_MESSAGES) {
    if (pattern.test(message)) {
      return message.replace(pattern, japanese);
    }
  }
  return message;
}

// For dates: the browser writes "2 Oct" or "10月2日" by itself, given this.
export function locale() {
  return currentLanguage() === "ja" ? "ja-JP" : "en-GB";
}

// Put the words into index.html, wherever it says data-i18n (the text), data-i18n-placeholder,
// data-i18n-label (what a screen reader says) or data-i18n-title (what shows when you point).
export function fillWords(root = document) {
  document.documentElement.lang = currentLanguage();
  for (const place of root.querySelectorAll("[data-i18n]")) {
    place.textContent = t(place.dataset.i18n);
  }
  for (const place of root.querySelectorAll("[data-i18n-placeholder]")) {
    place.placeholder = t(place.dataset.i18nPlaceholder);
  }
  for (const place of root.querySelectorAll("[data-i18n-label]")) {
    place.setAttribute("aria-label", t(place.dataset.i18nLabel));
  }
  for (const place of root.querySelectorAll("[data-i18n-title]")) {
    place.title = t(place.dataset.i18nTitle);
  }
}
