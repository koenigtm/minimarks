Introduction
============

Minimark is a minimal bookmarking application, built in Python and
using the Flask framework and a SQLite3 database. It's somewhat
multi-user capable and supports full text search in titles and URLs.

It's modelled after a similar service by a company that just announced
the retirement of another kind of service that I'm also an avid user
of and since I haven't done anything that speaks HTTP for nearly five
years...

Features
--------

- a very thin layer over a database to insert bookmarks and
  retrieve/display them

- full-text search on titles and links, using the FTS3 feature of
  SQLite3

- probably multi-user capable

- relatively simple to set up, all requirements are part of the
  standard Debian *wheezy* repositories

  - Flask 0.8.1 (package: python-flask) [LICENSE: 3BSD]

    - Python 2.7 (package: python2.7) [LICENSE: PSF]

      - or: Python 2.6 (package: python2.6)

      - SQLite3 (package: libsqlite3-0) [LICENSE: public domain]

    - Werkzeug (...)
    
    - Jinja2 (...)

  - Bootstrap 2.0.2 (package: libjs-twitter-bootstrap) [LICENSE: Apache]

    - jQuery 1.7.2 (package: libjs-jquery) [LICENSE: MIT]

  - recommends: nginx + uwsgi for a saner setup

- uses Bootstrap (yes, that's a feature -- the initial attempt at the
  markup was just mind boggling)

- a bookmarklet with optional login to directly add bookmarks when browsing

Non-features
------------

- Tests

- Scalability (I'm probably the only user of this)

- Security, the session model is out-of-the box Flask 0.8.1

- Usability without Javascript

License
=======

3BSD, the same as Flask. See LICENSE for details.

Open issues
===========

Important
---------

- Configuration needs to be read from a site-specific file

- The availability of the registration has to be configurable

- Logging (access, usage and error logs)

Nice-to-have
------------

- Debian packaging for easy installation

- Optional HTTP authentication support for directly fetching the
  export list (use case: backup).

- Using something like python-lust (or just virtualenv?) to make it
  easier to run this in a chroot.

- An example configuration for nginx + uwsgi, preferably in a chroot.

Misc
----

- Insert/update of a bookmark sets the time in UTC (that's okay), but
  the display should really use the local time

  - How do we get the user's local timezone? It's probably really
    preferrable to use this locally adjusted time for the HTML
    display, but for other uses (JSON, HTML export) the UTC timestamp
    is the only sensible choice.

- When adding is successful, the popup window should be closed, but
  *not* if something went wrong -> redirect to a special page (or to
  the same page with a special parameter?) and close the window -- or
  render the error message

Way off
-------

- RESTful API, i.e. better mapping of HTTP verbs to actions, JSON
  input/output capability
