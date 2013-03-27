# -*- coding: utf-8 -*-
"""
Minimarks - a minimal bookmark application

Copyright (c) 2013 by Tim Koenig <tim.koenig@gmail.com>.
License: BSD, see LICENSE for details.

Portions copyright (c) 2010 by Armin Ronacher (Flask "minitwit"
example).

"""
import sqlite3
from contextlib import closing
import time
import os.path
import cgi
from datetime import datetime
from flask import Flask, request, session, url_for, redirect, \
    render_template, abort, g, flash
from werkzeug import check_password_hash, generate_password_hash
from HTMLParser import HTMLParser

# configuration
DATABASE = '/tmp/minimarks.db'
DEBUG = True
SECRET_KEY = 'development key'
PER_PAGE = 50

app = Flask(__name__)
app.config.from_object(__name__)

class BookmarkParser(HTMLParser):
    links = []
    _link = None
    _charset = "cp1252"

    def __init__(self, stream):
        self.reset()
        self.feed(stream.read())
        self.close()
        
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "a" == tag:
            self._link = [a[k].decode(self._charset) if k in a else u""
                          for k in ('href', 'add_date')]
        if "meta" == tag:
            if ("http-equiv" in a and 
                "Content-Type" == a["http-equiv"] and
                "content" in a):
                parsed_header = cgi.parse_header("{}: {}".format(
                        a["http-equiv"], a["content"]))
                if parsed_header:
                    _, parameters = parsed_header
                    if "charset" in parameters:
                        self._charset = parameters["charset"]
            elif "charset" in a:
                self._charset = a["charset"]

    def handle_data(self, data):
        if self._link:
            print repr(data)
            self._link += [data.decode(self._charset)]

    def handle_endtag(self, tag):
        if "a" == tag and self._link:
            if len(self._link) == 3:
                self.links += [self._link]
            self._link = None

def connect_db():
    """Returns a new connection to the database."""
    if not os.path.exists(app.config['DATABASE']):
        with closing(sqlite3.connect(app.config['DATABASE'])) as db:
            with app.open_resource('schema.sql') as f:
                db.executescript(f.read())
            db.commit()
    return sqlite3.connect(app.config['DATABASE'])

def query_db(query, args=(), one=False):
    """Queries the database and returns a list of dictionaries."""
    cur = g.db.execute(query, args)
    rv = [dict((cur.description[idx][0], value)
               for idx, value in enumerate(row)) for row in cur.fetchall()]
    return (rv[0] if rv else None) if one else rv

def remove_bookmark(rowid, commit=True):
    c = g.db.execute("delete from bookmarks " +
                     "where rowid=? " +
                     "and user_id=?", 
                     (rowid, session["user_id"]))
    if not c.rowcount == 1:
        abort(400)

    g.db.execute("delete from bookmarks " +
                 "where rowid=? ", 
                 (rowid,))
    
    if commit:
        g.db.commit()

def update_bookmark(rowid, title, href, pub_date=None, commit=True):
    if not pub_date:
        pub_date = int(time.time())

    c = g.db.execute("update bookmarks " +
                     "set title=?, href=?, pub_date=? " +
                     "where user_id=? " +
                     "and search_id=?",
                     (title, href, pub_date, session["user_id"], rowid))
    if not c.rowcount == 1:
        abort(400)

    g.db.execute("update bookmark_search " +
                 "set title=?, href=? " +
                 "where rowid=?",
                 (title, href, rowid))

    if commit:
        g.db.commit()

def insert_bookmark(title, href, pub_date=None, commit=True):
    if not pub_date:
        pub_date = int(time.time())

    c = g.db.execute("insert into bookmark_search " +
                     "(title, href) " +
                     "values (?, ?)",
                     (title, href))
    
    g.db.execute("insert into bookmarks " +
                 "(user_id, search_id, title, href, pub_date) " +
                 "values (?, ?, ?, ?, ?)",
                 (session["user_id"], c.lastrowid, 
                  title, href, pub_date))

    if commit:
        g.db.commit()

def get_bookmark(rowid):
    return query_db("select title,href from bookmarks " +
                    "where search_id=? " +
                    "and user_id=?",
                    (rowid, session["user_id"]), 
                    one=True)

