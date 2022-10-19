#!/usr/bin/env python
# vim: set et ts=8 sts=4 sw=4 ai:

import os
import re
import pytest
import otterwiki

from pprint import pprint

def test_html(test_client):
    result = test_client.get("/")
    assert "<!DOCTYPE html>" in result.data.decode()
    assert "<title>" in result.data.decode()
    assert "</html>" in result.data.decode()


def test_create_form(test_client):
    result = test_client.get("/-/create")
    html = result.data.decode()
    assert "Create Page</h2>" in html
    assert '<form action="/-/create" method="POST"' in html


def test_create_page_sanitized(test_client):
    pagename = "CreateTest?"
    html = test_client.post(
        "/-/create",
        data={
            "pagename": pagename,
        },
        follow_redirects=True,
    ).data.decode()
    assert "Please check the pagename" in html


def test_create_page(test_client):
    pagename = "CreateTest"
    html = test_client.post(
        "/-/create",
        data={
            "pagename": pagename,
        },
        follow_redirects=True,
    ).data.decode()
    # check form
    assert 'action="/{}/preview"'.format(pagename) in html
    assert "<textarea" in html
    assert 'name="content_editor"' in html
    # test save
    html = test_client.post(
        "/{}/save".format(pagename),
        data={
            "content_update": "Test test 12345678\n\n**strong**",
            "commit": "Initial commit",
        },
        follow_redirects=True,
    ).data.decode()
    assert "Test test 12345678" in html
    assert "<title>{}".format(pagename) in html
    assert "<p><strong>strong</strong></p>" in html
    # check exisiting page
    html = test_client.post(
        "/-/create",
        data={
            "pagename": pagename,
        },
        follow_redirects=True,
    ).data.decode()
    assert "exists already" in html


def save_shortcut(test_client, pagename, content, commit_message):
    rv = test_client.post(
        "/{}/save".format(pagename),
        data={
            "content_update": content,
            "commit": commit_message,
        },
        follow_redirects=True,
    )
    assert rv.status_code == 200


def test_page_save(test_client):
    from otterwiki.server import storage

    pagename = "Save Test"
    content = "*em*\n\n**strong**\n"
    commit_message = "Save test commit message"
    save_shortcut(test_client, pagename, content, commit_message)
    # check file content
    assert content == storage.load("{}.md".format(pagename.lower()))
    # check history
    html = test_client.get("/{}/history".format(pagename)).data.decode()
    assert "History" in html
    assert commit_message in html


def test_blame_and_history_and_diff(test_client):
    pagename = "Blame Test"
    content = "Blame Test\naaa_aaa_aaa"
    commit_messages = ["initial commit", "update"]
    save_shortcut(test_client, pagename, content, commit_messages[0])
    # check history
    html = test_client.get("/{}/history".format(pagename)).data.decode()
    assert commit_messages[0] in html
    # check blame
    html = test_client.get("/{}/blame".format(pagename)).data.decode()
    for line in content.splitlines():
        assert line in html
    # update content
    content = "Blame Test\nbbb\nccc\nddd"
    save_shortcut(test_client, pagename, content, commit_messages[1])
    # check history
    html = test_client.get("/{}/history".format(pagename)).data.decode()
    # find revision
    revision = re.findall(r"class=\"btn revision-small\">([A-z0-9]+)</a>", html)
    assert len(revision) == 2
    for line in commit_messages:
        assert line in html
    # check blame
    html = test_client.get("/{}/blame".format(pagename)).data.decode()
    for line in content.splitlines():
        assert line in html
    assert "aaa_aaa_aaa" not in html
    # fetch diff
    rv = test_client.post(
        "/{}/history".format(pagename),
        data={"rev_a": revision[1], "rev_b": revision[0]},
    )
    assert rv.status_code == 200
    html = rv.data.decode()
    assert pagename in html
    assert revision[0] in html
    assert revision[1] in html


def test_blame_and_history_404(test_client):
    pagename = "Doe's not exist"
    # check blame
    rv = test_client.get("/{}/blame".format(pagename), follow_redirects=True)
    assert "Page not found" in rv.data.decode()
    assert rv.status_code == 404
    # check history
    rv = test_client.get("/{}/history".format(pagename), follow_redirects=True)
    assert "Page not found" in rv.data.decode()
    assert rv.status_code == 404


