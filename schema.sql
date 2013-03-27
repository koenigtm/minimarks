drop table if exists users;
create table users (
  user_id integer primary key autoincrement,
  username string unique not null,
  pw_hash string not null
);

drop table if exists bookmark_search;
create virtual table bookmark_search using fts3(
  title string not null,
  href string not null
);

drop table if exists bookmarks;
create table bookmarks (
  user_id integer not null,
  -- "rowid" in the virtual search table
  search_id integer primary key,
  title string not null,
  href string not null,
  pub_date integer not null
);

create index bookmark_search_index on bookmarks(search_id);
create index bookmark_link_index on bookmarks(href);
create index bookmark_user_index on bookmarks(user_id);