def get_bookmarks(page=1, per_page=-1, search_term=None):
    def query_bookmarks(column_snippet,
                        search_snippet,
                        parameters,
                        limit_snippet=""):
        query = " ".join(["select {columns} from bookmarks,bookmark_search",
                          "where bookmarks.user_id=:user_id",
                          "and bookmarks.search_id=bookmark_search.rowid",
                          "{search}",
                          "order by bookmarks.pub_date desc",
                          "{limit}"]).format(columns=column_snippet,
                                             search=search_snippet,
                                             limit=limit_snippet)
        return query_db(query, parameters)

    if page < 1:
        abort(400)

    if search_term:
        search_snippet = "and bookmark_search match :search_term "
    else:
        search_snippet = ""

    query_parameters = {"user_id" : session["user_id"],
                        "search_term" : search_term}

    count_result = query_bookmarks(column_snippet="count(*)",
                                   search_snippet=search_snippet,
                                   parameters=query_parameters)
    if 1 != len(count_result):
        abort(400)
    count = count_result[0]["count(*)"]

    if per_page > 0:
        pages = count / per_page
        if count % per_page != 0:
            pages += 1
        query_parameters["limit"] = per_page
        query_parameters["offset"] = (page - 1) * per_page
        limit_snippet = "limit :limit offset :offset"
    else:
        pages = 1
        limit_snippet = ""

    bookmark_columns = ",".join(["bookmark_search.rowid",
                                 "bookmarks.title",
                                 "bookmarks.href",
                                 "bookmarks.pub_date"])
    bookmarks = query_bookmarks(column_snippet=bookmark_columns,
                                search_snippet=search_snippet,
                                limit_snippet=limit_snippet,
                                parameters=query_parameters)

    return { "pages" : pages,
             "page" : page,
             "count": count,
             "bookmarks" : bookmarks }

def insert_or_update_bookmark(title, href, pub_date):    
    """ Adds or updates the bookmark -- does not commit! """
    bookmarks = query_db("select search_id,pub_date " +
                         "from bookmarks " +
                         "where bookmarks.user_id=? " +
                         "and bookmarks.href=?",
                         (session["user_id"], href))
    if 0 == len(bookmarks):
        insert_bookmark(title, href, pub_date, commit=False)
        return "insert"
    elif 1 == len(bookmarks):
        bookmark = bookmarks[0]
        if pub_date > bookmark["pub_date"]:
            update_bookmark(bookmark["search_id"], title, href, pub_date,
                            commit=False)
            return "update"
        else:
            return "skipped"
    else:
        return "error"

def import_file(stream):
    bookmarks = BookmarkParser(stream).links
    results = { "insert" : 0,
                "update" : 0,
                "skipped" : 0,
                "error" : 0 }
    for href, maybe_wrong_date, title in bookmarks:
        if maybe_wrong_date:
            pub_date = int(maybe_wrong_date[:10])
        else:
            pub_date = int(time.time())
        result = insert_or_update_bookmark(title, href, pub_date)
        results[result] += 1
    g.db.commit()
    return results

def format_datetime(timestamp):
    """Format a timestamp for display."""
    return datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%d @ %H:%M')

def get_user_id(username):
    """Convenience method to look up the id for a username."""
    rv = g.db.execute('select user_id from users where username = ?',
                       [username]).fetchone()
    return rv[0] if rv else None

@app.before_request
def before_request():
    """Make sure we are connected to the database each request and look
    up the current user so that we know he's there.
    """
    g.db = connect_db()
    g.user = None
    if 'user_id' in session:
        g.user = query_db('select * from users where user_id=?',
                          [session['user_id']], one=True)

@app.teardown_request
def teardown_request(exception):
    """Closes the database again at the end of the request."""
    if hasattr(g, 'db'):
        g.db.close()

@app.route('/', defaults={"page":1,})
@app.route("/bookmarks/<int:page>")
def show_bookmarks(page):
    if not g.user:
        return redirect(url_for('login'))

    search_term = None
    if "search" in request.args and request.args["search"]:
        search_term = request.args["search"]
    bookmarks = get_bookmarks(page=page, 
                              per_page=PER_PAGE, 
                              search_term=search_term)
    if page > 1 and page > bookmarks["pages"]:
        page = bookmarks["pages"]
        if 0 == page:
            page = 1
        return redirect(url_for("show_bookmarks", page=page, **request.args))
    else:
        return render_template("bookmarks.html", **bookmarks)
    