def test_search(test_client):
    # create additional haystacks
    save_shortcut(test_client, "HayStack 0", "Needle 0", "initial commit")
    save_shortcut(test_client, "HayStack 1", "Needle 1", "initial commit")
    save_shortcut(test_client, "Haystack 1a", "NeEdle 1", "initial commit")
    save_shortcut(test_client, "Haystack 2", "NeEdle 2\nNeEdle 2", "initial commit")
    # search 1
    rv = test_client.get("/-/search/{}".format("Haystack"))
    assert "Search matched 4 pages" in rv.data.decode()
    assert rv.status_code == 200
    # search 2
    rv = test_client.get("/-/search/{}".format("Needle"))
    assert "Search matched 4 pages" in rv.data.decode()
    assert rv.status_code == 200
    # search 3
    rv = test_client.get("/-/search/{}".format("Needle 1"))
    assert "Search matched 2 pages" in rv.data.decode()
    assert rv.status_code == 200
    # search 4
    rv = test_client.get("/-/search/{}".format("Haystack 1"))
    assert "Search matched 2 pages" in rv.data.decode()
    assert rv.status_code == 200
    # search via post 1
    rv = test_client.post("/-/search", data={"query": "Haystack"})
    assert "Search matched 4 pages" in rv.data.decode()
    assert rv.status_code == 200
    # search via post 2: case sensitive
    rv = test_client.post(
        "/-/search", data={"query": "HayStack", "is_casesensitive": "y"}
    )
    assert "Search matched 4 pages" in rv.data.decode()
    assert rv.status_code == 200
    # search via post 3: case sensitive
    rv = test_client.post(
        "/-/search", data={"query": "NeEdle", "is_casesensitive": "y"}
    )
    assert "Search matched 2 pages" in rv.data.decode()
    assert rv.status_code == 200
    # search via post 4: regex
    rv = test_client.post(
        "/-/search", data={"query": "NeEdle", "is_regexp": "y", "is_casesensitive": "y"}
    )
    assert "Search matched 2 pages" in rv.data.decode()
    assert rv.status_code == 200
    # search via post 4: regex
    rv = test_client.post("/-/search", data={"query": "N[eE]+dle", "is_regexp": "y"})
    assert "Search matched 4 pages" in rv.data.decode()
    assert rv.status_code == 200


def test_rename(test_client):
    old_pagename = "RenameTest"
    new_pagename = "RenameTestNew"
    content = "# Rename content\nabc abc abc def def def."
    # create page
    save_shortcut(
        test_client,
        pagename=old_pagename,
        content=content,
        commit_message="initial commit",
    )
    # check content
    rv = test_client.get("/{}/view".format(old_pagename))
    assert rv.status_code == 200
    # check new page doesn't exist
    rv = test_client.get("/{}/view".format(new_pagename))
    assert rv.status_code == 404
    # rename form
    rv = test_client.get("/{}/rename".format(old_pagename))
    assert (
        'form action="/{}/rename" method="POST"'.format(old_pagename)
        in rv.data.decode()
    )
    assert rv.status_code == 200
    # rename page
    rv = test_client.post(
        "/{}/rename".format(old_pagename),
        data={"new_pagename": new_pagename, "message": ""},
        follow_redirects=True,
    )
    # check old page doesn't exist
    rv = test_client.get("/{}/view".format(old_pagename))
    assert rv.status_code == 404
    # check new page exists
    rv = test_client.get("/{}/view".format(new_pagename))
    assert rv.status_code == 200


def test_delete(test_client):
    pagename = "DeleteTest"
    content = "# Delete content\nabc abc abc def def def."
    # create page
    save_shortcut(
        test_client, pagename=pagename, content=content, commit_message="initial commit"
    )
    # check content
    rv = test_client.get("/{}/view".format(pagename))
    assert rv.status_code == 200
    # delete form
    rv = test_client.get("/{}/delete".format(pagename))
    assert rv.status_code == 200
    assert 'form action="/{}/delete" method="POST"'.format(pagename) in rv.data.decode()
    # delete page
    rv = test_client.post(
        "/{}/delete".format(pagename),
        data={"message": "deleted ..."},
        follow_redirects=True,
    )
    assert rv.status_code == 200
    # check deletion
    rv = test_client.get("/{}/view".format(pagename))
    assert rv.status_code == 404


def test_non_version_control_file(test_client):
    p = test_client.application._otterwiki_tempdir

    filename = "no version file"
    content = 'oh no! no control!'
    with open(os.path.join(p, f'{filename}.md'), 'w') as f:
        f.write(content)

    # first, assert that a file that doesn't exists returns a 404
    response = test_client.get(f"/some crazy file name that doesn't exist")
    assert response.status_code == 404

    # then try that file that was previous created (but not added to version control)
    response = test_client.get(f"/{filename}")
    assert response.status_code == 200
    assert "This page was loaded from the repository but is not added under git version control" in response.data.decode()
    assert content in response.data.decode()