@app.route('/login', methods=['GET', 'POST'])
def login():
    def redirect_success():
        if "popup" in request.args:
            return redirect(url_for('add_bookmark', **request.args))
        else:
            # Not a popup -- just show the list
            return redirect(url_for('show_bookmarks'))

    if g.user:
        return redirect_success()

    error = None
    if request.method == 'POST':
        user = query_db('''select * from users where
            username = ?''', [request.form['username']], one=True)
        if user is None:
            error = 'Invalid username'
        elif not check_password_hash(user['pw_hash'],
                                     request.form['password']):
            error = 'Invalid password'
        else:
            session['user_id'] = user['user_id']
            flash('You were logged in')
            return redirect_success()

    base="popup.html" if "popup" in request.args else None
    return render_template('login.html',
                           base=base,
                           error=error, 
                           **request.args)

@app.route("/export/bookmarks.html")
def export_bookmarks():
    if not g.user:
        return redirect(url_for('login'))
    return render_template("export.html", **get_bookmarks())

@app.route("/import", methods=["GET", "POST"])
def import_bookmarks():
    if not g.user:
        return redirect(url_for('login'))
    if request.method == "POST":
        file_data = request.files["file"]
        if file_data:
            results = import_file(file_data)
            flash(("Imported bookmarks: " + 
                   "{insert} new, {update} updated, " + 
                   "{skipped} skipped and {error} errors").format(
                    **results))
            return redirect(url_for('show_bookmarks'))
    else:
        return render_template("import.html")

@app.route("/delete/<int:page>", methods=["POST"])
def delete_bookmarks(page):
    if not g.user:
        return redirect(url_for('login'))
    for rowid in request.form.getlist("rowid", int):
        remove_bookmark(rowid, commit=False)
    g.db.commit()
    return redirect(url_for("show_bookmarks", page=page, **request.args))

@app.route("/edit/<int:page>/<int:rowid>", methods=["GET", "POST"])
def edit_bookmark(page, rowid):
    if not g.user:
        return redirect(url_for('login'))
    if request.method == "POST":
        if "title" in request.form and "href" in request.form:
            update_bookmark(rowid,
                            request.form["title"], request.form["href"])
            flash('Your bookmark was changed')
            return redirect(url_for('show_bookmarks', 
                                    page=page,
                                    **request.args))
        else:
            abort(400)
    else:
        bookmark = get_bookmark(rowid)
        if bookmark:
            return render_template("add.html",
                                   operation="Edit",
                                   page=page,
                                   bookmark=bookmark)
        else:
            abort(400)

@app.route('/register', methods=['GET', 'POST'])
def register():
    def is_taken(username):
        result = query_db("select user_id from users where username=?",
                          (username, ), 
                          one=True)
        print repr(result)
        return result is not None
    if g.user:
        return redirect(url_for('show_bookmarks'))
    error = None
    if request.method == 'POST':
        if not request.form['username']:
            error = 'You have to enter a username'
        elif not request.form['password']:
            error = 'You have to enter a password'
        elif request.form['password'] != request.form['password2']:
            error = 'The two passwords do not match'
        elif is_taken(request.form["username"]):
            error = 'The username is already taken'
        else:
            g.db.execute('''insert into users (
                username, pw_hash) values (?, ?)''',
                [request.form['username'], 
                 generate_password_hash(request.form['password'])])
            g.db.commit()
            flash('You were successfully registered and can login now')
            return redirect(url_for('login'))
    return render_template('register.html', error=error)

@app.route('/logout')
def logout():
    flash('You were logged out')
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/add/<int:page>', methods=['POST', 'GET'])
@app.route('/add', defaults={"page":1,}, methods=['POST', 'GET'])
def add_bookmark(page):
    if not g.user:
        return redirect(url_for("login", **request.args))

    if request.method == 'POST':
        if "title" in request.form and "href" in request.form:
            insert_bookmark(request.form["title"], request.form["href"])
            flash('Your bookmark was added')
        else:
            abort(400)
        if "popup" in request.args:
            return render_template("close_window.html")
        else:
            return redirect(url_for("show_bookmarks", 
                                    page=page,
                                    **request.args))
    else:
        base="popup.html" if "popup" in request.args else None
        # Pre-populate form fields (compatible with "edit/")
        if "title" in request.args and "href" in request.args:
            bookmark = request.args
        else:
            bookmark = None
        return render_template("add.html", 
                               base=base,
                               bookmark=bookmark,
                               page=page,
                               **request.args)

# add some filter to jinja
app.jinja_env.filters['datetimeformat'] = format_datetime

if __name__ == '__main__':
    app.run()
